"""
vision/batch.py
Batch pipeline runner — walks the /fight_footage/ directory tree and processes
every fight that has not already been analysed.

Skips:
  - Fights with no video file (youtube_url only → download first with yt_scraper)
  - Fights already represented as a completed vision_job in Supabase

Usage:
    # Dry run: show what would be processed
    python -m vision.batch --footage-root fight_footage --dry-run

    # Process all pending fights
    python -m vision.batch --footage-root fight_footage --device cuda --interval 2.0

    # Process only benchmark fights
    python -m vision.batch --footage-root fight_footage --benchmark-only --device cuda

    # Process a single event subfolder
    python -m vision.batch --footage-root fight_footage/pfc_50 --device cuda
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Set

log = logging.getLogger(__name__)


def _get_completed_sources(supabase_url: str, supabase_key: str) -> Set[str]:
    """Return the set of video_source strings already in vision_jobs as 'done'."""
    try:
        from supabase import create_client
        sb = create_client(supabase_url, supabase_key)
        rows = (
            sb.table("vision_jobs")
            .select("video_source")
            .eq("status", "done")
            .execute()
            .data
        )
        return {r["video_source"] for r in rows}
    except Exception as exc:
        log.warning("Could not query vision_jobs (continuing anyway): %s", exc)
        return set()


def run_batch(
    footage_root: Path,
    device: str = "cpu",
    interval: float = 2.0,
    benchmark_only: bool = False,
    dry_run: bool = False,
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
) -> None:
    from .footage import scan_footage
    from .pipeline import run as run_pipeline

    # Optionally skip already-done jobs
    done_sources: Set[str] = set()
    if supabase_url and supabase_key and not dry_run:
        done_sources = _get_completed_sources(supabase_url, supabase_key)
        log.info("Already completed: %d jobs in vision_jobs", len(done_sources))

    processed = skipped = errors = 0

    for item in scan_footage(footage_root):
        if benchmark_only and not item.is_benchmark:
            continue

        source = item.source
        if source is None:
            log.warning("No video source for %s — skipping", item.fight_slug)
            skipped += 1
            continue

        source_str = str(source)
        if source_str in done_sources:
            log.debug("Already processed: %s", source_str)
            skipped += 1
            continue

        if not item.fighter_ids or all(fid is None for fid in item.fighter_ids):
            log.warning("No fighter_ids in metadata for %s — skipping", item.fight_slug)
            skipped += 1
            continue

        for idx, fighter_id in enumerate(item.fighter_ids):
            if fighter_id is None:
                log.debug(
                    "fighter_ids[%d] is None for %s — corner pairings incomplete",
                    idx, item.fight_slug,
                )
                continue

            corner = (item.corner or ["red", "blue"])[idx] if item.corner else ("red" if idx == 0 else "blue")

            if dry_run:
                print(
                    f"[DRY RUN] {item.fight_slug} | fighter={fighter_id} "
                    f"corner={corner} | source={source_str}"
                )
                continue

            log.info(
                "Processing %s | fighter=%s corner=%s",
                item.fight_slug, fighter_id, corner,
            )
            try:
                run_pipeline(
                    source      = source_str,
                    fighter_id  = fighter_id,
                    corner      = corner,
                    interval    = interval,
                    device      = device,
                )
                processed += 1
            except Exception as exc:
                log.error(
                    "Pipeline failed for %s fighter=%s: %s",
                    item.fight_slug, fighter_id, exc,
                )
                errors += 1

    if not dry_run:
        log.info(
            "Batch complete — processed=%d  skipped=%d  errors=%d",
            processed, skipped, errors,
        )
    else:
        log.info("Dry run complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch fight footage pipeline runner")
    p.add_argument("--footage-root", default="fight_footage",
                   help="Root directory to scan (default: fight_footage)")
    p.add_argument("--device",       default="cpu",
                   help="Torch device: cpu | cuda | mps (default: cpu)")
    p.add_argument("--interval",     type=float, default=2.0,
                   help="Frame sampling interval in seconds (default: 2.0)")
    p.add_argument("--benchmark-only", action="store_true",
                   help="Only process fights where is_benchmark=true")
    p.add_argument("--dry-run",      action="store_true",
                   help="List fights that would be processed, without running")
    p.add_argument("--supabase-url", default=None, help="Supabase URL (or set SUPABASE_URL env)")
    p.add_argument("--supabase-key", default=None, help="Supabase service key (or set SUPABASE_SERVICE_KEY env)")
    p.add_argument("--verbose",      action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    import os
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    supa_url = args.supabase_url or os.environ.get("SUPABASE_URL")
    supa_key = args.supabase_key or os.environ.get("SUPABASE_SERVICE_KEY")

    run_batch(
        footage_root    = Path(args.footage_root),
        device          = args.device,
        interval        = args.interval,
        benchmark_only  = args.benchmark_only,
        dry_run         = args.dry_run,
        supabase_url    = supa_url,
        supabase_key    = supa_key,
    )
