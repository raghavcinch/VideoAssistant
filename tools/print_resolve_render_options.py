from __future__ import annotations

import os
import sys


def _ensure_modules_on_syspath() -> None:
    candidates = [
        os.environ.get("RESOLVE_SCRIPTING_MODULES"),
        os.environ.get("RESOLVE_SCRIPT_API"),
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
        r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
    ]
    for p in candidates:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)


def main() -> int:
    _ensure_modules_on_syspath()
    import DaVinciResolveScript as dvr  # type: ignore

    resolve = dvr.scriptapp("Resolve")
    if not resolve:
        print("Resolve not reachable (is it running?)")
        return 2

    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    if not proj:
        print("No current project loaded.")
        return 3

    formats = proj.GetRenderFormats() or {}
    print("Render formats (format_key -> ext):")
    for k, v in formats.items():
        print(f"  {k} -> {v}")

    for fmt in formats.keys():
        codecs = proj.GetRenderCodecs(fmt) or {}
        print(f"\n{fmt} codecs ({len(codecs)}):")
        for desc, name in codecs.items():
            print(f"  {desc} => {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
