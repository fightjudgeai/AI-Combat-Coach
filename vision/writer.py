"""
vision/writer.py
Write computed style attributes back to the fighters table
and record the vision_job row in Supabase.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Optional

from supabase import create_client, Client


def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Vision job lifecycle
# ---------------------------------------------------------------------------

def create_job(
    video_source: str,
    source_type: str,
    fighter_id: Optional[str] = None,
) -> str:
    """Insert a vision_job row in 'running' state. Returns job UUID."""
    client = _get_client()
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
        "raw_attributes": raw_attributes,
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
        client.table("fighters").update(patch).eq("id", fighter_id).execute()
