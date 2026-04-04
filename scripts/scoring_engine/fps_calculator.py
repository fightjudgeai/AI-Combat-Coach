from dataclasses import dataclass


@dataclass
class RoundResult:
    round_number: int
    rps: float
    seconds: int


@dataclass
class FPSResult:
    fps: float
    fps_tier: str
    weighted_rps: float
    cardio_45: float | None          # only populated for 5-round fights
    finish_quality_score: float | None  # informational FQT sub-score (0–100)
    floor_applied: float | None      # non-None if a winner floor was enforced
    cap_applied: float | None        # non-None if a loser cap was enforced
    fight_total_seconds: int


# ─────────────────────────────────────────────────────────────────────────────
# FINISH QUALITY / TIME sub-scores  (informational — the 8% FQT component)
# These are NOT FPS floors/caps.  They represent the quality of the finish
# on a 0–100 scale that feeds the FinishQualityTime concept.
# ─────────────────────────────────────────────────────────────────────────────
FINISH_QUALITY_SCORES_WINNER = {
    # key: (method_key, finish_round, time_bucket)
    ('ko',  1, 'sub_60'):  98,
    ('sub', 1, 'sub_60'):  96,
    ('ko',  1, '61_90'):   95,
    ('sub', 1, '61_90'):   93,
    ('ko',  1, 'post_90'): 92,
    ('sub', 1, 'post_90'): 90,
    ('ko',  2, None):      86,
    ('sub', 2, None):      84,
    ('ko',  3, None):      80,
    ('sub', 3, None):      78,
    ('ko',  4, None):      77,
    ('sub', 4, None):      75,
    ('ko',  5, None):      74,
    ('sub', 5, None):      72,
    ('ud',  None, None):   68,
    ('sd',  None, None):   60,
    ('md',  None, None):   60,
}

FINISH_QUALITY_SCORES_LOSER = {1: 20, 2: 28, 3: 34, 4: 38, 5: 42}
DECISION_QUALITY_SCORE_LOSER = 44  # mid-point of 40–48 range


# ─────────────────────────────────────────────────────────────────────────────
# HARD OVERRIDE TABLES — these set hard floors/caps on the FINAL FPS score
# ─────────────────────────────────────────────────────────────────────────────

# Winner floors: =MAX(FPS_Base, FinishFloor)
WINNER_FLOORS = {
    (1, 'sub_60'):  82,
    (1, '61_90'):   79,
    (1, 'post_90'): 76,
    (2, None):      72,
    (3, None):      68,
}

# Finish-loss caps: =MIN(FPS_Base, FinishLossCap)
LOSER_CAPS = {1: 38, 2: 48, 3: 54}


def _time_bucket(seconds: int) -> str:
    """Classify R1 finish time into spec tiers."""
    if seconds <= 60:
        return 'sub_60'
    elif seconds <= 90:
        return '61_90'
    return 'post_90'


def get_fps_tier(fps: float) -> str:
    if fps >= 90: return "DOMINANT"
    if fps >= 75: return "STRONG"
    if fps >= 60: return "COMPETITIVE"
    if fps >= 45: return "MIXED"
    if fps >= 30: return "LOSING"
    return "POOR"


def normalize_method(method: str) -> str:
    """Map ufcstats method strings to normalised keys."""
    m = method.lower()
    if 'tko' in m or 'technical knockout' in m: return 'tko'
    if 'ko' in m or 'knockout' in m: return 'ko'
    if 'sub' in m or 'submission' in m: return 'sub'
    if 'unanimous' in m: return 'ud'
    if 'split' in m: return 'sd'
    if 'majority' in m: return 'md'
    return 'other'


