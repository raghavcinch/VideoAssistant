from __future__ import annotations

import argparse


def connect_resolve():
    from _resolve_bootstrap import connect_resolve as _cr

    return _cr()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", default="persp")
    args = ap.parse_args()
    q = str(args.q).lower()

    resolve = connect_resolve()
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")

    get_setting = getattr(proj, "GetSetting", None)
    if not callable(get_setting):
        raise SystemExit("No GetSetting")

    try:
        settings = get_setting()  # type: ignore[call-arg]
    except TypeError:
        raise SystemExit("GetSetting() with no args not supported")

    if not isinstance(settings, dict):
        raise SystemExit(f"Unexpected settings type: {type(settings)}")

    hits = []
    for k, v in settings.items():
        ks = str(k)
        vs = "" if v is None else str(v)
        if q in ks.lower() or q in vs.lower():
            hits.append((ks, vs))

    hits.sort(key=lambda x: x[0].lower())
    print(f"Query: {q!r} | hits: {len(hits)}")
    for ks, vs in hits[:200]:
        print(f"{ks}: {vs}")


if __name__ == "__main__":
    main()
