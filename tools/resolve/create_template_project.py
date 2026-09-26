from __future__ import annotations

import argparse

from _resolve_bootstrap import connect_resolve


def _ensure_bin(media_pool, parent, name: str):
    for b in parent.GetSubFolderList() or []:
        try:
            if b and b.GetName() == name:
                return b
        except Exception:
            pass
    try:
        return media_pool.AddSubFolder(parent, name)
    except Exception:
        return None


def _find_timeline_by_name(proj, name: str):
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
    ap = argparse.ArgumentParser(description="Create a Resolve template project for VideoAssistant workflows")
    ap.add_argument("--project", default="VA_TEMPLATE", help="Template project name")
    ap.add_argument("--bin", default="00_TEMPLATE", help="Bin name to create")
    ap.add_argument("--timeline", default="00_TEMPLATE", help="Timeline name to create")
    ap.add_argument("--timeout", type=int, default=30, help="Seconds to wait for Resolve scripting connection")
    args = ap.parse_args()

    resolve = connect_resolve(connect_timeout_s=int(args.timeout))
    pm = resolve.GetProjectManager()

    proj = pm.LoadProject(args.project)
    if not proj:
        proj = pm.CreateProject(args.project)
        if not proj:
            raise SystemExit(f"Failed to create project: {args.project}")
        try:
            pm.LoadProject(args.project)
        except Exception:
            pass
    else:
        # Make it current
        try:
            pm.LoadProject(args.project)
        except Exception:
            pass

    media_pool = proj.GetMediaPool()
    root = media_pool.GetRootFolder()

    b = _ensure_bin(media_pool, root, str(args.bin))
    if b:
        try:
            media_pool.SetCurrentFolder(b)
        except Exception:
            pass

    tl = _find_timeline_by_name(proj, str(args.timeline))
    if not tl:
        try:
            tl = media_pool.CreateEmptyTimeline(str(args.timeline))
        except Exception:
            tl = None

    # Best-effort save
    try:
        pm.SaveProject()
    except Exception:
        pass

    print(f"Template project ready: {args.project}")
    if b:
        print(f"Bin: {args.bin}")
    if tl:
        try:
            print(f"Timeline: {tl.GetName()}")
        except Exception:
            print(f"Timeline: {args.timeline}")
    else:
        print(f"Timeline: {args.timeline} (create failed; you can create it manually)")

    print("Next: open this project in Resolve, put any clip on the template timeline, set Inspector > Stabilization > Mode = Similarity, then keep this project to duplicate for new jobs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
