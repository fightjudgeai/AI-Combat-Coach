"""
Fighter Career Score (FCS) calculator.

FCS is a long-horizon score used for:
  matchmaking · contract value · prospect ranking · roster tiering · promotion planning

All component scores are on a 0–100 scale.
Final FCS = weighted sum of 11 components (weights sum to 1.0).

Architecture
────────────
Data preparation (SQL aggregation, recency weighting) happens upstream in
batch_processor.py / compute_all_career_fps().  This module receives
pre-computed sub-scores and applies the formula plus hard rules.

Recency weighting across last 5 fights: [0.35, 0.25, 0.18, 0.12, 0.10]
"""

from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# RECENCY WEIGHTS  (newest → oldest, last 5 fights)
# ─────────────────────────────────────────────────────────────────────────────
RECENCY_WEIGHTS = [0.35, 0.25, 0.18, 0.12, 0.10]


# ─────────────────────────────────────────────────────────────────────────────
# INPUT DATACLASS
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class FCSInputs:
    """
    All inputs required to compute a Fighter Career Score.

    Sub-scores that require heavy SQL aggregation or opponent data enrichment
    are passed in pre-computed (0–100 scale).  Simpler stats are passed raw
    so the calculator can derive the component score directly.

    Hard-rule guard inputs are explicitly named for clarity.
    """

    # ── Career metadata ───────────────────────────────────────────────────────
    pro_fight_count: int          # total professional fights
    fps_scores: list[float]       # FPS for last N fights, newest first

    # ── 1. Opponent Quality (15%) — pre-computed sub-scores ──────────────────
    wtd_opp_win_pct_score: float        # 0–100: weighted avg opp win % → score
    wtd_opp_experience_score: float     # 0–100: weighted avg opp fight count → score
    wins_vs_winning_opps_score: float   # 0–100: proportion of wins vs >0.500 opponents
    wins_vs_top_tier_opps_score: float  # 0–100: wins vs ranked / elite opposition

    # ── 2. Finish Rate (8%) ───────────────────────────────────────────────────
    career_finish_pct: float      # 0–1: career wins by finish / career wins
    recent_finish_pct: float      # 0–1: finish % over last 5 fights

    # ── 3. Damage Efficiency (10%) ────────────────────────────────────────────
    # Recency-weighted list of (offense_output, damage_absorbed) per fight
    # newest first.  offense_output and damage_absorbed are normalised strike
    # counts (e.g. SL per fight).
    damage_efficiency_fights: list[tuple[float, float]]  # [(off, absorb), ...]

    # ── 4. Defensive Responsibility (10%) — pre-computed penalties ───────────
    damage_taken_penalty: float       # 0–30
    kd_absorbed_penalty: float        # 0–20
    ctrl_conceded_penalty: float      # 0–15
    td_failure_penalty: float         # 0–15

    # ── 5. Control Effectiveness (8%) — pre-computed sub-scores ──────────────
    td_success_score: float           # 0–100
    control_share_score: float        # 0–100
    positional_advantage_score: float # 0–100
    anti_control_score: float         # 0–100

    # ── 6. Cardio / Pace (9%) — pre-computed sub-scores ─────────────────────
    late_round_output_score: float    # 0–100: late rounds relative to early
    pace_retention_score: float       # 0–100: R1→R3/R5 output retention
    work_rate_score: float            # 0–100: strikes+grappling attempts per minute
    late_threat_score: float          # 0–100: finish attempts / knockdowns in R3+

    # ── 7. Chin (10%) — penalty inputs ───────────────────────────────────────
    kd_absorbed_rate_penalty: float         # 0–40: KDs absorbed per fight, scaled
    ko_stoppage_rate_penalty: float         # 0–30: KO/TKO loss rate, scaled
    recent_durability_decline_penalty: float # 0–30: trend: absorbing more damage recently

    # ── 8. Fight IQ (10%) — pre-computed sub-scores ──────────────────────────
    decision_win_quality_score: float   # 0–100
    adaptability_score: float           # 0–100
    strategic_discipline_score: float   # 0–100
    risk_management_score: float        # 0–100
    round_stealing_score: float         # 0–100

    # ── 9. Career Momentum (10%) — pre-computed sub-scores ───────────────────
    last3_trend_score: float        # 0–100: FPS trend across last 3 fights
    last5_quality_score: float      # 0–100: recency-weighted avg quality of last 5
    recent_improvement_score: float # 0–100: delta of recent FPS vs prior FPS

    # ── 10. Excitement Index (5%) — pre-computed sub-scores ──────────────────
    finish_rate_excitement_score: float  # 0–100 (same data as FinishRate, different scale)
    kd_involvement_score: float          # 0–100: KDs per fight involvement
    pace_score: float                    # 0–100: total volume / time
    chaos_factor_score: float            # 0–100: high-variance swing fights

    # ── 11. Reliability (5%) — penalty inputs ────────────────────────────────
    inactivity_penalty: float    # 0–8:  +8 if 12+ months inactive
    withdrawal_penalty: float    # 0–10: per pullout/NC
    missed_weight_penalty: float # 0–6:  +6 if missed weight in last 3
    wild_variance_penalty: float # 0–10: high FPS swing between fights

    # ── Hard-rule guard inputs ────────────────────────────────────────────────
    stoppage_losses_last_4: int      # for Chin cap rule (≥2 → cap Chin at 72)
    opp_quality_raw: float           # raw OpponentQuality score (for gate rule)


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT DATACLASS
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class FCSResult:
    fcs: float
    fcs_tier: str
    is_provisional: bool   # True if < 3 pro fights

    # Component scores (each 0–100, before weighting)
    opponent_quality: float
    finish_rate: float
    damage_efficiency: float
    defensive_responsibility: float
    control_effectiveness: float
    cardio_pace: float
    chin: float
    fight_iq: float
    career_momentum: float
    excitement_index: float
    reliability: float

    # Hard-rule flags
    chin_was_capped: bool     # Chin capped at 72 (2+ stoppages in last 4)
    finish_rate_was_capped: bool  # FinishRate capped at 75 (OppQuality < 45)


