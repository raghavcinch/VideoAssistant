from __future__ import annotations

import argparse

from _resolve_bootstrap import connect_resolve


def _list_projects(pm) -> list[str]:
    # Try known APIs; fall back to empty list.
    for method_name in [
        "GetProjectListInCurrentFolder",
        "GetProjectList",
    ]:
        method = getattr(pm, method_name, None)
        if callable(method):
            try:
                res = method()
            except Exception:
                continue
            if isinstance(res, dict):
                # Some APIs return dict-like; take keys.
                return sorted([str(k) for k in res.keys()])
            if isinstance(res, (list, tuple)):
                return sorted([str(x) for x in res])
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="List Resolve projects in the current project library/folder")
    ap.add_argument("--timeout", type=int, default=30, help="Seconds to wait for Resolve scripting connection")
    args = ap.parse_args()

    resolve = connect_resolve(connect_timeout_s=int(args.timeout))
    pm = resolve.GetProjectManager()
    names = _list_projects(pm)

    if not names:
        print("No project list returned by API (or none found).")
        print("Tip: ensure you are in the expected project library/folder in Resolve.")
        return 1

    for n in names:
        print(n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
