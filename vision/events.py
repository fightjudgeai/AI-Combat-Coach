"""
vision/events.py
Canonical event types, body-part labels, and the FightEvent dataclass.
Single source of truth — used by classifier, writer, and the YOLO label map.
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations — mirror the DB CHECK constraints exactly
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    # Strikes
    PUNCH          = "punch"
    KICK           = "kick"
    ELBOW_STRIKE   = "elbow_strike"
    KNEE_STRIKE    = "knee_strike"
    # Finishing
    KNOCKDOWN      = "knockdown"
    # Takedown game
    TAKEDOWN       = "takedown"
    TAKEDOWN_STUFFED = "takedown_stuffed"
    # Clinch
    CLINCH_ENTRY   = "clinch_entry"
    CLINCH_BREAK   = "clinch_break"
    # Position
    POSITION_CHANGE = "position_change"
    # Submission
    SUBMISSION_ATTEMPT = "submission_attempt"
    SUBMISSION     = "submission"
    # Scrambles
    SWEEP          = "sweep"
    REVERSAL       = "reversal"
    # Cage
    CAGE_CONTROL_START = "cage_control_start"
    CAGE_CONTROL_END   = "cage_control_end"


class Limb(str, Enum):
    FIST   = "fist"
    GLOVE  = "glove"   # open-hand / guard-shell hit
    ELBOW  = "elbow"
    KNEE   = "knee"
    FOOT   = "foot"
    SHIN   = "shin"


class TargetZone(str, Enum):
    HEAD   = "head"
    BODY   = "body"
    LEG    = "leg"
    UNKNOWN = "unknown"


class Outcome(str, Enum):
    LANDED  = "landed"
    MISSED  = "missed"
    BLOCKED = "blocked"


class Position(str, Enum):
    STANDING       = "standing"
    CLINCH         = "clinch"
    HALF_GUARD     = "half_guard"
    FULL_GUARD     = "full_guard"
    SIDE_CONTROL   = "side_control"
    BACK_CONTROL   = "back_control"
    CAGE_GRAPPLING = "cage_grappling"


# ---------------------------------------------------------------------------
# YOLO custom-training class labels
# Two detection heads:
#   HEAD_A: body-part bounding boxes (for strike target resolution)
#   HEAD_B: action / position classification per fighter crop
# ---------------------------------------------------------------------------

# Body-part bbox classes (used as YOLO object detection targets)
BODY_PART_CLASSES: list[str] = [
    "fighter",          # 0 — full-body detection (always present)
    "head",             # 1
    "glove",            # 2
    "body_torso",       # 3
    "elbow",            # 4
    "knee",             # 5
    "foot",             # 6
    "shin",             # 7
]

# Action / position classification labels (for a per-crop classifier head)
ACTION_CLASSES: list[str] = [
    "standing",             # 0
    "punch_throwing",       # 1
    "kick_throwing",        # 2
    "elbow_throwing",       # 3
    "knee_throwing",        # 4
    "clinch",               # 5
    "takedown_attempt",     # 6
    "takedown_defense",     # 7
    "half_guard_top",       # 8
    "half_guard_bottom",    # 9
    "full_guard_top",       # 10
    "full_guard_bottom",    # 11
    "side_control_top",     # 12
    "side_control_bottom",  # 13
    "back_control_top",     # 14
    "back_control_bottom",  # 15
    "submission_attempt",   # 16
    "cage_grappling",       # 17
    "sweep",                # 18
    "reversal",             # 19
    "knockdown",            # 20
]

# Roboflow / Label Studio annotation guide mapping
ANNOTATION_GUIDE: dict[str, str] = {
    "fighter":              "Full fighter body bounding box. One per fighter per frame.",
    "head":                 "Fighter's head only.",
    "glove":                "Gloved fist / hand region.",
    "body_torso":           "Torso from shoulders to hips.",
    "elbow":                "Elbow joint + forearm tip region.",
    "knee":                 "Knee joint + lower-leg region.",
    "foot":                 "Foot / ankle region.",
    "shin":                 "Shin bone — used in leg kicks.",
    "punch_throwing":       "Arm extended >90° from shoulder, hand toward opponent.",
    "kick_throwing":        "Leg raised and extending toward opponent.",
    "elbow_throwing":       "Elbow bent, driving toward opponent.",
    "knee_throwing":        "Knee raised and thrusting toward opponent (usually in clinch).",
    "clinch":               "Both fighters' bodies in contact at close range.",
    "takedown_attempt":     "Attacker's hips below opponent, arms wrapping legs.",
    "takedown_defense":     "Defender sprawling, underhooks, or blocking double-leg.",
    "half_guard_top":       "Top fighter with one leg trapped between opponent's legs.",
    "half_guard_bottom":    "Bottom fighter with one leg locking top fighter's leg.",
    "full_guard_top":       "Top fighter inside opponent's closed or open guard.",
    "full_guard_bottom":    "Bottom fighter with both legs wrapped around opponent.",
    "side_control_top":     "Top fighter perpendicular to grounded opponent, hip to hip.",
    "side_control_bottom":  "Bottom fighter flat, opponent across chest.",
    "back_control_top":     "Fighter behind seated/prone opponent with hooks in.",
    "back_control_bottom":  "Opponent with back taken, facing away.",
    "submission_attempt":   "Fighter applying a choke, armlock, or leglock.",
    "cage_grappling":       "Both fighters pressed against the cage fence.",
    "sweep":                "Bottom fighter reverses to top using leverage.",
    "reversal":             "Either fighter flips position (general).",
    "knockdown":            "Fighter touches canvas from a strike (not a slip).",
}


# ---------------------------------------------------------------------------
# FightEvent dataclass — in-memory representation before DB insert
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class FightEvent:
    timestamp_secs: float
    event_type:     EventType
    confidence:     float = 0.0
    limb:           Optional[Limb]        = None
    target_zone:    Optional[TargetZone]  = None
    outcome:        Optional[Outcome]     = None
    position:       Optional[Position]    = None
    round_num:      Optional[int]         = None

    def to_db_row(self, job_id: str, fighter_id: Optional[str] = None) -> dict:
        return {
            "job_id":         job_id,
            "fighter_id":     fighter_id,
            "timestamp_secs": self.timestamp_secs,
            "round_num":      self.round_num,
            "event_type":     self.event_type.value,
            "limb":           self.limb.value if self.limb else None,
            "target_zone":    self.target_zone.value if self.target_zone else None,
            "outcome":        self.outcome.value if self.outcome else None,
            "position":       self.position.value if self.position else None,
            "confidence":     self.confidence,
        }
