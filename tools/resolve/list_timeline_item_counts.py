from __future__ import annotations

from _resolve_bootstrap import connect_resolve


def main() -> None:
    resolve = connect_resolve()
    proj = resolve.GetProjectManager().GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")

    names = []
    try:
        n = int(proj.GetTimelineCount() or 0)
    except Exception:
        n = 0
    for i in range(1, n + 1):
        tl = proj.GetTimelineByIndex(i)
        if not tl:
            continue
        try:
            name = tl.GetName()
        except Exception:
            name = f"<timeline {i}>"
        try:
            v1 = tl.GetItemListInTrack("video", 1) or []
            a1 = tl.GetItemListInTrack("audio", 1) or []
        except Exception:
            v1 = []
            a1 = []
        names.append((name, len(v1), len(a1)))

    names.sort(key=lambda t: t[0])
    for name, v, a in names:
        if any(tag in name for tag in ["_SELECTS", "_SELECTS_CINE"]):
            print(f"{name}: V1={v} A1={a}")


if __name__ == "__main__":
    main()
