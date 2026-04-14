"""
ufc_fight_pass_scraper.py
=========================
Production-ready async scraper for UFC Fight Pass.

Pipeline:
  1. Login  →  2. Discover events  →  3. Extract fight cards
  →  4. Grab video URL  →  5. Download (HLS via FFmpeg, MP4 via aiohttp)

Usage:
    UFC_EMAIL=you@example.com UFC_PASSWORD=secret python scripts/ufc_fight_pass_scraper.py

Requirements:
    pip install playwright aiohttp beautifulsoup4
    playwright install chromium
    # ffmpeg must be on $PATH
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import urljoin, urlparse

import aiohttp
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://ufcfightpass.com"
LOGIN_URL = f"{BASE_URL}/login"
EVENTS_URL = f"{BASE_URL}/events"

OUTPUT_ROOT = Path("ufc_fights")           # local download root
COOKIES_FILE = Path(".ufc_cookies.json")   # persisted session

MAX_CONCURRENT_DOWNLOADS = 3
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0                     # seconds; doubles each attempt

# Rotate user agents to reduce fingerprinting risk
USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("ufc_fp_scraper")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize(name: str) -> str:
    """Strip characters that are unsafe in directory / file names."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def is_hls(url: str) -> bool:
    return ".m3u8" in urlparse(url).path