def calculate_fps(
    rounds: list[RoundResult],
    fighter_won: bool,
    method: str,
    finish_round: int | None,
    finish_time_seconds: int | None,
    rounds_scheduled: int,
) -> FPSResult:
    """
    FPS = aggregated RPS + fight-wide adjustments.

    Base:        time-weighted RPS across all rounds
    5-round add: Cardio45 blended at 10% (rounds 4+5 retention vs rounds 1–3)
    Overrides:   winner floor if finish, loser cap if finish loss
    """
    method_norm = normalize_method(method)
    method_key = 'ko' if method_norm in ('ko', 'tko') else method_norm
    is_finish = finish_round is not None and method_key in ('ko', 'sub')

    # ─── TIME-WEIGHTED RPS (non-negotiable backbone) ─────────────────────────
    total_seconds = sum(r.seconds for r in rounds)
    weighted_rps = sum(r.rps * r.seconds for r in rounds) / max(1, total_seconds)

    # ─── CARDIO45  ── only for 5-round fights when R4/R5 existed ─────────────
    cardio_45: float | None = None
    if rounds_scheduled == 5 and len(rounds) >= 4:
        early = [r for r in rounds if r.round_number <= 3]
        late  = [r for r in rounds if r.round_number >= 4]

        early_sec = sum(r.seconds for r in early)
        late_sec  = sum(r.seconds for r in late)

        early_rps = sum(r.rps * r.seconds for r in early) / max(1, early_sec)
        late_rps  = sum(r.rps * r.seconds for r in late)  / max(1, late_sec)

        late_bonus = 5 if late_sec >= 480 else 0
        cardio_45  = max(0.0, min(100.0, 50 + (late_rps - early_rps) * 1.2 + late_bonus))

    # ─── BASE FPS ─────────────────────────────────────────────────────────────
    if cardio_45 is not None:
        base_fps = (weighted_rps * 0.90) + (cardio_45 * 0.10)
    else:
        base_fps = weighted_rps

    # ─── FINISH QUALITY SCORE  (informational sub-score) ─────────────────────
    finish_quality_score: float | None = None
    if is_finish and finish_round is not None:
        bucket = _time_bucket(finish_time_seconds or 300) if finish_round == 1 else None
        if fighter_won:
            finish_quality_score = FINISH_QUALITY_SCORES_WINNER.get((method_key, finish_round, bucket))
        else:
            finish_quality_score = float(FINISH_QUALITY_SCORES_LOSER.get(finish_round, 20))
    elif method_key in ('ud', 'sd', 'md'):
        fq_key = (method_key, None, None)
        if fighter_won:
            finish_quality_score = float(FINISH_QUALITY_SCORES_WINNER.get(fq_key, 68))
        else:
            finish_quality_score = float(DECISION_QUALITY_SCORE_LOSER)

    # ─── APPLY FLOORS / CAPS ─────────────────────────────────────────────────
    floor_applied: float | None = None
    cap_applied: float | None = None
    final_fps = base_fps

    if fighter_won and is_finish and finish_round is not None:
        # Winner floor: =MAX(FPS_Base, FinishFloor)
        bucket = _time_bucket(finish_time_seconds or 300) if finish_round == 1 else None
        floor = WINNER_FLOORS.get((finish_round, bucket))
        if floor is not None and base_fps < floor:
            floor_applied = floor
            final_fps = floor

    elif not fighter_won and is_finish and finish_round is not None:
        # Finish-loss cap: =MIN(FPS_Base, FinishLossCap)
        cap = LOSER_CAPS.get(finish_round)
        if cap is not None and base_fps > cap:
            cap_applied = cap
            final_fps = cap

    # Decision outcomes use weighted RPS as-is (no static floor/cap)

    final_fps = round(max(0.0, min(100.0, final_fps)), 2)

    return FPSResult(
        fps=final_fps,
        fps_tier=get_fps_tier(final_fps),
        weighted_rps=round(weighted_rps, 2),
        cardio_45=round(cardio_45, 2) if cardio_45 is not None else None,
        finish_quality_score=finish_quality_score,
        floor_applied=floor_applied,
        cap_applied=cap_applied,
        fight_total_seconds=total_seconds,
    )
