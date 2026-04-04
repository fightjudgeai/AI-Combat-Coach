from dataclasses import dataclass
import math

@dataclass
class RPSInputs:
    SL: int      # Significant strikes landed
    SA: int      # Significant strikes attempted
    KD_F: int    # Knockdowns landed
    KD_A: int    # Knockdowns taken
    TD_F: int    # Takedowns landed
    TA_F: int    # Takedowns attempted
    TD_A: int    # Opponent takedowns landed
    TA_A: int    # Opponent takedowns attempted
    CTRL_F: int  # Control time (seconds)
    CTRL_A: int  # Opponent control time (seconds)
    NF: int      # Near finish (0/1/2)
    ERR: int     # Errors (0/1/2)
    SEC: int     # Round seconds

@dataclass
class RPSComponents:
    offensive_efficiency: float
    defensive_response: float
    control_dictation: float
    finish_threat: float
    durability: float
    fight_iq: float
    dominance: float
    rps: float

def clamp(val: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, val))

def calculate_rps(i: RPSInputs) -> RPSComponents:
    """
    Your exact RPS formulas from the finalized scoring spec.
    """

    # Shared denominators
    total_strikes = max(1, i.SL + i.SA)  # avoid div/0
    total_td_att = max(1, i.TA_F)
    total_ctrl = max(1, i.CTRL_F + i.CTRL_A)
    opp_td_att = max(1, i.TA_A)

    # ────────────────────────────────────────
    # FORMULA A
    # ────────────────────────────────────────

    # Offensive Efficiency
    off_eff = (
        45
        + ((i.SL - i.SA) / total_strikes) * 22
        + (i.SL / total_strikes) * 18
        + i.KD_F * 10
        + i.TD_F * 4
        + i.NF * 6
    )

    # Defensive Response
    def_resp = (
        65
        - i.SA * 1.2
        - i.KD_A * 14
        - i.TD_A * 4
        - (i.CTRL_A / 300) * 12
        + (1 - i.TD_A / opp_td_att) * 8
    )

    # Control Dictation
    # Bonus tier: 60+ seconds control = +8, 30+ = +4, else 0
    ctrl_bonus = 8 if i.CTRL_F >= 60 else (4 if i.CTRL_F >= 30 else 0)
    ctrl_dict = (
        45
        + (i.CTRL_F / total_ctrl) * 22
        + i.TD_F * 5
        - i.TD_A * 4
        + ctrl_bonus
    )

    # Finish Threat
    # Strike differential bonus: SL - SA >= 10 = +8
    strike_diff_bonus = 8 if (i.SL - i.SA) >= 10 else 0
    fin_threat = (
        40
        + i.KD_F * 16
        + i.NF * 14
        + strike_diff_bonus
    )

    # ────────────────────────────────────────
    # FORMULA B
    # ────────────────────────────────────────

    # Durability
    durability = (
        78
        - i.KD_A * 18
        - i.SA * 0.9
    )

    # Fight IQ
    fight_iq = (
        55
        + (i.SL / total_strikes) * 10
        + (i.TD_F / total_td_att) * 8
        + (i.CTRL_F / total_ctrl) * 8
        - i.ERR * 10
        - i.KD_A * 6
    )

    # Dominance
    dominance = (
        50
        + ((i.SL - i.SA) / total_strikes) * 24
        + ((i.CTRL_F - i.CTRL_A) / total_ctrl) * 16
        + (i.KD_F - i.KD_A) * 10
    )

    # ────────────────────────────────────────
    # CLAMP ALL COMPONENTS 0–100
    # ────────────────────────────────────────
    off_eff = clamp(off_eff)
    def_resp = clamp(def_resp)
    ctrl_dict = clamp(ctrl_dict)
    fin_threat = clamp(fin_threat)
    durability = clamp(durability)
    fight_iq = clamp(fight_iq)
    dominance = clamp(dominance)

    # ────────────────────────────────────────
    # WEIGHTED RPS
    # ────────────────────────────────────────
    rps = round(
        (off_eff * 0.28)
        + (def_resp * 0.18)
        + (ctrl_dict * 0.16)
        + (fin_threat * 0.14)
        + (durability * 0.10)
        + (fight_iq * 0.08)
        + (dominance * 0.06),
        0
    )

    return RPSComponents(
        offensive_efficiency=round(off_eff, 2),
        defensive_response=round(def_resp, 2),
        control_dictation=round(ctrl_dict, 2),
        finish_threat=round(fin_threat, 2),
        durability=round(durability, 2),
        fight_iq=round(fight_iq, 2),
        dominance=round(dominance, 2),
        rps=rps,
    )
