"""
ufc_fight_pass_scraper.py
=========================
Production-ready async scraper for UFC Fight Pass.

Default mode: scrape the 11 "UFC Title Fights" playlists (369 videos).

Pipeline:
  1. Login  →  2. Scrape playlist pages  →  3. Extract video URLs
  →  4. Download (HLS via FFmpeg, MP4 via aiohttp)

Output structure:
  ufc_fights/<Playlist Name>/<Fight Title>.mp4

Usage:
    UFC_EMAIL=you@example.com UFC_PASSWORD=secret python scripts/ufc_fight_pass_scraper.py

    # Limit fights per playlist (useful for testing)
    UFC_MAX_FIGHTS=2 UFC_EMAIL=… UFC_PASSWORD=… python scripts/ufc_fight_pass_scraper.py

    # Show browser window
    UFC_HEADLESS=0 UFC_EMAIL=… UFC_PASSWORD=… python scripts/ufc_fight_pass_scraper.py

    # Override playlists (comma-separated URLs)
    UFC_PLAYLISTS=https://ufcfightpass.com/playlist/22872 UFC_EMAIL=… UFC_PASSWORD=… python …

Requirements:
    pip install "playwright==1.49.0" aiohttp beautifulsoup4
    playwright install chromium
    # ffmpeg must be on $PATH
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

# ---------------------------------------------------------------------------
# Target playlists  –  369 UFC Title Fights across 11 playlists
# ---------------------------------------------------------------------------

TITLE_FIGHT_PLAYLISTS: list[str] = [
    "https://ufcfightpass.com/playlist/13383",
    "https://ufcfightpass.com/playlist/2608",
    "https://ufcfightpass.com/playlist/21286",
    "https://ufcfightpass.com/playlist/12324",
    "https://ufcfightpass.com/playlist/18480",
    "https://ufcfightpass.com/playlist/13592",
    "https://ufcfightpass.com/playlist/13916",
    "https://ufcfightpass.com/playlist/14160",
    "https://ufcfightpass.com/playlist/22328",
    "https://ufcfightpass.com/playlist/3148",
]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL    = "https://ufcfightpass.com"
LOGIN_URL   = f"{BASE_URL}/login"
OUTPUT_ROOT = Path("ufc_fights")          # download root
COOKIES_FILE = Path(".ufc_cookies.json")  # persisted session

MAX_CONCURRENT_DOWNLOADS = 3
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds; doubles each attempt

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
    """Strip characters unsafe in directory / file names."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def is_hls(url: str) -> bool:
    return ".m3u8" in urlparse(url).path


