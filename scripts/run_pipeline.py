#!/usr/bin/env python3
"""
scripts/run_pipeline.py

End-to-end UFC data pipeline orchestrator.

Stages
------
0. SETUP   ? ensure one-time DB constraints exist (idempotent)
1. SCRAPE  ? pull all events + fights + round stats from ufcstats.com
             ? data/ufc_all_fights.json  (cached; re-scrape with --fresh)
2. FILTER  ? keep fights where ?1 fighter has 5+ appearances
             ? data/filtered_fights.json
3. SCORE   ? compute RPS per round + FPS per fight (pure Python, no DB)
4. PERSIST ? upsert fighters / fights / round_stats to Supabase via PostgREST
5. APPEARANCES ? update ufc_appearances counts per fighter
6. CAREER  ? compute career FPS for fighters with 5+ scored fights
7. REFRESH ? REFRESH MATERIALIZED VIEW simulation_calibration

Usage
-----
    python scripts/run_pipeline.py           # full run (uses cache)
    python scripts/run_pipeline.py --fresh   # discard scrape cache, re-pull
    python scripts/run_pipeline.py --skip-scrape   # start from stage 2
    python scripts/run_pipeline.py --skip-persist  # score only, no DB writes
    python scripts/run_pipeline.py --limit 100     # process first 100 fights
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
import time
from pathlib import Path

# Force UTF-8 stdout/stderr so Unicode in print() doesn't crash on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx

# ?? Project paths ?????????????????????????????????????????????????????????????
REPO_ROOT = Path(__file__).resolve().parent.parent  # AI-Combat-Coach/
DATA_DIR  = REPO_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ?? Supabase config ???????????????????????????????????????????????????????????
SUPABASE_URL = "https://cxvtipiogkgpqiksakld.supabase.co"
SUPABASE_SERVICE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN4dnRpcGlvZ2tncHFpa3Nha2xkIiwicm9sZSI6"
    "InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDc0ODAzNywiZXhwIjoyMDkwMzI0MDM3fQ"
    ".4VR7AB701DMRD-g8KFntVlCucr9GQITqYDXddqWHFrk"
)
REST_HEADERS = {
    "apikey":        SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type":  "application/json",
}

# Management API (for raw SQL ? career FPS + mat view refresh)
SUPABASE_PROJECT_REF = "cxvtipiogkgpqiksakld"
SUPABASE_API_BASE    = "https://api.supabase.com/v1"

BATCH_SIZE = 200   # rows per POST

# ufcstats date format ? ISO
import re as _re
from datetime import datetime as _dt

_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

def _parse_date(raw: str | None) -> str | None:
    """Convert 'June 14, 2024' ? '2024-06-14'. Returns None on failure."""
    if not raw:
        return None
    raw = raw.strip()
    # Try ISO first
    if _re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    # Try "Month DD, YYYY"
    m = _re.match(r"(\w+)\s+(\d+),?\s+(\d{4})", raw)
    if m:
        month = _MONTH_MAP.get(m.group(1).lower())
        if month:
            return f"{m.group(3)}-{month}-{int(m.group(2)):02d}"
    return None


# ?? Credential helper (Management API token) ?????????????????????????????????
import ctypes
import ctypes.wintypes as wt
import os

class _CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wt.DWORD), ("Type", wt.DWORD), ("TargetName", wt.LPWSTR),
        ("Comment", wt.LPWSTR), ("LastWritten", wt.FILETIME),
        ("CredentialBlobSize", wt.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wt.DWORD), ("AttributeCount", wt.DWORD),
        ("Attributes", ctypes.c_void_p), ("TargetAlias", wt.LPWSTR),
        ("UserName", wt.LPWSTR),
    ]

def _read_windows_credential(target: str) -> str | None:
    try:
        ptr = ctypes.c_void_p()
        ok = ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(ptr))
        if not ok:
            return None
        cred = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
        blob = bytes(cred.CredentialBlob[i] for i in range(cred.CredentialBlobSize))
        ctypes.windll.advapi32.CredFree(ptr)
        return blob.decode("utf-8", errors="replace")
    except Exception:
        return None

def _get_mgmt_token() -> str | None:
    return (
        _read_windows_credential("Supabase CLI:supabase")
        or os.environ.get("SUPABASE_ACCESS_TOKEN")
    )


# ?????????????????????????????????????????????????????????????????????????????
# PostgREST helpers
# ?????????????????????????????????????????????????????????????????????????????

def _rest_upsert(client: httpx.Client, table: str, rows: list[dict],
                 on_conflict: str, *, returning: bool = False) -> list[dict]:
    """
    Upsert a batch of rows via PostgREST.
    Returns inserted/updated rows (with server-generated IDs) when returning=True.
    """
    url     = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        **REST_HEADERS,
        "Prefer": f"resolution=merge-duplicates,return={'representation' if returning else 'minimal'}",
    }
    params = {"on_conflict": on_conflict}
    resp = client.post(url, headers=headers, params=params, json=rows, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"PostgREST upsert {table} failed {resp.status_code}: {resp.text[:300]}")
    return resp.json() if returning else []


def _rest_patch(client: httpx.Client, table: str, match: dict, updates: dict) -> None:
    """PATCH a single row matching `match` filters."""
    url     = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {**REST_HEADERS, "Prefer": "return=minimal"}
    params  = {k: f"eq.{v}" for k, v in match.items()}
    resp = client.patch(url, headers=headers, params=params, json=updates, timeout=30)
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"PostgREST PATCH {table} failed {resp.status_code}: {resp.text[:200]}")


def _rest_select(client: httpx.Client, table: str, filters: dict,
                 columns: str = "*") -> list[dict]:
    """SELECT rows matching `filters`."""
    url    = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {**{k: f"eq.{v}" for k, v in filters.items()}, "select": columns}
    resp = client.get(url, headers=REST_HEADERS, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"PostgREST SELECT {table} failed {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def _mgmt_sql(sql: str, token: str) -> list[dict]:
    """Execute raw SQL via Management API. Returns rows for SELECT; [] otherwise."""
    url  = f"{SUPABASE_API_BASE}/projects/{SUPABASE_PROJECT_REF}/database/query"
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = httpx.post(url, headers=hdrs, json={"query": sql}, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Management API error {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    return data if isinstance(data, list) else data.get("rows", [])


# ?????????????????????????????????????????????????????????????????????????????
# Import scoring engine
# ?????????????????????????????????????????????????????????????????????????????
sys.path.insert(0, str(REPO_ROOT))

from scripts.scoring_engine.rps_calculator import RPSInputs, calculate_rps
from scripts.scoring_engine.fps_calculator import (
    RoundResult, calculate_fps, get_fps_tier, normalize_method,
)
from scripts.scoring_engine.ufc_derivations import derive_nf, derive_err


# ?????????????????????????????????????????????????????????????????????????????
# Stage 0 ? SETUP (idempotent one-time DB patches)
# ?????????????????????????????????????????????????????????????????????????????

def stage_setup(token: str | None) -> None:
    """
    Ensure one-time DDL changes are in place.
    Safe to call on every run ? all statements use IF NOT EXISTS / DO NOTHING.
    """
    if not token:
        print("[SETUP] No Management API token ? skipping DDL setup")
        print("        UNIQUE constraint on ufc_fighters.name may be missing.")
        return

    print("[SETUP] Ensuring UNIQUE(name) on ufc_fighters ?")
    _mgmt_sql("""
        CREATE UNIQUE INDEX IF NOT EXISTS ufc_fighters_name_unique
        ON ufc_fighters (name)
    """, token)
    print("[SETUP] Done")


# ?????????????????????????????????????????????????????????????????????????????
# Stage 1 ? SCRAPE
# ?????????????????????????????????????????????????????????????????????????????

async def stage_scrape(fresh: bool = False) -> list[dict]:
    cache = DATA_DIR / "ufc_all_fights.json"
    if cache.exists() and not fresh:
        print(f"[SCRAPE] Using cached {cache} ? pass --fresh to re-pull")
        return json.loads(cache.read_text())

    # Import here so httpx + bs4 errors surface clearly
    from scripts.ufc_data_pipeline.scraper import pull_all_ufc_data

    print("[SCRAPE] Pulling events + fights + round stats from ufcstats.com ?")
    print("         This takes ~30?60 minutes on a fresh pull (15k+ requests).")
    t0 = time.time()
    await pull_all_ufc_data()
    elapsed = time.time() - t0
    all_fights = json.loads(cache.read_text())
    print(f"[SCRAPE] Done in {elapsed/60:.1f}m ? {len(all_fights)} fights")
    return all_fights


# ?????????????????????????????????????????????????????????????????????????????
# Stage 2 ? FILTER
# ?????????????????????????????????????????????????????????????????????????????

def stage_filter(all_fights: list[dict], limit: int | None = None) -> list[dict]:
    from scripts.ufc_data_pipeline.filter_and_load import (
        filter_eligible_fighters,
        filter_fights_for_eligible,
    )
    eligible, _ = filter_eligible_fighters(all_fights)
    filtered = filter_fights_for_eligible(all_fights, eligible)

    cache = DATA_DIR / "filtered_fights.json"
    cache.write_text(json.dumps(filtered, indent=2))
    print(f"[FILTER] {len(filtered)} fights saved ? {cache}")

    if limit:
        filtered = filtered[:limit]
        print(f"[FILTER] --limit {limit}: processing first {len(filtered)} fights")

    return filtered


# ?????????????????????????????????????????????????????????????????????????????
# Stage 3+4 ? SCORE + PERSIST
# ?????????????????????????????????????????????????????????????????????????????

def _parse_time_to_seconds(t: str | None) -> int | None:
    if not t:
        return None
    parts = str(t).strip().split(":")
    if len(parts) == 2:
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            pass
    return None


def _infer_rounds_scheduled(fight_data: dict) -> int:
    """
    3-round default; promote to 5 when we can detect it:
    - rounds array has 4+ entries, or
    - finish_round > 3
    """
    rounds_in_data = len(fight_data.get("rounds") or [])
    finish_round   = fight_data.get("finish_round") or 0
    if rounds_in_data >= 4 or finish_round >= 4:
        return 5
    return 3


def score_fight(fight_data: dict) -> dict | None:
    """
    Score a single fight in memory.
    Returns a dict ready for DB insert, or None if data is unusable.
    """
    if not fight_data.get("rounds"):
        return None
    if not fight_data.get("fighter_a_name") or not fight_data.get("fighter_b_name"):
        return None

    finish_seconds   = _parse_time_to_seconds(fight_data.get("finish_time"))
    method_norm      = normalize_method(fight_data.get("method"))
    is_finish        = method_norm in ("ko", "tko", "sub")
    winner_name      = fight_data.get("winner")
    fighter_a_won    = winner_name == fight_data["fighter_a_name"]
    finish_round     = fight_data.get("finish_round")
    rounds_scheduled = _infer_rounds_scheduled(fight_data)

    a_round_results: list[RoundResult] = []
    b_round_results: list[RoundResult] = []
    round_stats_rows: list[dict]       = []   # pending ? fighter_id filled later

    for rd in fight_data["rounds"]:
        rnd              = rd["round"]
        is_finish_round  = (rnd == finish_round and is_finish)
        round_sec        = finish_seconds if is_finish_round else 300

        for fighter_key, fighter_won in [("fighter_a", fighter_a_won),
                                          ("fighter_b", not fighter_a_won)]:
            stats = rd[fighter_key]
            ctx   = {**stats, "is_finish_round": is_finish_round, "fighter_won": fighter_won}

            inp = RPSInputs(
                SL=stats["SL"], SA=stats["SA"],
                KD_F=stats["KD_F"], KD_A=stats["KD_A"],
                TD_F=stats["TD_F"], TA_F=stats["TA_F"],
                TD_A=stats["TD_A"], TA_A=stats["TA_A"],
                CTRL_F=stats["CTRL_F"], CTRL_A=stats["CTRL_A"],
                NF=derive_nf(ctx), ERR=derive_err(ctx),
                SEC=round_sec,
            )
            comp = calculate_rps(inp)

            round_stats_rows.append({
                "_fighter_key": fighter_key,   # resolved to fighter_id later
                "round_number":          rnd,
                "sl": inp.SL,  "sa": inp.SA,
                "kd_f": inp.KD_F, "kd_a": inp.KD_A,
                "td_f": inp.TD_F, "ta_f": inp.TA_F,
                "td_a": inp.TD_A, "ta_a": inp.TA_A,
                "ctrl_f": inp.CTRL_F, "ctrl_a": inp.CTRL_A,
                "sub_att": stats.get("sub_att", 0),
                "nf": inp.NF, "err": inp.ERR, "sec": inp.SEC,
                "is_finish_round":   is_finish_round,
                "fighter_won_fight": fighter_won,
                "offensive_efficiency": comp.offensive_efficiency,
                "defensive_response":   comp.defensive_response,
                "control_dictation":    comp.control_dictation,
                "finish_threat":        comp.finish_threat,
                "durability":           comp.durability,
                "fight_iq":             comp.fight_iq,
                "dominance":            comp.dominance,
                "rps":                  comp.rps,
            })

            rr = RoundResult(round_number=rnd, rps=comp.rps, seconds=round_sec)
            (a_round_results if fighter_key == "fighter_a" else b_round_results).append(rr)

    if not a_round_results:
        return None

    fps_a = calculate_fps(a_round_results, fighter_a_won,
                          fight_data.get("method", ""),
                          finish_round, finish_seconds, rounds_scheduled)
    fps_b = calculate_fps(b_round_results, not fighter_a_won,
                          fight_data.get("method", ""),
                          finish_round, finish_seconds, rounds_scheduled)

    # Hard rule: winner >= loser + 2
    if fighter_a_won:
        if fps_a.fps < fps_b.fps + 2:
            fps_a = dataclasses.replace(fps_a, fps=round(fps_b.fps + 2, 2))
    else:
        if fps_b.fps < fps_a.fps + 2:
            fps_b = dataclasses.replace(fps_b, fps=round(fps_a.fps + 2, 2))

    return {
        "fight_url": fight_data.get("ufcstats_fight_url") or fight_data.get("fight_url"),
        "event_name":         fight_data.get("event_name"),
        "event_date":         fight_data.get("event_date"),
        "weight_class":       fight_data.get("weight_class"),
        "fighter_a_name":     fight_data["fighter_a_name"],
        "fighter_b_name":     fight_data["fighter_b_name"],
        "winner_name":        winner_name,
        "fighter_a_won":      fighter_a_won,
        "method":             fight_data.get("method"),
        "method_normalized":  method_norm,
        "finish_round":       finish_round,
        "finish_time":        fight_data.get("finish_time"),
        "finish_time_seconds": finish_seconds,
        "rounds_scheduled":   rounds_scheduled,
        "fps_a": fps_a.fps,
        "fps_b": fps_b.fps,
        "round_stats": round_stats_rows,
    }


def stage_score_and_persist(
    filtered_fights: list[dict],
    client: httpx.Client,
    skip_persist: bool = False,
) -> None:
    print(f"\n[SCORE] Scoring {len(filtered_fights)} fights ?")

    # ?? Score all fights in memory ????????????????????????????????????????
    scored: list[dict] = []
    skipped = 0
    for fd in filtered_fights:
        result = score_fight(fd)
        if result:
            scored.append(result)
        else:
            skipped += 1

    print(f"[SCORE] {len(scored)} fights scored, {skipped} skipped (no round data)")

    if skip_persist:
        print("[SCORE] --skip-persist: not writing to DB")
        return

    # ?? Upsert all unique fighters ????????????????????????????????????????
    print("\n[PERSIST] Upserting fighters ?")
    all_names: set[str] = set()
    for s in scored:
        all_names.add(s["fighter_a_name"])
        all_names.add(s["fighter_b_name"])

    fighter_rows = [{"name": n} for n in sorted(all_names)]
    upserted_fighters: list[dict] = []
    for i in range(0, len(fighter_rows), BATCH_SIZE):
        batch = fighter_rows[i:i + BATCH_SIZE]
        rows = _rest_upsert(client, "ufc_fighters", batch,
                             on_conflict="name", returning=True)
        upserted_fighters.extend(rows)
        print(f"  fighters {i+len(batch)}/{len(fighter_rows)}", end="\r")

    name_to_id: dict[str, str] = {r["name"]: r["id"] for r in upserted_fighters}
    print(f"\n[PERSIST] {len(name_to_id)} fighters upserted")

    # ?? Upsert fights + round_stats ???????????????????????????????????????
    print("\n[PERSIST] Upserting fights + round stats ?")
    processed = 0
    errors    = 0

    fight_batch:       list[dict] = []
    fight_batch_meta:  list[dict] = []   # keep scored dict for round_stats

    for s in scored:
        a_id = name_to_id.get(s["fighter_a_name"])
        b_id = name_to_id.get(s["fighter_b_name"])
        if not a_id or not b_id:
            errors += 1
            continue

        winner_id = a_id if s["fighter_a_won"] else b_id

        fight_batch.append({
            "ufcstats_fight_url": s["fight_url"],
            "event_name":         s["event_name"],
            "fight_date":         _parse_date(s["event_date"]),
            "weight_class":       s["weight_class"],
            "fighter_a_id":       a_id,
            "fighter_b_id":       b_id,
            "fighter_a_name":     s["fighter_a_name"],
            "fighter_b_name":     s["fighter_b_name"],
            "winner_id":          winner_id,
            "winner_name":        s["winner_name"],
            "method":             s["method"],
            "method_normalized":  s["method_normalized"],
            "finish_round":       s["finish_round"],
            "finish_time":        s["finish_time"],
            "finish_time_seconds": s["finish_time_seconds"],
            "rounds_scheduled":   s["rounds_scheduled"],
            "fighter_a_fps":      s["fps_a"],
            "fighter_b_fps":      s["fps_b"],
        })
        fight_batch_meta.append({"scored": s, "a_id": a_id, "b_id": b_id})

        # Flush in batches
        if len(fight_batch) >= BATCH_SIZE:
            _flush_fights(client, fight_batch, fight_batch_meta, name_to_id)
            processed += len(fight_batch)
            fight_batch      = []
            fight_batch_meta = []
            print(f"  fights {processed}/{len(scored)}", end="\r")

    # Final flush
    if fight_batch:
        _flush_fights(client, fight_batch, fight_batch_meta, name_to_id)
        processed += len(fight_batch)

    print(f"\n[PERSIST] {processed} fights persisted, {errors} errors")


def _flush_fights(
    client: httpx.Client,
    fight_batch: list[dict],
    fight_batch_meta: list[dict],
    name_to_id: dict[str, str],
) -> None:
    """Upsert a batch of fights, then upsert their round_stats."""
    fights_returned = _rest_upsert(
        client, "ufc_fights", fight_batch,
        on_conflict="ufcstats_fight_url", returning=True,
    )
    # Build fight_url ? UUID map
    fight_url_to_id: dict[str, str] = {
        r["ufcstats_fight_url"]: r["id"] for r in fights_returned
    }

    round_batch: list[dict] = []
    for meta, fight_row in zip(fight_batch_meta, fight_batch):
        fight_id = fight_url_to_id.get(fight_row["ufcstats_fight_url"])
        if not fight_id:
            continue
        a_id = meta["a_id"]
        b_id = meta["b_id"]
        for rs in meta["scored"]["round_stats"]:
            fighter_id   = a_id if rs["_fighter_key"] == "fighter_a" else b_id
            fighter_name = (meta["scored"]["fighter_a_name"]
                            if rs["_fighter_key"] == "fighter_a"
                            else meta["scored"]["fighter_b_name"])
            row = {k: v for k, v in rs.items() if k != "_fighter_key"}
            row["fight_id"]     = fight_id
            row["fighter_id"]   = fighter_id
            row["fighter_name"] = fighter_name
            round_batch.append(row)

    if round_batch:
        _rest_upsert(client, "ufc_round_stats", round_batch,
                     on_conflict="fight_id,fighter_id,round_number")


# ?????????????????????????????????????????????????????????????????????????????
# Stage 5 ? UPDATE APPEARANCES
# ?????????????????????????????????????????????????????????????????????????????

def stage_update_appearances(token: str | None) -> None:
    """
    Set ufc_appearances = number of fights in ufc_fights for each fighter.
    This is needed so the generated column `meets_5_fight_threshold` flips to TRUE.
    """
    if not token:
        print("\n[APPEARANCES] No Management API token ? skipping appearance counts")
        return

    print("\n[APPEARANCES] Updating ufc_appearances counts ?")
    result = _mgmt_sql("""
        UPDATE ufc_fighters f
        SET ufc_appearances = counts.cnt
        FROM (
            SELECT fighter_id, COUNT(*) AS cnt
            FROM (
                SELECT fighter_a_id AS fighter_id FROM ufc_fights WHERE fighter_a_id IS NOT NULL
                UNION ALL
                SELECT fighter_b_id AS fighter_id FROM ufc_fights WHERE fighter_b_id IS NOT NULL
            ) all_fighters
            GROUP BY fighter_id
        ) counts
        WHERE f.id = counts.fighter_id
        RETURNING f.id
    """, token)
    print(f"[APPEARANCES] {len(result)} fighters updated")


# ?????????????????????????????????????????????????????????????????????????????
# Stage 6 ? CAREER FPS
# ?????????????????????????????????????????????????????????????????????????????

def stage_career_fps(token: str | None) -> None:
    if not token:
        print("\n[CAREER] No Management API token ? skipping career FPS computation")
        print("         Set SUPABASE_ACCESS_TOKEN or run `supabase login`")
        return

    print("\n[CAREER] Computing career FPS for fighters with 5+ scored fights ?")
    RECENCY_WEIGHTS = [0.35, 0.25, 0.18, 0.12, 0.10]

    # Fetch eligible fighters
    fighters = _mgmt_sql("""
        SELECT id, name FROM ufc_fighters
        WHERE meets_5_fight_threshold = TRUE
        ORDER BY name
    """, token)
    print(f"[CAREER] {len(fighters)} eligible fighters")

    updated = 0
    for fighter in fighters:
        fid = fighter["id"]
        fights = _mgmt_sql(f"""
            SELECT
                CASE WHEN f.fighter_a_id = '{fid}' THEN f.fighter_a_fps
                     ELSE f.fighter_b_fps END AS fps,
                CASE WHEN f.fighter_a_id = '{fid}' THEN f.fighter_a_fps
                     ELSE f.fighter_b_fps END AS fps2
            FROM ufc_fights f
            WHERE (f.fighter_a_id = '{fid}' OR f.fighter_b_id = '{fid}')
              AND CASE WHEN f.fighter_a_id = '{fid}' THEN f.fighter_a_fps
                       ELSE f.fighter_b_fps END IS NOT NULL
            ORDER BY f.fight_date DESC
            LIMIT 5
        """, token)

        if len(fights) < 5:
            continue

        fps_scores = [float(f["fps"]) for f in fights]
        n = min(len(fps_scores), len(RECENCY_WEIGHTS))
        w = RECENCY_WEIGHTS[:n]
        career_fps = sum(s * wt for s, wt in zip(fps_scores, w)) / sum(w)

        # Component averages across last 5 fights
        comps = _mgmt_sql(f"""
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
            WHERE rs.fighter_id = '{fid}'
              AND f.fight_date >= (
                SELECT MIN(fight_date) FROM (
                    SELECT fight_date FROM ufc_fights
                    WHERE fighter_a_id = '{fid}' OR fighter_b_id = '{fid}'
                    ORDER BY fight_date DESC LIMIT 5
                ) sub
              )
        """, token)
        c = comps[0] if comps else {}

        tier = get_fps_tier(career_fps)
        _mgmt_sql(f"""
            UPDATE ufc_fighters SET
                career_fps               = {round(career_fps, 2)},
                career_fps_tier          = '{tier}',
                fps_fight_count          = {n},
                fps_last_calculated      = NOW(),
                avg_offensive_efficiency = {c.get('avg_off_eff') or 'NULL'},
                avg_defensive_response   = {c.get('avg_def_resp') or 'NULL'},
                avg_control_dictation    = {c.get('avg_ctrl')     or 'NULL'},
                avg_finish_threat        = {c.get('avg_fin_threat') or 'NULL'},
                avg_durability           = {c.get('avg_dur')       or 'NULL'},
                avg_fight_iq             = {c.get('avg_iq')        or 'NULL'},
                avg_dominance            = {c.get('avg_dom')       or 'NULL'}
            WHERE id = '{fid}'
        """, token)
        updated += 1

    print(f"[CAREER] {updated} fighters updated with career FPS")


# ?????????????????????????????????????????????????????????????????????????????
# Stage 7 ? REFRESH MATERIALIZED VIEW
# ?????????????????????????????????????????????????????????????????????????????

def stage_refresh_mat_view(token: str | None) -> None:
    if not token:
        print("\n[REFRESH] No Management API token ? skipping mat view refresh")
        return
    print("\n[REFRESH] Refreshing simulation_calibration ?")
    _mgmt_sql("REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_calibration", token)
    rows = _mgmt_sql("SELECT COUNT(*) AS n FROM simulation_calibration", token)
    count = rows[0]["n"] if rows else "?"
    print(f"[REFRESH] simulation_calibration now has {count} rows")


# ?????????????????????????????????????????????????????????????????????????????
# Entry point
# ?????????????????????????????????????????????????????????????????????????????

def main() -> None:
    parser = argparse.ArgumentParser(description="UFC data pipeline")
    parser.add_argument("--fresh",        action="store_true",
                        help="Discard scrape cache and re-pull from ufcstats.com")
    parser.add_argument("--skip-scrape",  action="store_true",
                        help="Skip stage 1 ? use existing data/ufc_all_fights.json")
    parser.add_argument("--skip-persist", action="store_true",
                        help="Score fights but do not write to Supabase")
    parser.add_argument("--limit",        type=int, default=None,
                        help="Process only the first N filtered fights (for testing)")
    args = parser.parse_args()

    t_start = time.time()
    token   = _get_mgmt_token()

    # ?? Stage 0: Setup ????????????????????????????????????????????????????
    if not args.skip_persist:
        stage_setup(token)

    # ?? Stage 1: Scrape ???????????????????????????????????????????????????
    if args.skip_scrape:
        cache = DATA_DIR / "ufc_all_fights.json"
        if not cache.exists():
            sys.exit(f"--skip-scrape set but {cache} does not exist. Run without flag first.")
        print(f"[SCRAPE] Using {cache}")
        all_fights = json.loads(cache.read_text())
    else:
        all_fights = asyncio.run(stage_scrape(fresh=args.fresh))

    # ?? Stage 2: Filter ???????????????????????????????????????????????????
    filtered = stage_filter(all_fights, limit=args.limit)

    # ?? Stage 3+4: Score + Persist ????????????????????????????????????????
    with httpx.Client() as client:
        stage_score_and_persist(filtered, client, skip_persist=args.skip_persist)

    # ?? Stage 5: Appearances ??????????????????????????????????????????????
    if not args.skip_persist:
        stage_update_appearances(token)

    # ?? Stage 6: Career FPS ???????????????????????????????????????????????
    if not args.skip_persist:
        stage_career_fps(token)
        stage_refresh_mat_view(token)

    elapsed = time.time() - t_start
    print(f"\n[DONE] Pipeline complete in {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()