async def retry(coro_fn, *args, retries: int = MAX_RETRIES, **kwargs):
    """
    Call an async coroutine function with exponential-backoff retry.
    `coro_fn` must be a *callable* that returns a coroutine (not already awaited).
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            log.warning(
                "Attempt %d/%d failed (%s). Retrying in %.1fs…",
                attempt, retries, exc, wait,
            )
            await asyncio.sleep(wait)
    raise RuntimeError(f"All {retries} retries exhausted") from last_exc


# ---------------------------------------------------------------------------
# Browser / context setup
# ---------------------------------------------------------------------------

async def build_context(pw: Playwright, *, headless: bool = True) -> tuple[Browser, BrowserContext]:
    """
    Launch a Chromium browser with a realistic context.
    Loads saved cookies if available so we can skip login on repeat runs.
    """
    import random

    browser = await pw.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )

    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York",
        # Pretend we are a real browser by injecting typical headers
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        },
    )

    # Mask navigator.webdriver so bot-detection scripts see a real browser
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    # Restore a prior session if we have one
    if COOKIES_FILE.exists():
        import json
        cookies = json.loads(COOKIES_FILE.read_text())
        await context.add_cookies(cookies)
        log.info("Loaded %d cookies from %s", len(cookies), COOKIES_FILE)

    return browser, context


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

async def login(page: Page, email: str, password: str) -> bool:
    """
    Navigate to the Fight Pass login page and submit credentials.
    Returns True if login succeeded, False otherwise.
    Persists session cookies to COOKIES_FILE on success.
    """
    log.info("Navigating to login page…")
    await page.goto(LOGIN_URL, wait_until="networkidle", timeout=60_000)

    # Fill email
    email_sel = 'input[type="email"], input[name="email"], input[id*="email"]'
    await page.wait_for_selector(email_sel, timeout=15_000)
    await page.fill(email_sel, email)

    # Fill password
    pw_sel = 'input[type="password"]'
    await page.wait_for_selector(pw_sel, timeout=10_000)
    await page.fill(pw_sel, password)

    # Submit – try a visible submit button first, fall back to Enter
    submit_sel = 'button[type="submit"], button:has-text("Sign In"), button:has-text("Log In")'
    submit_btn = page.locator(submit_sel).first
    if await submit_btn.count() > 0:
        await submit_btn.click()
    else:
        await page.keyboard.press("Enter")

    # Wait for navigation away from the login URL
    try:
        await page.wait_for_url(
            lambda url: "login" not in url,
            timeout=20_000,
        )
    except Exception:
        log.error("Login may have failed – still on %s", page.url)
        return False

    log.info("Login successful, now at %s", page.url)

    # Persist cookies for future runs
    import json
    cookies = await page.context.cookies()
    COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
    log.info("Saved %d cookies to %s", len(cookies), COOKIES_FILE)
    return True


async def ensure_authenticated(page: Page, email: str, password: str) -> None:
    """
    Check whether the current session is already authenticated.
    If not, perform login. Raises RuntimeError on failure.
    """
    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30_000)
    # A logged-in page typically shows an avatar / account element
    account_sel = '[data-testid="account-menu"], [aria-label*="account" i], .user-avatar'
    already_in = await page.locator(account_sel).count() > 0
    if already_in:
        log.info("Session is already authenticated.")
        return

    ok = await retry(login, page, email, password)
    if not ok:
        raise RuntimeError("Authentication failed after retries.")


# ---------------------------------------------------------------------------
# Event discovery
# ---------------------------------------------------------------------------

async def _scroll_until_stable(page: Page, *, max_scrolls: int = 30) -> None:
    """
    Scroll to the bottom of an infinitely-scrolling page until no new content loads.
    """
    prev_height = 0
    for _ in range(max_scrolls):
        cur_height: int = await page.evaluate("document.body.scrollHeight")
        if cur_height == prev_height:
            break
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1.5)          # give the page time to lazy-load more items
        prev_height = cur_height


async def discover_events(page: Page, *, max_events: int | None = None) -> list[dict]:
    """
    Navigate to the Events listing and return a list of
    {'name': str, 'url': str} dicts, newest-first.

    Fight Pass renders events dynamically, so we scroll to trigger lazy loading.
    """
    log.info("Discovering events at %s …", EVENTS_URL)
    await page.goto(EVENTS_URL, wait_until="networkidle", timeout=60_000)

    # Wait for at least one event card to appear
    card_sel = '[data-testid*="event-card"], .event-card, a[href*="/events/"]'
    await page.wait_for_selector(card_sel, timeout=20_000)

    await _scroll_until_stable(page)

    # Collect all event links
    links = await page.evaluate(
        """() => {
            const anchors = Array.from(document.querySelectorAll('a[href*="/events/"]'));
            return [...new Set(
                anchors
                    .filter(a => a.href && !a.href.endsWith('/events/'))
                    .map(a => ({
                        url: a.href,
                        name: (a.querySelector('[class*="title"], h3, h4') || a).innerText.trim()
                    }))
            )];
        }"""
    )

    events = [e for e in links if e["url"] and e["name"]]
    if max_events:
        events = events[:max_events]

    log.info("Found %d events.", len(events))
    return events


# ---------------------------------------------------------------------------
# Fight card extraction
# ---------------------------------------------------------------------------

async def extract_fight_links(page: Page, event_url: str) -> list[dict]:
    """
    Navigate to a single event page and return a list of
    {'name': str, 'url': str} fight dicts for that card.
    """
    log.info("Extracting fight card from %s …", event_url)
    await page.goto(event_url, wait_until="networkidle", timeout=60_000)

    # Fight cards are typically listed as clickable rows/cards
    fight_sel = 'a[href*="/fight/"], a[href*="/video/"], [data-testid*="fight"]'
    try:
        await page.wait_for_selector(fight_sel, timeout=15_000)
    except Exception:
        log.warning("No fight links found on %s", event_url)
        return []

    fights = await page.evaluate(
        """(fightSel) => {
            const els = Array.from(document.querySelectorAll(fightSel));
            return [...new Map(
                els.map(a => {
                    const titleEl = a.querySelector(
                        '[class*="title"], [class*="fighter"], h3, h4, p'
                    );
                    return [a.href, {
                        url: a.href,
                        name: titleEl ? titleEl.innerText.trim() : a.innerText.trim()
                    }];
                })
            ).values()].filter(f => f.url && f.name);
        }""",
        fight_sel,
    )

    log.info("  → %d fights found.", len(fights))
    return fights


# ---------------------------------------------------------------------------
# Video URL extraction
# ---------------------------------------------------------------------------

async def _intercept_video_url(page: Page, fight_url: str) -> str | None:
    """
    Navigate to a fight/video page, intercept network requests for
    media manifests (.m3u8) or direct video files (.mp4), and return
    the first URL found.

    Fight Pass typically embeds video in an <iframe>; we handle that
    by iterating all frames of the page.
    """
    captured: list[str] = []

    def on_request(request) -> None:
        url = request.url
        if re.search(r"\.(m3u8|mp4)(\?|$)", url, re.IGNORECASE):
            captured.append(url)
            log.debug("Intercepted media URL: %s", url)

    page.on("request", on_request)

    log.info("Loading video page: %s", fight_url)
    await page.goto(fight_url, wait_until="networkidle", timeout=60_000)

    # Give JS players a moment to initialize and fire their first requests
    await asyncio.sleep(3)

    # If we captured something via network interception, return it now
    if captured:
        return captured[0]

    # --- Fallback: search iframes for a video element or source ---
    for frame in page.frames:
        src = await _extract_from_frame(frame)
        if src:
            return src

    log.warning("No video URL found on %s", fight_url)
    return None


async def _extract_from_frame(frame) -> str | None:
    """
    Look inside a single frame for <video src>, <source src>, or
    a jwplayer / Bitmovin player configuration object.
    """
    try:
        # Direct video/source tags
        src = await frame.evaluate(
            """() => {
                const v = document.querySelector('video[src]');
                if (v) return v.src;
                const s = document.querySelector('source[src]');
                if (s) return s.src;

                // JW Player
                if (window.jwplayer) {
                    try {
                        const p = jwplayer();
                        if (p && p.getPlaylistItem) {
                            const item = p.getPlaylistItem();
                            if (item && item.file) return item.file;
                        }
                    } catch (_) {}
                }

                // Bitmovin
                if (window.bitmovin) {
                    try {
                        const cfg = bitmovin.player('player').getConfig();
                        if (cfg && cfg.source) {
                            return cfg.source.hls || cfg.source.progressive || null;
                        }
                    } catch (_) {}
                }

                // Search inline scripts for m3u8/mp4 URLs
                const scripts = Array.from(document.querySelectorAll('script:not([src])'));
                for (const s of scripts) {
                    const m = s.textContent.match(/"(https?[^"]+\\.m3u8[^"]*)"/);
                    if (m) return m[1];
                    const m2 = s.textContent.match(/"(https?[^"]+\\.mp4[^"]*)"/);
                    if (m2) return m2[1];
                }
                return null;
            }"""
        )
        if src and src.startswith("http"):
            return src
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Download: HLS via FFmpeg
# ---------------------------------------------------------------------------

async def download_hls(m3u8_url: str, output_path: Path) -> None:
    """
    Use FFmpeg to download and remux an HLS stream into a single .mp4 file.
    Runs in a thread pool so the event loop stays unblocked.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",                          # overwrite without asking
        "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
        "-i", m3u8_url,
        "-c", "copy",                  # stream-copy (no re-encode)
        "-movflags", "+faststart",     # optimise for streaming playback
        str(output_path),
    ]
    log.info("FFmpeg: %s", " ".join(cmd))

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run_ffmpeg, cmd)
    log.info("HLS download complete → %s", output_path)


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )


