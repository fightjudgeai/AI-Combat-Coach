"""
vision/classifier.py
Rule-based event classifier.

Converts sequences of FighterObservation + positional geometry into
FightEvent instances using:
  - Keypoint velocity (strike detection)
  - Relative body positions (grappling positions)
  - Cage proximity (cage control)
  - Ground-state detection (knockdown)
  - Temporal state machine (clinch entry/break, position changes)
"""
from __future__ import annotations

import math
from collections import deque
from typing import Deque, List, Optional, Tuple

import numpy as np

from .detect import FighterObservation, Keypoints
from .events import (
    EventType, FightEvent, Limb, Outcome, Position, PunchSubtype, TargetZone,
)

# ---------------------------------------------------------------------------
# COCO keypoint indices (referenced in detect.py Keypoints dataclass)
# ---------------------------------------------------------------------------
# We receive pre-extracted Keypoints objects, not raw indices.
# Additional keypoints we need from the raw 17-kp array:
#   0=nose  7=left_wrist  8=right_wrist  9=left_elbow  10=right_elbow

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_STRIKE_VELOCITY_THRESHOLD   = 0.04   # wrist/ankle displacement per frame (fraction of frame)
_CLINCH_DISTANCE             = 0.18   # fraction of frame width
_CAGE_EDGE_THRESHOLD         = 0.08   # fraction of frame width from edge
_GROUND_HIP_THRESHOLD        = 0.72   # hip y > this fraction of frame height → grounded
_KD_SHOULDER_THRESHOLD       = 0.80   # shoulder y → fighter floored
_GRAPPLE_PROXIMITY           = 0.14   # bodies this close + one grounded → grappling
_MIN_EVENT_SEPARATION        = 0.5    # seconds — suppress duplicate events within window
_CONFIDENCE_STRIKE_RULE      = 0.55
_CONFIDENCE_POSITION_RULE    = 0.60

# Punch subtype geometry thresholds
_HOOK_LATERAL_RATIO          = 0.55   # lateral dx / total displacement → hook
_UPPERCUT_UPWARD_RATIO       = 0.45   # upward (-dy) / total displacement → uppercut
_LEAD_HAND_TOLERANCE         = 0.05   # cx offset tolerance for lead/rear hand determination

# KO detection: frames fighter stays floored before we emit KO vs knockdown
_KO_FLOOR_FRAMES             = 3      # at sample_interval=2s this is ~6 s of being down


# ---------------------------------------------------------------------------
# Frame-level snapshot including raw keypoint array access
# ---------------------------------------------------------------------------

class FrameState:
    """
    Wraps FighterObservation + raw 17-kp array for wrist/elbow access.
    We attach the raw xy array when available (detect.py can expose it).
    """
    __slots__ = ("ts", "obs", "opp", "raw_kp", "frame_w", "frame_h")

    def __init__(
        self,
        ts: float,
        obs: FighterObservation,
        opp: Optional[FighterObservation],
        frame_w: int,
        frame_h: int,
        raw_kp: Optional[np.ndarray] = None,   # shape (17, 2) in pixels
    ):
        self.ts      = ts
        self.obs     = obs
        self.opp     = opp
        self.raw_kp  = raw_kp
        self.frame_w = frame_w
        self.frame_h = frame_h

    # Normalised keypoints (0-1)
    def _norm(self, px: float, py: float) -> Tuple[float, float]:
        return px / self.frame_w, py / self.frame_h

    def wrist_l(self) -> Optional[Tuple[float, float]]:
        if self.raw_kp is not None and self.obs.keypoints and self.obs.keypoints.confidence[9] > 0.4:
            return self._norm(*self.raw_kp[9])
        return None

    def wrist_r(self) -> Optional[Tuple[float, float]]:
        if self.raw_kp is not None and self.obs.keypoints and self.obs.keypoints.confidence[10] > 0.4:
            return self._norm(*self.raw_kp[10])
        return None

    def ankle_l(self) -> Optional[Tuple[float, float]]:
        kp = self.obs.keypoints
        if kp and kp.confidence[15] > 0.4:
            return self._norm(*kp.left_ankle)
        return None

    def ankle_r(self) -> Optional[Tuple[float, float]]:
        kp = self.obs.keypoints
        if kp and kp.confidence[16] > 0.4:
            return self._norm(*kp.right_ankle)
        return None

    def hip_mid_y(self) -> Optional[float]:
        kp = self.obs.keypoints
        if kp and kp.confidence[11] > 0.3 and kp.confidence[12] > 0.3:
            return (kp.left_hip[1] + kp.right_hip[1]) / 2 / self.frame_h
        return None

    def shoulder_mid_y(self) -> Optional[float]:
        kp = self.obs.keypoints
        if kp and kp.confidence[5] > 0.3 and kp.confidence[6] > 0.3:
            return (kp.left_shoulder[1] + kp.right_shoulder[1]) / 2 / self.frame_h
        return None

    def is_grounded(self) -> bool:
        h = self.hip_mid_y()
        return h is not None and h > _GROUND_HIP_THRESHOLD

    def is_floored(self) -> bool:
        s = self.shoulder_mid_y()
        return s is not None and s > _KD_SHOULDER_THRESHOLD

    def dist_to_opp(self) -> Optional[float]:
        if self.opp is None:
            return None
        return abs(self.obs.cx - self.opp.cx)

    def near_cage_left(self) -> bool:
        return self.obs.cx < _CAGE_EDGE_THRESHOLD

    def near_cage_right(self) -> bool:
        return self.obs.cx > 1.0 - _CAGE_EDGE_THRESHOLD


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _dist2(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)


