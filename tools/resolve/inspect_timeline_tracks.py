from __future__ import annotations


def connect_resolve():
    from _resolve_bootstrap import connect_resolve as _cr

    return _cr()


def main() -> None:
    resolve = connect_resolve()
    proj = resolve.GetProjectManager().GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")

    name = "CROCKERY_SELECTS_CINE"

    tl = None
    try:
        get_by_name = getattr(proj, "GetTimelineByName", None)
        if callable(get_by_name):
            tl = get_by_name(name)
    except Exception:
        tl = None

    if not tl:
        # Scan by index
        try:
            n = int(proj.GetTimelineCount() or 0)
        except Exception:
            n = 0
        for i in range(1, n + 1):
            t = proj.GetTimelineByIndex(i)
            if t and t.GetName() == name:
                tl = t
                break

    if not tl:
        raise SystemExit(f"Timeline not found: {name}")

    print("Timeline:", tl.GetName())

    for track_type in ["video", "audio"]:
        try:
            tc = int(tl.GetTrackCount(track_type) or 0)
        except Exception:
            tc = 0
        print(f"{track_type} tracks:", tc)
        for idx in range(1, tc + 1):
            try:
                items = tl.GetItemListInTrack(track_type, idx) or []
            except Exception:
                items = []
            print(f"  {track_type.upper()}{idx}: {len(items)}")


if __name__ == "__main__":
    main()