async def retry_async(coro_fn, *args, retries: int = MAX_RETRIES, **kwargs):
    """
    Call an async callable with exponential-backoff retry on any exception.
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

async def build_context(
    pw: Playwright, *, headless: bool = True
) -> tuple[Browser, BrowserContext]:
    """
    Launch Chromium with a realistic context and restore any saved cookies.
    """
    import random

    # Resolve the installed Chromium binary; prefer headless-shell for headless
    # mode (faster), fall back to full Chrome if not present.
    _hs = Path("/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell")
    _ch = Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    _exe: str | None = None
    if headless and _hs.exists():
        _exe = str(_hs)
    elif _ch.exists():
        _exe = str(_ch)

    launch_kwargs: dict = dict(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )
    if _exe:
        launch_kwargs["executable_path"] = _exe
        log.info("Using Chromium binary: %s", _exe)

    browser = await pw.chromium.launch(**launch_kwargs)

    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        },
    )

    # Prevent bot-detection scripts from seeing navigator.webdriver = true
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    if COOKIES_FILE.exists():
        cookies = json.loads(COOKIES_FILE.read_text())
        await context.add_cookies(cookies)
        log.info("Restored %d cookies from %s", len(cookies), COOKIES_FILE)

    return browser, context


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

async def login(page: Page, email: str, password: str) -> bool:
    """
    Submit credentials on the Fight Pass login page.
    Saves cookies to COOKIES_FILE on success so future runs skip this step.
    """
    log.info("Navigating to login page…")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
    await asyncio.sleep(2)  # allow React to hydrate the login form

    email_sel = 'input[type="email"], input[name="email"], input[id*="email"]'
    await page.wait_for_selector(email_sel, timeout=15_000)
    await page.fill(email_sel, email)

    pw_sel = 'input[type="password"]'
    await page.wait_for_selector(pw_sel, timeout=10_000)
    await page.fill(pw_sel, password)

    submit_sel = (
        'button[type="submit"], '
        'button:has-text("Sign In"), '
        'button:has-text("Log In")'
    )
    btn = page.locator(submit_sel).first
    if await btn.count() > 0:
        await btn.click()
    else:
        await page.keyboard.press("Enter")

    try:
        await page.wait_for_url(lambda url: "login" not in url, timeout=25_000)
    except Exception:
        log.error("Login appears to have failed – still on %s", page.url)
        return False

    log.info("Logged in. Current URL: %s", page.url)

    cookies = await page.context.cookies()
    COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
    log.info("Saved %d cookies to %s", len(cookies), COOKIES_FILE)
    return True


async def ensure_authenticated(page: Page, email: str, password: str) -> None:
    """
    Navigate to home; if not already logged in, call login(). Raises on failure.
    """
    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30_000)
    account_sel = (
        '[data-testid="account-menu"], '
        '[aria-label*="account" i], '
        '.user-avatar, '
        '[class*="userMenu"], '
        '[class*="ProfileMenu"]'
    )
    if await page.locator(account_sel).count() > 0:
        log.info("Session already authenticated.")
        return

    ok = await retry_async(login, page, email, password)
    if not ok:
        raise RuntimeError("Authentication failed after retries.")


# ---------------------------------------------------------------------------
# Playlist scraping
# ---------------------------------------------------------------------------

async def _scroll_until_stable(
    page: Page, *, max_scrolls: int = 60, pause: float = 1.5
) -> None:
    """
    Scroll to the bottom repeatedly until the page height stops growing.
    Handles infinite-scroll / lazy-loaded grids.
    """
    prev_height = 0
    for i in range(max_scrolls):
        cur_height: int = await page.evaluate("document.body.scrollHeight")
        if cur_height == prev_height:
            log.debug("Scroll stable after %d iterations (height=%d)", i, cur_height)
            break
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(pause)
        prev_height = cur_height


async def scrape_playlist_videos(
    page: Page,
    playlist_url: str,
    *,
    max_videos: int | None = None,
) -> tuple[str, list[dict]]:
    """
    Navigate to a Fight Pass playlist page and extract all video entries.

    Returns:
        (playlist_name, [{'url': str, 'name': str}, …])
    """
    log.info("Opening playlist: %s", playlist_url)
    await page.goto(playlist_url, wait_until="domcontentloaded", timeout=60_000)
    await asyncio.sleep(3)  # allow React to render the video grid

    # ── Extract playlist title ────────────────────────────────────────────
    # Fight Pass uses various heading selectors; try most-specific first.
    title_sel = (
        "h1, "
        '[class*="playlistTitle"], '
        '[class*="PlaylistTitle"], '
        '[class*="pageTitle"], '
        '[data-testid*="title"]'
    )
    playlist_name = "UFC_Title_Fights"  # fallback
    try:
        title_el = page.locator(title_sel).first
        if await title_el.count() > 0:
            text = (await title_el.inner_text()).strip()
            if text:
                playlist_name = text
    except Exception:
        pass
    log.info("Playlist name: '%s'", playlist_name)

    # ── Wait for the first video card ────────────────────────────────────
    card_sel = (
        'a[href*="/video/"], '
        'a[href*="/fight/"], '
        'a[href*="/watch/"], '
        '[data-testid*="video"], '
        '[data-testid*="card"]'
    )
    try:
        await page.wait_for_selector(card_sel, timeout=20_000)
    except Exception:
        log.warning("No video cards found on %s after 20 s", playlist_url)
        return playlist_name, []

    # ── Scroll to load all lazy items ────────────────────────────────────
    await _scroll_until_stable(page)

    # ── Extract all video links + titles ─────────────────────────────────
    videos: list[dict] = await page.evaluate(
        """() => {
            // Candidate selectors for individual video/fight links
            const anchors = Array.from(document.querySelectorAll(
                'a[href*="/video/"], a[href*="/fight/"], a[href*="/watch/"]'
            ));

            const seen = new Set();
            const results = [];

            for (const a of anchors) {
                const href = a.href;
                if (!href || seen.has(href)) continue;
                seen.add(href);

                // Try progressively broader text sources for the title
                const titleEl = (
                    a.querySelector('[class*="title" i]') ||
                    a.querySelector('[class*="name" i]')  ||
                    a.querySelector('h2, h3, h4, p')
                );
                const rawName = titleEl
                    ? titleEl.innerText.trim()
                    : a.innerText.trim();

                // Skip nav / UI links that have no meaningful title
                if (!rawName || rawName.length < 3) continue;

                results.push({ url: href, name: rawName });
            }
            return results;
        }"""
    )

    if not videos:
        log.warning("JS extraction returned 0 videos for %s", playlist_url)
        return playlist_name, []

    if max_videos:
        videos = videos[:max_videos]

    log.info("  → %d videos found in playlist '%s'", len(videos), playlist_name)
    return playlist_name, videos


# ---------------------------------------------------------------------------
# Video URL extraction
# ---------------------------------------------------------------------------

async def _intercept_video_url(page: Page, video_url: str) -> str | None:
    """
    Navigate to a fight/video page and capture the media stream URL.

    Strategy (in order):
      1. Playwright network interception – catches .m3u8 / .mp4 requests.
      2. DOM inspection in every frame – checks <video>, JW Player, Bitmovin,
         and inline <script> tags.
    """
    captured: list[str] = []

    def _on_request(request) -> None:
        url = request.url
        if re.search(r"\.(m3u8|mp4)(\?|$)", url, re.IGNORECASE):
            captured.append(url)
            log.debug("Intercepted media request: %s", url)

    page.on("request", _on_request)

    log.info("Loading video page: %s", video_url)
    await page.goto(video_url, wait_until="domcontentloaded", timeout=60_000)
    await asyncio.sleep(2)  # allow the video player to initialise

    # Give the JS player time to initialise and fire its first manifest request
    await asyncio.sleep(4)

    if captured:
        # Prefer master/top-level manifests over segment playlists
        master = next(
            (u for u in captured if "master" in u.lower() or "index.m3u8" in u.lower()),
            captured[0],
        )
        return master

    # Fallback: inspect every frame's DOM
    for frame in page.frames:
        src = await _extract_from_frame(frame)
        if src:
            return src

    log.warning("No video URL found for %s", video_url)
    return None


async def _extract_from_frame(frame) -> str | None:
    """
    Inspect a single frame for video sources via DOM, JW Player, Bitmovin,
    or inline script JSON blobs.
    """
    try:
        src: str | None = await frame.evaluate(
            """() => {
                // 1. HTML5 <video> / <source>
                const v = document.querySelector('video[src]');
                if (v && v.src) return v.src;
                const s = document.querySelector('source[src]');
                if (s && s.src) return s.src;

                // 2. JW Player
                if (window.jwplayer) {
                    try {
                        const p = jwplayer();
                        const item = p && p.getPlaylistItem && p.getPlaylistItem();
                        if (item && item.file) return item.file;
                    } catch (_) {}
                }

                // 3. Bitmovin Player
                if (window.bitmovin) {
                    try {
                        const cfg = bitmovin.player('player').getConfig();
                        if (cfg && cfg.source)
                            return cfg.source.hls || cfg.source.progressive || null;
                    } catch (_) {}
                }

                // 4. VideoJS
                if (window.videojs) {
                    try {
                        const players = Object.values(videojs.players || {});
                        for (const p of players) {
                            const src = p.currentSrc && p.currentSrc();
                            if (src) return src;
                        }
                    } catch (_) {}
                }

                // 5. Scan inline <script> tags for m3u8 / mp4 URL literals
                for (const sc of document.querySelectorAll('script:not([src])')) {
                    let m;
                    m = sc.textContent.match(/"(https?[^"]+\\.m3u8[^"]*)"/);
                    if (m) return m[1];
                    m = sc.textContent.match(/"(https?[^"]+\\.mp4[^"]*)"/);
                    if (m) return m[1];
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
    Stream-copy an HLS playlist into a single .mp4 via FFmpeg.
    Runs in a thread-pool executor so the event loop stays unblocked.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
        "-i", m3u8_url,
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]
    log.info("FFmpeg → %s", output_path.name)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run_ffmpeg, cmd)
    log.info("HLS done → %s", output_path)


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg exited {result.returncode}:\n{result.stderr[-2000:]}"
        )


