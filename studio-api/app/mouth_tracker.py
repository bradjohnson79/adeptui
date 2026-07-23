from __future__ import annotations

"""
Sticky mouth-region tracker for up to 2 characters.

Strategy:
1) Seed from user-drawn black rectangle (normalized ROI).
2) While a face is visible near that ROI, snap mouth box to MediaPipe face landmarks.
3) If the face is lost (profile / 180 turn away), keep the box sticky via optical flow
   on the last mouth patch until a face reappears near the drifted position.

True back-of-head has no mouth landmarks — the rectangle stays on the last known
mouth patch via flow, then re-locks when the face returns into view.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np


@dataclass
class Roi:
    x: float
    y: float
    w: float
    h: float

    def clamp(self) -> "Roi":
        w = float(np.clip(self.w, 0.04, 0.6))
        h = float(np.clip(self.h, 0.03, 0.5))
        x = float(np.clip(self.x, 0.0, 1.0 - w))
        y = float(np.clip(self.y, 0.0, 1.0 - h))
        return Roi(x, y, w, h)

    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)

    def to_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        x1 = int(self.x * width)
        y1 = int(self.y * height)
        x2 = int((self.x + self.w) * width)
        y2 = int((self.y + self.h) * height)
        return x1, y1, max(x1 + 1, x2), max(y1 + 1, y2)


# MediaPipe Face Mesh lip landmark indices (outer + inner mouth)
_MOUTH_IDX = [
    61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308,
    78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308,
]


def _mouth_roi_from_landmarks(landmarks, frame_w: int, frame_h: int, pad: float = 0.35) -> Roi:
    xs = [landmarks[i].x for i in _MOUTH_IDX]
    ys = [landmarks[i].y for i in _MOUTH_IDX]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    bw = max(0.02, max_x - min_x)
    bh = max(0.015, max_y - min_y)
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    w = bw * (1.0 + pad)
    h = bh * (1.0 + pad * 1.2)
    return Roi(cx - w / 2.0, cy - h / 2.0, w, h).clamp()


def _iou(a: Roi, b: Roi) -> float:
    ax2, ay2 = a.x + a.w, a.y + a.h
    bx2, by2 = b.x + b.w, b.y + b.h
    ix1, iy1 = max(a.x, b.x), max(a.y, b.y)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = a.w * a.h + b.w * b.h - inter + 1e-8
    return inter / union


def _center_dist(a: Roi, b: Roi) -> float:
    acx, acy = a.center()
    bcx, bcy = b.center()
    return float(np.hypot(acx - bcx, acy - bcy))


def track_mouth_rois(
    video_path: Path,
    seed_roi: Roi,
    *,
    max_frames: int = 0,
) -> list[dict[str, Any]]:
    """
    Returns per-frame mouth ROIs as normalized dicts:
    {frame, x, y, w, h, visible, mode} where mode is landmark|flow|frozen
    """
    import cv2

    try:
        import mediapipe as mp
    except Exception as exc:
        raise RuntimeError(
            "mediapipe is required for sticky mouth tracking. "
            "Install with: pip install mediapipe opencv-python-headless"
        ) from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1)

    face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=2,
        refine_landmarks=True,
        min_detection_confidence=0.4,
        min_tracking_confidence=0.4,
    )

    path: list[dict[str, Any]] = []
    current = seed_roi.clamp()
    prev_gray: Optional[np.ndarray] = None
    prev_pts: Optional[np.ndarray] = None
    frame_idx = 0
    lost_frames = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if max_frames and frame_idx >= max_frames:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = face_mesh.process(rgb)
        mode = "frozen"
        visible = False
        chosen: Optional[Roi] = None

        if result.multi_face_landmarks:
            candidates = [
                _mouth_roi_from_landmarks(face.landmark, width, height)
                for face in result.multi_face_landmarks
            ]
            # Prefer face whose mouth is closest to current sticky box
            candidates.sort(key=lambda r: (_center_dist(r, current), -_iou(r, current)))
            best = candidates[0]
            # Lock if reasonably near, else still take nearest for re-acquisition after 180°
            if _center_dist(best, current) < 0.35 or lost_frames > 8:
                chosen = best
                mode = "landmark"
                visible = True
                lost_frames = 0
            else:
                lost_frames += 1
        else:
            lost_frames += 1

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if chosen is None and prev_gray is not None and prev_pts is not None:
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, prev_pts, None, winSize=(21, 21), maxLevel=3)
            if nxt is not None and st is not None and st.sum() >= 4:
                good = nxt[st.flatten() == 1]
                if len(good) >= 4:
                    cx = float(np.mean(good[:, 0]) / width)
                    cy = float(np.mean(good[:, 1]) / height)
                    chosen = Roi(cx - current.w / 2.0, cy - current.h / 2.0, current.w, current.h).clamp()
                    mode = "flow"
                    visible = False  # mouth may be occluded / turned away

        if chosen is None:
            chosen = current
            mode = "frozen"

        current = chosen.clamp()
        path.append(
            {
                "frame": frame_idx,
                "t": frame_idx / fps,
                "x": current.x,
                "y": current.y,
                "w": current.w,
                "h": current.h,
                "visible": visible,
                "mode": mode,
            }
        )

        # Refresh flow points from current mouth box
        x1, y1, x2, y2 = current.to_pixels(width, height)
        roi = gray[y1:y2, x1:x2]
        pts = None
        if roi.size > 0:
            corners = cv2.goodFeaturesToTrack(roi, maxCorners=40, qualityLevel=0.01, minDistance=4)
            if corners is not None:
                pts = corners.reshape(-1, 2)
                pts[:, 0] += x1
                pts[:, 1] += y1
                pts = pts.reshape(-1, 1, 2).astype(np.float32)

        prev_gray = gray
        prev_pts = pts
        frame_idx += 1

    face_mesh.close()
    cap.release()
    return path


def overlay_track_preview(
    video_path: Path,
    track_path: list[dict[str, Any]],
    out_path: Path,
    *,
    color: tuple[int, int, int] = (0, 0, 0),
    label: str = "C1",
) -> Path:
    """Burn black mouth rectangles onto a preview video for QA."""
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
    by_frame = {int(p["frame"]): p for p in track_path}
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        p = by_frame.get(idx)
        if p:
            roi = Roi(p["x"], p["y"], p["w"], p["h"]).clamp()
            x1, y1, x2, y2 = roi.to_pixels(width, height)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness=-1)
            cv2.putText(frame, label, (x1, max(16, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        writer.write(frame)
        idx += 1
    cap.release()
    writer.release()
    return out_path
