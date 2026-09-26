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
    ap.add_argument("--mode", default="Similarity", choices=["Perspective", "Similarity", "Translation"])
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
    print("Project:", proj.GetName())
    print("Timeline:", tl.GetName())
    print("Item:", ti.GetName())

    set_prop = getattr(ti, "SetProperty", None)
    if not callable(set_prop):
        raise SystemExit("TimelineItem has no SetProperty")

    candidates = [
        ("StabilizationMode", args.mode),
        ("StabilizeMode", args.mode),
        ("StabilizationMode", {"Perspective": 0, "Similarity": 1, "Translation": 2}[args.mode]),
        ("StabilizeMode", {"Perspective": 0, "Similarity": 1, "Translation": 2}[args.mode]),
        ("Stabilization", args.mode),
    ]

    for k, v in candidates:
        try:
            ok = set_prop(k, v)
        except Exception as e:
            ok = f"EXC: {e}"
        print(f"SetProperty({k!r}, {v!r}) -> {ok}")

    # Trigger stabilize to see if it errors (can't easily read back which mode used).
    stab = getattr(ti, "Stabilize", None)
    if callable(stab):
        try:
            ok = stab()
        except Exception as e:
            ok = f"EXC: {e}"
        print("Stabilize() ->", ok)

        # Probe whether Stabilize() accepts mode/strength parameters (undocumented in some versions).
        for arg in [args.mode, {"Perspective": 0, "Similarity": 1, "Translation": 2}[args.mode], "1", 1]:
            try:
                ok2 = stab(arg)
            except Exception as e:
                ok2 = f"EXC: {e}"
            print(f"Stabilize({arg!r}) -> {ok2}")


if __name__ == "__main__":
    main()
