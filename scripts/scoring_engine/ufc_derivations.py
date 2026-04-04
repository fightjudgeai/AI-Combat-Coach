"""
scripts/scoring_engine/ufc_derivations.py

Derive the two synthetic RPS inputs (NF, ERR) from the per-round
context dict produced by the ufcstats scraper + batch_processor:

  ctx keys (all ints/floats unless noted):
    SL         — significant strikes landed
    SA         — significant strikes attempted
    KD_F       — knockdowns scored by this fighter
    KD_A       — knockdowns scored by opponent
    TD_F       — takedowns landed by this fighter
    TA_F       — takedown attempts by this fighter
    TD_A       — takedowns landed on this fighter
    TA_A       — opponent's takedown attempts
    CTRL_F     — control time in seconds (this fighter)
    CTRL_A     — opponent's control time in seconds
    sub_att    — submission attempts by this fighter
    is_finish_round — bool: True if fight ended this round
    fighter_won     — bool: True if this fighter won the fight

Both functions return 0 / 1 / 2 — integer "strength" scores.
"""
from __future__ import annotations


def derive_nf(ctx: dict) -> int:
    """
    Near Finish (0 / 1 / 2) — how close did this fighter come to
    stopping the fight in this round?

    Scoring logic:
      2 — Scored 2+ knockdowns, OR scored a KD/sub attempt in the
          actual finish round as the winner (imminent stoppage).
      1 — Scored exactly 1 knockdown, OR threw a submission attempt,
          OR had a high-volume round (15+ SL) in the finish round
          while winning.
      0 — No notable finish threat.
    """
    kd_f       = int(ctx.get('KD_F', 0) or 0)
    sub_att    = int(ctx.get('sub_att', 0) or 0)
    sl         = int(ctx.get('SL', 0) or 0)
    is_finish  = bool(ctx.get('is_finish_round', False))
    won        = bool(ctx.get('fighter_won', False))

    # ── Level 2 ──────────────────────────────────────────────────────
    if kd_f >= 2:
        return 2
    # Scored a KD or sub attempt in the finish round as the winner
    if is_finish and won and (kd_f >= 1 or sub_att >= 1):
        return 2

    # ── Level 1 ──────────────────────────────────────────────────────
    if kd_f == 1:
        return 1
    if sub_att >= 1:
        return 1
    # High-volume dominant finish round (15+ landed, winning fighter)
    if is_finish and won and sl >= 15:
        return 1

    return 0


def derive_err(ctx: dict) -> int:
    """
    Errors (0 / 1 / 2) — how many tactical mistakes did this fighter
    make in this round?

    Counted independently (each worth 1), capped at 2:
      +1 if strike accuracy < 30% on 10+ attempts  (wild offense)
      +1 if took a knockdown (gave up a clean shot)
      +1 if conceded 2+ takedowns OR was controlled for 60+ seconds
         (surrendered grappling dominance for a sustained period)
    """
    sa     = int(ctx.get('SA', 0) or 0)
    sl     = int(ctx.get('SL', 0) or 0)
    kd_a   = int(ctx.get('KD_A', 0) or 0)
    td_a   = int(ctx.get('TD_A', 0) or 0)
    ctrl_a = int(ctx.get('CTRL_A', 0) or 0)

    mistakes = 0

    # Low strike accuracy: 10+ attempts with < 30% connecting
    if sa >= 10 and sl / sa < 0.30:
        mistakes += 1

    # Dropped — gave up a knockdown
    if kd_a >= 1:
        mistakes += 1

    # Grappling failures: multiple takedowns conceded or prolonged control
    if td_a >= 2 or ctrl_a >= 60:
        mistakes += 1

    return min(mistakes, 2)
