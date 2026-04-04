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
# COCO keypoint indices
# ---------------------------------------------------------------------------
# 0=nose  1-4=eyes/ears  5=left_shoulder  6=right_shoulder
# 7=left_elbow  8=right_elbow  9=left_wrist  10=right_wrist
# 11=left_hip  12=right_hip  13=left_knee  14=right_knee
# 15=left_ankle  16=right_ankle

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_STRIKE_VELOCITY_THRESHOLD   = 0.04   # wrist/ankle displacement per frame (fraction of frame)
_ELBOW_VELOCITY_THRESHOLD    = 0.035  # elbows move slightly less than wrists
_KNEE_VELOCITY_THRESHOLD     = 0.035  # knees in clinch
_ELBOW_RANGE_MULTIPLIER      = 2.0    # elbows fire within this * CLINCH_DISTANCE
_KNEE_RANGE_MULTIPLIER       = 1.5    # knees fire within clinch range
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

# Single-frame pose geometry thresholds (punch / kick extension-based detection)
_PUNCH_EXTENSION_RATIO       = 1.2    # wrist-to-ipsi-shoulder distance / shoulder-width
_KICK_HIP_RAISE_RATIO        = 0.10   # ankle must be at least this far above hip_y (normalised)
_KICK_MAX_ANKLE_Y            = 0.78   # ankle must be ABOVE this y-fraction (below = on ground)
_PUNCH_GUARD_WX_BUFFER       = 0.03   # ignore wrists this close to the fighter centre-x (guard pos)


# ---------------------------------------------------------------------------
# Frame-level snapshot including raw keypoint array access
# ---------------------------------------------------------------------------

