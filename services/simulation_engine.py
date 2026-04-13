"""
services/simulation_engine.py

Monte Carlo fight simulator backed by real UFC probability tables.
Probability tables and style modifiers are pre-computed from simulation_calibration
and stored in system_config — loaded once at startup, not per-request.

Key entry-points:
  build_fighter_vector_from_db(db, fighter_name) -> UFCFighterVector | None
  run_monte_carlo_simulation(...) -> dict
  fps_delta_to_bucket(fps_delta) -> str
  validate_simulation_accuracy(db, probability_tables, style_modifiers) -> list[dict]
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np


# ---------------------------------------------------------------------------
# δ-bucket mapping (mirrors migration 010_simulation_calibration.sql)
# ---------------------------------------------------------------------------
# Bucket labels are keyed from fighter_a's perspective:
#   positive delta  → fighter_a is the favorite
#   negative delta  → fighter_a is the underdog

_DELTA_THRESHOLDS: list[tuple[float, str]] = [
    (20,  "massive_favorite"),
    (10,  "big_favorite"),
    (5,   "moderate_favorite"),
    (0,   "slight_favorite"),
    (-5,  "slight_underdog"),
    (-10, "moderate_underdog"),
    (-20, "big_underdog"),
]
_FALLBACK_BUCKET = "massive_underdog"


def fps_delta_to_bucket(fps_delta: float) -> str:
    """
    Convert a career-FPS delta (fighter_a - fighter_b) to the string bucket
    label used in simulation_calibration and probability_tables.

    Mirrors the CASE expression in migrations/010_simulation_calibration.sql.
    """
    for threshold, label in _DELTA_THRESHOLDS:
        if fps_delta >= threshold:
            return label
    return _FALLBACK_BUCKET


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class UFCFighterVector:
    """Built from ufc_fighters table — real FPS scores."""
    fighter_id: str
    name: str
    career_fps: float
    style_archetype: str
    style_tags: list[str]

    # FPS components (career averages from real UFC fights)
    offensive_efficiency: float
    defensive_response: float
    control_dictation: float
    finish_threat: float
    cardio_pace: float
    durability: float
    fight_iq: float
    dominance: float


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def build_fighter_vector_from_db(db, fighter_name: str) -> UFCFighterVector | None:
    """
    Pull fighter vector from ufc_fighters table.
    Only returns data for fighters with 5+ UFC fights and real FPS scores.
    """
    row = await db.fetchrow("""
        SELECT
            id, name, career_fps, style_archetype, style_tags,
            avg_offensive_efficiency,
            avg_defensive_response,
            avg_control_dictation,
            avg_finish_threat,
            avg_cardio_pace,
            avg_durability,
            avg_fight_iq,
            avg_dominance
        FROM ufc_fighters
        WHERE name ILIKE $1
          AND meets_5_fight_threshold = TRUE
          AND career_fps IS NOT NULL
        ORDER BY ufc_appearances DESC
        LIMIT 1
    """, f"%{fighter_name}%")

    if not row:
        return None

    return UFCFighterVector(
        fighter_id=str(row["id"]),
        name=row["name"],
        career_fps=float(row["career_fps"]),
        style_archetype=row["style_archetype"] or "balanced",
        style_tags=row["style_tags"] or [],
        offensive_efficiency=float(row["avg_offensive_efficiency"] or 55),
        defensive_response=float(row["avg_defensive_response"]    or 55),
        control_dictation=float(row["avg_control_dictation"]      or 55),
        finish_threat=float(row["avg_finish_threat"]              or 55),
        cardio_pace=float(row["avg_cardio_pace"]                  or 55),
        durability=float(row["avg_durability"]                    or 60),
        fight_iq=float(row["avg_fight_iq"]                        or 55),
        dominance=float(row["avg_dominance"]                      or 50),
    )


async def load_probability_tables(db) -> dict:
    """Load pre-computed probability tables from system_config."""
    row = await db.fetchrow("""
        SELECT value FROM system_config
        WHERE key = 'simulation_probability_tables'
    """)
    return row["value"] if row else {}


async def load_style_modifiers(db) -> dict:
    """Load pre-computed style modifiers from system_config."""
    row = await db.fetchrow("""
        SELECT value FROM system_config
        WHERE key = 'style_modifiers'
    """)
    if not row:
        return {}
    payload = row["value"]
    # system_config stores {"baseline": {...}, "pairings": {...}}
    # Caller expects {style_key: {ko_modifier, sub_modifier, dec_modifier}}
    return payload.get("pairings", {}) if isinstance(payload, dict) else {}


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

# Fallback base probabilities when a delta bucket has no calibration data.
# Values are conservative mid-range estimates.
_FALLBACK_BASE: dict = {
    "favorite_win_rate": 0.55,
    "ko_tko_rate":       0.12,
    "submission_rate":   0.07,
    "decision_rate":     0.39,
    "round_distribution": {"1": 0.25, "2": 0.35, "3": 0.40},
    "sample_size": 0,
}

_FALLBACK_STYLE_MOD: dict = {
    "ko_modifier":  0.0,
    "sub_modifier": 0.0,
    "dec_modifier": 0.0,
}


def run_monte_carlo_simulation(
    fighter_a: UFCFighterVector,
    fighter_b: UFCFighterVector,
    rounds_scheduled: int,
    probability_tables: dict,
    style_modifiers: dict,
    n_simulations: int = 10_000,
    rng_seed: int | None = None,
) -> dict:
    """
    Run n_simulations Monte Carlo trials and return aggregate probabilities.

    Args:
        fighter_a:           Attacker vector built from DB.
        fighter_b:           Defender vector built from DB.
        rounds_scheduled:    3 or 5.
        probability_tables:  Loaded from system_config['simulation_probability_tables'].
        style_modifiers:     Loaded from system_config['style_modifiers']['pairings'].
        n_simulations:       Number of trials (default 10,000).
        rng_seed:            Optional seed for reproducible output.

    Returns:
        dict with win/method/round distribution probabilities and metadata.
    """
    rng = np.random.default_rng(rng_seed)

    # ── Delta bucket → base probabilities ─────────────────────────────────
    fps_delta    = fighter_a.career_fps - fighter_b.career_fps
    delta_bucket = fps_delta_to_bucket(fps_delta)
    base_probs   = probability_tables.get(delta_bucket, _FALLBACK_BASE)

    # ── Style modifier ─────────────────────────────────────────────────────
    style_key = "_vs_".join(sorted([fighter_a.style_archetype, fighter_b.style_archetype]))
    style_mod = style_modifiers.get(style_key, _FALLBACK_STYLE_MOD)

    # ── Component-based adjustments ────────────────────────────────────────
    # finish_threat and durability are on → [0, 100] scale.
    # The multiplicative term keeps the adjustment bounded even when base is
    # already high; max contribution is ±15pp (KO) and ±10pp (sub).
    ko_component  = (fighter_a.finish_threat / 100) * (1 - fighter_b.durability / 100)
    sub_component = (fighter_a.control_dictation / 100) * (1 - fighter_b.fight_iq / 100)

    # ── Win probability ────────────────────────────────────────────────────
    # base_probs is always from fighter_a's perspective (a = higher FPS).
    # When fps_delta < 0, fighter_a is actually the underdog — flip win rate.
    p_win_a = (
        float(base_probs["favorite_win_rate"])
        if fps_delta >= 0
        else 1.0 - float(base_probs["favorite_win_rate"])
    )

    # ── Method probabilities ───────────────────────────────────────────────
    raw_ko  = (
        float(base_probs["ko_tko_rate"])
        + float(style_mod.get("ko_modifier",  0))
        + ko_component  * 0.15
    )
    raw_sub = (
        float(base_probs["submission_rate"])
        + float(style_mod.get("sub_modifier", 0))
        + sub_component * 0.10
    )
    raw_dec = float(base_probs["decision_rate"]) + float(style_mod.get("dec_modifier", 0))

    # Clamp then renormalize so KO + sub + dec = 1.0
    p_ko  = float(np.clip(raw_ko,  0.0, 0.75))
    p_sub = float(np.clip(raw_sub, 0.0, 0.60))
    p_dec = float(np.clip(raw_dec, 0.10, 0.90))
    total = p_ko + p_sub + p_dec
    p_ko  /= total
    p_sub /= total
    p_dec /= total

    # ── Round distribution ─────────────────────────────────────────────────
    round_dist: dict = base_probs.get("round_distribution", {})
    rnd_keys  = [int(k) for k in round_dist if int(k) <= rounds_scheduled]
    rnd_probs = [float(round_dist[str(k)]) for k in rnd_keys]

    if not rnd_keys:
        rnd_keys  = list(range(1, rounds_scheduled + 1))
        rnd_probs = [1.0 / rounds_scheduled] * rounds_scheduled

    rnd_total = sum(rnd_probs)
    if rnd_total <= 0:
        # Fallback: uniform distribution across scheduled rounds
        rnd_keys  = list(range(1, rounds_scheduled + 1))
        rnd_probs = [1.0 / rounds_scheduled] * rounds_scheduled
        rnd_total = 1.0
    rnd_probs = [p / rnd_total for p in rnd_probs]

    # ── Vectorised Monte Carlo ─────────────────────────────────────────────
    # Draw all n_simulations outcomes at once for speed.
    win_rolls    = rng.random(n_simulations)
    method_rolls = rng.choice(["ko", "sub", "decision"], size=n_simulations,
                               p=[p_ko, p_sub, p_dec])
    round_rolls  = rng.choice(rnd_keys, size=n_simulations, p=rnd_probs)

    wins_a = int(np.sum(win_rolls < p_win_a))
    wins_b = n_simulations - wins_a

    ko_mask  = method_rolls == "ko"
    sub_mask = method_rolls == "sub"
    dec_mask = method_rolls == "decision"

    ko_count  = int(np.sum(ko_mask))
    sub_count = int(np.sum(sub_mask))
    dec_count = int(np.sum(dec_mask))

    # Round tally — only for finishes
    finish_mask = ~dec_mask
    finish_rounds = round_rolls[finish_mask]
    round_tally: dict[int, int] = defaultdict(int)
    for rnd in finish_rounds:
        round_tally[int(rnd)] += 1

    n_finishes = ko_count + sub_count
    round_distribution = {
        k: round(v / max(n_finishes, 1), 3)
        for k, v in sorted(round_tally.items())
    }
    predicted_finish_round = (
        int(max(round_tally, key=round_tally.get)) if round_tally else None
    )

    return {
        "fighter_a_win_probability": round(wins_a / n_simulations, 3),
        "fighter_b_win_probability": round(wins_b / n_simulations, 3),
        "ko_tko_probability":        round(ko_count  / n_simulations, 3),
        "submission_probability":    round(sub_count / n_simulations, 3),
        "decision_probability":      round(dec_count / n_simulations, 3),
        "round_distribution":        round_distribution,
        "predicted_finish_round":    predicted_finish_round,
        # Metadata
        "fps_delta":              round(fps_delta, 2),
        "delta_bucket":           delta_bucket,
        "style_key":              style_key,
        "data_source":            "real_ufc_fps",
        "calibration_sample_size": int(base_probs.get("sample_size", 0)),
        "n_simulations":          n_simulations,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# Normalise method_normalized values from DB to the three sim output keys.
_METHOD_TO_SIM_KEY: dict[str, str] = {
    "ko":  "ko_tko",
    "tko": "ko_tko",
    "sub": "submission",
    "ud":  "decision",
    "sd":  "decision",
    "md":  "decision",
}

_ALL_BUCKETS: list[str] = [
    "massive_favorite",
    "big_favorite",
    "moderate_favorite",
    "slight_favorite",
    "slight_underdog",
    "moderate_underdog",
    "big_underdog",
    "massive_underdog",
]


def _vector_from_calibration_row(row, side: str) -> UFCFighterVector:
    """
    Build a UFCFighterVector directly from a simulation_calibration row.
    side is 'a' or 'b'.
    """
    s = side  # column prefix
    return UFCFighterVector(
        fighter_id=str(row[f"fighter_{s}_id"]),
        name=row[f"fighter_{s}_name"],
        career_fps=float(row[f"{s}_career_fps"]),
        style_archetype=row[f"{s}_style"] or "balanced",
        style_tags=[],
        offensive_efficiency=float(row[f"{s}_off_eff"]  or 55),
        defensive_response=float(row[f"{s}_def_resp"]   or 55),
        control_dictation=float(row[f"{s}_ctrl"]        or 55),
        finish_threat=float(row[f"{s}_fin_threat"]      or 55),
        cardio_pace=float(row[f"{s}_cardio"]            or 55),
        durability=float(row[f"{s}_durability"]         or 60),
        fight_iq=float(row[f"{s}_iq"]                   or 55),
        dominance=float(row[f"{s}_dom"]                 or 50),
    )


async def validate_simulation_accuracy(
    db,
    probability_tables: dict,
    style_modifiers: dict,
    *,
    holdout_n: int = 500,
    n_simulations: int = 1_000,
) -> list[dict]:
    """
    Run the simulator over the most-recent holdout_n fights in simulation_calibration
    and compare each prediction to the actual recorded outcome.

    Only fights with a known winner (fighter_a_won IS NOT NULL) and a known
    method (actual_method IS NOT NULL) are included, so the accuracy numbers
    are not diluted by fights where the DB has incomplete data.

    Returns a list of per-fight result dicts.  Prints a bucket-by-bucket and
    overall accuracy report to stdout.

    Accuracy target: ≥65% winner prediction (UFC moneyline favourite wins ~68%).
    """
    calibration_fights = await db.fetch("""
        SELECT *
        FROM simulation_calibration
        WHERE fighter_a_won   IS NOT NULL
          AND actual_method   IS NOT NULL
          AND a_career_fps    IS NOT NULL
          AND b_career_fps    IS NOT NULL
        ORDER BY fight_date DESC
        LIMIT $1
    """, holdout_n)

    if not calibration_fights:
        print("No calibration fights found — run the UFC data pipeline first.")
        return []

    results: list[dict] = []

    for fight in calibration_fights:
        fighter_a = _vector_from_calibration_row(fight, "a")
        fighter_b = _vector_from_calibration_row(fight, "b")

        sim = run_monte_carlo_simulation(
            fighter_a,
            fighter_b,
            int(fight["rounds_scheduled"]),
            probability_tables,
            style_modifiers,
            n_simulations=n_simulations,
        )

        # Winner prediction
        predicted_a_wins = sim["fighter_a_win_probability"] > 0.5
        actual_a_wins    = bool(int(fight["fighter_a_won"]))
        correct_winner   = predicted_a_wins == actual_a_wins

        # Method prediction — pick the sim output key with the highest probability
        method_probs = {
            "ko_tko":     sim["ko_tko_probability"],
            "submission": sim["submission_probability"],
            "decision":   sim["decision_probability"],
        }
        predicted_method = max(method_probs, key=method_probs.__getitem__)
        actual_method_raw = fight["actual_method"]  # 'ko','tko','sub','ud'…
        actual_method_key = _METHOD_TO_SIM_KEY.get(actual_method_raw, "decision")
        correct_method    = predicted_method == actual_method_key

        results.append({
            "fight_date":         fight["fight_date"],
            "fighter_a":          fight["fighter_a_name"],
            "fighter_b":          fight["fighter_b_name"],
            "delta_bucket":       fight["delta_bucket"],
            "career_fps_delta":   float(fight["career_fps_delta"]),
            "fighter_a_win_prob": sim["fighter_a_win_probability"],
            "predicted_a_wins":   predicted_a_wins,
            "actual_a_won":       actual_a_wins,
            "correct_winner":     correct_winner,
            "predicted_method":   predicted_method,
            "actual_method":      actual_method_key,
            "correct_method":     correct_method,
        })

    # ── Accuracy report ────────────────────────────────────────────────────
    total = len(results)
    winner_accuracy = sum(r["correct_winner"] for r in results) / total
    method_accuracy = sum(r["correct_method"] for r in results) / total

    print(f"\n{'='*55}")
    print(f"Simulation accuracy  —  holdout n={total}")
    print(f"{'='*55}")
    print(f"{'Bucket':<24} {'n':>5}  {'WinAcc':>7}  {'MethAcc':>8}")
    print(f"{'-'*55}")

    for bucket in _ALL_BUCKETS:
        bucket_results = [r for r in results if r["delta_bucket"] == bucket]
        if not bucket_results:
            continue
        n_b   = len(bucket_results)
        w_acc = sum(r["correct_winner"] for r in bucket_results) / n_b
        m_acc = sum(r["correct_method"] for r in bucket_results) / n_b
        flag  = "  ✓" if w_acc >= 0.65 else "  ✗"
        print(f"{bucket:<24} {n_b:>5}   {w_acc:>6.1%}    {m_acc:>6.1%}{flag}")

    print(f"{'='*55}")
    print(f"{'OVERALL':<24} {total:>5}   {winner_accuracy:>6.1%}    {method_accuracy:>6.1%}")
    print(f"\nTarget: ≥65% winner accuracy  (UFC moneyline favourite: ~68%)")
    meets_target = "PASS" if winner_accuracy >= 0.65 else "BELOW TARGET"
    print(f"Result: {meets_target}")
    print(f"{'='*55}\n")

    return results
