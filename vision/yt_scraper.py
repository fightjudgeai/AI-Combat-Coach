"""
vision/yt_scraper.py
Harvest UFC "Free Fight" videos from the official UFC YouTube channel.

UFC channel: https://www.youtube.com/@UFC
Free Fight playlist pattern: /playlist?list=PLlmhCOOqsNNbD...

Usage:
    # List all free fight URLs (dry run)
    python -m vision.yt_scraper --list --max 50

    # Download to fight_footage/ufc_benchmark/
    python -m vision.yt_scraper --download --dest fight_footage/ufc_benchmark --max 20

    # Download and auto-generate metadata.json for each fight
    python -m vision.yt_scraper --download --dest fight_footage/ufc_benchmark --metadata --max 20
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# UFC YouTube constants
# ---------------------------------------------------------------------------

# yt-dlp search query — reliably returns free fight full videos from UFC channel
_SEARCH_QUERY_TEMPLATE = "ytsearch{n}:UFC free fight full fight"

# Known UFC free fights playlists (fallback if search fails)
_UFC_FREE_FIGHTS_PLAYLISTS = [
    "https://www.youtube.com/playlist?list=PLlVlyGVtvuVlNfIHkdcD7DOfGewsS6mGb",
]

# Min duration in seconds to filter out clips (full fights are usually 10+ min)
_MIN_DURATION_SECS = 600   # 10 min

# Max results from channel scan
_DEFAULT_MAX = 20


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class UFCFreeFightScraper:
    """Wraps yt-dlp to discover and download UFC free fight videos."""

    def __init__(self, quiet: bool = True):
        try:
            import yt_dlp
            self._yt_dlp = yt_dlp
        except ImportError:
            raise ImportError("yt-dlp required: pip install yt-dlp")
        self._quiet = quiet

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def list_free_fights(self, max_results: int = _DEFAULT_MAX) -> List[Dict[str, Any]]:
        """
        Return a list of dicts: {url, title, duration, upload_date}
        Uses yt-dlp YouTube search for "UFC free fight full fight".
        Falls back to known UFC free fights playlists.
        """
        results = self._search_youtube(max_results)
        if not results:
            log.info("Search returned nothing — trying known playlists")
            results = self._scrape_playlists(max_results)
        log.info("Found %d free fight videos", len(results))
        return results

    def _search_youtube(self, max_results: int) -> List[Dict[str, Any]]:
        """Use ytsearchN: query to find UFC free fight videos."""
        search_url = _SEARCH_QUERY_TEMPLATE.format(n=max_results * 3)
        ydl_opts = {
            "quiet":        self._quiet,
            "no_warnings":  True,
            "extract_flat": True,
            "ignoreerrors": True,
        }
        results = []
        with self._yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            if not info:
                return []
            for entry in (info.get("entries") or []):
                if entry is None:
                    continue
                title = (entry.get("title") or "").lower()
                # Must contain "free fight" or "full fight" to qualify
                if "free fight" not in title and "full fight" not in title:
                    continue
                duration = entry.get("duration") or 0
                if duration and duration < _MIN_DURATION_SECS:
                    continue
                results.append({
                    "url":         f"https://www.youtube.com/watch?v={entry['id']}",
                    "video_id":    entry["id"],
                    "title":       entry.get("title", ""),
                    "duration":    duration,
                    "upload_date": entry.get("upload_date"),
                })
                if len(results) >= max_results:
                    break
        return results

    def _scrape_playlists(self, max_results: int) -> List[Dict[str, Any]]:
        """Scrape known UFC free-fight playlists as a fallback."""
        ydl_opts = {
            "quiet":          self._quiet,
            "no_warnings":    True,
            "extract_flat":   "in_playlist",
            "playlistend":    max_results,
            "ignoreerrors":   True,
        }
        results = []
        with self._yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for pl_url in _UFC_FREE_FIGHTS_PLAYLISTS:
                info = ydl.extract_info(pl_url, download=False)
                if not info or "entries" not in info:
                    continue
                for entry in (info.get("entries") or []):
                    if entry is None:
                        continue
                    results.append({
                        "url":         f"https://www.youtube.com/watch?v={entry['id']}",
                        "video_id":    entry["id"],
                        "title":       entry.get("title", ""),
                        "duration":    entry.get("duration"),
                        "upload_date": entry.get("upload_date"),
                    })
                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break
        return results

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(
        self,
        url: str,
        dest_dir: Path,
        generate_metadata: bool = True,
    ) -> Optional[Path]:
        """
        Download a single video to dest_dir/fight_<video_id>/.
        Optionally create a stub metadata.json.
        Returns the fight directory Path.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Extract info first to get video_id + title
        info_opts = {"quiet": self._quiet, "no_warnings": True, "skip_download": True}
        with self._yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            log.error("Could not fetch info for %s", url)
            return None

        video_id   = info.get("id", "unknown")
        title      = info.get("title", "unknown")
        slug       = _slugify(title)
        fight_dir  = dest_dir / f"{slug}_{video_id}"
        fight_dir.mkdir(exist_ok=True)

        # Download
        ydl_opts = {
            "format":     "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl":    str(fight_dir / "full_fight.%(ext)s"),
            "quiet":      self._quiet,
            "no_warnings": True,
        }
        with self._yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        log.info("Downloaded: %s → %s", title, fight_dir)

        if generate_metadata:
            _write_stub_metadata(fight_dir, info, url)

        return fight_dir

    def download_many(
        self,
        dest_dir: Path,
        max_results: int = _DEFAULT_MAX,
        generate_metadata: bool = True,
    ) -> List[Path]:
        fights = self.list_free_fights(max_results=max_results)
        downloaded = []
        for f in fights:
            try:
                path = self.download(f["url"], dest_dir, generate_metadata)
                if path:
                    downloaded.append(path)
            except Exception as exc:
                log.error("Failed to download %s: %s", f["url"], exc)
        return downloaded


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:60]


