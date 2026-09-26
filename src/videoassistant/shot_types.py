from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ShotTypeResult:
    shot_type: str
    confidence: float
    speed: float
    dir_var: float
    curvature: float
    axis_ratio: float


def _circular_variance(angles_rad: np.ndarray) -> float:
    if angles_rad.size == 0:
        return 1.0
    v = np.exp(1j * angles_rad.astype(np.float64))
    m = np.mean(v)
    r = float(np.abs(m))
    return float(max(0.0, min(1.0, 1.0 - r)))


def _angle_diff(a: np.ndarray) -> np.ndarray:
    # wrap to [-pi, pi]
    d = (a + math.pi) % (2 * math.pi) - math.pi
    return d


def classify_shot_from_motion(
    shifts_xy: np.ndarray,
    shakiness: np.ndarray | None = None,
) -> ShotTypeResult:
    """Classify a segment based on global translation trajectory.

    This is a lightweight heuristic classifier. It does NOT reliably detect true optical zoom.
    It focuses on the most common real-estate moves: static, pan, tilt, walk, arc/rotate, whip, shaky.
    """

    if shifts_xy.size == 0:
        return ShotTypeResult("unknown", 0.0, 0.0, 1.0, 0.0, 1.0)

    xy = shifts_xy.astype(np.float32)
    dx = xy[:, 0]
    dy = xy[:, 1]
    speed = float(np.mean(np.sqrt(dx * dx + dy * dy)))

    ax = float(np.mean(np.abs(dx))) + 1e-6
    ay = float(np.mean(np.abs(dy))) + 1e-6
    axis_ratio = float(ax / ay)  # >1 means mostly horizontal

    angles = np.arctan2(dy, dx)
    dir_var = _circular_variance(angles)

    if angles.size >= 3:
        d = _angle_diff(np.diff(angles.astype(np.float64)))
        curvature = float(np.mean(np.abs(d)))
    else:
        curvature = 0.0

    jitter = float(np.mean(shakiness.astype(np.float32))) if (shakiness is not None and shakiness.size) else 0.0

    # Thresholds tuned for sampled frames at ~320px width.
    static_thr = 0.35
    slow_thr = 1.2
    whip_thr = 6.0
    shaky_thr = 1.25

    if jitter >= shaky_thr and speed >= slow_thr:
        conf = min(1.0, (jitter - shaky_thr) / 1.0)
        return ShotTypeResult("shaky", conf, speed, dir_var, curvature, axis_ratio)

    if speed <= static_thr:
        conf = min(1.0, (static_thr - speed) / static_thr)
        return ShotTypeResult("static", conf, speed, dir_var, curvature, axis_ratio)

    if speed >= whip_thr:
        conf = min(1.0, (speed - whip_thr) / whip_thr)
        return ShotTypeResult("whip", conf, speed, dir_var, curvature, axis_ratio)

    # Strong single-axis motion with stable direction
    if dir_var <= 0.28:
        if axis_ratio >= 1.6:
            st = "slow_pan" if speed <= slow_thr else "pan"
            conf = min(1.0, (1.6 - min(axis_ratio, 1.6)) / 1.6 + (0.28 - dir_var) / 0.28)
            conf = max(0.35, min(0.95, conf))
            return ShotTypeResult(st, conf, speed, dir_var, curvature, axis_ratio)
        if axis_ratio <= 0.62:
            st = "slow_tilt" if speed <= slow_thr else "tilt"
            conf = min(1.0, (0.62 - min(axis_ratio, 0.62)) / 0.62 + (0.28 - dir_var) / 0.28)
            conf = max(0.35, min(0.95, conf))
            return ShotTypeResult(st, conf, speed, dir_var, curvature, axis_ratio)

    # Curving motion: arc/rotate
    if curvature >= 0.35 and dir_var >= 0.35:
        conf = min(1.0, (curvature - 0.35) / 0.5)
        conf = max(0.35, min(0.9, conf))
        return ShotTypeResult("arc", conf, speed, dir_var, curvature, axis_ratio)

    # Default: walk / handheld move
    conf = 0.45
    if speed <= slow_thr:
        conf += 0.1
    if jitter <= 0.9:
        conf += 0.1
    return ShotTypeResult("walk", min(0.85, conf), speed, dir_var, curvature, axis_ratio)
