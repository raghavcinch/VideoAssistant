from __future__ import annotations

import argparse

from _resolve_bootstrap import connect_resolve


def _delete_project(pm, project_name: str) -> bool:
    # Try common deletion APIs.
    for method_name, arg in [
        ("DeleteProject", project_name),
        ("DeleteProjects", [project_name]),
        ("DeleteProjects", project_name),
    ]:
        method = getattr(pm, method_name, None)
        if not callable(method):
            continue
        try:
            res = method(arg)
        except TypeError:
            continue
        except Exception:
            continue
        if res is None:
            # Some APIs return None even when they succeed.
            return True
        try:
            return bool(res)
        except Exception:
            return True
    raise SystemExit(
        "Project deletion API not found on ProjectManager. "
        "Run tools/resolve/probe_* scripts or update this script for your Resolve version."
    )


def _project_exists(pm, project_name: str) -> bool:
    try:
        proj = pm.LoadProject(project_name)
        return proj is not None
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Delete (optional) and recreate a Resolve project")
    ap.add_argument("--project", required=True, help="Resolve project name")
    ap.add_argument("--delete", action="store_true", help="Delete the project first if it exists")
    ap.add_argument("--yes", action="store_true", help="Required confirmation when using --delete")
    ap.add_argument("--timeout", type=int, default=30, help="Seconds to wait for Resolve scripting connection")
    args = ap.parse_args()

    if args.delete and not args.yes:
        raise SystemExit("Refusing to delete without --yes")

    resolve = connect_resolve(connect_timeout_s=int(args.timeout))
    pm = resolve.GetProjectManager()

    exists = _project_exists(pm, args.project)
    if exists and args.delete:
        print(f"Deleting project: {args.project}")
        ok = _delete_project(pm, args.project)
        if not ok:
            raise SystemExit("DeleteProject reported failure")
        exists = False

    if exists:
        print(f"Project already exists (not deleted): {args.project}")
        return 0

    proj = pm.CreateProject(args.project)
    if not proj:
        raise SystemExit(f"Failed to create project: {args.project}")

    # Load it to make it current.
    try:
        pm.LoadProject(args.project)
    except Exception:
        pass

    print(f"Created fresh project: {args.project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
