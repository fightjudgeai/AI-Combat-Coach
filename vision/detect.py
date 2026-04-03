"""
vision/detect.py
YOLOv8-pose inference + BoT-SORT tracker.

Each frame produces a list of FighterObservation — one per tracked fighter.
We keep only the two largest (by bbox area) fighters per frame.

COCO keypoint indices used:
  5=left_shoulder  6=right_shoulder
  11=left_hip      12=right_hip
  15=left_ankle    16=right_ankle
"""
from __future__ import annotations

import dataclasses
from typing import List, Optional, Tuple
import numpy as np


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Keypoints:
    """
    Full COCO-17 keypoint snapshot for one fighter in one frame.

    Named pixel-coordinate pairs follow COCO order:
      0=nose        1-4=eyes/ears
      5=left_shoulder   6=right_shoulder
      7=left_elbow      8=right_elbow
      9=left_wrist     10=right_wrist  (proxy: left/right glove)
     11=left_hip       12=right_hip
     13=left_knee      14=right_knee
     15=left_ankle     16=right_ankle  (proxy: foot / shin)
    """
    # Head
    nose:           Tuple[float, float]       # idx 0
    # Upper body
    left_shoulder:  Tuple[float, float]       # idx 5
    right_shoulder: Tuple[float, float]       # idx 6
    # Arms
    left_elbow:     Tuple[float, float]       # idx 7
    right_elbow:    Tuple[float, float]       # idx 8
    left_wrist:     Tuple[float, float]       # idx 9  — left glove proxy
    right_wrist:    Tuple[float, float]       # idx 10 — right glove proxy
    # Core
    left_hip:       Tuple[float, float]       # idx 11
    right_hip:      Tuple[float, float]       # idx 12
    # Legs
    left_knee:      Tuple[float, float]       # idx 13
    right_knee:     Tuple[float, float]       # idx 14
    left_ankle:     Tuple[float, float]       # idx 15 — left foot / shin proxy
    right_ankle:    Tuple[float, float]       # idx 16 — right foot / shin proxy
    # Full confidence + raw coord arrays
    confidence:     np.ndarray                # shape (17,) per-keypoint confidence
    raw_xy:         np.ndarray                # shape (17, 2) all keypoints in pixels


@dataclasses.dataclass
class FighterObservation:
    track_id:   int
    bbox:       Tuple[float, float, float, float]   # x1, y1, x2, y2
    conf:       float
    keypoints:  Optional[Keypoints]
    cx:         float   # bbox centre x (0-1 relative to frame width)
    cy:         float   # bbox centre y (0-1 relative to frame height)


# ---------------------------------------------------------------------------
# Detector (lazy-loaded so import is fast when YOLO not installed)
# ---------------------------------------------------------------------------

class PoseDetector:
    """Wraps ultralytics YOLOv8-pose + BoT-SORT tracker."""

    def __init__(self, model_name: str = "yolov8n-pose.pt", device: str = "cuda"):
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError(
                "ultralytics required: pip install ultralytics"
            )
        self._model = YOLO(model_name)
        self._device = device

    def detect(
        self,
        frame: np.ndarray,
        frame_w: int,
        frame_h: int,
    ) -> List[FighterObservation]:
        """
        Run pose + tracking on a single BGR frame.
        Returns up to 2 FighterObservations (the two largest fighters).
        """
        results = self._model.track(
            frame,
            persist=True,
            tracker="botsort.yaml",
            device=self._device,
            verbose=False,
            conf=0.4,
            iou=0.5,
        )

        observations: List[FighterObservation] = []
        if not results or results[0].boxes is None:
            return observations

        res = results[0]
        boxes = res.boxes
        kps_data = res.keypoints  # may be None for non-pose models

        for i, box in enumerate(boxes):
            if box.id is None:
                continue
            track_id = int(box.id.item())
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0].item())
            area = (x2 - x1) * (y2 - y1)
            cx = ((x1 + x2) / 2) / frame_w
            cy = ((y1 + y2) / 2) / frame_h

            kp_obj: Optional[Keypoints] = None
            if kps_data is not None and i < len(kps_data.xy):
                xy = kps_data.xy[i].cpu().numpy()     # (17, 2)
                kp_conf = kps_data.conf[i].cpu().numpy() if kps_data.conf is not None else np.ones(17)
                kp_obj = Keypoints(
                    nose           = (float(xy[0, 0]),  float(xy[0, 1])),
                    left_shoulder  = (float(xy[5, 0]),  float(xy[5, 1])),
                    right_shoulder = (float(xy[6, 0]),  float(xy[6, 1])),
                    left_elbow     = (float(xy[7, 0]),  float(xy[7, 1])),
                    right_elbow    = (float(xy[8, 0]),  float(xy[8, 1])),
                    left_wrist     = (float(xy[9, 0]),  float(xy[9, 1])),
                    right_wrist    = (float(xy[10, 0]), float(xy[10, 1])),
                    left_hip       = (float(xy[11, 0]), float(xy[11, 1])),
                    right_hip      = (float(xy[12, 0]), float(xy[12, 1])),
                    left_knee      = (float(xy[13, 0]), float(xy[13, 1])),
                    right_knee     = (float(xy[14, 0]), float(xy[14, 1])),
                    left_ankle     = (float(xy[15, 0]), float(xy[15, 1])),
                    right_ankle    = (float(xy[16, 0]), float(xy[16, 1])),
                    confidence     = kp_conf,
                    raw_xy         = xy,
                )

            observations.append(FighterObservation(
                track_id=track_id, bbox=(x1, y1, x2, y2),
                conf=conf, keypoints=kp_obj, cx=cx, cy=cy,
            ))

        # Keep only the two fighters with the largest bboxes
        observations.sort(key=lambda o: (o.bbox[2]-o.bbox[0])*(o.bbox[3]-o.bbox[1]), reverse=True)
        return observations[:2]
