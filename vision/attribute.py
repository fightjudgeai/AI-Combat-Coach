"""
vision/attribute.py
Accumulate per-frame FighterObservations and derive the 7 style columns
that go into the fighters table (+ style_tags).

Usage:
    acc = FighterAccumulator(target_track_id)
    for ts, obs in frame_observations:
        acc.ingest(ts, obs, opponent_obs)
    attrs = acc.compute()
"""
from __future__ import annotations

import dataclasses
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple
import numpy as np

from .detect import FighterObservation, Keypoints


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# % of frame width: fighters within this distance are considered "clinch range"
_CLINCH_DISTANCE_THRESHOLD = 0.18

# Activity window used to detect late-round fade (seconds)
_ROUND_DURATION = 300  # 5-minute rounds assumed

# Minimum keypoint confidence to use a landmark
_KP_CONF_MIN = 0.4

# Stance vote threshold: fraction of frames that must agree
_STANCE_MAJORITY = 0.55


# ---------------------------------------------------------------------------
# Per-frame snapshot
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class FrameSnapshot:
    ts: float
    cx: float           # fighter centre-x (0-1)
    kp: Optional[Keypoints]
    opp_cx: Optional[float]   # opponent centre-x this frame


# ---------------------------------------------------------------------------
# Accumulator
# ---------------------------------------------------------------------------

