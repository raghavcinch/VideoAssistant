from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RoomRuleSet:
    # Map canonical room -> list of keyword patterns
    keywords: dict[str, list[str]]


DEFAULT_ROOM_RULES = RoomRuleSet(
    keywords={
        "living_room": [
            r"living", r"lounge", r"family[_ -]?room", r"great[_ -]?room",
        ],
        "kitchen": [r"kitchen", r"pantry"],
        "dining": [r"dining"],
        "bedroom": [r"bed(room)?\b", r"master", r"guest"],
        "bathroom": [r"bath(room)?\b", r"toilet", r"wash", r"powder"],
        "balcony": [r"balcony", r"terrace", r"deck"],
        "utility": [r"utility", r"laundry"],
        "corridor": [r"hall(way)?", r"corridor", r"passage"],
        "staircase": [r"stairs?", r"staircase"],
        "exterior": [r"exterior", r"outside", r"front", r"back", r"garden", r"yard", r"parking", r"drive(way)?"],
        "amenities": [r"gym", r"pool", r"club", r"lobby", r"elevator", r"lift"],
        "neighborhood": [r"neighbou?r", r"street", r"road", r"view", r"nearby"],
    }
)


def _norm(s: str) -> str:
    s = s.lower()
    s = s.replace("-", " ").replace("_", " ")
    return s


def _canon_room_from_folder_name(folder: str) -> str:
    # Normalize folder names like "01 Living Room" -> "living_room"
    s = folder.strip().lower()
    s = re.sub(r"^[0-9]+\s*[\-_. ]*", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "unknown"


def infer_room_from_path(rel_path: str, filename: str, rules: RoomRuleSet = DEFAULT_ROOM_RULES) -> str:
    """Infer a canonical room name from a path/filename using keyword rules.

    Priority: filename tokens > folder tokens.
    Returns 'unknown' if no match.
    """

    rel = _norm(rel_path)
    name = _norm(filename)

    # Token sources
    candidates = [name, rel]

    for canon, patterns in rules.keywords.items():
        for pat in patterns:
            rx = re.compile(pat, re.IGNORECASE)
            if any(rx.search(c) for c in candidates):
                return canon

    # Folder-based fallback: if user organized as <root>/<room>/<files>, use that room folder.
    # Example rel_path: "Living Room/A001_...mov" or "Kitchen/Walkthrough/clip.mov"
    try:
        parts = Path(rel_path).parts
        if len(parts) >= 2:
            top = parts[0]
            return _canon_room_from_folder_name(top)
    except Exception:
        pass

    return "unknown"


def load_room_rules(path: Path) -> RoomRuleSet:
    """Load a room keyword map from JSON.

    Expected format:
      {
        "living_room": ["living", "lounge"],
        "pooja": ["pooja", "prayer"],
        ...
      }

    Values are treated as regex patterns.
    """

    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("room keywords JSON must be an object mapping room -> [patterns]")

    keywords: dict[str, list[str]] = {}
    for k, v in data.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, str):
            patterns = [v]
        elif isinstance(v, list) and all(isinstance(x, str) for x in v):
            patterns = list(v)
        else:
            continue

        canon = k.strip().lower().replace(" ", "_")
        if not canon:
            continue
        keywords[canon] = patterns

    if not keywords:
        raise ValueError("room keywords JSON produced an empty rule set")
    return RoomRuleSet(keywords=keywords)


def default_room_rules_template() -> dict[str, list[str]]:
    return {k: list(v) for k, v in DEFAULT_ROOM_RULES.keywords.items()}


def room_display_name(canon: str) -> str:
    return canon.replace("_", " ").title()


def room_timeline_name(canon: str) -> str:
    # Keep it Resolve-friendly.
    return canon.upper()
