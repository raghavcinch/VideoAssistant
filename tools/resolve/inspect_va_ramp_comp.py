from __future__ import annotations


def _connect_resolve():
    from _resolve_bootstrap import connect_resolve as _cr

    return _cr()


def _first(items):
    return (items or [None])[0]


def main() -> None:
    resolve = _connect_resolve()
    proj = resolve.GetProjectManager().GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")
    tl = proj.GetCurrentTimeline()
    if not tl:
        raise SystemExit("No current timeline")

    # Find first V1 item that has VA_RAMP comp.
    v1 = tl.GetItemListInTrack("video", 1) or []
    target = None
    for it in v1:
        try:
            names = it.GetFusionCompNameList() or []
        except Exception:
            names = []
        if "VA_RAMP" in names:
            target = it
            break
    if not target:
        raise SystemExit("No V1 item contains VA_RAMP in current timeline")

    comp = target.GetFusionCompByName("VA_RAMP")
    if not comp:
        raise SystemExit("GetFusionCompByName('VA_RAMP') returned None")

    tools = comp.GetToolList(False) or {}
    ts = None
    for _k, t in (tools.items() if hasattr(tools, "items") else []):
        try:
            reg = (t.GetAttrs() or {}).get("TOOLS_RegID")
        except Exception:
            reg = None
        if reg == "TimeSpeed":
            ts = t
            break

    if not ts:
        # Dump what we do have.
        regs = []
        for _k, t in (tools.items() if hasattr(tools, "items") else []):
            try:
                regs.append((t.GetAttrs() or {}).get("TOOLS_RegID"))
            except Exception:
                pass
        raise SystemExit(f"No TimeSpeed tool found. Tools: {regs}")

    print("Timeline:", tl.GetName())
    try:
        print("Item:", target.GetName())
    except Exception:
        pass

    # List TimeSpeed inputs and current values.
    try:
        inps = ts.GetInputList() or {}
    except Exception as e:
        raise SystemExit(f"TimeSpeed.GetInputList failed: {e}")

    print("TimeSpeed inputs:")
    for name, inp in (inps.items() if hasattr(inps, "items") else []):
        try:
            attrs = inp.GetAttrs() or {}
        except Exception:
            attrs = {}
        inps_id = attrs.get("INPS_ID")
        dtype = attrs.get("INPS_DataType")
        inps_name = attrs.get("INPS_Name")
        val = None
        # In Fusion scripting, tool inputs are typically accessible by their INPS_ID string.
        if isinstance(inps_id, str) and inps_id:
            try:
                val = ts[inps_id]
            except Exception:
                val = None
        print(
            f"  {str(name):20s} id={str(inps_id):10s} type={str(dtype):10s} name={str(inps_name):20s} val={val!r}"
        )

    # Sample Speed values.
    try:
        speed = ts.Speed
        samples = []
        for f in [0, 5, 10, 15, 20, 30, 60]:
            try:
                samples.append((f, float(speed[f])))
            except Exception:
                try:
                    samples.append((f, float(speed)))
                except Exception:
                    samples.append((f, None))
        print("Speed samples:", samples)
    except Exception as e:
        print("Speed sampling failed:", e)


if __name__ == "__main__":
    main()
