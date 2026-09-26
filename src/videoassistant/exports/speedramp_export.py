from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe

from videoassistant.exports.resolve_export import _cinematic_sequence


@dataclass
class SpeedRampSettings:
    output_fps: float = 30.0
    scale_even: bool = True
    # If a segment is shorter than this, don’t ramp (too jittery / too many cuts).
    min_ramp_seconds: float = 2.2

    # Encoding
    vcodec: str = "libx264"  # or h264_nvenc
    crf: int = 18
    preset: str = "veryfast"  # x264 preset; ignored by some codecs
    extra_args: list[str] | None = None

    # Curve resolution
    # Note: higher values produce more frequent speed changes, which can look
    # jittery/"steppy" when applied as a retime curve. Keep this modest.
    curve_pieces: int = 7

    # Curve style: controls how aggressive the ramps are.
    # - luxury: less speed-up, a bit more slow-down
    # - youtube: balanced
    # - fast: more speed-up, less slow-down
    style: str = "youtube"


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        msg = (p.stderr or p.stdout or "").strip()
        raise RuntimeError(f"ffmpeg failed (exit={p.returncode}): {msg}")


def _speed_target_for_shot(shot_type: str | None) -> float:
    st = (shot_type or "").lower()
    # Heuristic: keep motion readable, but add a gentle “push/pull” feel.
    # IMPORTANT: deep slowdowns create repeated frames ("looping") and jittery
    # motion unless you have true optical-flow retiming. Keep targets near 1.0.
    if st in {"static"}:
        return 0.96
    if st in {"slow_pan", "slow_tilt"}:
        return 0.97
    if st in {"pan", "tilt"}:
        return 0.98
    if st in {"walk", "arc"}:
        return 0.98
    if st in {"whip"}:
        return 1.05
    if st in {"shaky"}:
        return 1.0
    return 0.98


def _clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def _sigmoid01(x: float) -> float:
    # Smoothly map R->(0,1). x=0 -> 0.5
    return float(1.0 / (1.0 + math.exp(-x)))


def _apply_style(style: str, s_start: float, s_mid: float, s_end: float) -> tuple[float, float, float]:
    st = (style or "youtube").lower().strip()
    if st in {"lux", "luxury", "slow", "slow_reveal", "luxury_slow"}:
        # Pull speed-ups closer to 1.0, and slightly deepen slow section.
        s_start = 1.0 + (s_start - 1.0) * 0.55
        s_end = 1.0 + (s_end - 1.0) * 0.55
        s_mid = 1.0 - (1.0 - s_mid) * 1.12
    elif st in {"fast", "reels", "tiktok"}:
        s_start = 1.0 + (s_start - 1.0) * 1.25
        s_end = 1.0 + (s_end - 1.0) * 1.25
        s_mid = 1.0 - (1.0 - s_mid) * 0.90
    # youtube/default: unchanged
    return float(s_start), float(s_mid), float(s_end)


def _style_speed_bounds(style: str) -> tuple[float, float]:
    st = (style or "youtube").lower().strip()
    # Clamp speeds to a "professional" range to avoid obvious frame repeats.
    if st in {"lux", "luxury", "slow", "slow_reveal", "luxury_slow"}:
        return 0.92, 1.08
    if st in {"fast", "reels", "tiktok"}:
        return 0.95, 1.12
    return 0.94, 1.10


