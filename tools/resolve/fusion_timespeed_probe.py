from __future__ import annotations


def _connect_resolve():
    from _resolve_bootstrap import connect_resolve as _cr

    return _cr()


def main() -> None:
    resolve = _connect_resolve()
    proj = resolve.GetProjectManager().GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")
    tl = proj.GetCurrentTimeline()
    if not tl:
        raise SystemExit("No current timeline")

    ti = (tl.GetItemListInTrack("video", 1) or [None])[0]
    if not ti:
        raise SystemExit("No V1 items")

    # Create a fresh Fusion comp on this item
    comp = ti.AddFusionComp()

    tools = comp.GetToolList(False)
    media_in = None
    media_out = None
    for _k, t in tools.items():
        attrs = t.GetAttrs()
        if attrs.get("TOOLS_RegID") == "MediaIn":
            media_in = t
        elif attrs.get("TOOLS_RegID") == "MediaOut":
            media_out = t

    if not media_in or not media_out:
        raise SystemExit("Could not find MediaIn/MediaOut")

    print("Before wiring:")
    print("  MediaOut.Input:", getattr(media_out, "Input", None))

    # Add TimeSpeed
    ts = comp.AddTool("TimeSpeed")
    print("Created TimeSpeed:", ts)

    # Dump inputs for TimeSpeed
    try:
        inps = ts.GetInputList()
        print("TimeSpeed inputs:")
        for name, inp in inps.items():
            try:
                attrs = inp.GetAttrs()
            except Exception:
                attrs = {}
            print(" ", name, attrs.get("INPS_ID"), attrs.get("INPS_Name"), attrs.get("INPS_DataType"))
    except Exception as e:
        print("GetInputList failed:", e)

    # Try to connect MediaIn -> TimeSpeed -> MediaOut
    # (Fusion scripting typically uses tool.Input = otherTool.Output)
    try:
        ts.Input = media_in.Output
        media_out.Input = ts.Output
        print("Connected via .Input/.Output")
    except Exception as e:
        print("Connect via .Input/.Output failed:", e)

    # Try setting Speed and keyframes
    try:
        ts.Speed = 1.0
        print("Set Speed=1.0")
    except Exception as e:
        print("Setting Speed failed:", e)

    # Try keyframe-like indexing
    for frame, speed in [(0, 0.5), (10, 2.0), (20, 1.0)]:
        try:
            ts.Speed[frame] = speed  # type: ignore[index]
            print(f"Keyframed Speed[{frame}]={speed}")
        except Exception as e:
            print(f"Keyframe Speed[{frame}] failed:", e)


if __name__ == "__main__":
    main()
