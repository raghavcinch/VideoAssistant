from __future__ import annotations

import json
from dataclasses import dataclass

from videoassistant.agents.base import AgentContext, AgentResult, write_json
from videoassistant.indexing import index_media
from videoassistant.rooms import load_room_rules


@dataclass
class IndexAgent:
    name: str = "index"

    def run(self, ctx: AgentContext) -> AgentResult:
        out_path = ctx.va_dir / "index.json"

        # If the user isn't re-stabilizing, don't clobber a stabilized index.
        # This keeps reruns fast and ensures downstream analysis uses stabilized renders.
        if not ctx.stabilize_first and out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
                if existing.get("stabilized") is True and existing.get("clips"):
                    ctx.artifacts["index"] = out_path
                    return AgentResult(
                        name=self.name,
                        ok=True,
                        summary=f"Reused existing stabilized index ({len(existing.get('clips', []))} clips)",
                        artifacts={"index_json": str(out_path)},
                    )
            except Exception:
                pass

        room_rules = None
        if ctx.room_rules_path and ctx.room_rules_path.exists():
            room_rules = load_room_rules(ctx.room_rules_path)

        idx = index_media(ctx.root, room_rules=room_rules)
        write_json(out_path, idx)

        ctx.artifacts["index"] = out_path
        return AgentResult(
            name=self.name,
            ok=True,
            summary=f"Indexed {len(idx.get('clips', []))} clips",
            artifacts={"index_json": str(out_path)},
        )
