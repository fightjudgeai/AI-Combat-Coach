"""
vision/aggression.py
Pressure + aggression scorer.

Pressure  = how consistently the fighter advances and dictates distance
Aggression = volume and intensity of offensive output

Both are scored 0–100 and stored in fight_event_summary.
"""
from __future__ import annotations

from typing import List

from .events import EventType, FightEvent, Outcome


def compute_pressure_aggression(
    events: List[FightEvent],
    frame_snapshots_cx: List[tuple[float, float]],   # list of (ts, cx) for this fighter
    video_duration_secs: float,
) -> tuple[float, float]:
    """
    Returns (pressure_score, aggression_score) in [0, 100].

    pressure_score:
        Combines:
          - % of frame pairs where fighter advanced toward opponent (weighted 60%)
          - % of time in clinch / cage control positions (weighted 20%)
          - Takedown attempt rate per minute (weighted 20%)

    aggression_score:
        Combines:
          - Strikes attempted per minute (volume, weighted 50%)
          - Strikes landed % of total (accuracy incentive, weighted 25%)
          - Knockdowns + takedowns scored per minute (weighted 25%)
    """
    duration_mins = max(video_duration_secs / 60.0, 0.01)

    # -----------------------------------------------------------------------
    # Pressure
    # -----------------------------------------------------------------------
    # 1. Advance ratio from cx snapshots
    snaps = [(t, cx) for t, cx in frame_snapshots_cx]
    advance_ratio = 0.5  # default neutral
    if len(snaps) >= 4:
        opp_cx_list = []
        # We don't have opponent cx here; use direction-of-movement heuristic:
        # treat consistent forward motion as pressure (cx change toward centre)
        movements = [snaps[i][1] - snaps[i-1][1] for i in range(1, len(snaps))]
        # Net forward = moving toward centre (from either edge)
        first_cx   = snaps[0][1]
        toward_centre = (0.5 - first_cx)  # positive if fighter starts left
        signed_moves   = [m * math.copysign(1, toward_centre) for m in movements]
        advances       = sum(1 for m in signed_moves if m > 0)
        advance_ratio  = advances / len(signed_moves)

    # 2. Clinch + cage time ratio
    clinch_events   = [e for e in events if e.position in (_CLINCH_POSITIONS)]
    cc_entries      = len([e for e in events if e.event_type == EventType.CAGE_CONTROL_START])
    clinch_ratio    = min(len(clinch_events) / max(duration_mins * 10, 1), 1.0)

    # 3. Takedown attempts per minute
    td_attempts     = len([e for e in events if e.event_type in (EventType.TAKEDOWN, EventType.TAKEDOWN_STUFFED)])
    td_rate         = min(td_attempts / duration_mins / 5.0, 1.0)  # cap at 5/min = 100%

    pressure = (
        advance_ratio   * 60.0 +
        clinch_ratio    * 20.0 +
        td_rate         * 20.0
    )

    # -----------------------------------------------------------------------
    # Aggression
    # -----------------------------------------------------------------------
    strike_types = {EventType.PUNCH, EventType.KICK, EventType.ELBOW_STRIKE, EventType.KNEE_STRIKE}
    all_strikes  = [e for e in events if e.event_type in strike_types]
    landed       = [e for e in all_strikes if e.outcome == Outcome.LANDED]
    kd_td        = [e for e in events if e.event_type in (EventType.KNOCKDOWN, EventType.KO, EventType.TAKEDOWN)]

    strikes_per_min  = len(all_strikes) / duration_mins
    volume_score     = min(strikes_per_min / 20.0, 1.0)   # 20 strikes/min = 100%
    accuracy         = len(landed) / max(len(all_strikes), 1)
    finishing_rate   = min(len(kd_td) / duration_mins / 2.0, 1.0)  # 2/min = 100%

    aggression = (
        volume_score    * 50.0 +
        accuracy        * 25.0 +
        finishing_rate  * 25.0
    )

    return round(min(pressure, 100.0), 2), round(min(aggression, 100.0), 2)


# ---------------------------------------------------------------------------
# Summarise all events into a fight_event_summary dict
# ---------------------------------------------------------------------------

from .events import Position

_CLINCH_POSITIONS = {Position.CLINCH, Position.CAGE_GRAPPLING}

import math