# ─────────────────────────────────────────────────────────────────────────────
# TIER LABELS
# ─────────────────────────────────────────────────────────────────────────────
def get_fcs_tier(fcs: float) -> str:
    """
    The same tier labels as FPS but applied to career score.
    (Provisional fighters always use tier "PROVISIONAL".)
    """
    if fcs >= 90: return "ELITE"
    if fcs >= 75: return "HIGH LEVEL"
    if fcs >= 60: return "SOLID"
    if fcs >= 45: return "DEVELOPING"
    if fcs >= 30: return "WEAK"
    return "POOR"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def _recency_weighted_avg(values: list[float], weights: list[float] = RECENCY_WEIGHTS) -> float:
    """
    Weighted average using specified recency weights.
    If fewer values than weights, only the first len(values) weights are used
    and they are re-normalised to sum to 1.
    """
    n = min(len(values), len(weights))
    if n == 0:
        return 50.0
    w = weights[:n]
    total_w = sum(w)
    return sum(v * wt for v, wt in zip(values[:n], w)) / total_w


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT CALCULATIONS
# ─────────────────────────────────────────────────────────────────────────────

def _opponent_quality(i: FCSInputs) -> float:
    """
    OpponentQuality =
        0.45 * WeightedOppWinPctScore +
        0.20 * WeightedOppExperienceScore +
        0.20 * WinsVsWinningOppsScore +
        0.15 * WinsVsTopTierScore
    """
    score = (
        0.45 * i.wtd_opp_win_pct_score
        + 0.20 * i.wtd_opp_experience_score
        + 0.20 * i.wins_vs_winning_opps_score
        + 0.15 * i.wins_vs_top_tier_opps_score
    )
    return _clamp(score)


def _finish_rate(i: FCSInputs) -> float:
    """
    FinishRate = 0.65 * CareerFinishPct_score + 0.35 * RecentFinishPct_score
    (pct values 0–1 are scaled to 0–100)
    """
    career_score = _clamp(i.career_finish_pct * 100)
    recent_score = _clamp(i.recent_finish_pct * 100)
    return _clamp(0.65 * career_score + 0.35 * recent_score)


