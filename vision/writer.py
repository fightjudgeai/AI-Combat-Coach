"""
vision/writer.py
Write computed style attributes, event log, and summary to Supabase.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def _to_json_safe(obj: Any) -> Any:
    """Recursively convert numpy/non-native types to JSON-serialisable Python types."""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    # numpy scalars expose .item(); numpy arrays expose .tolist()
    if hasattr(obj, "item"):
        return obj.item()
    if hasattr(obj, "tolist"):
        return obj.tolist()
    return obj

from supabase import create_client, Client

from .events import FightEvent


def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Vision job lifecycle
# ---------------------------------------------------------------------------

def create_job(
    video_source: str,
    source_type: str,
    fighter_id: Optional[str] = None,
) -> str:
    """
    Insert a vision_job row in 'running' state. Returns job UUID.

    If a job already exists for this video_source with status 'running' or
    'pending' (e.g. a previous interrupted run or concurrent container),
    returns its existing id instead of creating a duplicate.
    """
    client = _get_client()

    # Check for an existing non-done job for this source first
    existing = (
        client.table("vision_jobs")
        .select("id,status")
        .eq("video_source", video_source)
        .neq("status", "done")
        .neq("status", "error")
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return existing[0]["id"]

    row = {
        "video_source": video_source,
        "source_type":  source_type,
        "status":       "running",
    }
    if fighter_id:
        row["fighter_id"] = fighter_id

    res = client.table("vision_jobs").insert(row).execute()
    return res.data[0]["id"]


def complete_job(
    job_id: str,
    frames_sampled: int,
    duration_secs: float,
    raw_attributes: Dict[str, Any],
) -> None:
    _get_client().table("vision_jobs").update({
        "status":         "done",
        "frames_sampled": frames_sampled,
        "duration_secs":  duration_secs,
        "raw_attributes": _to_json_safe(raw_attributes),
    }).eq("id", job_id).execute()


def fail_job(job_id: str, error_msg: str) -> None:
    _get_client().table("vision_jobs").update({
        "status":    "error",
        "error_msg": error_msg[:2000],
    }).eq("id", job_id).execute()


# ---------------------------------------------------------------------------
# Fighter update
# ---------------------------------------------------------------------------

def update_fighter_attributes(fighter_id: str, attrs: Dict[str, Any]) -> None:
    """
    Patch only the non-None style columns on the fighters row.
    Merges style_tags with any existing tags (union, preserves existing).
    """
    client = _get_client()

    # Fetch current style_tags so we can merge
    existing = (
        client.table("fighters")
        .select("style_tags")
        .eq("id", fighter_id)
        .single()
        .execute()
        .data
    )
    existing_tags: list = existing.get("style_tags") or []

    patch: Dict[str, Any] = {}

    for col in ("stance", "pressure_rating", "clinch_frequency",
                "grappling_first", "late_round_fade", "finish_urgency"):
        val = attrs.get(col)
        if val is not None:
            patch[col] = val

    new_tags = attrs.get("style_tags") or []
    merged_tags = list(dict.fromkeys(existing_tags + new_tags))  # dedupe, preserve order
    if merged_tags:
        patch["style_tags"] = merged_tags

    if patch:
        client.table("fighters").update(_to_json_safe(patch)).eq("id", fighter_id).execute()


# ---------------------------------------------------------------------------
# Event log + summary
# ---------------------------------------------------------------------------

_BATCH_SIZE = 500   # max rows per Supabase insert call


def insert_events(
    job_id: str,
    fighter_id: Optional[str],
    events: List[FightEvent],
) -> None:
    """Batch-insert all FightEvent rows into fight_events."""
    if not events:
        return
    client = _get_client()
    rows = [_to_json_safe(e.to_db_row(job_id, fighter_id)) for e in events]
    for i in range(0, len(rows), _BATCH_SIZE):
        client.table("fight_events").insert(rows[i:i + _BATCH_SIZE]).execute()


def upsert_summary(
    job_id: str,
    fighter_id: Optional[str],
    summary: Dict[str, Any],
) -> None:
    """Upsert a fight_event_summary row (unique on job_id + fighter_id)."""
    client = _get_client()
    row = _to_json_safe({"job_id": job_id, "fighter_id": fighter_id, **summary})
    try:
        client.table("fight_event_summary").upsert(row, on_conflict="job_id,fighter_id").execute()
    except Exception as exc:
        # If migration 007 hasn't been applied yet, the JSONB columns and
        # kicks_missed_head/body/leg won't exist.  Strip them and retry so
        # that the core stats are still persisted.
        if "does not exist" in str(exc) or "PGRST204" in str(exc) or "Could not find" in str(exc):
            _MIG_007_COLS = {
                "body_part_frames", "kinematic_features", "spatial_coverage",
                "kicks_missed_head", "kicks_missed_body", "kicks_missed_leg",
            }
            stripped = {k: v for k, v in row.items() if k not in _MIG_007_COLS}
            log.warning("Migration 007 not applied — retrying upsert without new columns")
            client.table("fight_event_summary").upsert(
                stripped, on_conflict="job_id,fighter_id"
            ).execute()
        else:
            raise
