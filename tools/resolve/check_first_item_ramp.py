from __future__ import annotations


def connect_resolve():
    from _resolve_bootstrap import connect_resolve as _cr

    return _cr()


def main() -> None:
    resolve = connect_resolve()
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")

    tl = None
    get_by_name = getattr(proj, "GetTimelineByName", None)
    if callable(get_by_name):
        try:
            tl = get_by_name("CROCKERY_SELECTS_CINE")
        except Exception:
            tl = None

    if not tl:
        get_current = getattr(proj, "GetCurrentTimeline", None)
        if callable(get_current):
            try:
                tl = get_current()
            except Exception:
                tl = None

    # For debugging: list timelines we can see.
    timeline_names = []
    get_count = getattr(proj, "GetTimelineCount", None)
    get_idx = getattr(proj, "GetTimelineByIndex", None)
    if callable(get_count) and callable(get_idx):
        try:
            n = int(get_count() or 0)
        except Exception:
            n = 0
        for i in range(1, n + 1):
            try:
                cand = get_idx(i)
                if cand and getattr(cand, "GetName", None):
                    timeline_names.append(cand.GetName())
            except Exception:
                pass
    if timeline_names:
        print("Timelines:", timeline_names)

    # Prefer checking crockery timeline when present.
    if "CROCKERY_SELECTS_CINE" in timeline_names:
        for i, name in enumerate(timeline_names, 1):
            if name == "CROCKERY_SELECTS_CINE":
                try:
                    tl = get_idx(i)
                except Exception:
                    tl = None
                break

    if not tl:
        # Fallback: scan by index for crockery
        get_count = getattr(proj, "GetTimelineCount", None)
        get_idx = getattr(proj, "GetTimelineByIndex", None)
        if callable(get_count) and callable(get_idx):
            try:
                n = int(get_count() or 0)
            except Exception:
                n = 0
            for i in range(1, n + 1):
                try:
                    cand = get_idx(i)
                    if cand and getattr(cand, "GetName", None) and cand.GetName() == "CROCKERY_SELECTS_CINE":
                        tl = cand
                        break
                except Exception:
                    pass
    if not tl:
        raise SystemExit("No timeline")

    items = tl.GetItemListInTrack("video", 1) or []
    if not items:
        raise SystemExit("No V1 items")

    print("V1 item count:", len(items))
    # Scan for clips that already have VA_RAMP.
    ramped = []
    for idx, it in enumerate(items):
        try:
            names = it.GetFusionCompNameList() or []
        except Exception:
            names = []
        if "VA_RAMP" in names:
            ramped.append(idx)
    print("Items with VA_RAMP:", ramped)

    ti = items[0]
    print("Project:", proj.GetName())
    print("Timeline:", tl.GetName())
    print("First item:", ti.GetName())

    try:
        rot = ti.GetProperty('RotationAngle')
    except Exception:
        rot = None
    print("RotationAngle:", rot)

    try:
        markers = ti.GetMarkers() or {}
    except Exception:
        markers = {}
    if markers:
        # Show a compact view.
        names = [(int(k), (v or {}).get('name'), (v or {}).get('note')) for k, v in markers.items()]
        names = sorted(names, key=lambda x: x[0])
        print("Markers:", names[:10])
    else:
        print("Markers: []")

    try:
        names = ti.GetFusionCompNameList() or []
    except Exception:
        names = []
    print("Fusion comps:", names)

    # Try to locate VA_RAMP and confirm TimeSpeed tool exists.
    if "VA_RAMP" not in names:
        print("VA_RAMP: MISSING")
        try:
            print("Attempting ti.AddFusionComp() for diagnostics...")
            comp = ti.AddFusionComp()
            print("AddFusionComp ok:", comp)
            try:
                print("Fusion comps after:", ti.GetFusionCompNameList() or [])
            except Exception as e:
                print("GetFusionCompNameList failed:", e)
        except Exception as e:
            print("AddFusionComp failed:", e)
        return

    comp = ti.GetFusionCompByName("VA_RAMP")
    tools = comp.GetToolList(False)
    has_ts = False
    for _k, t in tools.items():
        try:
            reg = (t.GetAttrs() or {}).get("TOOLS_RegID")
        except Exception:
            reg = None
        if reg == "TimeSpeed":
            has_ts = True
            # Print a couple of speed keyframes if any.
            try:
                speed_inp = t.Speed
                # Probe a handful of frames.
                samples = []
                for f in [0, 5, 10, 15, 20, 30, 60]:
                    try:
                        samples.append((f, float(speed_inp[f])))  # type: ignore[index]
                    except Exception:
                        pass
                print("TimeSpeed Speed samples:", samples)
            except Exception:
                pass
            break

    print("TimeSpeed present:", has_ts)


if __name__ == "__main__":
    main()
