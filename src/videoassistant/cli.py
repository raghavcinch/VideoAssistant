from __future__ import annotations

import argparse
import json
from pathlib import Path

from videoassistant.exports.csv_export import write_selects_csv
from videoassistant.exports.resolve_export import write_resolve_script
from videoassistant.exports.resolve_render import write_resolve_render_timeline_script
from videoassistant.exports.speedramp_export import SpeedRampSettings, export_speedramped_rooms
from videoassistant.motion import analyze_shakiness
from videoassistant.rooms import default_room_rules_template, load_room_rules
from videoassistant.selects import build_selects
from videoassistant.agents.base import AgentContext
from videoassistant.agents.video_editor import VideoEditorAgent
from videoassistant.indexing import index_media


def _p(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videoassistant")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="Scan root for video files and write index.json")
    p_index.add_argument("--root", required=True)
    p_index.add_argument("--out", default=None, help="Output folder (default: <root>/.va)")

    p_rooms = sub.add_parser("init-rooms", help="Write a room keyword template to <root>/.va/room_keywords.json")
    p_rooms.add_argument("--root", required=True)

    p_an = sub.add_parser("analyze", help="Compute time-sliced shakiness metrics per clip")
    p_an.add_argument("--root", required=True)
    p_an.add_argument("--out", default=None)
    p_an.add_argument("--sample-fps", type=float, default=5.0)
    p_an.add_argument("--scale-width", type=int, default=320)

    p_sel = sub.add_parser("selects", help="Generate best stable segments per clip")
    p_sel.add_argument("--root", required=True)
    p_sel.add_argument("--out", default=None)
    p_sel.add_argument("--min-seg-seconds", type=float, default=3.0)
    p_sel.add_argument("--edge-ignore-seconds", type=float, default=1.0)
    p_sel.add_argument("--max-segs-per-clip", type=int, default=2)

    p_exp = sub.add_parser("export", help="Export selects to CSV + Resolve helper script")
    p_exp.add_argument("--root", required=True)
    p_exp.add_argument("--out", required=True)
    p_exp.add_argument("--project", default="VA_Selects")

    p_rnd = sub.add_parser("render-timeline", help="Render a Resolve timeline to a single MP4/MKV/QuickTime file")
    p_rnd.add_argument("--root", required=True, help="Root folder (used to store script under <root>/.va)")
    p_rnd.add_argument("--project", required=True, help="Resolve project name")
    p_rnd.add_argument("--timeline", required=True, help="Timeline name (e.g. CROCKERY_SELECTS)")
    p_rnd.add_argument("--out", required=True, help="Output folder for rendered file")
    p_rnd.add_argument("--name", default=None, help="Custom output name (no extension recommended)")
    p_rnd.add_argument("--render-preset", default=None, help="Resolve render preset name (optional)")
    p_rnd.add_argument("--render-format", default=None, help="Resolve render format (optional)")
    p_rnd.add_argument("--render-codec", default=None, help="Resolve render codec (optional)")
    p_rnd.add_argument("--connect-timeout-s", type=int, default=120, help="Seconds to wait for Resolve scripting connection")

    p_sr = sub.add_parser("speedramps", help="Bake cinematic speed ramps into per-room MP4s (FFmpeg-based)")
    p_sr.add_argument("--root", required=True, help="Property root (expects <root>/.va/index.json and selects.json)")
    p_sr.add_argument("--out", required=True, help="Output folder (writes <out>/speedramps/<room>.mp4)")
    p_sr.add_argument("--fps", type=float, default=30.0, help="Output fps used for all segments")
    p_sr.add_argument("--vcodec", default="libx264", help="Video codec (e.g. libx264, h264_nvenc)")
    p_sr.add_argument("--crf", type=int, default=18, help="CRF (x264/x265) or CQ (nvenc)")
    p_sr.add_argument("--preset", default="veryfast", help="Encoder preset (x264)")
    p_sr.add_argument("--min-ramp-seconds", type=float, default=2.2, help="Don’t ramp segments shorter than this")
    p_sr.add_argument(
        "--style",
        default="youtube",
        choices=["luxury", "youtube", "fast"],
        help="Ramp style preset (luxury=slow reveal, youtube=balanced, fast=more aggressive)",
    )

    p_proc = sub.add_parser("process", help="One-shot: index + analyze + selects + export")
    p_proc.add_argument("--root", required=True)
    p_proc.add_argument("--out", required=True)
    p_proc.add_argument("--project", default="VA_Selects")
    p_proc.add_argument("--sample-fps", type=float, default=5.0)
    p_proc.add_argument("--scale-width", type=int, default=320)
    p_proc.add_argument("--min-seg-seconds", type=float, default=3.0)
    p_proc.add_argument("--edge-ignore-seconds", type=float, default=1.0)
    p_proc.add_argument("--max-segs-per-clip", type=int, default=2)

    p_pro = sub.add_parser(
        "process-pro",
        help="Resolve-first: stabilize (Resolve) -> analyze stabilized -> selects -> export -> import -> correction",
    )
    p_pro.add_argument("--root", required=True)
    p_pro.add_argument("--out", required=True)
    p_pro.add_argument("--project", default="VA_Selects")
    p_pro.add_argument("--sample-fps", type=float, default=5.0)
    p_pro.add_argument("--scale-width", type=int, default=320)
    p_pro.add_argument("--min-seg-seconds", type=float, default=3.0)
    p_pro.add_argument("--edge-ignore-seconds", type=float, default=1.0)
    p_pro.add_argument("--max-segs-per-clip", type=int, default=2)
    p_pro.add_argument("--stabilize", action="store_true", help="Stabilize+render clips first using Resolve scripting")
    p_pro.add_argument("--stabilized-dir", default=None, help="Where stabilized renders are written (default: <root>/.va/stabilized)")
    p_pro.add_argument("--render-preset", default=None, help="Resolve render preset name (optional)")
    p_pro.add_argument("--render-format", default=None, help="Resolve render format (optional)")
    p_pro.add_argument("--render-codec", default=None, help="Resolve render codec (optional)")
    p_pro.add_argument(
        "--stabilize-mode",
        default="similarity",
        choices=["similarity", "translation", "perspective"],
        help="UI hint for Resolve Stabilizer Mode to use (Resolve scripting can't reliably set this per-clip).",
    )
    p_pro.add_argument(
        "--stabilize-interactive",
        action="store_true",
        help="Pause the generated Resolve stabilization script and prompt you to set Stabilizer Mode in the UI before continuing.",
    )
    p_pro.add_argument(
        "--no-stabilize-qc",
        action="store_true",
        help="Disable post-stabilization QC that compares original vs stabilized shakiness and flags regressions.",
    )
    p_pro.add_argument(
        "--opencv-fallback",
        action="store_true",
        help="If stabilization QC finds regressions, re-stabilize only those clips with OpenCV and use them instead (non-interactive).",
    )
    p_pro.add_argument(
        "--opencv-mode",
        default="similarity",
        choices=["translation", "similarity"],
        help="OpenCV fallback stabilization mode (similarity usually works best; translation is the most conservative).",
    )
    p_pro.add_argument("--import-to-resolve", action="store_true", help="Run generated resolve_import_selects.py automatically")
    p_pro.add_argument(
        "--export-pretrim",
        action="store_true",
        help="Export full selected clips (stabilized + graded/LUT baked) into <out>/exports/pretrim/<room>/ before autotrim",
    )
    p_pro.add_argument(
        "--export-pretrim-prefix",
        default="PRETRIM_{room}_",
        help="Filename prefix template for exported pretrim clips. Supports {room} and {project}.",
    )
    p_pro.add_argument(
        "--no-skip-timeline-correction",
        action="store_true",
        help="If set, still run timeline correction even when --export-pretrim is enabled (may double-grade).",
    )
    p_pro.add_argument("--grade-drx", default=None, help="Path to a .drx still to apply to *_SELECTS timelines")
    p_pro.add_argument("--grade-mode", type=int, default=0, help="0=no keyframes, 1=timecode aligned, 2=start aligned")
    p_pro.add_argument("--grade-lut", default=None, help="Optional LUT path/name to apply to node 1 on *_SELECTS timelines")
    p_pro.add_argument("--no-auto-grade", action="store_true", help="Disable the built-in auto-grade (CDL contrast/sat)")
    p_pro.add_argument("--cdl-slope", default="1.02 1.02 1.02")
    p_pro.add_argument("--cdl-offset", default="0.0 0.0 0.0")
    p_pro.add_argument("--cdl-power", default="0.98 0.98 0.98")
    p_pro.add_argument("--cdl-saturation", default="1.08")

    args = parser.parse_args(argv)

    root = _p(args.root)
    out_base = _p(args.out) if getattr(args, "out", None) else (root / ".va")
    out_base.mkdir(parents=True, exist_ok=True)

    room_rules_path = out_base / "room_keywords.json"
    room_rules = None
    if room_rules_path.exists():
        try:
            room_rules = load_room_rules(room_rules_path)
        except Exception as e:
            raise SystemExit(f"Invalid room rules in {room_rules_path}: {e}")

    if args.cmd == "init-rooms":
        room_rules_path.parent.mkdir(parents=True, exist_ok=True)
        if room_rules_path.exists():
            raise SystemExit(f"Already exists: {room_rules_path}")
        room_rules_path.write_text(json.dumps(default_room_rules_template(), indent=2), encoding="utf-8")
        print(f"Wrote room keyword template -> {room_rules_path}")
        return 0

    if args.cmd == "index":
        idx = index_media(root, room_rules=room_rules)
        (out_base / "index.json").write_text(json.dumps(idx, indent=2), encoding="utf-8")
        print(f"Indexed {len(idx['clips'])} clips -> {out_base / 'index.json'}")
        return 0

    if args.cmd == "analyze":
        analyze_shakiness(root, out_base, sample_fps=args.sample_fps, scale_width=args.scale_width)
        return 0

    if args.cmd == "selects":
        selects = build_selects(
            out_base,
            min_seg_seconds=args.min_seg_seconds,
            edge_ignore_seconds=args.edge_ignore_seconds,
            max_segs_per_clip=args.max_segs_per_clip,
        )
        (out_base / "selects.json").write_text(json.dumps(selects, indent=2), encoding="utf-8")
        print(f"Wrote selects -> {out_base / 'selects.json'}")
        return 0

    if args.cmd == "export":
        va_dir = root / ".va"
        selects_path = va_dir / "selects.json"
        index_path = va_dir / "index.json"
        if not selects_path.exists() or not index_path.exists():
            raise SystemExit("Missing .va/index.json or .va/selects.json. Run index/analyze/selects first.")

        out_dir = _p(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        selects = json.loads(selects_path.read_text(encoding="utf-8"))
        index = json.loads(index_path.read_text(encoding="utf-8"))

        write_selects_csv(out_dir / "selects.csv", index, selects)
        write_resolve_script(out_dir / "resolve_import_selects.py", index, selects, project_name=args.project)
        print(f"Wrote: {out_dir / 'selects.csv'}")
        print(f"Wrote: {out_dir / 'resolve_import_selects.py'}")
        return 0

    if args.cmd == "render-timeline":
        va_dir = root / ".va"
        va_dir.mkdir(parents=True, exist_ok=True)

        out_dir = _p(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)

        script_path = va_dir / "resolve_render_timeline.py"
        payload = {
            "project_name": args.project,
            "timeline_name": args.timeline,
            "target_dir": str(out_dir),
            "custom_name": args.name or args.timeline,
            "render_preset": args.render_preset,
            "render_format": args.render_format,
            "render_codec": args.render_codec,
            "connect_timeout_s": int(args.connect_timeout_s),
        }
        write_resolve_render_timeline_script(script_path, payload)

        import subprocess
        import sys

        proc = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"Resolve render script failed (exit={proc.returncode}).\n{proc.stderr.strip()}")

        # Prefer stdout; include stderr as warning-ish output if present.
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.stderr.strip():
            print(proc.stderr.strip())
        return 0

    if args.cmd == "speedramps":
        va_dir = root / ".va"
        out_dir = _p(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)

        settings = SpeedRampSettings(
            output_fps=float(args.fps),
            vcodec=str(args.vcodec),
            crf=int(args.crf),
            preset=str(args.preset),
            min_ramp_seconds=float(args.min_ramp_seconds),
            style=str(args.style),
        )
        outs = export_speedramped_rooms(va_dir=va_dir, out_dir=out_dir, settings=settings)
        if not outs:
            raise SystemExit("No outputs created (no segments or missing media).")
        for p in outs:
            print(f"Wrote: {p}")
        return 0

    if args.cmd == "process":
        va_dir = root / ".va"
        va_dir.mkdir(parents=True, exist_ok=True)

        out_dir = _p(args.out)
        room_rules_path = va_dir / "room_keywords.json"
        ctx = AgentContext(
            root=root,
            va_dir=va_dir,
            out_dir=out_dir,
            project_name=args.project,
            sample_fps=args.sample_fps,
            scale_width=args.scale_width,
            min_seg_seconds=args.min_seg_seconds,
            edge_ignore_seconds=args.edge_ignore_seconds,
            max_segs_per_clip=args.max_segs_per_clip,
            room_rules_path=room_rules_path,
        )

        res = VideoEditorAgent().run(ctx)
        if not res.ok:
            raise SystemExit(res.summary)

        print(f"Done. Wrote: {out_dir / 'selects.csv'}")
        print(f"Done. Wrote: {out_dir / 'resolve_import_selects.py'}")
        print(f"Run log: {va_dir / 'run_log.json'}")
        if res.warnings:
            print("Warnings:")
            for w in res.warnings:
                print(f"- {w}")
        return 0

    if args.cmd == "process-pro":
        va_dir = root / ".va"
        va_dir.mkdir(parents=True, exist_ok=True)

        out_dir = _p(args.out)
        room_rules_path = va_dir / "room_keywords.json"
        stabilized_dir = _p(args.stabilized_dir) if args.stabilized_dir else (va_dir / "stabilized")

        ctx = AgentContext(
            root=root,
            va_dir=va_dir,
            out_dir=out_dir,
            project_name=args.project,
            sample_fps=args.sample_fps,
            scale_width=args.scale_width,
            min_seg_seconds=args.min_seg_seconds,
            edge_ignore_seconds=args.edge_ignore_seconds,
            max_segs_per_clip=args.max_segs_per_clip,
            room_rules_path=room_rules_path,
            stabilize_first=bool(args.stabilize),
            stabilized_dir=stabilized_dir,
            stabilize_render_preset=args.render_preset,
            stabilize_render_format=args.render_format,
            stabilize_render_codec=args.render_codec,
            stabilize_mode_hint=str(args.stabilize_mode).capitalize() if args.stabilize_mode else None,
            stabilize_interactive=bool(args.stabilize_interactive),
            stabilize_qc=not bool(args.no_stabilize_qc),
            stabilize_opencv_fallback=bool(args.opencv_fallback),
            opencv_mode=str(args.opencv_mode),
            run_resolve_import=bool(args.import_to_resolve),
            export_pretrim=bool(args.export_pretrim),
            export_pretrim_dir=None,
            export_pretrim_prefix=str(args.export_pretrim_prefix),
            skip_timeline_correction_if_pretrim=not bool(args.no_skip_timeline_correction),
            grade_drx_path=_p(args.grade_drx) if args.grade_drx else None,
            grade_mode=int(args.grade_mode),
            grade_lut_path=args.grade_lut,
            auto_grade=not bool(args.no_auto_grade),
            cdl_slope=args.cdl_slope,
            cdl_offset=args.cdl_offset,
            cdl_power=args.cdl_power,
            cdl_saturation=args.cdl_saturation,
        )

        res = VideoEditorAgent().run(ctx)
        if not res.ok:
            raise SystemExit(res.summary)

        print(f"Done. Wrote: {out_dir / 'selects.csv'}")
        print(f"Done. Wrote: {out_dir / 'resolve_import_selects.py'}")
        print(f"Run log: {va_dir / 'run_log.json'}")
        if res.warnings:
            print("Warnings:")
            for w in res.warnings:
                print(f"- {w}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
