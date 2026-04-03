"""
vision/body_tagger.py
Per-frame body-part visibility tracker and kinematic feature extractor.

For each sampled frame the accumulator records which COCO keypoints are
confidently detected and their normalised (x, y) positions.  After a full
video is processed, ``compute()`` returns:

  visibility   – frame counts + % visible for each body part
  kinematics   – mean / max / p95 velocity per body part (normalised px/frame)
  spatial      – centre-of-mass bbox range (proxy for ring coverage)

These features are stored in ``fight_event_summary.body_part_frames`` (JSONB)
and ``fight_event_summary.kinematic_features`` (JSONB) and can be used as
input feature vectors for downstream ML models.

COCO-17 keypoint indices used:
  0  = nose         → head
  7  = left_elbow   → elbow_l
  8  = right_elbow  → elbow_r
  9  = left_wrist   → glove_l  (left glove proxy)
  10 = right_wrist  → glove_r  (right glove proxy)
  11+12 body avg    → body     (torso centre from shoulders + hips)
  13 = left_knee    → knee_l
  14 = right_knee   → knee_r
  15 = left_ankle   → foot_l   (left foot / shin proxy)
  16 = right_ankle  → foot_r   (right foot / shin proxy)
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from .detect import FighterObservation

# Keypoint label → COCO index.  None = computed from multiple keypoints.
_PART_INDICES: Dict[str, Optional[int]] = {
    "head":    0,    # nose
    "elbow_l": 7,
    "elbow_r": 8,
    "glove_l": 9,    # left wrist
    "glove_r": 10,   # right wrist
    "body":    None, # average of shoulder (5,6) + hip (11,12)
    "knee_l":  13,
    "knee_r":  14,
    "foot_l":  15,   # left ankle
    "foot_r":  16,   # right ankle
}

# Composite body parts backed by multiple keypoints.
# Each entry: (indices, min individual confidence)
_COMPOSITE: Dict[str, Tuple[List[int], float]] = {
    "body": ([5, 6, 11, 12], 0.30),
}

_KP_CONF_MIN = 0.35


class BodyPartAccumulator:
    """
    Collects per-frame body-part observations for ONE fighter and
    computes aggregated visibility + kinematic stats.
    """

    def __init__(self, min_conf: float = _KP_CONF_MIN):
        self._min_conf = min_conf
        self._n_frames: int = 0

        # frame counts
        self._visible: Dict[str, int] = {p: 0 for p in _PART_INDICES}

        # normalised position lists [(x, y), ...]
        self._positions: Dict[str, List[Tuple[float, float]]] = {
            p: [] for p in _PART_INDICES
        }

        # per-frame velocity list
        self._velocities: Dict[str, List[float]] = {
            p: [] for p in _PART_INDICES
        }

        # previous normalised position for velocity calculation
        self._prev: Dict[str, Optional[Tuple[float, float]]] = {
            p: None for p in _PART_INDICES
        }

        # fighter centre-of-mass range (for ring coverage metric)
        self._cx_list: List[float] = []
        self._cy_list: List[float] = []

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(
        self,
        ts: float,
        obs: FighterObservation,
        frame_w: int,
        frame_h: int,
    ) -> None:
        """Record one sampled frame for this fighter."""
        self._n_frames += 1
        kp = obs.keypoints
        if kp is None:
            # No keypoints — reset velocity baselines
            for p in _PART_INDICES:
                self._prev[p] = None
            return

        # Track fighter centre for spatial coverage
        self._cx_list.append(obs.cx)
        cy = (obs.bbox[1] + obs.bbox[3]) / 2 / frame_h
        self._cy_list.append(cy)

        for part, idx in _PART_INDICES.items():
            pos: Optional[Tuple[float, float]] = None

            if idx is None:
                # Composite part (body torso)
                indices, min_c = _COMPOSITE[part]
                confs = [float(kp.confidence[i]) for i in indices]
                if min(confs) >= min_c:
                    coords = kp.raw_xy[indices]          # shape (4, 2)
                    cx_p = float(np.mean(coords[:, 0])) / frame_w
                    cy_p = float(np.mean(coords[:, 1])) / frame_h
                    pos = (cx_p, cy_p)
            else:
                if float(kp.confidence[idx]) >= self._min_conf:
                    px = float(kp.raw_xy[idx, 0]) / frame_w
                    py = float(kp.raw_xy[idx, 1]) / frame_h
                    pos = (px, py)

            if pos is not None:
                self._visible[part] += 1
                self._positions[part].append(pos)
                prev = self._prev[part]
                if prev is not None:
                    v = math.sqrt((pos[0] - prev[0]) ** 2 + (pos[1] - prev[1]) ** 2)
                    self._velocities[part].append(v)
                self._prev[part] = pos
            else:
                # Keypoint lost — reset velocity baseline to avoid
                # large velocity spike on next detection.
                self._prev[part] = None

    # ------------------------------------------------------------------
    # Compute final stats
    # ------------------------------------------------------------------

    def compute(self) -> Dict:
        """
        Returns a dict with two sub-dicts:
          ``visibility``  — frame counts per part
          ``kinematics``  — velocity stats per part (useful ML features)
          ``spatial``     — fighter ring/cage coverage
        """
        if self._n_frames == 0:
            return {}

        visibility: Dict[str, Dict] = {}
        kinematics: Dict[str, Dict] = {}

        for part in _PART_INDICES:
            n = self._visible[part]
            pct = round(n / self._n_frames * 100, 1)
            visibility[part] = {
                "frames_visible":  n,
                "visibility_pct":  pct,
            }

            vels = self._velocities[part]
            if vels:
                arr = np.array(vels, dtype=np.float32)
                kinematics[part] = {
                    "mean_vel":  round(float(np.mean(arr)), 4),
                    "max_vel":   round(float(np.max(arr)), 4),
                    "p95_vel":   round(float(np.percentile(arr, 95)), 4),
                    "n_samples": len(vels),
                }
            else:
                kinematics[part] = {
                    "mean_vel": 0.0, "max_vel": 0.0, "p95_vel": 0.0,
                    "n_samples": 0,
                }

        # Spatial coverage: bounding range of fighter centre of mass
        spatial: Dict = {}
        if self._cx_list and self._cy_list:
            cx_arr = np.array(self._cx_list)
            cy_arr = np.array(self._cy_list)
            spatial = {
                "cx_mean":  round(float(np.mean(cx_arr)), 3),
                "cx_range": round(float(np.max(cx_arr) - np.min(cx_arr)), 3),
                "cy_mean":  round(float(np.mean(cy_arr)), 3),
                "cy_range": round(float(np.max(cy_arr) - np.min(cy_arr)), 3),
            }

        return {
            "total_frames": self._n_frames,
            "visibility":   visibility,
            "kinematics":   kinematics,
            "spatial":      spatial,
        }
