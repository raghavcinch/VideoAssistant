from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from _resolve_bootstrap import connect_resolve


def _project_exists(pm, name: str) -> bool:
    try:
        names = pm.GetProjectListInCurrentFolder() or []
        return name in names
    except Exception:
        # Fallback: load attempt
        try:
            return pm.LoadProject(name) is not None
        except Exception:
            return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Duplicate a Resolve project by exporting+importing a .drp")
    ap.add_argument("--template", default="VA_TEMPLATE", help="Existing project to clone")
    ap.add_argument("--new", required=True, help="New project name to create")
    ap.add_argument("--out", default=None, help="Where to write the temporary .drp (default: <repo>/out/resolve_templates)")
    ap.add_argument("--overwrite", action="store_true", help="Delete target project if it already exists")
    ap.add_argument("--yes", action="store_true", help="Required confirmation when using --overwrite")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    if args.overwrite and not args.yes:
        raise SystemExit("Refusing to overwrite without --yes")

    resolve = connect_resolve(connect_timeout_s=int(args.timeout))
    pm = resolve.GetProjectManager()

    # Validate template exists
    if not _project_exists(pm, args.template):
        raise SystemExit(f"Template project not found: {args.template}")

    if _project_exists(pm, args.new):
        if not args.overwrite:
            print(f"Target project already exists (not overwritten): {args.new}")
            return 0
        print(f"Deleting existing project: {args.new}")
        ok = pm.DeleteProject(args.new)
        if ok is False:
            raise SystemExit("DeleteProject reported failure")

    out_dir = Path(args.out) if args.out else (Path(__file__).resolve().parents[2] / "out" / "resolve_templates")
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d-%H%M%S")
    drp = out_dir / f"{args.template}__{ts}.drp"

    # Export template
    print(f"Exporting {args.template} -> {drp}")
    ok = pm.ExportProject(args.template, str(drp))
    if ok is False:
        raise SystemExit("ExportProject reported failure")
    if not drp.exists() or drp.stat().st_size == 0:
        raise SystemExit(f"Export did not produce a valid file: {drp}")

    # Import as new name
    print(f"Importing -> {args.new}")
    ok = pm.ImportProject(str(drp), args.new)
    if ok is False:
        raise SystemExit("ImportProject reported failure")

    try:
        pm.LoadProject(args.new)
    except Exception:
        pass

    try:
        pm.SaveProject()
    except Exception:
        pass

    print(f"Created project from template: {args.new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
