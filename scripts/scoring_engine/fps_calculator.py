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
    cardio_45: float | None  # only for 5-round fights
    was_override_applied: bool
    override_base: float | None
    fight_total_seconds: int

# ────────────────────────────────────────
# FINISH OVERRIDE TABLE (winner)
# Exact from your spec
# ────────────────────────────────────────
FINISH_OVERRIDES_WINNER = {
    ('ko',  1, (0,   60)): 98,
    ('sub', 1, (0,   60)): 96,
    ('ko',  1, (61,  90)): 95,
    ('sub', 1, (61,  90)): 93,
    ('ko',  1, (91, 300)): 92,
    ('sub', 1, (91, 300)): 90,
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

# Loser FPS by finish round
FINISH_LOSERS = {1: 20, 2: 28, 3: 34, 4: 38, 5: 42}
DECISION_LOSS = 44  # middle of 40-48 range

# Winner floors (minimum FPS even with low RPS)
WINNER_FLOORS = {
    (1, (0,   60)): 82,
    (1, (61,  90)): 79,
    (1, (91, 300)): 76,
    (2, None):      72,
    (3, None):      68,
}

# Loser caps (maximum FPS even with high RPS)
LOSER_CAPS = {1: 38, 2: 48, 3: 54}

def get_fps_tier(fps: float) -> str:
    if fps >= 90: return "DOMINANT"
    if fps >= 75: return "STRONG"
    if fps >= 60: return "COMPETITIVE"
    if fps >= 45: return "MIXED"
    if fps >= 30: return "LOSING"
    return "POOR"

def normalize_method(method: str) -> str:
    """Map ufcstats method strings to your normalized keys"""
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
    rounds_scheduled: int
) -> FPSResult:

    method_norm = normalize_method(method)

    # ────────────────────────────────────────
    # WEIGHTED RPS BASE
    # ────────────────────────────────────────
    total_seconds = sum(r.seconds for r in rounds)
    weighted_rps = sum(r.rps * r.seconds for r in rounds) / max(1, total_seconds)

    # ────────────────────────────────────────
    # CARDIO45 (5-round fights only)
    # ────────────────────────────────────────
    cardio_45 = None
    if rounds_scheduled == 5 and len(rounds) >= 4:
        early_rounds = [r for r in rounds if r.round_number <= 3]
        late_rounds = [r for r in rounds if r.round_number >= 4]

        early_sec = sum(r.seconds for r in early_rounds)
        late_sec = sum(r.seconds for r in late_rounds)

        early_rps = sum(r.rps * r.seconds for r in early_rounds) / max(1, early_sec)
        late_rps = sum(r.rps * r.seconds for r in late_rounds) / max(1, late_sec)

        late_rounds_full = sum(r.seconds for r in late_rounds if r.round_number in [4, 5])
        late_bonus = 5 if late_rounds_full >= 480 else 0

        cardio_45 = 50 + (late_rps - early_rps) * 1.2 + late_bonus

        # FPS for 5-round fights includes cardio
        base_fps = (weighted_rps * 0.90) + (cardio_45 * 0.10)
    else:
        base_fps = weighted_rps

    # ────────────────────────────────────────
    # FINISH OVERRIDES
    # ────────────────────────────────────────
    override_value = None
    floor_value = None
    cap_value = None

    if fighter_won and finish_round and method_norm in ('ko', 'tko', 'sub'):
        method_key = 'ko' if method_norm in ('ko', 'tko') else 'sub'
        finish_sec = finish_time_seconds or 300

        # Look up override
        for (m, rnd, time_range), val in FINISH_OVERRIDES_WINNER.items():
            if m == method_key and rnd == finish_round:
                if time_range is None or (time_range[0] <= finish_sec <= time_range[1]):
                    override_value = val
                    break

        # Look up floor
        for (rnd, time_range), val in WINNER_FLOORS.items():
            if rnd == finish_round:
                if time_range is None or (time_range[0] <= finish_sec <= time_range[1]):
                    floor_value = val
                    break

        final_fps = max(base_fps, floor_value or 0)
        if override_value:
            final_fps = max(final_fps, override_value)

    elif not fighter_won and finish_round and method_norm in ('ko', 'tko', 'sub'):
        # Loss by finish
        final_fps = FINISH_LOSERS.get(finish_round, DECISION_LOSS)
        cap_value = LOSER_CAPS.get(finish_round)
        if cap_value:
            final_fps = min(final_fps, cap_value)

    elif not fighter_won and method_norm in ('ud', 'sd', 'md'):
        final_fps = DECISION_LOSS

    elif fighter_won and method_norm in ('ud', 'sd', 'md'):
        final_fps = base_fps  # no override on decision wins — weighted RPS decides

    else:
        final_fps = base_fps

    # Hard rule: winner always >= loser + 2
    # (enforced at fight level in the batch processor)
    final_fps = round(max(0, min(100, final_fps)), 2)

    return FPSResult(
        fps=final_fps,
        fps_tier=get_fps_tier(final_fps),
        weighted_rps=round(weighted_rps, 2),
        cardio_45=round(cardio_45, 2) if cardio_45 is not None else None,
        was_override_applied=override_value is not None,
        override_base=override_value,
        fight_total_seconds=total_seconds,
    )
