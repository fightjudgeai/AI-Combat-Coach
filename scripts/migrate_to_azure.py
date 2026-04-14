"""
scripts/migrate_to_azure.py
Upload all local UFC fight videos from fight_footage/ to Azure Blob Storage
and update each metadata.json with the resulting azure:// URI.

Usage:
    # Dry-run: show what would be uploaded
    python scripts/migrate_to_azure.py --container ufc-fights --dry-run

    # Live migration (reads AZURE_STORAGE_CONNECTION_STRING from env)
    python scripts/migrate_to_azure.py --container ufc-fights

    # Use explicit account name + key instead of connection string
    python scripts/migrate_to_azure.py \\
        --container ufc-fights \\
        --account-name mystorage \\
        --account-key "base64key=="

    # Skip already-uploaded blobs (idempotent re-run)
    python scripts/migrate_to_azure.py --container ufc-fights --skip-existing

Environment variables (alternative to CLI flags):
    AZURE_STORAGE_CONNECTION_STRING
    AZURE_STORAGE_ACCOUNT_NAME
    AZURE_STORAGE_ACCOUNT_KEY
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

FIGHT_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi"}
METADATA_FILENAME = "metadata.json"


# ---------------------------------------------------------------------------
# Azure client construction
# ---------------------------------------------------------------------------

def _build_service_client(
    conn_str: Optional[str],
    account_name: Optional[str],
    account_key: Optional[str],
):
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        raise ImportError(
            "azure-storage-blob is required: pip install azure-storage-blob"
        )

    if conn_str:
        return BlobServiceClient.from_connection_string(conn_str)
    if account_name and account_key:
        return BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=account_key,
        )
    raise EnvironmentError(
        "Provide AZURE_STORAGE_CONNECTION_STRING or both "
        "AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY"
    )


# ---------------------------------------------------------------------------
# Core migration logic
# ---------------------------------------------------------------------------

def migrate(
    footage_root: Path,
    container: str,
    conn_str: Optional[str],
    account_name: Optional[str],
    account_key: Optional[str],
    skip_existing: bool = False,
    dry_run: bool = False,
) -> None:
    if not footage_root.exists():
        log.error("Footage root not found: %s", footage_root)
        sys.exit(1)

    service = None
    if not dry_run:
        service = _build_service_client(conn_str, account_name, account_key)
        # Ensure container exists
        try:
            service.create_container(container)
            log.info("Created container: %s", container)
        except Exception:
            # Container already exists — that's fine
            pass

    uploaded = skipped = errors = 0

    for event_dir in sorted(footage_root.iterdir()):
        if not event_dir.is_dir():
            continue

        for fight_dir in sorted(event_dir.iterdir()):
            if not fight_dir.is_dir():
                continue

            meta_path = fight_dir / METADATA_FILENAME
            if not meta_path.exists():
                continue

            # Find the video file
            video_path: Optional[Path] = None
            for ext in FIGHT_VIDEO_EXTENSIONS:
                candidates = list(fight_dir.glob(f"*{ext}"))
                if candidates:
                    full = [c for c in candidates if "full_fight" in c.stem.lower()]
                    video_path = full[0] if full else candidates[0]
                    break

            if video_path is None:
                log.debug("No video file in %s — skipping", fight_dir)
                skipped += 1
                continue

            # Blob name: <event_slug>/<fight_slug>/<filename>
            blob_name = (
                f"{event_dir.name}/{fight_dir.name}/{video_path.name}"
            )
            azure_uri = f"azure://{container}/{blob_name}"

            with meta_path.open("r", encoding="utf-8") as fh:
                meta = json.load(fh)

            if dry_run:
                action = "[DRY RUN] Would upload"
                if meta.get("azure_url"):
                    action = "[DRY RUN] Already has azure_url, would skip" if skip_existing else "[DRY RUN] Would re-upload"
                log.info("%s  %s  →  %s", action, video_path, azure_uri)
                skipped += 1
                continue

            # Skip if metadata already has this URI and --skip-existing
            if skip_existing and meta.get("azure_url") == azure_uri:
                log.debug("Already uploaded: %s", azure_uri)
                skipped += 1
                continue

            # Upload
            blob_client = service.get_blob_client(
                container=container, blob=blob_name
            )
            try:
                if skip_existing:
                    # Only upload if blob doesn't exist in Azure
                    try:
                        blob_client.get_blob_properties()
                        log.info("Blob exists, skipping upload: %s", blob_name)
                        # Still update metadata if missing
                        if meta.get("azure_url") != azure_uri:
                            meta["azure_url"] = azure_uri
                            with meta_path.open("w", encoding="utf-8") as fh:
                                json.dump(meta, fh, indent=2, ensure_ascii=False)
                                fh.write("\n")
                        skipped += 1
                        continue
                    except Exception:
                        pass  # Blob does not exist, proceed with upload

                log.info(
                    "Uploading %s  (%s)  →  %s",
                    video_path.name,
                    _human_size(video_path.stat().st_size),
                    blob_name,
                )
                with video_path.open("rb") as data:
                    blob_client.upload_blob(data, overwrite=True)

                # Patch metadata.json with azure_url
                meta["azure_url"] = azure_uri
                with meta_path.open("w", encoding="utf-8") as fh:
                    json.dump(meta, fh, indent=2, ensure_ascii=False)
                    fh.write("\n")

                log.info("Done: %s", azure_uri)
                uploaded += 1

            except Exception as exc:
                log.error("Failed to upload %s: %s", video_path, exc)
                errors += 1

    if dry_run:
        log.info("Dry-run complete. %d file(s) would be processed.", uploaded + skipped)
    else:
        log.info(
            "Migration complete — uploaded=%d  skipped=%d  errors=%d",
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
        description="Migrate local UFC fight videos to Azure Blob Storage"
    )
    p.add_argument(
        "--footage-root", default="fight_footage",
        help="Local footage root directory (default: fight_footage)",
    )
    p.add_argument(
        "--container", required=True,
        help="Azure Blob Storage container name (created if it doesn't exist)",
    )
    p.add_argument(
        "--connection-string", default=None,
        help="Azure Storage connection string (overrides env var)",
    )
    p.add_argument(
        "--account-name", default=None,
        help="Azure Storage account name (used with --account-key)",
    )
    p.add_argument(
        "--account-key", default=None,
        help="Azure Storage account key (used with --account-name)",
    )
    p.add_argument(
        "--skip-existing", action="store_true",
        help="Skip blobs that already exist in Azure; still patch metadata.json",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be uploaded without transferring any data",
    )
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    conn_str = (
        args.connection_string
        or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    )
    account_name = args.account_name or os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
    account_key = args.account_key or os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")

    migrate(
        footage_root  = Path(args.footage_root),
        container     = args.container,
        conn_str      = conn_str,
        account_name  = account_name,
        account_key   = account_key,
        skip_existing = args.skip_existing,
        dry_run       = args.dry_run,
    )
