from __future__ import annotations

import csv
from pathlib import Path


def write_selects_csv(path: Path, index: dict, selects: dict) -> None:
    root = index.get("root")
    clips_by_rel = {c["rel"]: c for c in index["clips"]}

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["room", "group", "rel", "abs_path", "t_in", "t_out", "score", "root"])
        for rel, info in selects["clips"].items():
            if info.get("error"):
                continue
            clip = clips_by_rel.get(rel, {})
            group = info.get("group") or clip.get("group")
            room = info.get("room") or clip.get("room") or "unknown"
            for seg in info.get("segments", []):
                w.writerow([
                    room,
                    group,
                    rel,
                    clip.get("path") or info.get("path"),
                    f"{seg['t_in']:.3f}",
                    f"{seg['t_out']:.3f}",
                    f"{seg['score']:.6f}",
                    root,
                ])