def _damage_efficiency(i: FCSInputs) -> float:
    """
    DamageEfficiency = 50 + 50 * WtdAvg( (off - abs) / max(1, off + abs) )

    If no fights have damage data, returns 50 (neutral).
    """
    if not i.damage_efficiency_fights:
        return 50.0

    n = min(len(i.damage_efficiency_fights), len(RECENCY_WEIGHTS))
    weights = RECENCY_WEIGHTS[:n]
    total_w = sum(weights)

    wtd_ratio = sum(
        ((off - absorb) / max(1.0, off + absorb)) * wt
        for (off, absorb), wt in zip(i.damage_efficiency_fights[:n], weights)
    ) / total_w

    return _clamp(50.0 + 50.0 * wtd_ratio)


def _defensive_responsibility(i: FCSInputs) -> float:
    """
    DefensiveResponsibility =
        100 - DamageTakenPenalty - KDAbsorbedPenalty
            - CtrlConcededPenalty - TDFailurePenalty
    """
    return _clamp(
        100.0
        - i.damage_taken_penalty
        - i.kd_absorbed_penalty
        - i.ctrl_conceded_penalty
        - i.td_failure_penalty
    )


def _control_effectiveness(i: FCSInputs) -> float:
    """
    ControlEffectiveness =
        0.35 * TakedownSuccessScore +
        0.35 * ControlShareScore +
        0.15 * PositionalAdvantageScore +
        0.15 * AntiControlScore
    """
    return _clamp(
        0.35 * i.td_success_score
        + 0.35 * i.control_share_score
        + 0.15 * i.positional_advantage_score
        + 0.15 * i.anti_control_score
    )


def _cardio_pace(i: FCSInputs) -> float:
    """
    CardioPace =
        0.40 * LateRoundOutputScore +
        0.30 * PaceRetentionScore +
        0.20 * WorkRateScore +
        0.10 * LateThreatScore
    """
    return _clamp(
        0.40 * i.late_round_output_score
        + 0.30 * i.pace_retention_score
        + 0.20 * i.work_rate_score
        + 0.10 * i.late_threat_score
    )


def _chin(i: FCSInputs) -> tuple[float, bool]:
    """
    Chin =
        100 - KDAbsorbedRatePenalty
            - KOStoppageRatePenalty
            - RecentDurabilityDeclinePenalty

    Hard rule: 2+ stoppage losses in last 4 fights → cap at 72.
    Returns (chin_score, was_capped).
    """
    raw = _clamp(
        100.0
        - i.kd_absorbed_rate_penalty
        - i.ko_stoppage_rate_penalty
        - i.recent_durability_decline_penalty
    )
    if i.stoppage_losses_last_4 >= 2:
        return min(raw, 72.0), True
    return raw, False


def _fight_iq(i: FCSInputs) -> float:
    """
    FightIQ =
        0.30 * DecisionWinQualityScore +
        0.25 * AdaptabilityScore +
        0.20 * StrategicDisciplineScore +
        0.15 * RiskManagementScore +
        0.10 * RoundStealingScore

    Hard rule: fighters with repeated late-fight collapses / reckless chasing
    (captured upstream via low strategic_discipline_score or high ERR) should
    not exceed 78.  Enforced in apply_hard_rules() below.
    """
    return _clamp(
        0.30 * i.decision_win_quality_score
        + 0.25 * i.adaptability_score
        + 0.20 * i.strategic_discipline_score
        + 0.15 * i.risk_management_score
        + 0.10 * i.round_stealing_score
    )


def _career_momentum(i: FCSInputs) -> float:
    """
    CareerMomentum =
        0.50 * Last3FightTrendScore +
        0.30 * Last5FightQualityScore +
        0.20 * RecentImprovementScore
    """
    return _clamp(
        0.50 * i.last3_trend_score
        + 0.30 * i.last5_quality_score
        + 0.20 * i.recent_improvement_score
    )


