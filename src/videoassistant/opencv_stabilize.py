from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class OpenCVStabilizeSettings:
    mode: str = "translation"  # translation|similarity
    smooth_seconds: float = 0.5
    zoom: float = 1.06
    max_corners: int = 200
    quality_level: float = 0.01
    min_distance: int = 30


def _moving_average(x: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return x
    win = 2 * radius + 1
    if x.shape[0] < win:
        return x
    kernel = np.ones((win,), dtype=np.float32) / float(win)
    # pad edges to keep same length
    pad = radius
    xp = np.pad(x.astype(np.float32), (pad, pad), mode="edge")
    y = np.convolve(xp, kernel, mode="valid")
    return y.astype(np.float32)


def _extract_da_ds(m: np.ndarray) -> tuple[float, float]:
    # m is 2x3 affine
    a = float(m[0, 0])
    b = float(m[0, 1])
    # rotation angle
    da = float(np.arctan2(b, a))
    # scale (approx)
    ds = float(np.sqrt(a * a + b * b))
    return da, ds


def stabilize_video_opencv(
    in_path: Path,
    out_path: Path,
    settings: OpenCVStabilizeSettings,
) -> dict:
    """Stabilize a video using OpenCV feature tracking.

    Writes an MP4 to out_path. Audio is not preserved.

    Returns basic metadata (frames processed, fps, mode).
    """

    import cv2  # local import so the rest of the project works without OpenCV installed

    in_path = Path(in_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(in_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV failed to open video: {in_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0:
        fps = 30.0

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if w <= 0 or h <= 0:
        raise RuntimeError(f"OpenCV could not read dimensions: {in_path}")

    ok, prev = cap.read()
    if not ok or prev is None:
        raise RuntimeError(f"OpenCV could not read first frame: {in_path}")

    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

    transforms = []  # (dx,dy,da,ds)
    frame_count = 1

    while True:
        ok, cur = cap.read()
        if not ok or cur is None:
            break
        cur_gray = cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY)

        prev_pts = cv2.goodFeaturesToTrack(
            prev_gray,
            maxCorners=int(settings.max_corners),
            qualityLevel=float(settings.quality_level),
            minDistance=int(settings.min_distance),
        )

        dx = dy = da = 0.0
        ds = 1.0

        if prev_pts is not None and len(prev_pts) >= 4:
            cur_pts, status, _err = cv2.calcOpticalFlowPyrLK(prev_gray, cur_gray, prev_pts, None)
            if cur_pts is not None and status is not None:
                good_prev = prev_pts[status.flatten() == 1]
                good_cur = cur_pts[status.flatten() == 1]
                if len(good_prev) >= 4 and len(good_cur) >= 4:
                    if settings.mode == "translation":
                        diffs = (good_cur - good_prev).reshape(-1, 2)
                        dx = float(np.median(diffs[:, 0]))
                        dy = float(np.median(diffs[:, 1]))
                        da = 0.0
                        ds = 1.0
                    else:
                        m, _inliers = cv2.estimateAffinePartial2D(
                            good_prev,
                            good_cur,
                            method=cv2.RANSAC,
                            ransacReprojThreshold=3.0,
                        )
                        if m is not None:
                            dx = float(m[0, 2])
                            dy = float(m[1, 2])
                            da, ds = _extract_da_ds(m)

        transforms.append((dx, dy, da, ds))
        prev_gray = cur_gray
        frame_count += 1

    cap.release()

    if frame_count < 2 or not transforms:
        raise RuntimeError(f"Not enough frames to stabilize: {in_path}")

    t = np.asarray(transforms, dtype=np.float32)  # (N-1,4)
    dx = t[:, 0]
    dy = t[:, 1]
    da = t[:, 2]
    ds = t[:, 3]

    traj_x = np.cumsum(dx)
    traj_y = np.cumsum(dy)
    traj_a = np.cumsum(da)
    traj_s = np.cumsum(ds - 1.0)

    radius = int(max(0.0, float(settings.smooth_seconds)) * fps)
    radius = int(min(radius, 60))

    sx = _moving_average(traj_x, radius)
    sy = _moving_average(traj_y, radius)
    sa = _moving_average(traj_a, radius)
    ss = _moving_average(traj_s, radius)

    diff_x = sx - traj_x
    diff_y = sy - traj_y
    diff_a = sa - traj_a
    diff_s = ss - traj_s

    new_dx = dx + diff_x
    new_dy = dy + diff_y
    new_da = da + diff_a
    new_ds = (ds - 1.0) + diff_s + 1.0

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"OpenCV failed to open VideoWriter: {out_path}")

    cap2 = cv2.VideoCapture(str(in_path))
    ok, frame0 = cap2.read()
    if not ok or frame0 is None:
        cap2.release()
        writer.release()
        raise RuntimeError(f"OpenCV could not re-read first frame: {in_path}")

    # write first frame as-is (or with identity warp)
    writer.write(frame0)

    zoom = float(settings.zoom)
    cx = w / 2.0
    cy = h / 2.0

    i = 0
    while True:
        ok, frame = cap2.read()
        if not ok or frame is None:
            break
        if i >= new_dx.shape[0]:
            writer.write(frame)
            continue

        ang = float(new_da[i])
        sc = float(new_ds[i])
        cos_a = float(np.cos(ang) * sc)
        sin_a = float(np.sin(ang) * sc)
        m = np.array(
            [
                [cos_a, -sin_a, float(new_dx[i])],
                [sin_a, cos_a, float(new_dy[i])],
            ],
            dtype=np.float32,
        )

        # Apply zoom around center to hide borders
        if zoom and zoom != 1.0:
            z = float(zoom)
            zm = np.array([[z, 0.0, (1.0 - z) * cx], [0.0, z, (1.0 - z) * cy]], dtype=np.float32)
            m = zm @ np.vstack([m, [0.0, 0.0, 1.0]])
            m = m[:2, :].astype(np.float32)

        stabilized = cv2.warpAffine(
            frame,
            m,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        writer.write(stabilized)
        i += 1

    cap2.release()
    writer.release()

    return {
        "mode": settings.mode,
        "smooth_seconds": float(settings.smooth_seconds),
        "zoom": float(settings.zoom),
        "fps": float(fps),
        "width": int(w),
        "height": int(h),
        "frames": int(frame_count),
    }
