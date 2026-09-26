from __future__ import annotations

from dataclasses import dataclass

from videoassistant.agents.base import AgentContext, AgentResult
from videoassistant.motion import analyze_shakiness


@dataclass
class ShakinessAgent:
    name: str = "shakiness"

    def run(self, ctx: AgentContext) -> AgentResult:
        analyze_shakiness(ctx.root, ctx.va_dir, sample_fps=ctx.sample_fps, scale_width=ctx.scale_width)
        out_path = ctx.va_dir / "shakiness.json"
        ctx.artifacts["shakiness"] = out_path
        return AgentResult(
            name=self.name,
            ok=True,
            summary=f"Computed shakiness (sample_fps={ctx.sample_fps}, scale_width={ctx.scale_width})",
            artifacts={"shakiness_json": str(out_path)},
        )