class FighterAccumulator:
    """
    Collect observations for ONE fighter across all sampled frames,
    then compute style attributes in a single pass.
    """

    def __init__(self, target_track_id: int):
        self.track_id = target_track_id
        self._frames: List[FrameSnapshot] = []

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(
        self,
        ts: float,
        obs: FighterObservation,
        opponent_obs: Optional[FighterObservation],
    ) -> None:
        self._frames.append(FrameSnapshot(
            ts=ts,
            cx=obs.cx,
            kp=obs.keypoints,
            opp_cx=opponent_obs.cx if opponent_obs else None,
        ))

    # ------------------------------------------------------------------
    # Compute attributes
    # ------------------------------------------------------------------

    def compute(self) -> Dict:
        if not self._frames:
            return {}

        stance          = self._compute_stance()
        pressure_rating = self._compute_pressure()
        clinch_frequency = self._compute_clinch()
        late_round_fade  = self._compute_late_round_fade()
        style_tags      = self._compute_style_tags(pressure_rating, clinch_frequency, stance)

        return {
            "stance":           stance,
            "pressure_rating":  round(pressure_rating, 2),
            "clinch_frequency": round(clinch_frequency, 2),
            "late_round_fade":  late_round_fade,
            "style_tags":       style_tags,
            # grappling_first and finish_urgency require labelled event data;
            # set to None so they are left unchanged in the DB unless overridden.
            "grappling_first":  None,
            "finish_urgency":   None,
        }

    # ------------------------------------------------------------------
    # Stance: infer orthodox / southpaw / switch from ankle positions
    # ------------------------------------------------------------------

    def _compute_stance(self) -> Optional[str]:
        orthodox_votes = 0
        southpaw_votes = 0
        total = 0

        for snap in self._frames:
            if snap.kp is None:
                continue
            la = snap.kp.left_ankle
            ra = snap.kp.right_ankle
            kc = snap.kp.confidence

            # Skip low-confidence ankles
            if kc[15] < _KP_CONF_MIN or kc[16] < _KP_CONF_MIN:
                continue

            ls = snap.kp.left_shoulder
            rs = snap.kp.right_shoulder
            if kc[5] < _KP_CONF_MIN or kc[6] < _KP_CONF_MIN:
                continue

            # Determine which direction the fighter faces by shoulder width
            # and whether opponent is to the left or right.
            # Simpler heuristic: if left ankle is closer to body midline
            # (i.e., between the two ankles left is behind right foot)
            # → southpaw (right foot leads). Orthodox = left foot leads.
            mid_x = (ls[0] + rs[0]) / 2
            # "lead foot" = ankle closer to opponent side
            if snap.opp_cx is not None:
                opp_is_right = snap.opp_cx > snap.cx
                if opp_is_right:
                    lead_is_left = la[0] > ra[0]   # larger x = more right = leads if opp on right
                    lead_is_left = not lead_is_left # flip: higher x is toward opp
                    # Actually: if opp is to the right, the lead foot has higher x.
                    lead_foot_left = la[0] > ra[0]  # left ankle has higher x → left ankle is forward
                else:
                    lead_foot_left = la[0] < ra[0]  # lower x is toward opponent (left)
            else:
                # Fall back: left ankle lower x = orthodox lead
                lead_foot_left = la[0] < ra[0]

            if lead_foot_left:
                orthodox_votes += 1
            else:
                southpaw_votes += 1
            total += 1

        if total == 0:
            return None

        if orthodox_votes / total >= _STANCE_MAJORITY:
            return "orthodox"
        if southpaw_votes / total >= _STANCE_MAJORITY:
            return "southpaw"
        return "switch"

    # ------------------------------------------------------------------
    # Pressure: % of frames where fighter is advancing toward opponent
    # ------------------------------------------------------------------

    def _compute_pressure(self) -> float:
        snaps = [s for s in self._frames if s.opp_cx is not None]
        if len(snaps) < 2:
            return 50.0

        advancing = 0
        for i in range(1, len(snaps)):
            prev, curr = snaps[i - 1], snaps[i]
            opp_cx = curr.opp_cx
            # Distance to opponent
            prev_dist = abs(prev.cx - opp_cx)
            curr_dist = abs(curr.cx - opp_cx)
            if curr_dist < prev_dist:
                advancing += 1

        return (advancing / (len(snaps) - 1)) * 100.0

    # ------------------------------------------------------------------
    # Clinch frequency: % of frames where distance to opponent < threshold
    # ------------------------------------------------------------------

    def _compute_clinch(self) -> float:
        snaps = [s for s in self._frames if s.opp_cx is not None]
        if not snaps:
            return 0.0

        clinch_frames = sum(
            1 for s in snaps
            if abs(s.cx - s.opp_cx) < _CLINCH_DISTANCE_THRESHOLD
        )
        return (clinch_frames / len(snaps)) * 100.0

    # ------------------------------------------------------------------
    # Late-round fade: activity (movement) in last third vs first two thirds
    # ------------------------------------------------------------------

    def _compute_late_round_fade(self) -> Optional[bool]:
        if len(self._frames) < 6:
            return None

        max_ts = self._frames[-1].ts
        split = max_ts * (2 / 3)

        early = [s for s in self._frames if s.ts <= split]
        late  = [s for s in self._frames if s.ts > split]

        if len(early) < 3 or len(late) < 3:
            return None

        def movement(snaps: list) -> float:
            diffs = [abs(snaps[i].cx - snaps[i-1].cx) for i in range(1, len(snaps))]
            return float(np.mean(diffs)) if diffs else 0.0

        early_activity = movement(early)
        late_activity  = movement(late)

        if early_activity == 0:
            return None

        fade_ratio = (early_activity - late_activity) / early_activity
        return bool(fade_ratio > 0.20)  # activity drops >20% in late frames

    # ------------------------------------------------------------------
    # Style tags: rule-based from computed metrics
    # ------------------------------------------------------------------

    def _compute_style_tags(
        self,
        pressure: float,
        clinch: float,
        stance: Optional[str],
    ) -> List[str]:
        tags: List[str] = []

        if pressure >= 65:
            tags.append("pressure fighter")
        elif pressure <= 35:
            tags.append("counterpuncher")

        if clinch >= 35:
            tags.append("clinch fighter")

        if stance == "southpaw":
            tags.append("southpaw")
        elif stance == "switch":
            tags.append("switch hitter")

        return tags
