from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe

from videoassistant.shot_types import classify_shot_from_motion


@dataclass
class SelectSettings:
    min_seg_seconds: float = 3.0
    edge_ignore_seconds: float = 1.0
    max_segs_per_clip: int = 2


def _ffmpeg_gray_frames(path: Path, *, t_in: float, t_out: float, sample_fps: float, scale_width: int) -> np.ndarray:
    """Decode a small number of low-res gray frames from [t_in, t_out].

    Returns frames as (T,H,W) uint8.
    """

    duration = max(0.0, float(t_out) - float(t_in))
    if duration <= 0.0:
        return np.zeros((0, 0, 0), dtype=np.uint8)

    ffmpeg = get_ffmpeg_exe()
    vf = f"fps={sample_fps},scale={scale_width}:-1:flags=lanczos,format=gray"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{t_in:.3f}",
        "-t",
        f"{duration:.3f}",
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
    p = subprocess.run(cmd, capture_output=True)
    raw = p.stdout or b""
    if not raw:
        return np.zeros((0, 0, 0), dtype=np.uint8)

    # Infer dimensions from the first frame by re-running with ffprobe would be nicer,
    # but we can infer height from raw length since width is fixed.
    # Try a small set of likely aspect ratios.
    w = int(scale_width)
    candidates_h = [int(w * 9 / 16), int(w * 3 / 4), int(w * 2 / 3), int(w * 16 / 9), int(w * 4 / 3)]
    h = None
    for hh in candidates_h:
        if hh > 0 and len(raw) % (w * hh) == 0:
            h = hh
            break
    if h is None:
        return np.zeros((0, 0, 0), dtype=np.uint8)

    frame_size = w * h
    t = len(raw) // frame_size
    if t <= 0:
        return np.zeros((0, 0, 0), dtype=np.uint8)
    raw = raw[: t * frame_size]
    return np.frombuffer(raw, dtype=np.uint8).reshape((t, h, w))


