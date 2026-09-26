from __future__ import annotations

import subprocess
from dataclasses import dataclass
import sys

from videoassistant.agents.base import AgentContext, AgentResult


@dataclass
class ResolveImportAgent:
    name: str = "resolve_import"

    def run(self, ctx: AgentContext) -> AgentResult:
        if not ctx.run_resolve_import:
            return AgentResult(name=self.name, ok=True, summary="Skipped Resolve import")

        script_path = ctx.out_dir / "resolve_import_selects.py"
        if not script_path.exists():
            return AgentResult(name=self.name, ok=False, summary=f"Missing Resolve script: {script_path}")

        proc = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
        if proc.returncode != 0:
            return AgentResult(
                name=self.name,
                ok=False,
                summary=f"Resolve import script failed (exit={proc.returncode}).\n{proc.stderr.strip()}",
                artifacts={"resolve_script": str(script_path)},
            )

        warnings = []
        if proc.stderr.strip():
            warnings.append(proc.stderr.strip())
        if proc.stdout.strip():
            warnings.append(proc.stdout.strip())

        return AgentResult(
            name=self.name,
            ok=True,
            summary="Imported selected segments into Resolve timelines",
            artifacts={"resolve_script": str(script_path), "stdout": proc.stdout.strip()},
            warnings=warnings,
        )
