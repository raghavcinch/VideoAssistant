from __future__ import annotations

from dataclasses import dataclass

from videoassistant.agents.base import AgentContext, AgentResult, write_json
from videoassistant.selects import build_selects


@dataclass
class SelectsAgent:
    name: str = "selects"

    def run(self, ctx: AgentContext) -> AgentResult:
        selects = build_selects(
            ctx.va_dir,
            min_seg_seconds=ctx.min_seg_seconds,
            edge_ignore_seconds=ctx.edge_ignore_seconds,
            max_segs_per_clip=ctx.max_segs_per_clip,
        )
        out_path = ctx.va_dir / "selects.json"
        write_json(out_path, selects)
        ctx.artifacts["selects"] = out_path

        # Basic warning if many clips have no segments.
        missing = 0
        total = 0
        for _rel, info in selects.get("clips", {}).items():
            if info.get("error"):
                continue
            total += 1
            if not info.get("segments"):
                missing += 1
        warnings = []
        if total and missing / total > 0.5:
            warnings.append("More than 50% of clips produced zero stable segments; consider lowering min_seg_seconds or edge_ignore_seconds.")

        return AgentResult(
            name=self.name,
            ok=True,
            summary=f"Generated selects for {len(selects.get('clips', {}))} clips",
            artifacts={"selects_json": str(out_path)},
            warnings=warnings,
        )