# ---------------------------------------------------------------------------
# Download: MP4 via aiohttp
# ---------------------------------------------------------------------------

async def download_mp4(
    mp4_url: str,
    output_path: Path,
    *,
    session: aiohttp.ClientSession,
    chunk_size: int = 1 << 20,  # 1 MiB
) -> None:
    """
    Stream an MP4 file to disk using aiohttp, with a progress log every 50 MiB.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading MP4: %s", mp4_url)

    headers = {
        "User-Agent": USER_AGENTS[0],
        "Referer": BASE_URL,
    }

    async with session.get(mp4_url, headers=headers) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        written = 0

        with output_path.open("wb") as fh:
            async for chunk in resp.content.iter_chunked(chunk_size):
                fh.write(chunk)
                written += len(chunk)
                if total and written % (50 * chunk_size) < chunk_size:
                    pct = written / total * 100
                    log.info("  %.1f%% (%.1f / %.1f MiB)", pct, written / 1e6, total / 1e6)

    log.info("MP4 download complete → %s (%.1f MiB)", output_path, written / 1e6)


# ---------------------------------------------------------------------------
# Dispatcher: choose the right downloader
# ---------------------------------------------------------------------------

async def download_video(
    video_url: str,
    output_path: Path,
    *,
    session: aiohttp.ClientSession,
) -> None:
    """Route to FFmpeg (HLS) or aiohttp (MP4) based on the URL."""
    if is_hls(video_url):
        await retry(download_hls, video_url, output_path)
    else:
        await retry(download_mp4, video_url, output_path, session=session)


# ---------------------------------------------------------------------------
# Per-fight orchestration
# ---------------------------------------------------------------------------

async def scrape_and_download_fight(
    page: Page,
    fight: dict,
    event_name: str,
    sem: asyncio.Semaphore,
    session: aiohttp.ClientSession,
) -> None:
    """
    Full pipeline for one fight: extract video URL → download.
    Concurrency is bounded by `sem`.
    """
    fight_name = sanitize(fight["name"]) or "unknown_fight"
    event_dir = OUTPUT_ROOT / sanitize(event_name)
    output_path = event_dir / f"{fight_name}.mp4"

    if output_path.exists():
        log.info("Already downloaded, skipping: %s", output_path)
        return

    async with sem:
        try:
            video_url = await retry(_intercept_video_url, page, fight["url"])
            if not video_url:
                log.error("No video URL for fight '%s', skipping.", fight["name"])
                return

            log.info("Video URL for '%s': %s", fight["name"], video_url)
            await download_video(video_url, output_path, session=session)

        except Exception as exc:
            log.error("Failed to process fight '%s': %s", fight["name"], exc, exc_info=True)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

async def run(
    email: str,
    password: str,
    *,
    max_events: int | None = None,
    headless: bool = True,
) -> None:
    """
    Full end-to-end scrape:
      1. Launch browser & authenticate
      2. Discover events
      3. For each event, extract the fight card
      4. Download each fight video (bounded concurrency)
    """
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_DOWNLOADS)
    async with aiohttp.ClientSession(connector=connector) as http_session:
        async with async_playwright() as pw:
            browser, context = await build_context(pw, headless=headless)

            try:
                # One page is reused for navigation; fights need isolated pages
                # so we don't lose the event-page state.
                nav_page: Page = await context.new_page()
                await ensure_authenticated(nav_page, email, password)

                # ── Event discovery ──────────────────────────────────────
                events = await discover_events(nav_page, max_events=max_events)

                for event in events:
                    log.info("=== Event: %s ===", event["name"])
                    fights = await extract_fight_links(nav_page, event["url"])

                    if not fights:
                        log.warning("No fights found for event '%s'.", event["name"])
                        continue

                    # ── Parallel fight downloads ──────────────────────────
                    # Each fight gets its own page so video interception is isolated
                    tasks: list[asyncio.Task] = []
                    for fight in fights:
                        fight_page = await context.new_page()

                        async def _task(fp=fight_page, f=fight):
                            try:
                                await scrape_and_download_fight(
                                    fp, f, event["name"], sem, http_session
                                )
                            finally:
                                await fp.close()

                        tasks.append(asyncio.create_task(_task()))

                    await asyncio.gather(*tasks, return_exceptions=True)

            finally:
                await context.close()
                await browser.close()

    log.info("All done. Files saved under %s/", OUTPUT_ROOT)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    email = os.environ.get("UFC_EMAIL") or input("UFC Fight Pass email: ")
    password = os.environ.get("UFC_PASSWORD") or input("UFC Fight Pass password: ")

    # Optional: limit scraping scope for testing
    max_events_env = os.environ.get("UFC_MAX_EVENTS")
    max_events = int(max_events_env) if max_events_env else None

    headless = os.environ.get("UFC_HEADLESS", "1") != "0"

    asyncio.run(
        run(
            email,
            password,
            max_events=max_events,
            headless=headless,
        )
    )


if __name__ == "__main__":
    main()