def build_summary(
    events: List[FightEvent],
    frame_snapshots_cx: List[tuple[float, float]],
    video_duration_secs: float,
    sample_interval: float,
) -> dict:
    """
    Aggregate a flat list of FightEvents into the fight_event_summary columns.
    """
    pressure, aggression = compute_pressure_aggression(
        events, frame_snapshots_cx, video_duration_secs
    )

    def count(
        etype: EventType,
        outcome: "Outcome | None" = None,
        target: "TargetZone | None" = None,
        punch_subtype: "PunchSubtype | None" = None,
        is_ground: bool | None = None,
    ) -> int:
        from .events import TargetZone
        total = 0
        for e in events:
            if e.event_type != etype:
                continue
            if outcome is not None and e.outcome != outcome:
                continue
            if target is not None and e.target_zone != target:
                continue
            if punch_subtype is not None and e.punch_subtype != punch_subtype:
                continue
            if is_ground is not None and e.is_ground_strike != is_ground:
                continue
            total += 1
        return total

    from .events import TargetZone, Outcome as O, PunchSubtype

    # Position time: count position_change events, compute duration between them
    pos_time = _compute_position_times(events, video_duration_secs, sample_interval)

    return {
        "punches_attempted":        count(EventType.PUNCH),
        "kicks_attempted":          count(EventType.KICK),
        "elbow_strikes_attempted":  count(EventType.ELBOW_STRIKE),
        "knee_strikes_attempted":   count(EventType.KNEE_STRIKE),
        "punches_landed":           count(EventType.PUNCH,        O.LANDED),
        "kicks_landed_head":        count(EventType.KICK,         O.LANDED, TargetZone.HEAD),
        "kicks_landed_body":        count(EventType.KICK,         O.LANDED, TargetZone.BODY),
        "kicks_landed_leg":         count(EventType.KICK,         O.LANDED, TargetZone.LEG),
        "elbows_landed":            count(EventType.ELBOW_STRIKE,  O.LANDED),
        "knees_landed":             count(EventType.KNEE_STRIKE,   O.LANDED),
        "punches_missed":           count(EventType.PUNCH,        O.MISSED),
        "kicks_missed":             count(EventType.KICK,         O.MISSED),
        "elbows_missed":            count(EventType.ELBOW_STRIKE,  O.MISSED),
        "knees_missed":             count(EventType.KNEE_STRIKE,   O.MISSED),
        "jabs_attempted":            count(EventType.PUNCH, punch_subtype=PunchSubtype.JAB),
        "jabs_landed":               count(EventType.PUNCH, O.LANDED,  punch_subtype=PunchSubtype.JAB),
        "crosses_attempted":         count(EventType.PUNCH, punch_subtype=PunchSubtype.CROSS),
        "crosses_landed":            count(EventType.PUNCH, O.LANDED,  punch_subtype=PunchSubtype.CROSS),
        "hooks_attempted":           count(EventType.PUNCH, punch_subtype=PunchSubtype.HOOK),
        "hooks_landed":              count(EventType.PUNCH, O.LANDED,  punch_subtype=PunchSubtype.HOOK),
        "uppercuts_attempted":       count(EventType.PUNCH, punch_subtype=PunchSubtype.UPPERCUT),
        "uppercuts_landed":          count(EventType.PUNCH, O.LANDED,  punch_subtype=PunchSubtype.UPPERCUT),
        "ground_strikes_attempted":  count(EventType.GROUND_STRIKE),
        "ground_strikes_landed":     count(EventType.GROUND_STRIKE, O.LANDED),
        "ko_scored":                 count(EventType.KO),
        "knockdowns_scored":         count(EventType.KNOCKDOWN),
        "takedowns_landed":         count(EventType.TAKEDOWN),
        "takedowns_stuffed":        count(EventType.TAKEDOWN_STUFFED),
        "clinch_entries":           count(EventType.CLINCH_ENTRY),
        "cage_control_sequences":   count(EventType.CAGE_CONTROL_START),
        "time_in_half_guard":       pos_time.get(Position.HALF_GUARD, 0),
        "time_in_full_guard":       pos_time.get(Position.FULL_GUARD, 0),
        "time_in_side_control":     pos_time.get(Position.SIDE_CONTROL, 0),
        "time_in_back_control":     pos_time.get(Position.BACK_CONTROL, 0),
        "time_in_clinch":           pos_time.get(Position.CLINCH, 0),
        "time_in_cage_grappling":   pos_time.get(Position.CAGE_GRAPPLING, 0),
        "submission_attempts":      count(EventType.SUBMISSION_ATTEMPT),
        "submissions_completed":    count(EventType.SUBMISSION),
        "sweeps":                   count(EventType.SWEEP),
        "reversals":                count(EventType.REVERSAL),
        "pressure_score":           pressure,
        "aggression_score":         aggression,
    }


def _compute_position_times(
    events: List[FightEvent],
    total_duration: float,
    sample_interval: float,
) -> dict:
    """
    Walk through position_change events and accumulate time spent in each Position.
    """
    pos_events = [e for e in events if e.event_type == EventType.POSITION_CHANGE and e.position]
    pos_events.sort(key=lambda e: e.timestamp_secs)

    times: dict[Position, float] = {}
    current_pos = Position.STANDING
    current_start = 0.0

    for e in pos_events:
        duration = e.timestamp_secs - current_start
        times[current_pos] = times.get(current_pos, 0.0) + duration
        current_pos   = e.position
        current_start = e.timestamp_secs

    # Final segment
    times[current_pos] = times.get(current_pos, 0.0) + (total_duration - current_start)
    return times
