from __future__ import annotations

import argparse

from _resolve_bootstrap import connect_resolve


def _find_timeline(proj, name: str):
    get_by_name = getattr(proj, "GetTimelineByName", None)
    if callable(get_by_name):
        try:
            tl = get_by_name(name)
            if tl:
                return tl
        except Exception:
            pass
    try:
        n = int(proj.GetTimelineCount() or 0)
    except Exception:
        n = 0
    for i in range(1, n + 1):
        try:
            tl = proj.GetTimelineByIndex(i)
        except Exception:
            tl = None
        if not tl:
            continue
        try:
            if tl.GetName() == name:
                return tl
        except Exception:
            pass
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Add a placeholder clip to a template timeline")
    ap.add_argument("--project", default="VA_TEMPLATE")
    ap.add_argument("--timeline", default="00_TEMPLATE")
    ap.add_argument("--kind", default="composition", choices=["composition", "generator", "title"], help="Type of Fusion placeholder")
    ap.add_argument("--name", default="VA_PLACEHOLDER", help="Name for the inserted Fusion item")
    ap.add_argument("--seconds", type=float, default=5.0, help="Duration in seconds")
    ap.add_argument("--fps", type=float, default=30.0, help="Timeline FPS used to convert seconds->frames")
    ap.add_argument("--track", type=int, default=1, help="Video track index")
    ap.add_argument("--start", type=int, default=0, help="Start frame")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    resolve = connect_resolve(connect_timeout_s=int(args.timeout))
    pm = resolve.GetProjectManager()
    proj = pm.LoadProject(args.project)
    if not proj:
        raise SystemExit(f"Project not found: {args.project}")

    tl = _find_timeline(proj, args.timeline)
    if not tl:
        raise SystemExit(f"Timeline not found: {args.timeline}")

    # Make it current
    try:
        proj.SetCurrentTimeline(tl)
    except Exception:
        pass

    frames = max(1, int(round(float(args.seconds) * float(args.fps))))
    start = int(args.start)
    track = int(args.track)

    if args.kind == "composition":
        fn = getattr(tl, "InsertFusionCompositionIntoTimeline", None)
        payload = {
            "trackIndex": track,
            "startFrame": start,
            "duration": frames,
            "name": str(args.name),
        }
    elif args.kind == "generator":
        fn = getattr(tl, "InsertFusionGeneratorIntoTimeline", None)
        payload = {
            "trackIndex": track,
            "startFrame": start,
            "duration": frames,
            "generatorName": str(args.name),
        }
    else:
        fn = getattr(tl, "InsertFusionTitleIntoTimeline", None)
        payload = {
            "trackIndex": track,
            "startFrame": start,
            "duration": frames,
            "titleName": str(args.name),
        }

    if not callable(fn):
        raise SystemExit(f"Timeline does not support insertion kind={args.kind}")

    try:
        res = fn(payload)
    except Exception as e:
        raise SystemExit(f"Insert failed: {e}")

    try:
        pm.SaveProject()
    except Exception:
        pass

    print(f"Inserted placeholder ({args.kind}) into {args.project}/{args.timeline}: {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