def _estimate_roll_deg(frames: np.ndarray) -> tuple[float | None, float]:
    """Estimate roll angle (degrees) from low-res gray frames.

    This is a lightweight heuristic for interior walkthrough footage. It looks for
    dominant line direction by analyzing edge orientations.

    Returns (roll_deg, confidence) where confidence is in [0,1].
    """

    if frames.ndim != 3 or frames.size == 0:
        return None, 0.0

    def _wmean(x: np.ndarray, w: np.ndarray) -> float | None:
        wsum = float(np.sum(w))
        if not np.isfinite(wsum) or wsum <= 0.0:
            return None
        v = float(np.sum(x * w) / wsum)
        return v if np.isfinite(v) else None

    def _wstd(x: np.ndarray, w: np.ndarray, mean: float) -> float:
        wsum = float(np.sum(w))
        if not np.isfinite(wsum) or wsum <= 0.0:
            return 1e9
        v = float(np.sum(((x - mean) ** 2) * w) / wsum)
        return float(np.sqrt(max(0.0, v))) if np.isfinite(v) else 1e9

    per_frame: list[float] = []
    per_conf: list[float] = []

    for fr in frames:
        f = fr.astype(np.float32) / 255.0
        if f.shape[0] < 8 or f.shape[1] < 8:
            continue

        # Simple centered gradients (fast, good enough for roll estimation)
        gx = f[:, 2:] - f[:, :-2]
        gy = f[2:, :] - f[:-2, :]
        gx = gx[1:-1, :]
        gy = gy[:, 1:-1]

        mag = np.hypot(gx, gy)
        if mag.size == 0:
            continue

        thr = float(np.percentile(mag, 90))
        sel = mag >= thr
        if int(np.count_nonzero(sel)) < 200:
            continue

        # Edge direction is gradient direction + 90deg.
        ang = np.arctan2(gy[sel], gx[sel]) + (np.pi / 2.0)
        # Map to [-pi/2, pi/2] (degrees in [-90, 90]).
        ang = ((ang + (np.pi / 2.0)) % np.pi) - (np.pi / 2.0)
        ang_deg_all = (ang * (180.0 / np.pi)).astype(np.float32)
        w_all = mag[sel].astype(np.float32)

        # Use both near-horizontal and near-vertical structure.
        # - Horizontal lines have direction ~ roll.
        # - Vertical lines have direction ~ +/-90 + roll.
        mask_h = np.abs(ang_deg_all) <= 25.0
        mask_v = np.abs(ang_deg_all) >= 65.0

        wsum_all = float(np.sum(w_all))
        if not np.isfinite(wsum_all) or wsum_all <= 0.0:
            continue

        roll_candidates: list[tuple[float, float, float]] = []

        if int(np.count_nonzero(mask_h)) >= 80:
            a_h = ang_deg_all[mask_h]
            w_h = w_all[mask_h]
            roll_h = _wmean(a_h, w_h)
            if roll_h is not None:
                std_h = _wstd(a_h, w_h, roll_h)
                roll_candidates.append((float(roll_h), float(np.sum(w_h)), float(std_h)))

        if int(np.count_nonzero(mask_v)) >= 80:
            a_v_raw = ang_deg_all[mask_v]
            w_v = w_all[mask_v]
            # Convert near-vertical angles to small roll values near 0.
            a_v = a_v_raw - (np.sign(a_v_raw) * 90.0)
            roll_v = _wmean(a_v, w_v)
            if roll_v is not None:
                std_v = _wstd(a_v, w_v, roll_v)
                roll_candidates.append((float(roll_v), float(np.sum(w_v)), float(std_v)))

        if not roll_candidates:
            continue

        # If we have both a horizontal and vertical estimate and they agree, blend.
        if len(roll_candidates) >= 2:
            r0, w0, s0 = roll_candidates[0]
            r1, w1, s1 = roll_candidates[1]
            if abs(r0 - r1) <= 1.25:
                roll = (r0 * w0 + r1 * w1) / max(1e-6, (w0 + w1))
                spread = min(s0, s1)
                wsum = w0 + w1
                agree = 1.0
            else:
                # Pick the stronger signal; penalize confidence due to disagreement.
                r, w, s = max(roll_candidates, key=lambda t: t[1])
                roll = r
                spread = s
                wsum = w
                agree = 0.6
        else:
            roll, wsum, spread = roll_candidates[0]
            agree = 1.0

        # Confidence: fraction of strong-edge energy supporting the chosen direction,
        # penalized if the angle distribution is broad.
        frac = float(np.clip(wsum / (wsum_all + 1e-6), 0.0, 1.0))
        sharp = float(np.exp(-((float(spread) / 18.0) ** 2)))
        conf = float(np.clip(frac * sharp * agree, 0.0, 1.0))

        if np.isfinite(roll):
            per_frame.append(float(roll))
            per_conf.append(float(conf))

    if not per_frame:
        return None, 0.0

    rolls = np.asarray(per_frame, dtype=np.float32)
    confs = np.asarray(per_conf, dtype=np.float32)

    # Prefer a confidence-weighted average across frames to reduce jitter.
    wsum = float(np.sum(confs))
    if np.isfinite(wsum) and wsum > 0.0:
        roll_med = float(np.sum(rolls * confs) / wsum)
    else:
        roll_med = float(np.median(rolls))
    conf_med = float(np.median(confs))

    # Clamp to something reasonable; if it wants to rotate a lot, we probably mis-detected.
    roll_med = float(np.clip(roll_med, -10.0, 10.0))
    return roll_med, float(np.clip(conf_med, 0.0, 1.0))


