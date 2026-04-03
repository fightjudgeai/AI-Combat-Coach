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
    GROUND_STRIKE  = "ground_strike"      # either fighter grounded during strike
    # Finishing
    KNOCKDOWN      = "knockdown"
    KO             = "ko"                 # fighter doesn't recover within window
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


class PunchSubtype(str, Enum):
    JAB       = "jab"        # lead hand, straight, horizontal
    CROSS     = "cross"      # rear hand, straight, horizontal
    HOOK      = "hook"       # lateral arc, elbow bent ~90°
    UPPERCUT  = "uppercut"   # upward trajectory, tight arc


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
    "jab_throwing",         # 1  — lead hand straight
    "cross_throwing",       # 2  — rear hand straight
    "hook_throwing",        # 3  — lateral arc
    "uppercut_throwing",    # 4  — upward arc
    "kick_throwing",        # 5
    "elbow_throwing",       # 6
    "knee_throwing",        # 7
    "ground_strike",        # 8  — striking a grounded opponent
    "clinch",               # 9
    "takedown_attempt",     # 10
    "takedown_defense",     # 11
    "half_guard_top",       # 12
    "half_guard_bottom",    # 13
    "full_guard_top",       # 14
    "full_guard_bottom",    # 15
    "side_control_top",     # 16
    "side_control_bottom",  # 17
    "back_control_top",     # 18
    "back_control_bottom",  # 19
    "submission_attempt",   # 20
    "cage_grappling",       # 21
    "sweep",                # 22
    "reversal",             # 23
    "knockdown",            # 24
    "ko",                   # 25  — fighter does not rise
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
    "ko":                   "Fighter knocked out — stays on canvas, fight stopped.",
    "jab_throwing":         "Lead hand extends straight forward at speed; arm nearly fully extended.",
    "cross_throwing":       "Rear hand straight punch; shoulder rotation clearly visible.",
    "hook_throwing":        "Elbow bent ~90°, arm sweeps laterally toward opponent's head/body.",
    "uppercut_throwing":    "Fist rises upward with bent elbow, typically targeting chin or body.",
    "ground_strike":        "Striker throws punches/elbows while opponent is grounded (GnP).",
}


# ---------------------------------------------------------------------------
# FightEvent dataclass — in-memory representation before DB insert
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class FightEvent:
    timestamp_secs:  float
    event_type:      EventType
    confidence:      float = 0.0
    limb:            Optional[Limb]         = None
    target_zone:     Optional[TargetZone]   = None
    outcome:         Optional[Outcome]      = None
    position:        Optional[Position]     = None
    punch_subtype:   Optional[PunchSubtype] = None
    is_ground_strike: bool                  = False
    round_num:       Optional[int]          = None

    def to_db_row(self, job_id: str, fighter_id: Optional[str] = None) -> dict:
        return {
            "job_id":           job_id,
            "fighter_id":       fighter_id,
            "timestamp_secs":   self.timestamp_secs,
            "round_num":        self.round_num,
            "event_type":       self.event_type.value,
            "limb":             self.limb.value if self.limb else None,
            "target_zone":      self.target_zone.value if self.target_zone else None,
            "outcome":          self.outcome.value if self.outcome else None,
            "position":         self.position.value if self.position else None,
            "punch_subtype":    self.punch_subtype.value if self.punch_subtype else None,
            "is_ground_strike": self.is_ground_strike,
            "confidence":       self.confidence,
        }
