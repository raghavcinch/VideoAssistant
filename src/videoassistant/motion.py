from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe
from tqdm import tqdm


@dataclass
class MotionSettings:
    sample_fps: float = 5.0
    scale_width: int = 320


def _ffmpeg_gray_stream(path: Path, sample_fps: float, scale_width: int) -> subprocess.Popen[bytes]:
    ffmpeg = get_ffmpeg_exe()
    # Output raw gray frames at a low FPS for fast motion analysis.
    # We scale by width, preserving aspect ratio. Use lanczos for stable edges.
    vf = f"fps={sample_fps},scale={scale_width}:-1:flags=lanczos,format=gray"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-vf",
        vf,
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    ]
    # Avoid deadlocks: even with -loglevel error, ffmpeg can emit stderr.
    # We don't rely on it for this analysis, so discard it.
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


def _probe_dims(path: Path) -> tuple[int, int, float]:
    ffmpeg = get_ffmpeg_exe()
    # Use ffmpeg itself to print stream info; parse width/height/fps approximately.
    cmd = [ffmpeg, "-hide_banner", "-i", str(path)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    text = p.stderr

    width = height = 0
    fps = 0.0
    for line in text.splitlines():
        if " Video:" in line and ("x" in line):
            # e.g. 3840x2160
            parts = line.replace(",", " ").split()
            for token in parts:
                if "x" in token and token.count("x") == 1:
                    a, b = token.split("x")
                    if a.isdigit() and b.isdigit():
                        width, height = int(a), int(b)
                        break
            # fps token like 29.97 fps
            if "fps" in parts:
                try:
                    i = parts.index("fps")
                    fps = float(parts[i - 1])
                except Exception:
                    pass
            break
    return width, height, fps


def _shakiness_series(frames: np.ndarray) -> np.ndarray:
    """Compute per-step shakiness from gray frames.

    Important: for gimbal/walkthrough footage, *smooth global motion* is common.
    We want to measure *jitter* (high-frequency motion changes), not overall motion.

    Approach:
    - Estimate global translation between consecutive frames using phase correlation.
    - Convert translations into a motion trajectory.
    - Shakiness ~= magnitude of changes in motion (acceleration / jerk).

    frames: (T, H, W) uint8
    returns: (T-1,) float
    """

    t = frames.shape[0]
    if t < 2:
        return np.array([], dtype=np.float32)

    f = frames.astype(np.float32) / 255.0

    # Precompute FFT for each frame for speed.
    # Using rfft2 would be a bit faster, but fft2 keeps code simpler.
    F = np.fft.fft2(f, axes=(1, 2))

    shifts = np.zeros((t - 1, 2), dtype=np.float32)
    h, w = f.shape[1], f.shape[2]

    eps = 1e-9
    for i in range(t - 1):
        # Cross-power spectrum
        R = F[i] * np.conj(F[i + 1])
        R /= (np.abs(R) + eps)
        r = np.fft.ifft2(R)
        r_abs = np.abs(r)
        y, x = np.unravel_index(np.argmax(r_abs), r_abs.shape)

        # Convert peak location to signed shift (wrap-around)
        if x > w // 2:
            x = x - w
        if y > h // 2:
            y = y - h

        shifts[i, 0] = float(x)
        shifts[i, 1] = float(y)

    # Shakiness as acceleration magnitude.
    if shifts.shape[0] < 2:
        accel = np.linalg.norm(shifts, axis=1)
    else:
        accel = np.linalg.norm(shifts[1:] - shifts[:-1], axis=1)
        # Pad to length (t-1) by repeating first accel
        accel = np.concatenate([accel[:1], accel], axis=0)

    # Robust normalize and compress tails.
    med = float(np.median(accel)) if accel.size else 0.0
    out = np.log1p(accel / (med + 1e-6))
    return out.astype(np.float32)


def _motion_features(frames: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (shifts_xy, speed, shakiness).

    shifts_xy: (T-1, 2) float32, per-step translation estimate in pixels on the sampled frames.
    speed: (T-1,) float32, magnitude of shifts.
    shakiness: (T-1,) float32, jitter metric (log-compressed accel magnitude).
    """

    t = frames.shape[0]
    if t < 2:
        empty_xy = np.zeros((0, 2), dtype=np.float32)
        empty_1 = np.zeros((0,), dtype=np.float32)
        return empty_xy, empty_1, empty_1

    f = frames.astype(np.float32) / 255.0
    F = np.fft.fft2(f, axes=(1, 2))

    shifts = np.zeros((t - 1, 2), dtype=np.float32)
    h, w = f.shape[1], f.shape[2]
    eps = 1e-9

    for i in range(t - 1):
        R = F[i] * np.conj(F[i + 1])
        R /= (np.abs(R) + eps)
        r = np.fft.ifft2(R)
        r_abs = np.abs(r)
        y, x = np.unravel_index(np.argmax(r_abs), r_abs.shape)

        if x > w // 2:
            x = x - w
        if y > h // 2:
            y = y - h

        shifts[i, 0] = float(x)
        shifts[i, 1] = float(y)

    speed = np.linalg.norm(shifts, axis=1).astype(np.float32)

    if shifts.shape[0] < 2:
        accel = speed
    else:
        accel = np.linalg.norm(shifts[1:] - shifts[:-1], axis=1)
        accel = np.concatenate([accel[:1], accel], axis=0)

    med = float(np.median(accel)) if accel.size else 0.0
    shakiness = np.log1p(accel / (med + 1e-6)).astype(np.float32)
    return shifts, speed, shakiness


def analyze_shakiness(root: Path, out_dir: Path, sample_fps: float = 5.0, scale_width: int = 320) -> None:
    idx_path = out_dir / "index.json"
    if not idx_path.exists():
        raise SystemExit(f"Missing index: {idx_path}. Run 'index' first.")

    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    clips = idx["clips"]

    results: dict[str, dict] = {"sample_fps": sample_fps, "scale_width": scale_width, "clips": {}}

    for clip in tqdm(clips, desc="Analyze"):
        path = Path(clip["path"])
        width, height, fps = _probe_dims(path)

        # Prefer streaming analysis to avoid reading huge raw buffers into memory.
        # We only need per-frame-pair shifts, so we can compute them incrementally.
        if width <= 0 or height <= 0:
            results["clips"][clip["rel"]] = {"error": "probe_failed"}
            continue
        scaled_w = scale_width
        scaled_h = int(round(height * (scale_width / width)))
        frame_size = int(scaled_w * scaled_h)
        if frame_size <= 0:
            results["clips"][clip["rel"]] = {"error": "bad_dims"}
            continue

        proc = _ffmpeg_gray_stream(path, sample_fps=sample_fps, scale_width=scale_width)
        assert proc.stdout is not None

        prev_F = None
        shifts_list: list[list[float]] = []
        t_frames = 0
        h, w = scaled_h, scaled_w
        eps = 1e-9

        while True:
            buf = proc.stdout.read(frame_size)
            if not buf or len(buf) < frame_size:
                break
            t_frames += 1
            frame = np.frombuffer(buf, dtype=np.uint8).reshape((h, w)).astype(np.float32) / 255.0
            F = np.fft.fft2(frame)
            if prev_F is not None:
                R = prev_F * np.conj(F)
                R /= (np.abs(R) + eps)
                r = np.fft.ifft2(R)
                r_abs = np.abs(r)
                y, x = np.unravel_index(np.argmax(r_abs), r_abs.shape)

                # Convert peak location to signed shift (wrap-around)
                if x > w // 2:
                    x = x - w
                if y > h // 2:
                    y = y - h

                shifts_list.append([float(x), float(y)])
            prev_F = F

        try:
            proc.stdout.close()
        except Exception:
            pass
        proc.wait()

        if t_frames < 2:
            results["clips"][clip["rel"]] = {"error": "no_frames"}
            continue

        shifts = np.asarray(shifts_list, dtype=np.float32)
        speed = np.linalg.norm(shifts, axis=1).astype(np.float32)
        if shifts.shape[0] < 2:
            accel = speed
        else:
            accel = np.linalg.norm(shifts[1:] - shifts[:-1], axis=1)
            accel = np.concatenate([accel[:1], accel], axis=0)
        med = float(np.median(accel)) if accel.size else 0.0
        series = np.log1p(accel / (med + 1e-6)).astype(np.float32)
        results["clips"][clip["rel"]] = {
            "path": str(path),
            "group": clip.get("group"),
            "orig": {"w": width, "h": height, "fps": fps},
            "sample": {"fps": sample_fps, "w": scaled_w, "h": scaled_h, "frames": int(t_frames)},
            "shakiness": series.tolist(),
            "shifts_xy": shifts.tolist(),
            "speed": speed.tolist(),
        }

    (out_dir / "shakiness.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote shakiness -> {out_dir / 'shakiness.json'}")


def quick_shakiness_score(
    path: Path,
    *,
    sample_fps: float = 3.0,
    scale_width: int = 256,
    max_frames: int = 96,
) -> tuple[float | None, dict]:
    """Compute a fast scalar shakiness score for a clip.

    This is designed for stabilization QC where we only need a rough comparison
    between original vs stabilized renders.

    Returns (score, details). score is None when the clip couldn't be analyzed.
    """

    try:
        width, height, fps = _probe_dims(path)
        if width <= 0 or height <= 0:
            return None, {"error": "probe_failed"}
        scaled_w = int(scale_width)
        scaled_h = int(round(height * (scaled_w / width)))
        frame_size = int(scaled_w * scaled_h)
        if frame_size <= 0:
            return None, {"error": "bad_dims"}

        proc = _ffmpeg_gray_stream(path, sample_fps=float(sample_fps), scale_width=int(scale_width))
        assert proc.stdout is not None

        prev_F = None
        shifts: list[list[float]] = []
        t_frames = 0
        h, w = scaled_h, scaled_w
        eps = 1e-9

        while t_frames < int(max_frames):
            buf = proc.stdout.read(frame_size)
            if not buf or len(buf) < frame_size:
                break
            t_frames += 1
            frame = np.frombuffer(buf, dtype=np.uint8).reshape((h, w)).astype(np.float32) / 255.0
            F = np.fft.fft2(frame)
            if prev_F is not None:
                R = prev_F * np.conj(F)
                R /= (np.abs(R) + eps)
                r = np.fft.ifft2(R)
                r_abs = np.abs(r)
                y, x = np.unravel_index(np.argmax(r_abs), r_abs.shape)
                if x > w // 2:
                    x = x - w
                if y > h // 2:
                    y = y - h
                shifts.append([float(x), float(y)])
            prev_F = F

        try:
            proc.stdout.close()
        except Exception:
            pass

        # Ensure ffmpeg exits promptly.
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

        if t_frames < 2 or not shifts:
            return None, {"error": "no_frames", "frames": int(t_frames)}

        sh = np.asarray(shifts, dtype=np.float32)
        if sh.shape[0] < 2:
            accel = np.linalg.norm(sh, axis=1)
        else:
            accel = np.linalg.norm(sh[1:] - sh[:-1], axis=1)
            accel = np.concatenate([accel[:1], accel], axis=0)

        med = float(np.median(accel)) if accel.size else 0.0
        series = np.log1p(accel / (med + 1e-6)).astype(np.float32)
        score = float(np.mean(series)) if series.size else None
        return score, {
            "orig": {"w": width, "h": height, "fps": fps},
            "sample": {"fps": float(sample_fps), "w": int(scaled_w), "h": int(scaled_h), "frames": int(t_frames)},
        }
    except Exception as e:
        return None, {"error": f"exception: {e}"}