def _velocity(prev: Optional[Tuple[float, float]],
               curr: Optional[Tuple[float, float]],
               dt: float) -> float:
    if prev is None or curr is None or dt <= 0:
        return 0.0
    return _dist2(prev, curr) / dt


# ---------------------------------------------------------------------------
# Event classifier (stateful)
# ---------------------------------------------------------------------------

class FightClassifier:
    """
    Call ingest(frame_state) for every sampled frame.
    Returns a list of FightEvent detected in that frame.
    Call flush() at end to emit any pending position-end events.
    """

    def __init__(self, sample_interval: float = 2.0):
        self._dt         = sample_interval
        self._history: Deque[FrameState] = deque(maxlen=4)
        self._position   = Position.STANDING
        self._pos_start  = 0.0
        self._last_events: dict[str, float] = {}   # event_type → last_ts
        self._floored_frames = 0   # consecutive frames fighter is floored (KO detector)
        self._kd_emitted     = False  # whether knockdown event already emitted this sequence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, fs: FrameState) -> List[FightEvent]:
        events: List[FightEvent] = []

        events.extend(self._detect_strikes(fs))
        events.extend(self._detect_knockdown(fs))
        events.extend(self._detect_takedown(fs))
        events.extend(self._detect_position(fs))
        events.extend(self._detect_clinch(fs))
        events.extend(self._detect_cage(fs))

        self._history.append(fs)
        return [e for e in events if self._not_duplicate(e)]

    def flush(self, final_ts: float) -> List[FightEvent]:
        """Emit a final position event if still in non-standing position."""
        if self._position != Position.STANDING:
            return [FightEvent(
                timestamp_secs=final_ts,
                event_type=EventType.POSITION_CHANGE,
                position=Position.STANDING,
                confidence=_CONFIDENCE_POSITION_RULE,
            )]
        return []

    # ------------------------------------------------------------------
    # Duplicate suppression
    # ------------------------------------------------------------------

    def _not_duplicate(self, event: FightEvent) -> bool:
        key = event.event_type.value
        last = self._last_events.get(key, -999)
        if event.timestamp_secs - last < _MIN_EVENT_SEPARATION:
            return False
        self._last_events[key] = event.timestamp_secs
        return True

    # ------------------------------------------------------------------
    # Strike detection
    # ------------------------------------------------------------------

    def _detect_strikes(self, fs: FrameState) -> List[FightEvent]:
        events: List[FightEvent] = []
        if not self._history:
            return events

        prev = self._history[-1]
        dt = fs.ts - prev.ts
        striker_grounded = fs.is_grounded()
        opp_grounded     = False
        if fs.opp and fs.opp.keypoints:
            opp_grounded = fs.opp.keypoints.left_hip[1] / fs.frame_h > _GROUND_HIP_THRESHOLD

        # --- Punch (wrist velocity toward opponent) ---
        for wrist_fn in (FrameState.wrist_l, FrameState.wrist_r):
            w_prev = wrist_fn(prev)
            w_curr = wrist_fn(fs)
            v = _velocity(w_prev, w_curr, dt)
            if v >= _STRIKE_VELOCITY_THRESHOLD and w_curr is not None and w_prev is not None:
                landed   = self._strike_landed(w_curr, fs, "upper")
                subtype  = self._classify_punch_subtype(w_prev, w_curr, fs, wrist_fn)
                is_ground = striker_grounded or opp_grounded
                etype    = EventType.GROUND_STRIKE if is_ground else EventType.PUNCH
                events.append(FightEvent(
                    timestamp_secs   = fs.ts,
                    event_type       = etype,
                    limb             = Limb.FIST,
                    target_zone      = self._resolve_target_zone(w_curr, fs),
                    outcome          = Outcome.LANDED if landed else Outcome.MISSED,
                    punch_subtype    = subtype if not is_ground else None,
                    is_ground_strike = is_ground,
                    confidence       = min(_CONFIDENCE_STRIKE_RULE + v, 0.9),
                ))
                break  # one punch event per frame

        # --- Kick (ankle velocity) ---
        for ankle_fn in (FrameState.ankle_l, FrameState.ankle_r):
            a_prev = ankle_fn(prev)
            a_curr = ankle_fn(fs)
            v = _velocity(a_prev, a_curr, dt)
            if v >= _STRIKE_VELOCITY_THRESHOLD and a_curr is not None:
                target = self._resolve_target_zone(a_curr, fs)
                limb   = Limb.FOOT if target == TargetZone.HEAD else Limb.SHIN
                landed = self._strike_landed(a_curr, fs, "lower")
                events.append(FightEvent(
                    timestamp_secs = fs.ts,
                    event_type     = EventType.KICK,
                    limb           = limb,
                    target_zone    = target,
                    outcome        = Outcome.LANDED if landed else Outcome.MISSED,
                    confidence     = min(_CONFIDENCE_STRIKE_RULE + v, 0.9),
                ))
                break

        return events

    def _classify_punch_subtype(
        self,
        prev_pt: Tuple[float, float],
        curr_pt: Tuple[float, float],
        fs: FrameState,
        wrist_fn,                        # FrameState.wrist_l or wrist_r
    ) -> Optional[PunchSubtype]:
        """
        Geometry-based punch subtype from wrist displacement vector.

        Coordinate system (normalised):
          x: 0=left edge, 1=right edge
          y: 0=top edge, 1=bottom edge (y increases downward)

        Displacement (dx, dy):
          dx > 0  → moving right  (toward opponent if fighter faces right)
          dy < 0  → moving up     (upward in image = upward in reality)

        Lead hand: ankle closer to opponent
        """
        dx = curr_pt[0] - prev_pt[0]
        dy = curr_pt[1] - prev_pt[1]   # negative = upward
        total = math.sqrt(dx**2 + dy**2)
        if total < 1e-6:
            return None

        lateral_ratio = abs(dx) / total
        upward_ratio  = max(-dy, 0) / total   # upward component
        forward_ratio = 1.0 - lateral_ratio   # proxy for straight

        # Uppercut: dominant upward motion
        if upward_ratio >= _UPPERCUT_UPWARD_RATIO:
            return PunchSubtype.UPPERCUT

        # Hook: dominant lateral motion
        if lateral_ratio >= _HOOK_LATERAL_RATIO:
            return PunchSubtype.HOOK

        # Jab vs Cross: determine lead hand
        # Lead ankle = ankle closer to opponent
        is_left_wrist = (wrist_fn is FrameState.wrist_l)
        if fs.opp is not None:
            opp_is_right   = fs.opp.cx > fs.obs.cx
            left_is_lead   = (fs.obs.keypoints.left_ankle[0] > fs.obs.keypoints.right_ankle[0]) \
                             if (fs.obs.keypoints and opp_is_right) else \
                             (fs.obs.keypoints.left_ankle[0] < fs.obs.keypoints.right_ankle[0]) \
                             if fs.obs.keypoints else True
            lead_is_left   = left_is_lead
        else:
            lead_is_left   = True  # default orthodox

        if is_left_wrist and lead_is_left:
            return PunchSubtype.JAB
        if not is_left_wrist and not lead_is_left:
            return PunchSubtype.JAB
        return PunchSubtype.CROSS

    def _strike_landed(
        self, point: Tuple[float, float], fs: FrameState, region: str
    ) -> bool:
        """Heuristic: point is within opponent bbox."""
        if fs.opp is None:
            return False
        x1, y1, x2, y2 = fs.opp.bbox
        px = point[0] * fs.frame_w
        py = point[1] * fs.frame_h
        return x1 <= px <= x2 and y1 <= py <= y2

    def _resolve_target_zone(
        self, point: Tuple[float, float], fs: FrameState
    ) -> TargetZone:
        """Classify target zone by comparing strike y to opponent body thirds."""
        if fs.opp is None or fs.opp.keypoints is None:
            return TargetZone.UNKNOWN
        kp = fs.opp.keypoints
        # Rough thirds: above shoulder = head, shoulder-hip = body, below hip = leg
        shoulder_y = (kp.left_shoulder[1] + kp.right_shoulder[1]) / 2 / fs.frame_h
        hip_y      = (kp.left_hip[1] + kp.right_hip[1]) / 2 / fs.frame_h
        strike_y   = point[1]
        if strike_y < shoulder_y * 1.1:
            return TargetZone.HEAD
        if strike_y < hip_y * 1.1:
            return TargetZone.BODY
        return TargetZone.LEG

    # ------------------------------------------------------------------
    # Knockdown
    # ------------------------------------------------------------------

    def _detect_knockdown(self, fs: FrameState) -> List[FightEvent]:
        events: List[FightEvent] = []
        if not self._history:
            self._floored_frames = 0
            return events

        prev = self._history[-1]

        if fs.is_floored():
            self._floored_frames += 1
            # First frame down → knockdown
            if not prev.is_floored() and not self._kd_emitted:
                events.append(FightEvent(
                    timestamp_secs = fs.ts,
                    event_type     = EventType.KNOCKDOWN,
                    confidence     = 0.75,
                ))
                self._kd_emitted = True
            # Stayed down long enough → upgrade to KO
            elif self._kd_emitted and self._floored_frames >= _KO_FLOOR_FRAMES:
                events.append(FightEvent(
                    timestamp_secs = fs.ts,
                    event_type     = EventType.KO,
                    confidence     = 0.80,
                ))
                # Reset so we don't keep emitting
                self._kd_emitted     = False
                self._floored_frames = 0
        else:
            # Fighter back up
            self._floored_frames = 0
            self._kd_emitted     = False

        return events

    # ------------------------------------------------------------------
    # Takedown
    # ------------------------------------------------------------------

    def _detect_takedown(self, fs: FrameState) -> List[FightEvent]:
        if not self._history:
            return []
        prev = self._history[-1]

        # Attacker was standing and drove opponent to the ground
        if fs.opp is None:
            return []

        opp_was_up   = not prev.is_grounded()
        opp_is_down  = fs.opp.keypoints is not None and \
                       (fs.opp.keypoints.left_hip[1] / fs.frame_h > _GROUND_HIP_THRESHOLD)

        if opp_was_up and opp_is_down and not fs.is_grounded():
            return [FightEvent(
                timestamp_secs=fs.ts,
                event_type=EventType.TAKEDOWN,
                confidence=0.65,
            )]

        # Stuffed: attacker went low but came back up, opponent never hit ground
        if fs.is_grounded() and not prev.is_grounded() and not opp_is_down:
            return [FightEvent(
                timestamp_secs=fs.ts,
                event_type=EventType.TAKEDOWN_STUFFED,
                confidence=0.60,
            )]
        return []

    # ------------------------------------------------------------------
    # Grappling position (state machine)
    # ------------------------------------------------------------------

    def _detect_position(self, fs: FrameState) -> List[FightEvent]:
        new_pos = self._infer_position(fs)
        if new_pos == self._position:
            return []

        events = [FightEvent(
            timestamp_secs=fs.ts,
            event_type=EventType.POSITION_CHANGE,
            position=new_pos,
            confidence=_CONFIDENCE_POSITION_RULE,
        )]

        # Sweep / reversal detection: bottom fighter becomes top
        if self._position in (Position.FULL_GUARD, Position.HALF_GUARD) \
                and new_pos in (Position.SIDE_CONTROL, Position.FULL_GUARD):
            events.append(FightEvent(
                timestamp_secs=fs.ts,
                event_type=EventType.SWEEP,
                confidence=0.6,
            ))
        elif self._position in (Position.SIDE_CONTROL, Position.BACK_CONTROL) \
                and new_pos == Position.STANDING:
            events.append(FightEvent(
                timestamp_secs=fs.ts,
                event_type=EventType.REVERSAL,
                confidence=0.6,
            ))

        self._position  = new_pos
        self._pos_start = fs.ts
        return events

    def _infer_position(self, fs: FrameState) -> Position:
        """Heuristic position inference from body geometry."""
        target_grounded = fs.is_grounded()
        opp_grounded    = False
        if fs.opp and fs.opp.keypoints:
            opp_grounded = fs.opp.keypoints.left_hip[1] / fs.frame_h > _GROUND_HIP_THRESHOLD

        dist = fs.dist_to_opp()

        # Both standing, close → clinch
        if not target_grounded and not opp_grounded:
            if dist is not None and dist < _GRAPPLE_PROXIMITY:
                return Position.CLINCH
            return Position.STANDING

        # Target grounded, opponent not → opponent on top
        if target_grounded and not opp_grounded:
            return self._classify_guard(fs, bottom=True)

        # Target standing, opponent grounded → target on top
        if not target_grounded and opp_grounded:
            return self._classify_guard(fs, bottom=False)

        # Both grounded → back-take or scramble, default to half guard
        return Position.HALF_GUARD

    def _classify_guard(self, fs: FrameState, bottom: bool) -> Position:
        """
        Rough guard classification based on hip spread and limb proximity.
        Without a trained classifier this is an approximation.
        """
        if fs.opp is None or fs.opp.keypoints is None:
            return Position.HALF_GUARD

        opp_kp = fs.opp.keypoints
        # Hip spread as proxy for guard tightness
        hip_spread = abs(opp_kp.left_hip[0] - opp_kp.right_hip[0]) / fs.frame_w
        dist = fs.dist_to_opp() or 0.2

        if dist < _GRAPPLE_PROXIMITY and hip_spread > 0.1:
            return Position.BACK_CONTROL
        if dist < 0.22:
            return Position.SIDE_CONTROL if not bottom else Position.FULL_GUARD
        return Position.HALF_GUARD

    # ------------------------------------------------------------------
    # Clinch
    # ------------------------------------------------------------------

    def _detect_clinch(self, fs: FrameState) -> List[FightEvent]:
        if not self._history:
            return []
        prev = self._history[-1]
        dist = fs.dist_to_opp()
        prev_dist = prev.dist_to_opp()
        if dist is None or prev_dist is None:
            return []

        events = []
        if prev_dist >= _CLINCH_DISTANCE > dist:
            events.append(FightEvent(
                timestamp_secs=fs.ts,
                event_type=EventType.CLINCH_ENTRY,
                position=Position.CLINCH,
                confidence=0.65,
            ))
        elif prev_dist < _CLINCH_DISTANCE <= dist:
            events.append(FightEvent(
                timestamp_secs=fs.ts,
                event_type=EventType.CLINCH_BREAK,
                confidence=0.65,
            ))
        return events

    # ------------------------------------------------------------------
    # Cage control
    # ------------------------------------------------------------------

    def _detect_cage(self, fs: FrameState) -> List[FightEvent]:
        if not self._history:
            return []
        prev = self._history[-1]
        was_cage = prev.near_cage_left() or prev.near_cage_right()
        is_cage  = fs.near_cage_left() or fs.near_cage_right()

        if not was_cage and is_cage:
            return [FightEvent(
                timestamp_secs=fs.ts,
                event_type=EventType.CAGE_CONTROL_START,
                position=Position.CAGE_GRAPPLING,
                confidence=0.70,
            )]
        if was_cage and not is_cage:
            return [FightEvent(
                timestamp_secs=fs.ts,
                event_type=EventType.CAGE_CONTROL_END,
                confidence=0.70,
            )]
        return []
