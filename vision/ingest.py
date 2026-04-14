"""
vision/ingest.py
Resolve a video source (local path, S3 URI, Azure Blob URI, YouTube URL) to a
local file path.  Returns a pathlib.Path ready for OpenCV / frame extraction.

Azure Blob URIs use the scheme:
    azure://<container>/<blob/path/video.mp4>

The storage account is resolved from the environment variable
AZURE_STORAGE_CONNECTION_STRING (preferred) or the pair
AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY.
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
    if source.startswith("azure://"):
        return "azure"
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

    if src_type == "azure":
        return _download_azure_blob(source, workdir), src_type

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
# Azure Blob Storage download
# ---------------------------------------------------------------------------

def _download_azure_blob(uri: str, workdir: Path) -> Path:
    """Download azure://<container>/<blob-path> to workdir."""
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        raise ImportError(
            "azure-storage-blob required for Azure sources: "
            "pip install azure-storage-blob"
        )

    # Parse  azure://container/path/to/video.mp4
    parsed = urllib.parse.urlparse(uri)
    container = parsed.netloc
    blob_name = parsed.path.lstrip("/")
    filename = Path(blob_name).name
    dest = workdir / filename

    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        service = BlobServiceClient.from_connection_string(conn_str)
    else:
        account = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
        key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
        if not account or not key:
            raise EnvironmentError(
                "Set AZURE_STORAGE_CONNECTION_STRING or both "
                "AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY"
            )
        service = BlobServiceClient(
            account_url=f"https://{account}.blob.core.windows.net",
            credential=key,
        )

    blob_client = service.get_blob_client(container=container, blob=blob_name)
    with dest.open("wb") as fh:
        fh.write(blob_client.download_blob().readall())
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
