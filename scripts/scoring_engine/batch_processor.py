import asyncio
import dataclasses
from pathlib import Path

from scripts.scoring_engine.rps_calculator import RPSInputs, calculate_rps
from scripts.scoring_engine.fps_calculator import (
    calculate_fps,
    get_fps_tier,
    normalize_method,
    RoundResult,
)
from scripts.scoring_engine.ufc_derivations import derive_nf, derive_err


async def process_all_fights(db, filtered_fights: list[dict]):
    """
    For each fight:
    1. Calculate RPS per round per fighter
    2. Calculate FPS per fight per fighter
    3. Enforce winner >= loser + 2 hard rule
    4. Insert to Supabase
    """

    processed = 0
    errors = 0

    for fight_data in filtered_fights:
        try:
            await process_single_fight(db, fight_data)
            processed += 1

            if processed % 100 == 0:
                print(f"Processed {processed}/{len(filtered_fights)} fights")

        except Exception as e:
            print(f"Error on fight {fight_data.get('fight_url')}: {e}")
            errors += 1

    print(f"\nComplete: {processed} fights processed, {errors} errors")

    # Now compute career FPS for each fighter
    await compute_all_career_fps(db)


async def process_single_fight(db, fight_data: dict) -> str:
    """Process one fight: insert to DB, calculate RPS+FPS, return fight UUID"""

    # Resolve or create fighter records
    fighter_a_id = await resolve_ufc_fighter(db, fight_data['fighter_a_name'])
    fighter_b_id = await resolve_ufc_fighter(db, fight_data['fighter_b_name'])

    # Parse finish time to seconds
    finish_seconds = parse_time_to_seconds(fight_data.get('finish_time'))
    method_norm = normalize_method(fight_data.get('method', ''))

    is_finish = method_norm in ('ko', 'tko', 'sub')
    winner_name = fight_data.get('winner')
    fighter_a_won = winner_name == fight_data['fighter_a_name']

    # winner_id is NULL for draws/NCs
    winner_id = None
    if winner_name == fight_data['fighter_a_name']:
        winner_id = fighter_a_id
    elif winner_name == fight_data['fighter_b_name']:
        winner_id = fighter_b_id

    # Insert fight record.
    # Note: was_finish, went_to_decision, fps_delta are generated columns — omitted.
    fight_id = await db.fetchval("""
        INSERT INTO ufc_fights (
            ufcstats_fight_url, event_name, fight_date,
            weight_class, fighter_a_id, fighter_b_id,
            fighter_a_name, fighter_b_name, winner_id, winner_name,
            method, method_normalized, finish_round, finish_time,
            finish_time_seconds, rounds_scheduled
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
        ON CONFLICT (ufcstats_fight_url) DO NOTHING
        RETURNING id
    """,
        fight_data['ufcstats_fight_url'],
        fight_data['event_name'],
        fight_data.get('event_date'),
        fight_data.get('weight_class'),
        fighter_a_id, fighter_b_id,
        fight_data['fighter_a_name'],
        fight_data['fighter_b_name'],
        winner_id,
        winner_name,
        fight_data.get('method'),
        method_norm,
        fight_data.get('finish_round'),
        fight_data.get('finish_time'),
        finish_seconds,
        fight_data.get('rounds_scheduled', 3),
    )

    # Process rounds
    a_round_results: list[RoundResult] = []
    b_round_results: list[RoundResult] = []

    finish_round = fight_data.get('finish_round')
    rounds_scheduled = fight_data.get('rounds_scheduled', 3)

    for round_data in fight_data.get('rounds', []):
        rnd = round_data['round']
        is_finish_round = (rnd == finish_round and is_finish)

        # Round seconds: full round = 300, finish round = actual elapsed
        round_seconds = finish_seconds if is_finish_round else 300

        for fighter_key, fighter_id, fighter_won in [
            ('fighter_a', fighter_a_id, fighter_a_won),
            ('fighter_b', fighter_b_id, not fighter_a_won),
        ]:
            stats = round_data[fighter_key]

            ctx = {**stats, 'is_finish_round': is_finish_round, 'fighter_won': fighter_won}

            # Build RPS inputs (scraper uses uppercase keys)
            inputs = RPSInputs(
                SL=stats['SL'], SA=stats['SA'],
                KD_F=stats['KD_F'], KD_A=stats['KD_A'],
                TD_F=stats['TD_F'], TA_F=stats['TA_F'],
                TD_A=stats['TD_A'], TA_A=stats['TA_A'],
                CTRL_F=stats['CTRL_F'], CTRL_A=stats['CTRL_A'],
                NF=derive_nf(ctx),
                ERR=derive_err(ctx),
                SEC=round_seconds,
            )

            components = calculate_rps(inputs)

            # ufc_round_stats columns are lowercase
            await db.execute("""
                INSERT INTO ufc_round_stats (
                    fight_id, fighter_id, fighter_name, round_number,
                    sl, sa, kd_f, kd_a, td_f, ta_f, td_a, ta_a,
                    ctrl_f, ctrl_a, sub_att, nf, err, sec,
                    is_finish_round, fighter_won_fight,
                    offensive_efficiency, defensive_response, control_dictation,
                    finish_threat, durability, fight_iq, dominance, rps
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,
                          $13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,
                          $24,$25,$26,$27,$28)
                ON CONFLICT (fight_id, fighter_id, round_number) DO NOTHING
            """,
                fight_id, fighter_id,
                fight_data[f'{fighter_key}_name'],
                rnd,
                inputs.SL, inputs.SA, inputs.KD_F, inputs.KD_A,
                inputs.TD_F, inputs.TA_F, inputs.TD_A, inputs.TA_A,
                inputs.CTRL_F, inputs.CTRL_A, stats['sub_att'],
                inputs.NF, inputs.ERR, inputs.SEC,
                is_finish_round, fighter_won,
                components.offensive_efficiency,
                components.defensive_response,
                components.control_dictation,
                components.finish_threat,
                components.durability,
                components.fight_iq,
                components.dominance,
                components.rps,
            )

            round_result = RoundResult(
                round_number=rnd,
                rps=components.rps,
                seconds=round_seconds,
            )
            if fighter_key == 'fighter_a':
                a_round_results.append(round_result)
            else:
                b_round_results.append(round_result)

    # ────────────────────────────────────────
    # Calculate FPS for both fighters
    # ────────────────────────────────────────
    fps_a = calculate_fps(
        rounds=a_round_results,
        fighter_won=fighter_a_won,
        method=fight_data.get('method', ''),
        finish_round=fight_data.get('finish_round'),
        finish_time_seconds=finish_seconds,
        rounds_scheduled=rounds_scheduled,
    )

    fps_b = calculate_fps(
        rounds=b_round_results,
        fighter_won=not fighter_a_won,
        method=fight_data.get('method', ''),
        finish_round=fight_data.get('finish_round'),
        finish_time_seconds=finish_seconds,
        rounds_scheduled=rounds_scheduled,
    )

    # Hard rule: winner FPS >= loser FPS + 2
    if fighter_a_won:
        if fps_a.fps < fps_b.fps + 2:
            fps_a = dataclasses.replace(fps_a, fps=round(fps_b.fps + 2, 2))
    else:
        if fps_b.fps < fps_a.fps + 2:
            fps_b = dataclasses.replace(fps_b, fps=round(fps_a.fps + 2, 2))

    # Update fight record with FPS scores.
    # fps_delta is a generated column (fighter_a_fps - fighter_b_fps) — omitted.
    await db.execute("""
        UPDATE ufc_fights
        SET fighter_a_fps = $1, fighter_b_fps = $2
        WHERE id = $3
    """, fps_a.fps, fps_b.fps, fight_id)

    return fight_id


