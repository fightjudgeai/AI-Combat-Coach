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
    left_shoulder:  Tuple[float, float]
    right_shoulder: Tuple[float, float]
    left_hip:       Tuple[float, float]
    right_hip:      Tuple[float, float]
    left_ankle:     Tuple[float, float]
    right_ankle:    Tuple[float, float]
    confidence:     np.ndarray          # shape (17,) raw confidence per keypoint


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
                    left_shoulder  = (float(xy[5, 0]),  float(xy[5, 1])),
                    right_shoulder = (float(xy[6, 0]),  float(xy[6, 1])),
                    left_hip       = (float(xy[11, 0]), float(xy[11, 1])),
                    right_hip      = (float(xy[12, 0]), float(xy[12, 1])),
                    left_ankle     = (float(xy[15, 0]), float(xy[15, 1])),
                    right_ankle    = (float(xy[16, 0]), float(xy[16, 1])),
                    confidence     = kp_conf,
                )

            observations.append(FighterObservation(
                track_id=track_id, bbox=(x1, y1, x2, y2),
                conf=conf, keypoints=kp_obj, cx=cx, cy=cy,
            ))

        # Keep only the two fighters with the largest bboxes
        observations.sort(key=lambda o: (o.bbox[2]-o.bbox[0])*(o.bbox[3]-o.bbox[1]), reverse=True)
        return observations[:2]
