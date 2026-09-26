from __future__ import annotations

from pathlib import Path

from videoassistant.rooms import DEFAULT_ROOM_RULES, RoomRuleSet, infer_room_from_path

VIDEO_EXTS = {".mov", ".mp4", ".m4v"}


def index_media(root: Path, room_rules: RoomRuleSet | None = None) -> dict:
    root = root.resolve()
    rules = room_rules or DEFAULT_ROOM_RULES
    clips: list[dict] = []

    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in VIDEO_EXTS:
            continue
        if ".va" in p.parts:
            continue
        try:
            st = p.stat()
            mtime = float(st.st_mtime)
            size = int(st.st_size)
        except Exception:
            mtime = None
            size = None
        clips.append(
            {
                "path": str(p),
                "rel": str(p.relative_to(root)),
                "name": p.name,
                "folder": str(p.parent),
                "group": str(p.parent.relative_to(root)),
                "room": infer_room_from_path(str(p.relative_to(root)), p.name, rules=rules),
                "mtime": mtime,
                "size": size,
            }
        )

    return {"root": str(root), "clips": clips}
