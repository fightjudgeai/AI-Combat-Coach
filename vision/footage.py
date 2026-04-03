"""
vision/footage.py
Scan the /fight_footage/ directory tree and yield FightFootageItem objects.

Expected layout:
  fight_footage/
    pfc_50/
      fight_01_hunt_vs_jones/
        full_fight.mp4           ← or any .mp4/.mov/.mkv
        metadata.json
      fight_02_.../
        ...
    pfc_51/
      ...
    ufc_benchmark/               ← reference clips only, no full_fight.mp4 required
      clip_01_left_hook/
        clip.mp4
        metadata.json

metadata.json schema:
  {
    "fighter_ids": ["uuid-a", "uuid-b"],   // fighters table UUIDs (or null if unverified)
    "fighter_names": ["Hunt", "Jones"],    // human-readable, required
    "corner": ["red", "blue"],             // which corner each fighter_id maps to
    "round_count": 3,
    "finish_method": "ko" | "tko" | "submission" | "decision" | null,
    "tags": ["full_fight", "pfc", "championship"],
    "youtube_url": "https://...",          // optional, used if video not local
    "is_benchmark": false
  }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional


FIGHT_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi"}
METADATA_FILENAME      = "metadata.json"
BENCHMARK_DIR_NAME     = "ufc_benchmark"


@dataclass
class FightFootageItem:
    fight_dir:     Path
    event_slug:    str          # e.g. "pfc_50"
    fight_slug:    str          # e.g. "fight_01_hunt_vs_jones"
    video_path:    Optional[Path]   # None if only a YouTube URL
    youtube_url:   Optional[str]
    fighter_ids:   List[Optional[str]]   # UUIDs (may be None if not in fighters table yet)
    fighter_names: List[str]
    corner:        List[str]    # ["red", "blue"]
    round_count:   int
    finish_method: Optional[str]
    tags:          List[str]
    is_benchmark:  bool

    @property
    def source(self) -> str:
        """Return the best available video source string for the pipeline."""
        if self.video_path is not None and self.video_path.exists():
            return str(self.video_path)
        if self.youtube_url:
            return self.youtube_url
        raise FileNotFoundError(
            f"No video source for {self.fight_slug}: "
            f"video_path={self.video_path}, youtube_url={self.youtube_url}"
        )

    @property
    def has_source(self) -> bool:
        return (self.video_path is not None and self.video_path.exists()) or bool(self.youtube_url)


def scan_footage(root: Path) -> Iterator[FightFootageItem]:
    """
    Recursively scan root for fight directories containing metadata.json.
    Yields one FightFootageItem per fight directory found.
    """
    if not root.exists():
        raise FileNotFoundError(f"Footage root not found: {root}")

    for event_dir in sorted(root.iterdir()):
        if not event_dir.is_dir():
            continue
        event_slug   = event_dir.name
        is_benchmark = (event_slug == BENCHMARK_DIR_NAME)

        for fight_dir in sorted(event_dir.iterdir()):
            if not fight_dir.is_dir():
                continue
            meta_path = fight_dir / METADATA_FILENAME
            if not meta_path.exists():
                continue

            try:
                item = _load_item(fight_dir, event_slug, is_benchmark, meta_path)
                yield item
            except Exception as exc:
                import warnings
                warnings.warn(f"Skipping {fight_dir}: {exc}")


def _load_item(
    fight_dir: Path,
    event_slug: str,
    is_benchmark: bool,
    meta_path: Path,
) -> FightFootageItem:
    with meta_path.open("r", encoding="utf-8") as f:
        meta = json.load(f)

    # Find video file
    video_path: Optional[Path] = None
    for ext in FIGHT_VIDEO_EXTENSIONS:
        candidates = list(fight_dir.glob(f"*{ext}"))
        if candidates:
            # Prefer "full_fight" in name if multiple
            full = [c for c in candidates if "full_fight" in c.stem.lower()]
            video_path = full[0] if full else candidates[0]
            break

    fighter_ids   = meta.get("fighter_ids") or [None, None]
    fighter_names = meta.get("fighter_names") or []
    corner        = meta.get("corner") or ["red", "blue"]

    # Normalise fighter_ids to exactly 2 entries
    while len(fighter_ids) < 2:
        fighter_ids.append(None)
    while len(fighter_names) < 2:
        fighter_names.append("Unknown")
    while len(corner) < 2:
        corner.append("unknown")

    return FightFootageItem(
        fight_dir      = fight_dir,
        event_slug     = event_slug,
        fight_slug     = fight_dir.name,
        video_path     = video_path,
        youtube_url    = meta.get("youtube_url"),
        fighter_ids    = fighter_ids[:2],
        fighter_names  = fighter_names[:2],
        corner         = corner[:2],
        round_count    = int(meta.get("round_count") or 3),
        finish_method  = meta.get("finish_method"),
        tags           = meta.get("tags") or [],
        is_benchmark   = meta.get("is_benchmark", is_benchmark),
    )
