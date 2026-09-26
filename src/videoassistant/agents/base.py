from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class AgentContext:
    root: Path
    va_dir: Path
    out_dir: Path
    project_name: str

    # Analysis settings
    sample_fps: float = 5.0
    scale_width: int = 320

    # Select settings
    min_seg_seconds: float = 3.0
    edge_ignore_seconds: float = 1.0
    max_segs_per_clip: int = 2

    # Optional: user-defined room rules file location
    room_rules_path: Path | None = None

    # Resolve automation (stabilize/import/grade)
    stabilize_first: bool = False
    stabilized_dir: Path | None = None
    stabilize_render_preset: str | None = None
    stabilize_render_format: str | None = None
    stabilize_render_codec: str | None = None

    # Stabilization mode control note:
    # Resolve scripting does not reliably expose per-clip Stabilizer Mode (Perspective/Similarity/Translation).
    # We treat these as UI-facing hints + QC, not hard guarantees.
    stabilize_mode_hint: str | None = "Similarity"
    stabilize_interactive: bool = False
    stabilize_qc: bool = True
    stabilize_qc_sample_fps: float = 3.0
    stabilize_qc_scale_width: int = 256
    stabilize_qc_max_frames: int = 96
    stabilize_qc_regression_ratio: float = 1.15

    # Optional: non-interactive fallback stabilization using OpenCV.
    # Used only for clips that regress (get shakier) after Resolve stabilization.
    stabilize_opencv_fallback: bool = False
    opencv_mode: str = "similarity"  # translation|similarity
    opencv_smooth_seconds: float = 0.5
    opencv_zoom: float = 1.06

    run_resolve_import: bool = False

    grade_drx_path: Path | None = None
    grade_mode: int = 0
    grade_lut_path: str | None = None

    # Auto-grade via CDL (simple, reliable “pro polish” baseline)
    auto_grade: bool = True
    cdl_slope: str = "1.02 1.02 1.02"
    cdl_offset: str = "0.0 0.0 0.0"
    cdl_power: str = "0.98 0.98 0.98"
    cdl_saturation: str = "1.08"

    # Optional: export full selected clips (stabilized + graded) BEFORE autotrim
    export_pretrim: bool = False
    export_pretrim_dir: Path | None = None
    export_pretrim_prefix: str = "PRETRIM_{room}_"
    skip_timeline_correction_if_pretrim: bool = True

    # Runtime info
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    name: str
    ok: bool
    summary: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class Agent(Protocol):
    name: str

    def run(self, ctx: AgentContext) -> AgentResult: ...


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ctx_to_dict(ctx: AgentContext) -> dict[str, Any]:
    d = asdict(ctx)
    # Convert Paths into strings for logs
    for k, v in list(d.items()):
        if isinstance(v, Path):
            d[k] = str(v)
        elif isinstance(v, dict):
            # artifacts may hold Paths
            d[k] = {kk: str(vv) if isinstance(vv, Path) else vv for kk, vv in v.items()}
    return d