# ---------------------------------------------------------------------------
# Download: MP4 via aiohttp
# ---------------------------------------------------------------------------

async def download_mp4(
    mp4_url: str,
    output_path: Path,
    *,
    session: aiohttp.ClientSession,
    chunk_size: int = 1 << 20,   # 1 MiB
) -> None:
    """
    Stream an MP4 file to disk; logs progress every 50 MiB.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading MP4 → %s", output_path.name)

    headers = {"User-Agent": USER_AGENTS[0], "Referer": BASE_URL}
    async with session.get(mp4_url, headers=headers) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        written = 0
        with output_path.open("wb") as fh:
            async for chunk in resp.content.iter_chunked(chunk_size):
                fh.write(chunk)
                written += len(chunk)
                if total and written % (50 * chunk_size) < chunk_size:
                    log.info(
                        "  %.1f%%  (%.1f / %.1f MiB)",
                        written / total * 100, written / 1e6, total / 1e6,
                    )

    log.info("MP4 done → %s  (%.1f MiB)", output_path, written / 1e6)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

async def download_video(
    video_url: str,
    output_path: Path,
    *,
    session: aiohttp.ClientSession,
) -> None:
    """Route to FFmpeg (HLS) or aiohttp (MP4) based on the URL."""
    if is_hls(video_url):
        await retry_async(download_hls, video_url, output_path)
    else:
        await retry_async(download_mp4, video_url, output_path, session=session)


# ---------------------------------------------------------------------------
# Per-video orchestration
# ---------------------------------------------------------------------------

async def process_video(
    context: BrowserContext,
    video: dict,
    output_dir: Path,
    sem: asyncio.Semaphore,
    session: aiohttp.ClientSession,
) -> None:
    """
    Open an isolated page, intercept the media URL, then download.
    The semaphore limits how many downloads run simultaneously.
    """
    name = sanitize(video["name"]) or sanitize(video["url"].split("/")[-1])
    output_path = output_dir / f"{name}.mp4"

    if output_path.exists():
        log.info("Skip (already exists): %s", output_path)
        return

    async with sem:
        page = await context.new_page()
        try:
            video_url = await retry_async(_intercept_video_url, page, video["url"])
            if not video_url:
                log.error("Could not find media URL for '%s'", video["name"])
                return
            log.info("Media URL: %s", video_url)
            await download_video(video_url, output_path, session=session)
        except Exception as exc:
            log.error("Failed '%s': %s", video["name"], exc, exc_info=True)
        finally:
            await page.close()


# ---------------------------------------------------------------------------
# Playlist orchestration
# ---------------------------------------------------------------------------

async def run_playlists(
    email: str,
    password: str,
    playlist_urls: list[str],
    *,
    max_fights: int | None = None,
    headless: bool = True,
) -> None:
    """
    Main entry point for playlist-based scraping.

    For each playlist URL:
      - Authenticate (once, reusing session)
      - Scrape the video listing (with scroll-to-bottom)
      - Download each video in parallel (bounded by MAX_CONCURRENT_DOWNLOADS)
    """
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_DOWNLOADS)
    async with aiohttp.ClientSession(connector=connector) as http_session:
        async with async_playwright() as pw:
            browser, context = await build_context(pw, headless=headless)
            try:
                nav_page: Page = await context.new_page()
                await ensure_authenticated(nav_page, email, password)

                total_downloaded = 0

                for playlist_url in playlist_urls:
                    log.info("=" * 60)
                    log.info("Playlist: %s", playlist_url)

                    playlist_name, videos = await scrape_playlist_videos(
                        nav_page, playlist_url, max_videos=max_fights
                    )
                    if not videos:
                        log.warning("No videos found – skipping playlist.")
                        continue

                    output_dir = OUTPUT_ROOT / sanitize(playlist_name)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    log.info(
                        "Downloading %d videos into '%s'", len(videos), output_dir
                    )

                    tasks = [
                        asyncio.create_task(
                            process_video(context, v, output_dir, sem, http_session)
                        )
                        for v in videos
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    succeeded = sum(1 for r in results if not isinstance(r, Exception))
                    total_downloaded += succeeded
                    log.info(
                        "Playlist done: %d/%d succeeded.", succeeded, len(videos)
                    )

                log.info("=" * 60)
                log.info("All playlists complete. Total videos processed: %d", total_downloaded)

            finally:
                await context.close()
                await browser.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    email    = os.environ.get("UFC_EMAIL")    or input("UFC Fight Pass email: ")
    password = os.environ.get("UFC_PASSWORD") or input("UFC Fight Pass password: ")

    # Allow overriding the playlist list via env var (comma-separated URLs)
    playlists_env = os.environ.get("UFC_PLAYLISTS")
    playlist_urls = (
        [u.strip() for u in playlists_env.split(",") if u.strip()]
        if playlists_env
        else TITLE_FIGHT_PLAYLISTS
    )

    # UFC_MAX_FIGHTS limits videos *per playlist* (handy for smoke-testing)
    max_fights_env = os.environ.get("UFC_MAX_FIGHTS")
    max_fights = int(max_fights_env) if max_fights_env else None

    headless = os.environ.get("UFC_HEADLESS", "1") != "0"

    log.info(
        "Starting – %d playlists, max_fights=%s, headless=%s",
        len(playlist_urls), max_fights, headless,
    )

    asyncio.run(
        run_playlists(
            email,
            password,
            playlist_urls,
            max_fights=max_fights,
            headless=headless,
        )
    )


if __name__ == "__main__":
    main()
