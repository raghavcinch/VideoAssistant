from __future__ import annotations

from dataclasses import dataclass

from videoassistant.agents.base import AgentContext, AgentResult, read_json
from videoassistant.exports.csv_export import write_selects_csv
from videoassistant.exports.resolve_export import write_resolve_script


@dataclass
class ExportAgent:
    name: str = "export"

    def run(self, ctx: AgentContext) -> AgentResult:
        index_path = ctx.va_dir / "index.json"
        selects_path = ctx.va_dir / "selects.json"
        if not index_path.exists() or not selects_path.exists():
            return AgentResult(
                name=self.name,
                ok=False,
                summary="Missing index/selects; run earlier agents first",
            )

        index = read_json(index_path)
        selects = read_json(selects_path)

        ctx.out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = ctx.out_dir / "selects.csv"
        resolve_path = ctx.out_dir / "resolve_import_selects.py"

        write_selects_csv(csv_path, index, selects)
        write_resolve_script(resolve_path, index, selects, project_name=ctx.project_name)

        ctx.artifacts["csv"] = csv_path
        ctx.artifacts["resolve_script"] = resolve_path

        return AgentResult(
            name=self.name,
            ok=True,
            summary="Exported selects.csv + Resolve import script",
            artifacts={"selects_csv": str(csv_path), "resolve_script": str(resolve_path)},
        )
