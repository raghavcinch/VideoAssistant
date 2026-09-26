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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="VA_TEMPLATE")
    ap.add_argument("--timeline", default="00_TEMPLATE")
    ap.add_argument("--track", type=int, default=1)
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

    items = tl.GetItemListInTrack("video", int(args.track)) or []
    print(f"{args.project}/{args.timeline}: V{args.track} items={len(items)}")
    if items:
        try:
            print("First item name:", items[0].GetName())
        except Exception:
            pass


if __name__ == "__main__":
    main()