def _excitement_index(i: FCSInputs) -> float:
    """
    ExcitementIndex =
        0.40 * FinishRateScore +
        0.25 * KDInvolvementScore +
        0.20 * PaceScore +
        0.15 * ChaosFactorScore
    """
    return _clamp(
        0.40 * i.finish_rate_excitement_score
        + 0.25 * i.kd_involvement_score
        + 0.20 * i.pace_score
        + 0.15 * i.chaos_factor_score
    )


def _reliability(i: FCSInputs) -> float:
    """
    Reliability =
        100 - InactivityPenalty - WithdrawalPenalty
            - MissedWeightPenalty - WildVariancePenalty
    """
    return _clamp(
        100.0
        - i.inactivity_penalty
        - i.withdrawal_penalty
        - i.missed_weight_penalty
        - i.wild_variance_penalty
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────

def calculate_fcs(i: FCSInputs) -> FCSResult:
    """
    Compute Fighter Career Score from pre-aggregated career statistics.

    Hard rules applied (in order):
      1. Provisional flag   — < 3 pro fights
      2. Opponent quality gate — FCS > 85 blocked without ≥ 40 OppQuality
      3. Finish fraud rule  — FinishRate capped at 75 when OppQuality < 45
      4. Chin cap rule      — Chin capped at 72 when 2+ stoppage losses in last 4
      5. Fight IQ cap rule  — FightIQ capped at 78 (applied via strategic_discipline)
    """

    # ── Provisional check ────────────────────────────────────────────────────
    is_provisional = i.pro_fight_count < 3

    # ── Compute raw component scores ─────────────────────────────────────────
    opp_quality   = _opponent_quality(i)
    finish_rate   = _finish_rate(i)
    damage_eff    = _damage_efficiency(i)
    def_resp      = _defensive_responsibility(i)
    ctrl_eff      = _control_effectiveness(i)
    cardio        = _cardio_pace(i)
    chin, chin_capped = _chin(i)
    fight_iq_raw  = _fight_iq(i)
    momentum      = _career_momentum(i)
    excitement    = _excitement_index(i)
    reliability   = _reliability(i)

    # ── Hard rule: Fight IQ cap (repeated late collapses / reckless chasing)
    # strategic_discipline_score drives this: if < 40 it implies systemic IQ issues
    fight_iq = min(fight_iq_raw, 78.0) if i.strategic_discipline_score < 40.0 else fight_iq_raw

    # ── Hard rule: Finish fraud — cap FinishRate at 75 when OppQuality < 45 ──
    finish_rate_capped = i.opp_quality_raw < 45.0
    if finish_rate_capped:
        finish_rate = min(finish_rate, 75.0)

    # ── Weighted FCS formula ─────────────────────────────────────────────────
    raw_fcs = (
        0.15 * opp_quality
        + 0.08 * finish_rate
        + 0.10 * damage_eff
        + 0.10 * def_resp
        + 0.08 * ctrl_eff
        + 0.09 * cardio
        + 0.10 * chin
        + 0.10 * fight_iq
        + 0.10 * momentum
        + 0.05 * excitement
        + 0.05 * reliability
    )

    fcs = _clamp(raw_fcs)

    # ── Hard rule: Opponent quality gate — block FCS > 85 without earned schedule
    if fcs > 85.0 and i.opp_quality_raw < 40.0:
        fcs = 85.0

    fcs = round(fcs, 2)

    return FCSResult(
        fcs=fcs,
        fcs_tier="PROVISIONAL" if is_provisional else get_fcs_tier(fcs),
        is_provisional=is_provisional,
        opponent_quality=round(opp_quality, 2),
        finish_rate=round(finish_rate, 2),
        damage_efficiency=round(damage_eff, 2),
        defensive_responsibility=round(def_resp, 2),
        control_effectiveness=round(ctrl_eff, 2),
        cardio_pace=round(cardio, 2),
        chin=round(chin, 2),
        fight_iq=round(fight_iq, 2),
        career_momentum=round(momentum, 2),
        excitement_index=round(excitement, 2),
        reliability=round(reliability, 2),
        chin_was_capped=chin_capped,
        finish_rate_was_capped=finish_rate_capped,
    )