class FrameState:
    """
    Wraps FighterObservation for one frame, providing normalised keypoint
    accessors and geometric helpers used by the classifier.

    All coordinate accessors return (x, y) in [0, 1] relative to frame
    dimensions, or None if the keypoint confidence is too low.
    """
    __slots__ = ("ts", "obs", "opp", "frame_w", "frame_h")

    def __init__(
        self,
        ts: float,
        obs: FighterObservation,
        opp: Optional[FighterObservation],
        frame_w: int,
        frame_h: int,
    ):
        self.ts      = ts
        self.obs     = obs
        self.opp     = opp
        self.frame_w = frame_w
        self.frame_h = frame_h

    # ------------------------------------------------------------------
    # Keypoint accessors (normalised 0-1)
    # ------------------------------------------------------------------

    def _norm(self, px: float, py: float) -> Tuple[float, float]:
        return px / self.frame_w, py / self.frame_h

    def _kp(
        self, idx: int, min_conf: float = 0.4
    ) -> Optional[Tuple[float, float]]:
        """Return normalised (x, y) for COCO keypoint index, or None."""
        kp = self.obs.keypoints
        if kp is None or kp.confidence[idx] < min_conf:
            return None
        return self._norm(kp.raw_xy[idx, 0], kp.raw_xy[idx, 1])

    # Head
    def nose(self)    -> Optional[Tuple[float, float]]: return self._kp(0)
    # Arms
    def wrist_l(self) -> Optional[Tuple[float, float]]: return self._kp(9)
    def wrist_r(self) -> Optional[Tuple[float, float]]: return self._kp(10)
    def elbow_l(self) -> Optional[Tuple[float, float]]: return self._kp(7)
    def elbow_r(self) -> Optional[Tuple[float, float]]: return self._kp(8)
    # Legs
    def knee_l(self)  -> Optional[Tuple[float, float]]: return self._kp(13)
    def knee_r(self)  -> Optional[Tuple[float, float]]: return self._kp(14)
    def ankle_l(self) -> Optional[Tuple[float, float]]: return self._kp(15)
    def ankle_r(self) -> Optional[Tuple[float, float]]: return self._kp(16)

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

    # Opponent keypoint helpers (for target zone resolution)
    def opp_nose(self) -> Optional[Tuple[float, float]]:
        if self.opp is None or self.opp.keypoints is None:
            return None
        kp = self.opp.keypoints
        if kp.confidence[0] < 0.35:
            return None
        return kp.raw_xy[0, 0] / self.frame_w, kp.raw_xy[0, 1] / self.frame_h

    # ------------------------------------------------------------------
    # Geometric helpers
    # ------------------------------------------------------------------

    def is_grounded(self) -> bool:
        """True when the fighter's hips are in the lower portion of the frame."""
        kp = self.obs.keypoints
        if kp is None:
            return False
        if kp.confidence[11] > 0.3:
            return kp.left_hip[1] / self.frame_h > _GROUND_HIP_THRESHOLD
        if kp.confidence[12] > 0.3:
            return kp.right_hip[1] / self.frame_h > _GROUND_HIP_THRESHOLD
        # Fallback: use tracked bbox centre
        return self.obs.cy > _GROUND_HIP_THRESHOLD

    def is_floored(self) -> bool:
        """True when the fighter is flat on the canvas (shoulders very low)."""
        kp = self.obs.keypoints
        if kp is None:
            return False
        if kp.confidence[5] > 0.3:
            return kp.left_shoulder[1] / self.frame_h > _KD_SHOULDER_THRESHOLD
        if kp.confidence[6] > 0.3:
            return kp.right_shoulder[1] / self.frame_h > _KD_SHOULDER_THRESHOLD
        return False

    def near_cage_left(self) -> bool:
        """True when the fighter is hugging the left wall of the octagon."""
        return self.obs.cx < _CAGE_EDGE_THRESHOLD

    def near_cage_right(self) -> bool:
        """True when the fighter is hugging the right wall of the octagon."""
        return self.obs.cx > (1.0 - _CAGE_EDGE_THRESHOLD)

    def dist_to_opp(self) -> Optional[float]:
        """Normalised Euclidean distance from target bbox centre to opponent."""
        if self.opp is None:
            return None
        dx = self.obs.cx - self.opp.cx
        dy = self.obs.cy - self.opp.cy
        return math.sqrt(dx * dx + dy * dy)


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
        events.extend(self._detect_elbow_strike(fs))
        events.extend(self._detect_knee_strike(fs))
        events.extend(self._detect_knockdown(fs))
        events.extend(self._detect_takedown(fs))
        events.extend(self._detect_position(fs))
        events.extend(self._detect_clinch(fs))
        events.extend(self._detect_cage(fs))
        events.extend(self._detect_submission_attempt(fs))

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
        """
        Pose-geometry strike detection (no inter-frame velocity needed).

        Punches: wrist is extended past a threshold relative to shoulder width
                 and wrist is forward of the fighter body toward the opponent.
        Kicks:   ankle is raised significantly above hip level.

        This works at any sample interval (including 2s) because it reads the
        pose in a single frame rather than measuring displacement across frames.
        """
        events: List[FightEvent] = []
        kp = fs.obs.keypoints
        if kp is None:
            return events

        striker_grounded = fs.is_grounded()
        opp_grounded = (
            fs.opp is not None
            and fs.opp.keypoints is not None
            and fs.opp.keypoints.left_hip[1] / fs.frame_h > _GROUND_HIP_THRESHOLD
        )

        # --- Shoulder-width scale (normalised) ---
        sh_l_conf = kp.confidence[5]
        sh_r_conf = kp.confidence[6]
        if sh_l_conf > 0.3 and sh_r_conf > 0.3:
            sh_l_x = kp.raw_xy[5, 0] / fs.frame_w
            sh_r_x = kp.raw_xy[6, 0] / fs.frame_w
            sh_l_y = kp.raw_xy[5, 1] / fs.frame_h
            sh_r_y = kp.raw_xy[6, 1] / fs.frame_h
            sh_width = max(abs(sh_l_x - sh_r_x), 0.06)   # min 6% frame to avoid div/0
            sh_mid_x = (sh_l_x + sh_r_x) / 2
            sh_mid_y = (sh_l_y + sh_r_y) / 2
        else:
            sh_width = 0.15
            sh_mid_x = fs.obs.cx
            sh_mid_y = fs.obs.cy - 0.1

        # --- Punch detection (wrist extension geometry) ---
        opp_cx = fs.opp.cx if fs.opp else None
        punch_detected = False
        for wrist_idx, sh_idx in ((9, 5), (10, 6)):   # (left wrist, left shoulder) / right
            if kp.confidence[wrist_idx] < 0.3:
                continue
            wx = kp.raw_xy[wrist_idx, 0] / fs.frame_w
            wy = kp.raw_xy[wrist_idx, 1] / fs.frame_h
            # Ipsilateral shoulder
            if kp.confidence[sh_idx] > 0.3:
                ex = kp.raw_xy[sh_idx, 0] / fs.frame_w
                ey = kp.raw_xy[sh_idx, 1] / fs.frame_h
            else:
                ex, ey = sh_mid_x, sh_mid_y
            ext_dist = math.sqrt((wx - ex)**2 + (wy - ey)**2)
            ext_ratio = ext_dist / sh_width

            # Wrist must be extended AND pointing toward opponent side
            if ext_ratio < _PUNCH_EXTENSION_RATIO:
                continue
            if opp_cx is not None:
                toward_opp = (opp_cx > sh_mid_x and wx > sh_mid_x + _PUNCH_GUARD_WX_BUFFER) or \
                             (opp_cx <= sh_mid_x and wx < sh_mid_x - _PUNCH_GUARD_WX_BUFFER)
                if not toward_opp:
                    continue

            wrist_norm = (wx, wy)
            landed   = self._strike_landed(wrist_norm, fs, "upper")
            is_ground = striker_grounded or opp_grounded
            etype    = EventType.GROUND_STRIKE if is_ground else EventType.PUNCH
            # Derive dummy prev-point for subtype: extrapolate from shoulder
            dummy_prev = (ex, ey)
            wrist_fn   = FrameState.wrist_l if wrist_idx == 9 else FrameState.wrist_r
            subtype    = self._classify_punch_subtype(dummy_prev, wrist_norm, fs, wrist_fn)
            events.append(FightEvent(
                timestamp_secs   = fs.ts,
                event_type       = etype,
                limb             = Limb.FIST,
                target_zone      = self._resolve_target_zone(wrist_norm, fs),
                outcome          = Outcome.LANDED if landed else Outcome.MISSED,
                punch_subtype    = subtype if not is_ground else None,
                is_ground_strike = is_ground,
                confidence       = min(_CONFIDENCE_STRIKE_RULE + (ext_ratio - _PUNCH_EXTENSION_RATIO) * 0.3, 0.9),
            ))
            punch_detected = True
            break  # one punch per frame

        # --- Kick detection (ankle raised above hip) ---
        hip_y = None
        if kp.confidence[11] > 0.3:
            hip_y = kp.raw_xy[11, 1] / fs.frame_h
        elif kp.confidence[12] > 0.3:
            hip_y = kp.raw_xy[12, 1] / fs.frame_h

        if hip_y is not None:
            for ankle_idx in (15, 16):
                if kp.confidence[ankle_idx] < 0.4:
                    continue
                ankle_x = kp.raw_xy[ankle_idx, 0] / fs.frame_w
                ankle_y = kp.raw_xy[ankle_idx, 1] / fs.frame_h

                # Ankle raised above hip by threshold AND not a ground-level ankle
                raise_amount = hip_y - ankle_y   # positive = ankle above hip (y inverted)
                if raise_amount < _KICK_HIP_RAISE_RATIO:
                    continue
                if ankle_y > _KICK_MAX_ANKLE_Y:  # ankle still near ground, not raised
                    continue

                ankle_norm = (ankle_x, ankle_y)
                target = self._resolve_target_zone(ankle_norm, fs)
                limb   = Limb.FOOT if target == TargetZone.HEAD else Limb.SHIN
                landed = self._strike_landed(ankle_norm, fs, "lower")
                events.append(FightEvent(
                    timestamp_secs = fs.ts,
                    event_type     = EventType.KICK,
                    limb           = limb,
                    target_zone    = target,
                    outcome        = Outcome.LANDED if landed else Outcome.MISSED,
                    confidence     = min(_CONFIDENCE_STRIKE_RULE + raise_amount * 0.5, 0.9),
                ))
                break  # one kick per frame

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
    # Elbow strike detection
    # ------------------------------------------------------------------

    def _detect_elbow_strike(self, fs: FrameState) -> List[FightEvent]:
        """
        Detect elbow strikes via elbow-keypoint velocity in close range.
        Elbows are typically deployed in clinch or from mid-range.
        """
        events: List[FightEvent] = []
        if not self._history:
            return events

        prev  = self._history[-1]
        dt    = max(fs.ts - prev.ts, 1e-3)
        dist  = fs.dist_to_opp() or 1.0

        # Only fire in elbow range (roughly 2× clinch distance)
        if dist > _CLINCH_DISTANCE * _ELBOW_RANGE_MULTIPLIER:
            return events

        for elbow_fn in (FrameState.elbow_l, FrameState.elbow_r):
            e_prev = elbow_fn(prev)
            e_curr = elbow_fn(fs)
            v = _velocity(e_prev, e_curr, dt)
            if v >= _ELBOW_VELOCITY_THRESHOLD and e_curr is not None:
                landed  = self._strike_landed(e_curr, fs, "upper")
                target  = self._resolve_target_zone(e_curr, fs)
                events.append(FightEvent(
                    timestamp_secs   = fs.ts,
                    event_type       = EventType.ELBOW_STRIKE,
                    limb             = Limb.ELBOW,
                    target_zone      = target,
                    outcome          = Outcome.LANDED if landed else Outcome.MISSED,
                    is_ground_strike = fs.is_grounded(),
                    confidence       = min(_CONFIDENCE_STRIKE_RULE + v * 0.8, 0.90),
                ))
                break  # one elbow event per frame
        return events

    # ------------------------------------------------------------------
    # Knee strike detection
    # ------------------------------------------------------------------

    def _detect_knee_strike(self, fs: FrameState) -> List[FightEvent]:
        """
        Detect knee strikes via knee-keypoint velocity.
        Knees are most common in clinch or Thai plum positions.
        """
        events: List[FightEvent] = []
        if not self._history:
            return events

        prev  = self._history[-1]
        dt    = max(fs.ts - prev.ts, 1e-3)
        dist  = fs.dist_to_opp() or 1.0
        in_clinch = (dist <= _CLINCH_DISTANCE * _KNEE_RANGE_MULTIPLIER)

        for knee_fn in (FrameState.knee_l, FrameState.knee_r):
            k_prev = knee_fn(prev)
            k_curr = knee_fn(fs)
            v = _velocity(k_prev, k_curr, dt)
            # Knees can also be thrown from mid-range (flying knee, etc.)
            if v >= _KNEE_VELOCITY_THRESHOLD and k_curr is not None:
                landed  = self._strike_landed(k_curr, fs, "body_head")
                target  = self._resolve_target_zone(k_curr, fs)
                events.append(FightEvent(
                    timestamp_secs   = fs.ts,
                    event_type       = EventType.KNEE_STRIKE,
                    limb             = Limb.KNEE,
                    target_zone      = target,
                    outcome          = Outcome.LANDED if landed else Outcome.MISSED,
                    is_ground_strike = fs.is_grounded() or (
                        fs.opp is not None and
                        fs.opp.keypoints is not None and
                        fs.opp.keypoints.left_hip[1] / fs.frame_h > _GROUND_HIP_THRESHOLD
                    ),
                    confidence       = min(
                        (_CONFIDENCE_STRIKE_RULE + v * 0.8) * (1.1 if in_clinch else 1.0),
                        0.90,
                    ),
                ))
                break
        return events

    # ------------------------------------------------------------------
    # Submission attempt detection
    # ------------------------------------------------------------------

    def _detect_submission_attempt(self, fs: FrameState) -> List[FightEvent]:
        """
        Heuristic: detect submission attempts when both fighters are in
        a ground position, one appears to have limb control (wrist near
        opponent hip/neck region).  Low confidence — this is a coarse signal
        that downstream ML should refine.
        """
        if not self._history:
            return []

        # Both fighters must be grounded
        if not fs.is_grounded():
            return []
        if fs.opp is None or fs.opp.keypoints is None:
            return []
        opp_grounded = (fs.opp.keypoints.left_hip[1] / fs.frame_h > _GROUND_HIP_THRESHOLD)
        if not opp_grounded:
            return []

        # Positional prerequisite: body contact (side_control / back_control / guard)
        in_ground_pos = self._position in (
            Position.HALF_GUARD, Position.FULL_GUARD,
            Position.SIDE_CONTROL, Position.BACK_CONTROL,
        )
        if not in_ground_pos:
            return []

        # Wrist near opponent neck region (y << opponent shoulder_y)
        opp_kp = fs.opp.keypoints
        shoulder_y = (opp_kp.left_shoulder[1] + opp_kp.right_shoulder[1]) / 2 / fs.frame_h

        for wrist_fn in (FrameState.wrist_l, FrameState.wrist_r):
            w = wrist_fn(fs)
            if w is None:
                continue
            # Wrist above (lower y value) or at opponent shoulder → choke attempt region
            if w[1] <= shoulder_y + 0.05:
                return [FightEvent(
                    timestamp_secs = fs.ts,
                    event_type     = EventType.SUBMISSION_ATTEMPT,
                    position       = self._position,
                    confidence     = 0.45,   # low — heuristic only
                )]
        return []

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
