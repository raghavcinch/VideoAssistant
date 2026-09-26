from __future__ import annotations

import time
from dataclasses import dataclass

from videoassistant.agents.base import AgentContext, AgentResult, ctx_to_dict, write_json
from videoassistant.agents.export_agent import ExportAgent
from videoassistant.agents.index_agent import IndexAgent
from videoassistant.agents.pretrim_export_agent import PretrimExportAgent
from videoassistant.agents.stabilize_agent import StabilizeAgent
from videoassistant.agents.selects_agent import SelectsAgent
from videoassistant.agents.shakiness_agent import ShakinessAgent
from videoassistant.agents.resolve_import_agent import ResolveImportAgent
from videoassistant.agents.correction_agent import CorrectionAgent


@dataclass
class VideoEditorAgent:
    """Orchestrates the end-to-end pipeline for a single property folder."""

    name: str = "video_editor"

    def run(self, ctx: AgentContext) -> AgentResult:
        start = time.time()
        steps = [IndexAgent()]
        if ctx.stabilize_first:
            steps.append(StabilizeAgent())
        steps.extend([ShakinessAgent(), SelectsAgent()])
        if ctx.export_pretrim:
            steps.append(PretrimExportAgent())
        steps.append(ExportAgent())
        if ctx.run_resolve_import:
            steps.append(ResolveImportAgent())
        steps.append(CorrectionAgent())
        run_log: list[dict] = []
        warnings: list[str] = []

        for agent in steps:
            t0 = time.time()
            res = agent.run(ctx)
            dt = time.time() - t0
            run_log.append(
                {
                    "agent": res.name,
                    "ok": res.ok,
                    "summary": res.summary,
                    "warnings": res.warnings,
                    "artifacts": res.artifacts,
                    "seconds": round(dt, 3),
                }
            )
            warnings.extend(res.warnings)
            if not res.ok:
                # Persist partial log
                write_json(ctx.va_dir / "run_log.json", {"ctx": ctx_to_dict(ctx), "steps": run_log})
                return AgentResult(
                    name=self.name,
                    ok=False,
                    summary=f"Failed at agent '{res.name}': {res.summary}",
                    artifacts={"run_log": str(ctx.va_dir / "run_log.json")},
                    warnings=warnings,
                )

        total_s = time.time() - start
        write_json(
            ctx.va_dir / "run_log.json",
            {"ctx": ctx_to_dict(ctx), "steps": run_log, "total_seconds": round(total_s, 3)},
        )

        return AgentResult(
            name=self.name,
            ok=True,
            summary=f"Pipeline complete in {total_s:.1f}s",
            artifacts={
                "run_log": str(ctx.va_dir / "run_log.json"),
                "selects_csv": str(ctx.out_dir / "selects.csv"),
                "resolve_script": str(ctx.out_dir / "resolve_import_selects.py"),
            },
            warnings=warnings,
        )
