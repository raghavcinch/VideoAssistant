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
        # Fall back to scan by index.
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
    ap.add_argument("--timeline", default=None, help="Timeline name (default: current)")
    ap.add_argument("--track", type=int, default=1, help="Video track index")
    ap.add_argument("--index", type=int, default=0, help="Item index in track (0-based)")
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

    idx = int(args.index)
    if idx < 0 or idx >= len(items):
        raise SystemExit(f"Index out of range: {idx} (items={len(items)})")

    ti = items[idx]
    print("Project:", proj.GetName())
    print("Timeline:", tl.GetName())
    try:
        print("Item name:", ti.GetName())
    except Exception:
        pass

    get_prop = getattr(ti, "GetProperty", None)
    if not callable(get_prop):
        raise SystemExit("TimelineItem has no GetProperty()")

    try:
        props = get_prop()  # type: ignore[call-arg]
    except TypeError:
        # Some APIs require a key. We'll brute a small set.
        props = {}

    if isinstance(props, dict) and props:
        keys = sorted([str(k) for k in props.keys()])
        print(f"Property keys: {len(keys)}")
        for k in keys:
            if "stabil" in k.lower() or "camera" in k.lower() or "gyro" in k.lower() or "persp" in k.lower():
                print(f"  {k}: {props.get(k)}")
        return

    # Fallback: try common suspected keys.
    candidate_keys = [
        "StabilizationMode",
        "Stabilization",
        "Stabilize",
        "StabilizeMode",
        "StabilizationMethod",
        "StabilizationStrength",
        "StabilizationCameraLock",
        "StabilizationCroppingRatio",
        "StabilizationSmooth",
        "StabilizationZoom",
    ]
    for k in candidate_keys:
        try:
            v = get_prop(k)
        except Exception:
            v = None
        if v is not None:
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()
