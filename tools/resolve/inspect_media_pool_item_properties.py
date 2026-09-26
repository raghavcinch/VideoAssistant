from __future__ import annotations

import argparse


def connect_resolve():
    from _resolve_bootstrap import connect_resolve as _cr

    return _cr()


def _find_timeline(proj, name: str | None):
    if name:
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
            if tl and getattr(tl, "GetName", None) and tl.GetName() == name:
                return tl

    get_current = getattr(proj, "GetCurrentTimeline", None)
    if callable(get_current):
        try:
            return get_current()
        except Exception:
            return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", default=None)
    ap.add_argument("--track", type=int, default=1)
    ap.add_argument("--index", type=int, default=0)
    args = ap.parse_args()

    resolve = connect_resolve()
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")

    tl = _find_timeline(proj, args.timeline)
    if not tl:
        raise SystemExit("No timeline")

    items = tl.GetItemListInTrack("video", int(args.track)) or []
    if not items:
        raise SystemExit("No items")

    ti = items[int(args.index)]
    mpi = None
    try:
        mpi = ti.GetMediaPoolItem()
    except Exception as e:
        raise SystemExit(f"GetMediaPoolItem failed: {e}")
    if not mpi:
        raise SystemExit("No MediaPoolItem")

    print("Project:", proj.GetName())
    print("Timeline:", tl.GetName())
    print("Item:", ti.GetName())

    # Inspect clip properties
    get_props = getattr(mpi, "GetClipProperty", None)
    if not callable(get_props):
        raise SystemExit("MediaPoolItem has no GetClipProperty")

    props = get_props()  # dict
    if not isinstance(props, dict):
        raise SystemExit(f"Unexpected GetClipProperty type: {type(props)}")

    keys = sorted([str(k) for k in props.keys()])
    print(f"ClipProperty keys: {len(keys)}")
    for k in keys:
        kl = k.lower()
        if "stabil" in kl or "gyro" in kl or "camera" in kl or "persp" in kl:
            print(f"  {k}: {props.get(k)}")


if __name__ == "__main__":
    main()
