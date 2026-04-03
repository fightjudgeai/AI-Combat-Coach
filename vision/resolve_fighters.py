"""
vision/resolve_fighters.py
Populate fighter_ids in metadata.json by fuzzy-matching fighter_names against
the Supabase fighters + scraped_fighters tables.

For each fight directory where fighter_ids[i] is null:
  1. Query fighters.full_name ILIKE (fuzzy) → return id (UUID)
  2. Fallback: scraped_fighters.name ILIKE → return id (TEXT)
  3. If still unresolved, leave null and log a warning

Updates metadata.json in-place.  Safe to re-run — only fills null slots.

Usage:
    # Dry-run: show what would be resolved without writing
    python -m vision.resolve_fighters --footage-root fight_footage --dry-run

    # Resolve and patch all metadata.json files
    python -m vision.resolve_fighters --footage-root fight_footage

    # Credentials via env (recommended)
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python -m vision.resolve_fighters ...
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB lookup
# ---------------------------------------------------------------------------

class FighterResolver:
    """Resolves a fighter name to a DB id via Supabase REST."""

    def __init__(self, supabase_url: str, supabase_key: str):
        try:
            from supabase import create_client
        except ImportError:
            raise ImportError("supabase-py required: pip install supabase")
        self._sb  = create_client(supabase_url, supabase_key)
        self._cache: dict[str, Optional[str]] = {}

    def resolve(self, name: str) -> Optional[str]:
        """Return fighter UUID (or TEXT id for scraped) for a display name."""
        if name in self._cache:
            return self._cache[name]

        fighter_id = self._lookup_fighters(name) or self._lookup_scraped(name)
        self._cache[name] = fighter_id

        if fighter_id:
            log.info("  ✓ %s  →  %s", name, fighter_id)
        else:
            log.warning("  ✗ Could not resolve: '%s'", name)

        return fighter_id

    def _lookup_fighters(self, name: str) -> Optional[str]:
        """Check the verified fighters table (full_name)."""
        try:
            rows = (
                self._sb.table("fighters")
                .select("id, full_name")
                .ilike("full_name", f"%{name}%")
                .limit(1)
                .execute()
                .data
            )
            return rows[0]["id"] if rows else None
        except Exception as exc:
            log.debug("fighters lookup error for '%s': %s", name, exc)
            return None

    def _lookup_scraped(self, name: str) -> Optional[str]:
        """Check the scraped/roster fighter tables as fallback."""
        for table, col in [("scraped_fighters", "name"), ("locker_room_fighters", "name")]:
            try:
                rows = (
                    self._sb.table(table)
                    .select("id, name")
                    .ilike(col, f"%{name}%")
                    .limit(1)
                    .execute()
                    .data
                )
                if rows:
                    return rows[0]["id"]
            except Exception as exc:
                log.debug("%s lookup error for '%s': %s", table, name, exc)
        return None


# ---------------------------------------------------------------------------
# Metadata patching
# ---------------------------------------------------------------------------

def resolve_footage_root(
    root: Path,
    resolver: FighterResolver,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """
    Walk all metadata.json files under root.
    Returns (resolved_count, already_set_count, unresolved_count).
    """
    resolved = already_set = unresolved = 0

    if not root.exists():
        log.warning("Footage root not found: %s", root)
        return 0, 0, 0

    for meta_path in sorted(root.rglob("metadata.json")):
        with meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)

        names = meta.get("fighter_names") or []
        ids   = meta.get("fighter_ids")   or [None] * len(names)

        # Pad ids list if shorter than names
        while len(ids) < len(names):
            ids.append(None)

        changed = False
        for i, (name, fid) in enumerate(zip(names, ids)):
            if fid is not None:
                already_set += 1
                continue
            if not name or name in ("Unknown", ""):
                log.warning("%s: fighter_names[%d] is unset — skipping", meta_path.parent.name, i)
                unresolved += 1
                continue

            log.info("[%s] resolving '%s' ...", meta_path.parent.name, name)
            found = resolver.resolve(name)
            if found:
                ids[i]   = found
                changed  = True
                resolved += 1
            else:
                unresolved += 1

        if changed:
            meta["fighter_ids"] = ids
            if dry_run:
                log.info("  [DRY RUN] would write fighter_ids=%s", ids)
            else:
                with meta_path.open("w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2, ensure_ascii=False)
                log.info("  Updated: %s", meta_path)

    return resolved, already_set, unresolved


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resolve fighter names to DB IDs in metadata.json")
    p.add_argument("--footage-root",  default="fight_footage",
                   help="Root footage directory (default: fight_footage)")
    p.add_argument("--supabase-url",  default=None)
    p.add_argument("--supabase-key",  default=None,
                   help="Supabase service key (or set SUPABASE_SERVICE_KEY env)")
    p.add_argument("--dry-run",       action="store_true",
                   help="Show what would change without writing files")
    p.add_argument("--verbose",       action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    url = args.supabase_url or os.environ.get("SUPABASE_URL")
    key = args.supabase_key or os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print(
            "ERROR: Supabase credentials required.\n"
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars, "
            "or pass --supabase-url / --supabase-key.\n"
            "\nExample:\n"
            "  $env:SUPABASE_URL='https://xxxx.supabase.co'\n"
            "  $env:SUPABASE_SERVICE_KEY='eyJh...'\n"
            "  python -m vision.resolve_fighters --footage-root fight_footage",
            file=sys.stderr,
        )
        sys.exit(1)

    resolver = FighterResolver(url, key)
    resolved, already_set, unresolved = resolve_footage_root(
        Path(args.footage_root), resolver, dry_run=args.dry_run
    )

    print(
        f"\nDone — resolved: {resolved}  already set: {already_set}"
        f"  unresolved: {unresolved}"
        + ("  [DRY RUN]" if args.dry_run else "")
    )
    if unresolved:
        print(
            "\nFor unresolved fighters, manually edit the metadata.json files\n"
            "and set 'fighter_ids' to the correct Supabase fighter UUIDs."
        )
    sys.exit(0 if unresolved == 0 else 2)
