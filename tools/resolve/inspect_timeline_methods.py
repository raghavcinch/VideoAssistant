from __future__ import annotations

import argparse

from _resolve_bootstrap import connect_resolve


def _find_timeline(proj, name: str):
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
        if not tl:
            continue
        try:
            if tl.GetName() == name:
                return tl
        except Exception:
            pass
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="VA_TEMPLATE")
    ap.add_argument("--timeline", default="00_TEMPLATE")
    ap.add_argument("--contains", default="fusion")
    args = ap.parse_args()

    resolve = connect_resolve()
    pm = resolve.GetProjectManager()
    proj = pm.LoadProject(args.project)
    if not proj:
        raise SystemExit(f"Project not found: {args.project}")

    tl = _find_timeline(proj, args.timeline)
    if not tl:
        raise SystemExit(f"Timeline not found: {args.timeline}")

    needle = str(args.contains).lower()
    names = sorted({n for n in dir(tl) if needle in n.lower()})
    print("Project:", proj.GetName())
    print("Timeline:", tl.GetName())
    print(f"Matches ({len(names)}):")
    for n in names:
        print(" ", n)


if __name__ == "__main__":
    main()
