"""
scripts/seed_benchmark_fighters.py
===================================
1. Fix broken fighter names in metadata.json files (where the scraper parsed
   partial names like "Gregor" instead of "Conor McGregor").
2. Upsert all 35 benchmark fighters into the Supabase `fighters` table.
3. Run FighterResolver to populate fighter_ids in every metadata.json.

Usage:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/seed_benchmark_fighters.py
    python scripts/seed_benchmark_fighters.py --dry-run
    python scripts/seed_benchmark_fighters.py --footage-root fight_footage/ufc_benchmark
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Corrections map  ➜  { metadata_dir_glob : [ corrected_fighter_names ] }
# Keys are directory name substrings (unique enough to identify the fight).
# ---------------------------------------------------------------------------
NAME_CORRECTIONS: dict[str, list[str]] = {
    "conor_mcgregor_vs_max_holloway": ["Conor McGregor", "Max Holloway"],
    "georges_st_pierre_vs_nick_diaz": ["Georges St-Pierre", "Nick Diaz"],
    "tj_dillashaw_vs_cody_garbrandt_1": ["TJ Dillashaw", "Cody Garbrandt"],
    "sean_omalley_vs_marlon_vera_2": ["Sean O'Malley", "Marlon Vera"],
    "renato_moicano_vs_beno": ["Renato Moicano", "Benoît Saint Denis"],
    # Cyrillic dir — Petr Yan vs Merab Dvalishvili 2
    "HscShxH_JtI": ["Petr Yan", "Merab Dvalishvili"],
}

# ---------------------------------------------------------------------------
# Canonical fighter records for the 35 benchmark fighters.
# Only columns that add real value are included; nulls are omitted so we don't
# overwrite data that may already be in the DB.
# ---------------------------------------------------------------------------
BENCHMARK_FIGHTERS: list[dict] = [
    # ── Featherweight ────────────────────────────────────────────────────────
    {"full_name": "Alexander Volkanovski",  "primary_weight_class": "Featherweight",    "stance": "Orthodox",  "primary_style": "MMA"},
    {"full_name": "Yair Rodriguez",         "primary_weight_class": "Featherweight",    "stance": "Orthodox",  "primary_style": "Muay Thai"},
    {"full_name": "Conor McGregor",         "primary_weight_class": "Featherweight",    "stance": "Southpaw", "primary_style": "Boxing"},
    {"full_name": "Max Holloway",           "primary_weight_class": "Featherweight",    "stance": "Orthodox",  "primary_style": "Boxing"},
    {"full_name": "Diego Lopes",            "primary_weight_class": "Featherweight",    "stance": "Southpaw", "primary_style": "MMA"},
    {"full_name": "Jean Silva",             "primary_weight_class": "Featherweight",    "stance": "Orthodox",  "primary_style": "BJJ"},
    # ── Lightweight ──────────────────────────────────────────────────────────
    {"full_name": "Dustin Poirier",         "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "Boxing"},
    {"full_name": "Dan Hooker",             "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "Muay Thai"},
    {"full_name": "Eddie Alvarez",          "primary_weight_class": "Lightweight",      "stance": "Southpaw", "primary_style": "Boxing"},
    {"full_name": "Justin Gaethje",         "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "Wrestling"},
    {"full_name": "Islam Makhachev",        "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "Wrestling"},
    {"full_name": "Arman Tsarukyan",        "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "Wrestling"},
    {"full_name": "Rafael Fiziev",          "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "Muay Thai"},
    {"full_name": "Khabib Nurmagomedov",    "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "Wrestling"},
    {"full_name": "Paddy Pimblett",         "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "BJJ"},
    {"full_name": "Michael Chandler",       "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "Wrestling"},
    {"full_name": "Renato Moicano",         "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "BJJ"},
    {"full_name": "Benoît Saint Denis",     "primary_weight_class": "Lightweight",      "stance": "Orthodox",  "primary_style": "MMA"},
    # ── Welterweight ─────────────────────────────────────────────────────────
    {"full_name": "Georges St-Pierre",      "primary_weight_class": "Welterweight",     "stance": "Orthodox",  "primary_style": "Wrestling"},
    {"full_name": "Nick Diaz",              "primary_weight_class": "Welterweight",     "stance": "Southpaw", "primary_style": "Boxing"},
    {"full_name": "Khamzat Chimaev",        "primary_weight_class": "Welterweight",     "stance": "Orthodox",  "primary_style": "Wrestling"},
    {"full_name": "Kamaru Usman",           "primary_weight_class": "Welterweight",     "stance": "Orthodox",  "primary_style": "Wrestling"},
    # ── Middleweight ─────────────────────────────────────────────────────────
    {"full_name": "Sean Strickland",        "primary_weight_class": "Middleweight",     "stance": "Orthodox",  "primary_style": "Boxing"},
    {"full_name": "Yoel Romero",            "primary_weight_class": "Middleweight",     "stance": "Orthodox",  "primary_style": "Wrestling"},
    {"full_name": "Paulo Costa",            "primary_weight_class": "Middleweight",     "stance": "Orthodox",  "primary_style": "Boxing"},
    # ── Light Heavyweight ────────────────────────────────────────────────────
    {"full_name": "Jiri Prochazka",         "primary_weight_class": "Light Heavyweight","stance": "Southpaw", "primary_style": "Muay Thai"},
    {"full_name": "Khalil Rountree",        "primary_weight_class": "Light Heavyweight","stance": "Orthodox",  "primary_style": "Boxing"},
    # ── Bantamweight ─────────────────────────────────────────────────────────
    {"full_name": "Sean O'Malley",          "primary_weight_class": "Bantamweight",     "stance": "Southpaw", "primary_style": "Boxing"},
    {"full_name": "Marlon Vera",            "primary_weight_class": "Bantamweight",     "stance": "Orthodox",  "primary_style": "MMA"},
    {"full_name": "TJ Dillashaw",           "primary_weight_class": "Bantamweight",     "stance": "Orthodox",  "primary_style": "Wrestling"},
    {"full_name": "Cody Garbrandt",         "primary_weight_class": "Bantamweight",     "stance": "Orthodox",  "primary_style": "Boxing"},
    {"full_name": "Petr Yan",               "primary_weight_class": "Bantamweight",     "stance": "Orthodox",  "primary_style": "Boxing"},
    {"full_name": "Merab Dvalishvili",      "primary_weight_class": "Bantamweight",     "stance": "Orthodox",  "primary_style": "Wrestling"},
    # ── Flyweight ────────────────────────────────────────────────────────────
    {"full_name": "Joshua Van",             "primary_weight_class": "Flyweight",        "stance": "Orthodox",  "primary_style": "MMA"},
    {"full_name": "Brandon Royval",         "primary_weight_class": "Flyweight",        "stance": "Orthodox",  "primary_style": "BJJ"},
]
for f in BENCHMARK_FIGHTERS:
    f["is_active"] = True


# ---------------------------------------------------------------------------
# Step 1 – Fix broken metadata fighter_names
# ---------------------------------------------------------------------------
def fix_metadata_names(footage_root: Path, dry_run: bool) -> int:
    fixed = 0
    for meta_path in sorted(footage_root.rglob("metadata.json")):
        dir_name = meta_path.parent.name
        match_key = next(
            (k for k in NAME_CORRECTIONS if k.lower() in dir_name.lower()), None
        )
        if match_key is None:
            continue

        with meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)

        old_names = meta.get("fighter_names", [])
        new_names = NAME_CORRECTIONS[match_key]
        if old_names == new_names:
            continue

        log.info("  Fix [%s]: %s  →  %s", dir_name[:60], old_names, new_names)
        if not dry_run:
            meta["fighter_names"] = new_names
            # Reset ids so resolver re-runs
            meta["fighter_ids"] = [None] * len(new_names)
            with meta_path.open("w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
        fixed += 1
    return fixed


# ---------------------------------------------------------------------------
# Step 2 – Upsert fighters into Supabase
# ---------------------------------------------------------------------------
def upsert_fighters(sb, fighters: list[dict], dry_run: bool) -> tuple[int, int]:
    """Return (inserted, already_existed)."""
    inserted = already_existed = 0
    for record in fighters:
        name = record["full_name"]
        existing = sb.table("fighters").select("id, full_name").ilike(
            "full_name", name
        ).execute()
        if existing.data:
            log.info("  SKIP (exists): %s  [%s]", name, existing.data[0]["id"])
            already_existed += 1
            continue
        log.info("  INSERT: %s", name)
        if not dry_run:
            sb.table("fighters").insert(record).execute()
        inserted += 1
    return inserted, already_existed


# ---------------------------------------------------------------------------
# Step 3 – Resolve fighter names → IDs in metadata.json
# ---------------------------------------------------------------------------
def resolve_all(footage_root: Path, sb, dry_run: bool) -> tuple[int, int, int]:
    """Thin wrapper around FighterResolver logic."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from vision.resolve_fighters import FighterResolver, resolve_footage_root

    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    resolver = FighterResolver(url, key)
    return resolve_footage_root(footage_root, resolver, dry_run=dry_run)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed benchmark fighters + resolve metadata IDs")
    p.add_argument("--footage-root", default="fight_footage",
                   help="Root footage directory (default: fight_footage)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would change without writing")
    p.add_argument("--skip-upsert", action="store_true",
                   help="Skip upserting fighters (useful if already seeded)")
    p.add_argument("--skip-resolve", action="store_true",
                   help="Skip metadata resolve step")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit(
            "ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
        )

    from supabase import create_client
    sb = create_client(url, key)

    footage_root = Path(args.footage_root)

    # ── Step 1: fix broken metadata names
    log.info("=== Step 1: Fix metadata.json fighter_names ===")
    fixed = fix_metadata_names(footage_root, dry_run=args.dry_run)
    log.info("  Fixed %d metadata files", fixed)

    # ── Step 2: upsert fighters
    if not args.skip_upsert:
        log.info("=== Step 2: Upsert %d benchmark fighters ===", len(BENCHMARK_FIGHTERS))
        inserted, skipped = upsert_fighters(sb, BENCHMARK_FIGHTERS, dry_run=args.dry_run)
        log.info("  Inserted: %d  |  Already existed: %d", inserted, skipped)
    else:
        log.info("=== Step 2: Skipped (--skip-upsert) ===")

    # ── Step 3: resolve fighter_ids in metadata
    if not args.skip_resolve:
        log.info("=== Step 3: Resolve fighter_ids in metadata.json ===")
        resolved, already_set, unresolved = resolve_all(footage_root, sb, dry_run=args.dry_run)
        log.info(
            "  Resolved: %d  |  Already set: %d  |  Unresolved: %d",
            resolved, already_set, unresolved,
        )
        if unresolved:
            log.warning("  %d fighter(s) could not be resolved — check names above", unresolved)
    else:
        log.info("=== Step 3: Skipped (--skip-resolve) ===")

    log.info("Done.")


if __name__ == "__main__":
    main()