def _plan_speed_curve(seg: dict, duration_s: float, pieces: int, style: str) -> tuple[str, list[tuple[float, float, float]]]:
    """Return (curve_kind, [(t0,t1,speed), ...]) for this segment.

    Speeds are playback multipliers (1.0 = realtime).
    """

    st = (seg.get("shot_type") or "").lower()
    motion_speed = float(seg.get("motion_speed") or 0.0)
    curvature = float(seg.get("motion_curvature") or 0.0)

    base = _speed_target_for_shot(st)

    # Intensity: higher motion_speed => keep curve subtle (avoid nausea / judder).
    # motion_speed is in pixels/step @ 320px sampled frames; typical range ~[0..3+]
    fastness = _sigmoid01((motion_speed - 1.0) / 0.5)  # ~0.12 at 0, ~0.88 at 2
    subtle = 0.35 + 0.55 * fastness  # 0.35..0.90

    # Defaults (used for constant curve)
    s_start = 1.0
    s_mid = base
    s_end = 1.0
    curve_kind = "constant"

    if st == "arc":
        # Rotation/arc: fast at start/end, slow mid (classic reveal feel).
        curve_kind = "fast_slow_fast"
        s_mid = _clamp(0.65 + 0.25 * subtle, 0.65, 0.90)
        s_start = _clamp(1.05 + 0.10 * (1.0 - subtle), 1.00, 1.18)
        s_end = s_start
    elif st in {"walk"}:
        # Walk-in: gradually slow down as we approach subject.
        curve_kind = "fast_to_slow"
        s_start = _clamp(1.08 + 0.12 * (1.0 - subtle), 1.00, 1.22)
        s_end = _clamp(0.78 + 0.12 * subtle, 0.75, 0.95)
        s_mid = s_end
    elif st in {"pan", "tilt", "slow_pan", "slow_tilt"}:
        # Pans/tilts: subtle fast-slow-fast (less dramatic than arcs).
        curve_kind = "subtle_fast_slow_fast"
        s_mid = _clamp(0.78 + 0.10 * subtle, 0.78, 0.95)
        s_start = _clamp(1.03 + 0.08 * (1.0 - subtle), 1.00, 1.14)
        s_end = s_start
    elif st == "static":
        curve_kind = "slow_hold"
        s_start = 1.0
        s_mid = _clamp(0.62 + 0.15 * subtle, 0.62, 0.82)
        s_end = 1.0

    # Fallback: if classifier missed a rotation but curvature is clearly arc-like,
    # apply arc curve (avoid overriding explicit walk/pan/tilt/static labels).
    elif curvature >= 0.42:
        curve_kind = "fast_slow_fast"
        s_mid = _clamp(0.70 + 0.20 * subtle, 0.70, 0.92)
        s_start = _clamp(1.03 + 0.10 * (1.0 - subtle), 1.00, 1.16)
        s_end = s_start

    s_start, s_mid, s_end = _apply_style(style, s_start, s_mid, s_end)

    # Clamp to a subtle range to avoid "cheap" repeated-frame slowdowns.
    sp_lo, sp_hi = _style_speed_bounds(style)
    s_start = _clamp(float(s_start), sp_lo, sp_hi)
    s_mid = _clamp(float(s_mid), sp_lo, sp_hi)
    s_end = _clamp(float(s_end), sp_lo, sp_hi)

    # If segment is too short, keep constant.
    if duration_s < 2.0 or pieces <= 1 or curve_kind == "constant":
        return "constant", [(0.0, duration_s, 1.0)]

    n = int(max(3, min(15, pieces)))

    def speed_at(u: float) -> float:
        u = _clamp(u, 0.0, 1.0)
        if curve_kind in {"fast_slow_fast", "subtle_fast_slow_fast", "slow_hold"}:
            # Low in the middle, high on edges.
            # abs(2u-1) is 1 at edges, 0 at center.
            a = abs(2.0 * u - 1.0)
            gamma = 1.4 if curve_kind != "subtle_fast_slow_fast" else 1.8
            w = a**gamma
            return float(s_mid + (s_start - s_mid) * w)
        if curve_kind == "fast_to_slow":
            gamma = 1.2
            return float(s_start + (s_end - s_start) * (u**gamma))
        return 1.0

    # Emit a small set of curve samples (keyframes) and let the consumer (Fusion)
    # interpolate smoothly between them.
    # Format stays (t0,t1,speed) for backward-compat; treat `t0` as keyframe time.
    pieces_out: list[tuple[float, float, float]] = []
    times: list[float] = []
    for i in range(n):
        u = 0.0 if n <= 1 else (i / (n - 1))
        times.append(duration_s * u)
    for i, t0 in enumerate(times):
        u = 0.0 if duration_s <= 1e-9 else (t0 / duration_s)
        sp = _clamp(speed_at(u), sp_lo, sp_hi)
        t1 = times[i + 1] if i + 1 < len(times) else duration_s
        pieces_out.append((float(t0), float(t1), float(sp)))

    if not pieces_out:
        return "constant", [(0.0, duration_s, 1.0)]
    # Ensure coverage
    if pieces_out[0][0] > 1e-6:
        pieces_out[0] = (0.0, pieces_out[0][1], pieces_out[0][2])
    if pieces_out[-1][1] < duration_s - 1e-6:
        pieces_out[-1] = (pieces_out[-1][0], duration_s, pieces_out[-1][2])
    return curve_kind, pieces_out


