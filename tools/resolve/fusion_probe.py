from __future__ import annotations

from _resolve_bootstrap import connect_resolve


def main() -> None:
    resolve = connect_resolve(connect_timeout_s=30)

    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    if not proj:
        raise SystemExit("No current project.")

    tl = proj.GetCurrentTimeline()
    if not tl:
        raise SystemExit("No current timeline.")

    print("Project:", proj.GetName())
    print("Timeline:", tl.GetName())

    items = tl.GetItemListInTrack("video", 1) or []
    print("V1 items:", len(items))
    if not items:
        return

    ti = items[0]
    print("First item:", ti.GetName())
    print("Fusion comp count before:", ti.GetFusionCompCount())

    comp = ti.AddFusionComp()
    print("AddFusionComp returned:", comp)
    print("Fusion comp count after:", ti.GetFusionCompCount())

    try:
        tools = comp.GetToolList(False)
        if hasattr(tools, "items"):
            items = list(tools.items())
        else:
            items = [(None, t) for t in list(tools)]  # type: ignore[arg-type]

        print("Tools:")
        for key, tool in items:
            try:
                attrs = tool.GetAttrs()
            except Exception:
                attrs = {}
            name = attrs.get("TOOLS_Name") or getattr(tool, "Name", None) or "?"
            tid = attrs.get("TOOLS_RegID") or attrs.get("TOOLS_ID") or "?"
            print(f"  - key={key!r} name={name!r} id={tid!r}")
    except Exception as e:
        print("GetToolList failed:", e)


if __name__ == "__main__":
    main()
