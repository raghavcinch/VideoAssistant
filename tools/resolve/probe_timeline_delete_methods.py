from __future__ import annotations


def connect_resolve():
    from _resolve_bootstrap import connect_resolve as _cr

    return _cr()


def main() -> None:
    resolve = connect_resolve()
    proj = resolve.GetProjectManager().GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")
    mp = proj.GetMediaPool()

    candidates = [
        ("Project.DeleteTimeline", getattr(proj, "DeleteTimeline", None)),
        ("Project.DeleteTimelines", getattr(proj, "DeleteTimelines", None)),
        ("MediaPool.DeleteTimeline", getattr(mp, "DeleteTimeline", None)),
        ("MediaPool.DeleteTimelines", getattr(mp, "DeleteTimelines", None)),
        ("MediaPool.RemoveTimeline", getattr(mp, "RemoveTimeline", None)),
        ("MediaPool.RemoveTimelines", getattr(mp, "RemoveTimelines", None)),
    ]

    print("Available delete-like methods:")
    for name, fn in candidates:
        print(" ", name, "callable=" + str(callable(fn)))


if __name__ == "__main__":
    main()