def _write_stub_metadata(fight_dir: Path, info: dict, url: str) -> None:
    """
    Generate a stub metadata.json from YouTube video info.
    Fighter names are parsed heuristically from the title.
    """
    title = info.get("title", "")
    # Try to parse "Fighter A vs. Fighter B" patterns
    fighters = _parse_fighters_from_title(title)

    meta = {
        "fighter_ids":    [None, None],
        "fighter_names":  fighters,
        "corner":         ["red", "blue"],
        "round_count":    None,          # unknown until reviewed
        "finish_method":  None,
        "tags":           ["free_fight", "ufc", "benchmark"],
        "youtube_url":    url,
        "is_benchmark":   True,
        "yt_title":       title,
        "yt_video_id":    info.get("id"),
        "yt_upload_date": info.get("upload_date"),
        "yt_duration":    info.get("duration"),
    }

    meta_path = fight_dir / "metadata.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    log.info("Wrote stub metadata: %s", meta_path)


_VS_PATTERNS = [
    r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+vs\.?\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)",
    r"([A-Za-z]+)\s+[Vv][Ss]\.?\s+([A-Za-z]+)",
]

def _parse_fighters_from_title(title: str) -> List[str]:
    for pat in _VS_PATTERNS:
        m = re.search(pat, title)
        if m:
            return [m.group(1).strip(), m.group(2).strip()]
    return ["Unknown", "Unknown"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="UFC free fight YouTube scraper")
    p.add_argument("--list",      action="store_true", help="List free fight URLs only")
    p.add_argument("--download",  action="store_true", help="Download videos")
    p.add_argument("--dest",      default="fight_footage/ufc_benchmark",
                   help="Download destination (default: fight_footage/ufc_benchmark)")
    p.add_argument("--max",       type=int, default=_DEFAULT_MAX,
                   help=f"Max videos to fetch (default: {_DEFAULT_MAX})")
    p.add_argument("--metadata",  action="store_true", default=True,
                   help="Auto-generate metadata.json for each download (default: true)")
    p.add_argument("--verbose",   action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    scraper = UFCFreeFightScraper(quiet=not args.verbose)

    if args.list:
        fights = scraper.list_free_fights(max_results=args.max)
        for f in fights:
            print(f"{f['upload_date']}  {f['url']}  {f['title']}")
        print(f"\n{len(fights)} free fights found.")
        sys.exit(0)

    if args.download:
        dest = Path(args.dest)
        downloaded = scraper.download_many(
            dest_dir         = dest,
            max_results      = args.max,
            generate_metadata = args.metadata,
        )
        print(f"\nDownloaded {len(downloaded)} fights to {dest}")
        sys.exit(0)

    print("Specify --list or --download")
    sys.exit(1)
