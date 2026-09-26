from __future__ import annotations

from _resolve_bootstrap import connect_resolve


def main() -> None:
    resolve = connect_resolve()
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")

    tl = proj.GetCurrentTimeline()
    if not tl:
        raise SystemExit("No current timeline")

    items = tl.GetItemListInTrack("video", 1) or []
    if not items:
        raise SystemExit("No items on V1")

    ti = items[0]
    print("Project:", proj.GetName())
    print("Timeline:", tl.GetName())
    print("Item:", ti.GetName())

    for arg in ["Banana", "", None, 999, -1, "Similarity", "Perspective", "Translation", 0, 1, 2, "0", "1", "2"]:
        try:
            ok = ti.Stabilize(arg)  # type: ignore[arg-type]
        except Exception as e:
            ok = f"EXC: {e}"
        print(f"Stabilize({arg!r}) -> {ok}")


if __name__ == "__main__":
    main()
