from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def add_resolve_modules_to_syspath() -> None:
    """Make external Python able to `import DaVinciResolveScript` on Windows."""

    candidates: list[str] = []

    for env_key in ["RESOLVE_SCRIPTING_MODULES", "RESOLVE_SCRIPT_API"]:
        env = os.environ.get(env_key)
        if env:
            candidates.append(env)

    candidates.extend(
        [
            r"C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting\\Modules",
            r"C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting\\Modules",
        ]
    )

    for p in candidates:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)


def connect_resolve(connect_timeout_s: int = 30):
    """Connect to Resolve scripting API with a short retry window."""

    add_resolve_modules_to_syspath()

    try:
        import DaVinciResolveScript as dvr  # type: ignore
    except Exception as e:
        raise SystemExit(
            "Cannot import DaVinciResolveScript.\n"
            "Fix by ensuring Resolve scripting Modules path is on sys.path, or set RESOLVE_SCRIPTING_MODULES.\n"
            f"Error: {e}"
        )

    deadline = time.time() + max(1, int(connect_timeout_s))
    last = None
    while time.time() < deadline:
        try:
            resolve = dvr.scriptapp("Resolve")
        except Exception as e:
            last = e
            resolve = None
        if resolve is not None:
            return resolve
        time.sleep(1)

    if last:
        raise SystemExit(f"Resolve scripting app not available: {last}")

    raise SystemExit(
        "Resolve scripting app not available.\n"
        "Start Resolve first (same user/admin level as this terminal) and enable external scripting in Preferences."  # noqa: E501
    )


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
