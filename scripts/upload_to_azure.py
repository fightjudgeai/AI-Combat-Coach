"""
scripts/upload_to_azure.py
Bulk-upload all video files from a local folder to Azure Blob Storage.
No metadata.json required — works with any flat or nested video directory.

Usage:
    # Dry-run: show what would be uploaded
    python scripts/upload_to_azure.py --source "C:\\ufc_fights" --container ufc-fights --dry-run

    # Live upload (skip blobs that already exist)
    python scripts/upload_to_azure.py --source "C:\\ufc_fights" --container ufc-fights --skip-existing

    # Upload PFC fights to a separate container
    python scripts/upload_to_azure.py --source "C:\\OneDrive\\fightvideos\\pfc" --container pfc-fights --skip-existing

Environment variables:
    AZURE_STORAGE_CONNECTION_STRING   (preferred)
    AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY  (alternative)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".wmv"}


# ---------------------------------------------------------------------------
# Azure client
# ---------------------------------------------------------------------------

def _build_service_client(
    conn_str: Optional[str],
    account_name: Optional[str],
    account_key: Optional[str],
):
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        raise ImportError("pip install azure-storage-blob")

    if conn_str:
        return BlobServiceClient.from_connection_string(conn_str)
    if account_name and account_key:
        return BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=account_key,
        )
    raise EnvironmentError(
        "Set AZURE_STORAGE_CONNECTION_STRING or both "
        "AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY"
    )


# ---------------------------------------------------------------------------
# Upload logic
# ---------------------------------------------------------------------------

def upload(
    source_dir: Path,
    container: str,
    conn_str: Optional[str],
    account_name: Optional[str],
    account_key: Optional[str],
    skip_existing: bool = False,
    dry_run: bool = False,
) -> None:
    if not source_dir.exists():
        log.error("Source directory not found: %s", source_dir)
        sys.exit(1)

    # Collect all video files
    video_files = [
        p for p in source_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    ]

    if not video_files:
        log.warning("No video files found in %s", source_dir)
        return

    log.info("Found %d video file(s) in %s", len(video_files), source_dir)

    service = None
    if not dry_run:
        service = _build_service_client(conn_str, account_name, account_key)
        try:
            service.create_container(container)
            log.info("Created container: %s", container)
        except Exception:
            pass  # Already exists

    uploaded = skipped = errors = 0

    for video_path in sorted(video_files):
        # Blob name preserves relative path from source root
        relative = video_path.relative_to(source_dir)
        # Normalise Windows backslashes to forward slashes for Azure
        blob_name = relative.as_posix()

        if dry_run:
            log.info("[DRY RUN] Would upload: %s  →  %s/%s",
                     video_path.name, container, blob_name)
            skipped += 1
            continue

        blob_client = service.get_blob_client(container=container, blob=blob_name)

        if skip_existing:
            try:
                blob_client.get_blob_properties()
                log.debug("Already exists, skipping: %s", blob_name)
                skipped += 1
                continue
            except Exception:
                pass  # Does not exist — proceed

        try:
            size = video_path.stat().st_size
            log.info("Uploading %s  (%s)  →  %s",
                     video_path.name, _human_size(size), blob_name)
            with video_path.open("rb") as fh:
                blob_client.upload_blob(fh, overwrite=True)
            uploaded += 1
        except Exception as exc:
            log.error("Failed: %s — %s", video_path.name, exc)
            errors += 1

    if dry_run:
        log.info("Dry-run complete. %d file(s) would be uploaded.", len(video_files))
    else:
        log.info(
            "Upload complete — uploaded=%d  skipped=%d  errors=%d",
            uploaded, skipped, errors,
        )
        if errors:
            sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Bulk-upload video files to Azure Blob Storage"
    )
    p.add_argument("--source", required=True,
                   help="Local folder to upload (all video files recursively)")
    p.add_argument("--container", required=True,
                   help="Azure Blob container name (created if absent)")
    p.add_argument("--connection-string", default=None,
                   help="Azure Storage connection string")
    p.add_argument("--account-name", default=None,
                   help="Storage account name (with --account-key)")
    p.add_argument("--account-key", default=None,
                   help="Storage account key (with --account-name)")
    p.add_argument("--skip-existing", action="store_true",
                   help="Skip blobs that already exist in Azure")
    p.add_argument("--dry-run", action="store_true",
                   help="List what would be uploaded without transferring data")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    conn_str = args.connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    account_name = args.account_name or os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
    account_key = args.account_key or os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")

    upload(
        source_dir   = Path(args.source),
        container    = args.container,
        conn_str     = conn_str,
        account_name = account_name,
        account_key  = account_key,
        skip_existing= args.skip_existing,
        dry_run      = args.dry_run,
    )
