"""
vision/ingest.py
Resolve a video source (local path, S3 URI, YouTube URL) to a local file path.
Returns a pathlib.Path ready for OpenCV / frame extraction.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import urllib.parse
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Source type detection
# ---------------------------------------------------------------------------

_YT_RE = re.compile(
    r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts/)", re.I
)

def detect_source_type(source: str) -> str:
    if source.startswith("s3://"):
        return "s3"
    if _YT_RE.search(source):
        return "youtube"
    return "local"


# ---------------------------------------------------------------------------
# Ingest dispatch
# ---------------------------------------------------------------------------

def resolve_video(source: str, workdir: Optional[Path] = None) -> tuple[Path, str]:
    """
    Returns (local_path, source_type).
    workdir is used as the download destination; defaults to a temp dir
    that callers are responsible for cleaning up.
    """
    src_type = detect_source_type(source)

    if src_type == "local":
        p = Path(source).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Video not found: {p}")
        return p, src_type

    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="fjai_vision_"))

    if src_type == "s3":
        return _download_s3(source, workdir), src_type

    if src_type == "youtube":
        return _download_youtube(source, workdir), src_type

    raise ValueError(f"Unknown source type for: {source}")


# ---------------------------------------------------------------------------
# S3 download
# ---------------------------------------------------------------------------

def _download_s3(uri: str, workdir: Path) -> Path:
    try:
        import boto3
    except ImportError:
        raise ImportError("boto3 required for S3 sources: pip install boto3")

    parsed = urllib.parse.urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    filename = Path(key).name
    dest = workdir / filename

    s3 = boto3.client("s3")
    s3.download_file(bucket, key, str(dest))
    return dest


# ---------------------------------------------------------------------------
# YouTube download
# ---------------------------------------------------------------------------

def _download_youtube(url: str, workdir: Path) -> Path:
    try:
        import yt_dlp
    except ImportError:
        raise ImportError("yt-dlp required for YouTube sources: pip install yt-dlp")

    dest_template = str(workdir / "%(id)s.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": dest_template,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get("id", "video")
        ext = info.get("ext", "mp4")

    result = workdir / f"{video_id}.{ext}"
    if not result.exists():
        # yt-dlp may have merged to mp4
        candidates = list(workdir.glob(f"{video_id}.*"))
        if not candidates:
            raise RuntimeError(f"yt-dlp download failed for {url}")
        result = candidates[0]
    return result