async def resolve_ufc_fighter(db, name: str) -> str:
    """Get or create a ufc_fighters row, returning the UUID."""
    row = await db.fetchrow(
        "SELECT id FROM ufc_fighters WHERE name = $1", name
    )
    if row:
        return str(row['id'])
    fighter_id = await db.fetchval(
        "INSERT INTO ufc_fighters (name) VALUES ($1) RETURNING id", name
    )
    return str(fighter_id)


def parse_time_to_seconds(time_str: str | None) -> int | None:
    """Convert 'M:SS' finish time to total seconds."""
    if not time_str:
        return None
    parts = str(time_str).strip().split(':')
    if len(parts) == 2:
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            pass
    return None


async def compute_all_career_fps(db):
    """
    For each UFC fighter with 5+ fights:
    Compute career FPS = weighted average of last 5 fights
    (recency weights: 35/25/18/12/10 from the FCS spec)
    """

    fighters = await db.fetch("""
        SELECT id, name FROM ufc_fighters
        WHERE meets_5_fight_threshold = TRUE
    """)

    recency_weights = [0.35, 0.25, 0.18, 0.12, 0.10]

    for fighter in fighters:
        fights = await db.fetch("""
            SELECT
                CASE WHEN f.fighter_a_id = $1 THEN f.fighter_a_fps
                     ELSE f.fighter_b_fps END AS fps,
                f.fight_date
            FROM ufc_fights f
            WHERE (f.fighter_a_id = $1 OR f.fighter_b_id = $1)
              AND (
                CASE WHEN f.fighter_a_id = $1 THEN f.fighter_a_fps
                     ELSE f.fighter_b_fps END
              ) IS NOT NULL
            ORDER BY f.fight_date DESC
            LIMIT 5
        """, fighter['id'])

        if len(fights) < 5:
            continue  # Needs 5 scored fights to produce career FPS

        fps_scores = [f['fps'] for f in fights]
        career_fps = sum(fps * w for fps, w in zip(fps_scores, recency_weights))

        components = await db.fetchrow("""
            SELECT
                AVG(rs.offensive_efficiency) AS avg_off_eff,
                AVG(rs.defensive_response)   AS avg_def_resp,
                AVG(rs.control_dictation)    AS avg_ctrl,
                AVG(rs.finish_threat)        AS avg_fin_threat,
                AVG(rs.durability)           AS avg_dur,
                AVG(rs.fight_iq)             AS avg_iq,
                AVG(rs.dominance)            AS avg_dom
            FROM ufc_round_stats rs
            JOIN ufc_fights f ON rs.fight_id = f.id
            WHERE rs.fighter_id = $1
              AND f.fight_date >= (
                SELECT MIN(fight_date) FROM (
                    SELECT fight_date FROM ufc_fights
                    WHERE fighter_a_id = $1 OR fighter_b_id = $1
                    ORDER BY fight_date DESC LIMIT 5
                ) sub
              )
        """, fighter['id'])

        archetype = classify_style_archetype(components)

        await db.execute("""
            UPDATE ufc_fighters SET
                career_fps                = $1,
                career_fps_tier           = $2,
                fps_fight_count           = $3,
                fps_last_calculated       = NOW(),
                avg_offensive_efficiency  = $4,
                avg_defensive_response    = $5,
                avg_control_dictation     = $6,
                avg_finish_threat         = $7,
                avg_durability            = $8,
                avg_fight_iq              = $9,
                avg_dominance             = $10,
                style_archetype           = $11
            WHERE id = $12
        """,
            round(career_fps, 2),
            get_fps_tier(career_fps),
            len(fights),
            components['avg_off_eff'], components['avg_def_resp'],
            components['avg_ctrl'],    components['avg_fin_threat'],
            components['avg_dur'],     components['avg_iq'],
            components['avg_dom'],
            archetype,
            fighter['id'],
        )

    print("Career FPS computation complete")


def classify_style_archetype(components) -> str:
    """Assign style archetype based on dominant FPS components."""
    off  = components['avg_off_eff']  or 0
    ctrl = components['avg_ctrl']     or 0
    fin  = components['avg_fin_threat'] or 0
    def_ = components['avg_def_resp'] or 0
    iq   = components['avg_iq']       or 0

    if fin >= 70 and off >= 65:  return "Pressure Finisher"
    if ctrl >= 70 and def_ >= 65: return "Grappling Control"
    if off >= 70 and ctrl < 50:  return "Volume Striker"
    if fin >= 65 and ctrl >= 60: return "Submission Hunter"
    if def_ >= 70 and off >= 60: return "Counter Striker"
    if iq >= 70 and off >= 60:   return "Technical Fighter"
    return "Balanced"