def _stable_segments(series: np.ndarray, sample_fps: float, min_len_s: float, edge_ignore_s: float) -> list[tuple[int, int, float]]:
    """Return segments as (start_idx, end_idx_excl, score) in shakiness-step units.

    series is length (T-1) where each step ~ 1/sample_fps seconds.
    """
    if series.size == 0:
        return []

    step_s = 1.0 / sample_fps
    min_len = int(round(min_len_s / step_s))
    edge_ignore = int(round(edge_ignore_s / step_s))

    start_i = max(0, edge_ignore)
    end_i = max(start_i, series.size - edge_ignore)
    s = series[start_i:end_i]
    if s.size == 0:
        return []

    # Threshold based on percentile: accept "good" windows (low jitter)
    # 60th percentile is intentionally permissive; we prefer returning a usable segment
    # rather than returning nothing for smooth-moving gimbal shots.
    thr = float(np.percentile(s, 60))
    good = s <= thr

    segments: list[tuple[int, int]] = []
    i = 0
    while i < good.size:
        if not good[i]:
            i += 1
            continue
        j = i
        while j < good.size and good[j]:
            j += 1
        if j - i >= min_len:
            segments.append((i + start_i, j + start_i))
        i = j

    out: list[tuple[int, int, float]] = []
    for a, b in segments:
        seg = series[a:b]
        score = float(1.0 / (1e-6 + np.mean(seg)))
        out.append((a, b, score))

    out.sort(key=lambda x: x[2], reverse=True)

    # Fallback: if nothing meets the run-length criteria, pick the best window.
    if not out:
        win = max(1, min_len)
        ss = series[start_i:end_i]
        if ss.size >= win:
            # Sliding window mean; pick minimal mean.
            csum = np.cumsum(np.concatenate([[0.0], ss.astype(np.float64)]))
            means = (csum[win:] - csum[:-win]) / win
            k = int(np.argmin(means))
            a = start_i + k
            b = start_i + k + win
        else:
            a = start_i
            b = end_i
        seg = series[a:b]
        score = float(1.0 / (1e-6 + np.mean(seg))) if seg.size else 0.0
        out = [(a, b, score)]

    return out


def build_selects(out_dir: Path, min_seg_seconds: float = 3.0, edge_ignore_seconds: float = 1.0, max_segs_per_clip: int = 2) -> dict:
    shak_path = out_dir / "shakiness.json"
    idx_path = out_dir / "index.json"
    if not shak_path.exists() or not idx_path.exists():
        raise SystemExit("Missing shakiness.json or index.json. Run index + analyze first.")

    shak = json.loads(shak_path.read_text(encoding="utf-8"))
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    clip_room = {c["rel"]: c.get("room", "unknown") for c in idx.get("clips", [])}
    sample_fps = float(shak["sample_fps"])

    selects: dict = {"sample_fps": sample_fps, "clips": {}}

    for rel, info in shak["clips"].items():
        if "error" in info:
            selects["clips"][rel] = {"error": info["error"]}
            continue

        series = np.asarray(info.get("shakiness", []), dtype=np.float32)
        shifts_xy = np.asarray(info.get("shifts_xy", []), dtype=np.float32)
        segs = _stable_segments(series, sample_fps, min_seg_seconds, edge_ignore_seconds)
        segs = segs[: max_segs_per_clip]

        # Convert step indices -> seconds (approx)
        step_s = 1.0 / sample_fps

        segments_out = []
        for a, b, score in segs:
            t_in = float(a * step_s)
            t_out = float((b + 1) * step_s)
            # Classify shot type using motion within the segment window.
            st = None
            try:
                win_xy = shifts_xy[a:b] if shifts_xy.size else np.zeros((0, 2), dtype=np.float32)
                win_shk = series[a:b] if series.size else np.zeros((0,), dtype=np.float32)
                st = classify_shot_from_motion(win_xy, shakiness=win_shk)
            except Exception:
                st = None

            seg_d = {
                "t_in": t_in,
                "t_out": t_out,
                "score": float(score),
            }
            if st is not None:
                seg_d.update(
                    {
                        "shot_type": st.shot_type,
                        "shot_confidence": float(st.confidence),
                        "motion_speed": float(st.speed),
                        "motion_dir_var": float(st.dir_var),
                        "motion_curvature": float(st.curvature),
                    }
                )

            # Estimate horizon roll for slight camera rotation; used for Resolve sizing correction.
            try:
                clip_path = Path(info.get("path") or "")
                if clip_path.exists():
                    roll_frames = _ffmpeg_gray_frames(clip_path, t_in=t_in, t_out=t_out, sample_fps=1.0, scale_width=320)
                    roll_deg, roll_conf = _estimate_roll_deg(roll_frames)
                    if roll_deg is not None and roll_conf >= 0.02 and abs(float(roll_deg)) >= 0.3:
                        seg_d["roll_deg"] = float(roll_deg)
                        seg_d["roll_confidence"] = float(roll_conf)
            except Exception:
                pass
            segments_out.append(seg_d)

        selects["clips"][rel] = {
            "path": info.get("path"),
            "group": info.get("group"),
            "room": info.get("room") or clip_room.get(rel, "unknown"),
            "segments": segments_out,
        }

    return selects