def _build_ramp_filter(duration_s: float, pieces: list[tuple[float, float, float]], out_fps: float, scale_even: bool) -> str:
    if duration_s <= 0.0:
        raise ValueError("duration_s must be > 0")

    chains = []
    outs = []
    for i, (a, b, sp) in enumerate(pieces):
        a = max(0.0, float(a))
        b = max(a, float(b))
        # setpts=PTS/<speed> : speed<1 slows down
        label = f"v{i}"
        chains.append(f"[0:v]trim=start={a:.6f}:end={b:.6f},setpts=PTS/{sp:.6f}[{label}]")
        outs.append(f"[{label}]")

    chains.append("".join(outs) + f"concat=n={len(outs)}:v=1:a=0[vcat]")

    post = "[vcat]"
    if scale_even:
        post += "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1,"
    # Standardize fps for clean concat.
    post += f"fps={out_fps:.6f},format=yuv420p[vout]"
    chains.append(post)
    return ";".join(chains)


def export_speedramped_rooms(
    *,
    va_dir: Path,
    out_dir: Path,
    settings: SpeedRampSettings | None = None,
) -> list[Path]:
    """Export per-room MP4s with cinematic speed ramps baked in.

    Inputs:
    - Reads va_dir/index.json + va_dir/selects.json
    Output:
    - Writes to out_dir/speedramps/<room>.mp4
    """

    settings = settings or SpeedRampSettings()
    ffmpeg = get_ffmpeg_exe()

    index_path = va_dir / "index.json"
    selects_path = va_dir / "selects.json"
    if not index_path.exists() or not selects_path.exists():
        raise SystemExit("Missing index.json/selects.json in va_dir. Run process-pro first.")

    index = json.loads(index_path.read_text(encoding="utf-8"))
    selects = json.loads(selects_path.read_text(encoding="utf-8"))

    clips_by_rel = {c.get("rel"): c for c in (index.get("clips") or [])}
    room_to_segments: dict[str, list[dict]] = {}

    for rel, info in (selects.get("clips") or {}).items():
        if not info or info.get("error"):
            continue
        clip = clips_by_rel.get(rel) or {}
        room = info.get("room") or clip.get("room") or "unknown"
        for seg in info.get("segments") or []:
            d = dict(seg)
            d["rel"] = rel
            d["mtime"] = clip.get("mtime")
            d["name"] = clip.get("name")
            room_to_segments.setdefault(room, []).append(d)

    out_dir = Path(out_dir)
    out_root = out_dir / "speedramps"
    tmp_root = out_dir / "_tmp_speedramps"
    out_root.mkdir(parents=True, exist_ok=True)
    tmp_root.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    plan: dict = {
        "output_fps": float(settings.output_fps),
        "min_ramp_seconds": float(settings.min_ramp_seconds),
        "curve_pieces": int(settings.curve_pieces),
        "style": str(settings.style),
        "rooms": {},
    }

    for room in sorted(room_to_segments.keys()):
        segs = room_to_segments[room]
        try:
            segs.sort(key=lambda s: (str(s.get("rel") or ""), float(s.get("t_in", 0.0))))
        except Exception:
            pass
        ordered = _cinematic_sequence(segs)

        plan_room: list[dict] = []

        room_tmp = tmp_root / room
        room_tmp.mkdir(parents=True, exist_ok=True)
        seg_files: list[Path] = []

        for i, seg in enumerate(ordered, 1):
            rel = seg.get("rel")
            clip = clips_by_rel.get(rel) if rel else None
            if not clip:
                continue

            src = Path(str(clip.get("path") or ""))
            if not src.exists():
                continue

            t_in = float(seg.get("t_in", 0.0))
            t_out = float(seg.get("t_out", 0.0))
            dur = max(0.0, t_out - t_in)
            if dur <= 0.15:
                continue

            shot_type = seg.get("shot_type")
            do_ramp = dur >= float(settings.min_ramp_seconds)

            curve_kind, curve_pieces = _plan_speed_curve(seg, dur, pieces=int(settings.curve_pieces), style=str(settings.style))
            if not do_ramp:
                curve_kind, curve_pieces = ("constant", [(0.0, dur, 1.0)])

            plan_room.append(
                {
                    "i": int(i),
                    "rel": seg.get("rel"),
                    "src": str(src),
                    "t_in": float(t_in),
                    "t_out": float(t_out),
                    "duration": float(dur),
                    "shot_type": shot_type,
                    "curve_kind": curve_kind,
                    "curve": [{"t0": float(a), "t1": float(b), "speed": float(sp)} for (a, b, sp) in curve_pieces],
                }
            )

            seg_out = room_tmp / f"{i:03d}_{src.stem}.mp4"

            if do_ramp:
                fc = _build_ramp_filter(dur, pieces=curve_pieces, out_fps=settings.output_fps, scale_even=settings.scale_even)
                cmd = [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{t_in:.3f}",
                    "-t",
                    f"{dur:.3f}",
                    "-i",
                    str(src),
                    "-filter_complex",
                    fc,
                    "-map",
                    "[vout]",
                    "-an",
                    "-c:v",
                    settings.vcodec,
                ]
                # codec-specific knobs
                if settings.vcodec.lower() in {"libx264", "libx265"}:
                    cmd += ["-crf", str(int(settings.crf)), "-preset", settings.preset]
                elif settings.vcodec.lower().endswith("_nvenc"):
                    # NVENC doesn’t use CRF; use a sane constant-quality-like target.
                    cmd += ["-cq", str(int(settings.crf)), "-preset", "p5"]

                if settings.extra_args:
                    cmd += list(settings.extra_args)

                cmd += ["-y", str(seg_out)]
            else:
                # Simple trim only.
                cmd = [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{t_in:.3f}",
                    "-t",
                    f"{dur:.3f}",
                    "-i",
                    str(src),
                    "-vf",
                    ("scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1," if settings.scale_even else "")
                    + f"fps={settings.output_fps:.6f},format=yuv420p",
                    "-an",
                    "-c:v",
                    settings.vcodec,
                ]
                if settings.vcodec.lower() in {"libx264", "libx265"}:
                    cmd += ["-crf", str(int(settings.crf)), "-preset", settings.preset]
                elif settings.vcodec.lower().endswith("_nvenc"):
                    cmd += ["-cq", str(int(settings.crf)), "-preset", "p5"]
                if settings.extra_args:
                    cmd += list(settings.extra_args)
                cmd += ["-y", str(seg_out)]

            _run(cmd)
            seg_files.append(seg_out)

        if not seg_files:
            continue

        plan["rooms"][room] = plan_room

        # Concatenate processed segments.
        list_file = room_tmp / "concat.txt"
        list_file.write_text("\n".join([f"file '{p.as_posix()}'" for p in seg_files]) + "\n", encoding="utf-8")

        room_out = out_root / f"{room}.mp4"
        cmd_concat = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-an",
            "-c:v",
            settings.vcodec,
        ]
        if settings.vcodec.lower() in {"libx264", "libx265"}:
            cmd_concat += ["-crf", str(int(settings.crf)), "-preset", settings.preset]
        elif settings.vcodec.lower().endswith("_nvenc"):
            cmd_concat += ["-cq", str(int(settings.crf)), "-preset", "p5"]
        if settings.extra_args:
            cmd_concat += list(settings.extra_args)
        cmd_concat += ["-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", str(room_out)]
        _run(cmd_concat)
        outputs.append(room_out)

    # Write plan (even if empty for some rooms)
    try:
        (out_root / "speedramp_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    except Exception:
        pass

    return outputs
