"""
scripts/simulation/build_probability_tables.py

Build win-probability and finish-method lookup tables from real UFC fight data
in the simulation_calibration materialised view.

The resulting tables are saved to `system_config` in Supabase under the key
'simulation_probability_tables' so the simulation engine can retrieve them at
runtime without re-scanning the fight history every request.

Usage (standalone):
    python -m scripts.simulation.build_probability_tables

The module also exports `build_outcome_probability_tables(db)` for use inside
the batch pipeline or any async context that already has a DB connection.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections import defaultdict

import httpx


# ---------------------------------------------------------------------------
# Core builder  (takes any asyncpg-compatible `db` connection pool)
# ---------------------------------------------------------------------------

async def build_outcome_probability_tables(db) -> dict:
    """
    Build lookup tables for simulation from real UFC FPS data.

    Reads from simulation_calibration (populated once both fighters have a
    computed career_fps).  Groups fights by delta_bucket and calculates:

      - favorite_win_rate
      - ko_tko_rate / submission_rate / decision_rate
      - round_distribution (among finishes only)
      - finish_threat_avg / durability_avg  (style modifiers for round sim)
      - avg_ctrl_share (grappling modifier)

    Persists result JSON to system_config so the simulation API can load it
    in O(1) without re-running this query.
    """

    fights = await db.fetch("""
        SELECT
            delta_bucket,
            fighter_a_won,
            was_ko,
            was_sub,
            was_decision,
            actual_finish_round,
            rounds_scheduled,
            a_fin_threat,
            b_durability,
            a_ctrl,
            b_ctrl
        FROM simulation_calibration
    """)

    if not fights:
        print("simulation_calibration is empty — run the UFC data pipeline first.")
        return {}

    # Group by delta bucket
    buckets: dict[str, list[dict]] = defaultdict(list)
    for fight in fights:
        buckets[fight["delta_bucket"]].append(dict(fight))

    tables: dict[str, dict] = {}

    for bucket, bucket_fights in sorted(buckets.items()):
        n = len(bucket_fights)

        # ── Win rate ───────────────────────────────────────────────────────
        win_rate = sum(f["fighter_a_won"] for f in bucket_fights) / n

        # ── Finish method rates ────────────────────────────────────────────
        ko_rate  = sum(f["was_ko"]       for f in bucket_fights) / n
        sub_rate = sum(f["was_sub"]      for f in bucket_fights) / n
        dec_rate = sum(f["was_decision"] for f in bucket_fights) / n

        # ── Round distribution (finishes only) ────────────────────────────
        finish_fights = [f for f in bucket_fights if not f["was_decision"]]
        round_dist: dict[int, int] = defaultdict(int)
        for f in finish_fights:
            if f["actual_finish_round"]:
                round_dist[f["actual_finish_round"]] += 1
        total_finishes = len(finish_fights) or 1
        round_probs = {str(r): round(c / total_finishes, 3)
                       for r, c in sorted(round_dist.items())}

        # ── Style modifiers ───────────────────────────────────────────────
        # Average finish-threat and durability across fights in this bucket.
        # Used by the round simulator to weight KO probability up/down.
        fin_threat_values = [
            f["a_fin_threat"] for f in bucket_fights if f["a_fin_threat"] is not None
        ]
        durability_values = [
            f["b_durability"] for f in bucket_fights if f["b_durability"] is not None
        ]
        ctrl_a_values = [f["a_ctrl"] for f in bucket_fights if f["a_ctrl"] is not None]
        ctrl_b_values = [f["b_ctrl"] for f in bucket_fights if f["b_ctrl"] is not None]

        avg_fin_threat  = round(sum(fin_threat_values)  / len(fin_threat_values),  1) if fin_threat_values  else None
        avg_durability  = round(sum(durability_values)  / len(durability_values),  1) if durability_values  else None
        avg_ctrl_share_a = round(sum(ctrl_a_values) / len(ctrl_a_values), 1) if ctrl_a_values else None
        avg_ctrl_share_b = round(sum(ctrl_b_values) / len(ctrl_b_values), 1) if ctrl_b_values else None

        tables[bucket] = {
            "sample_size":        n,
            "favorite_win_rate":  round(win_rate,  3),
            "ko_tko_rate":        round(ko_rate,   3),
            "submission_rate":    round(sub_rate,  3),
            "decision_rate":      round(dec_rate,  3),
            "round_distribution": round_probs,
            # Style modifiers (may be None if data not yet populated)
            "avg_finish_threat":  avg_fin_threat,
            "avg_durability":     avg_durability,
            "avg_ctrl_share_a":   avg_ctrl_share_a,
            "avg_ctrl_share_b":   avg_ctrl_share_b,
        }

        print(f"\nBucket: {bucket} (n={n})")
        print(f"  Favorite wins: {win_rate:.1%}")
        print(f"  KO/TKO: {ko_rate:.1%} | Sub: {sub_rate:.1%} | Dec: {dec_rate:.1%}")
        if round_probs:
            print(f"  Round dist:   {round_probs}")

    # ── Persist to Supabase for runtime lookup ────────────────────────────
    await db.execute("""
        INSERT INTO system_config (key, value, updated_at)
        VALUES ('simulation_probability_tables', $1, NOW())
        ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
    """, json.dumps(tables))

    print(f"\nProbability tables built from {len(fights)} real UFC fights "
          f"across {len(tables)} delta buckets.")
    print("Saved to system_config['simulation_probability_tables'].")
    return tables


# ---------------------------------------------------------------------------
# Standalone entry-point (uses Supabase Management API + asyncpg)
# ---------------------------------------------------------------------------

async def _main_standalone() -> None:
    """Run directly: python -m scripts.simulation.build_probability_tables"""
    try:
        import asyncpg  # type: ignore[import]
    except ImportError:
        raise SystemExit("asyncpg not installed — run: pip install asyncpg")

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise SystemExit(
            "SUPABASE_DB_URL not set.\n"
            "Set it to: postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres"
        )

    conn = await asyncpg.connect(db_url)
    try:
        await build_outcome_probability_tables(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main_standalone())
