"""
Recovery scraper: re-fetch winner + method + rounds_scheduled for all cached fights.

Uses corrected CSS selectors based on actual ufcstats.com HTML structure:
  - Winner:  person whose .b-fight-details__person-status == 'W'
  - Method:  first line of .b-fight-details__content after stripping 'Method:'
  - Rounds:  'Time format:' text-item → parse '3 Rnd' or '5 Rnd'
  - Date:    from events.json (already scraped)

Runs 20 concurrent coroutines; skips fights already recovered (cache marker).
After fetching, bulk-updates ufc_fights in Supabase.
"""
import asyncio, json, os, re, sys, ctypes, ctypes.wintypes as wt
from pathlib import Path
import httpx
from bs4 import BeautifulSoup

# ── Paths ────────────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
_RAW  = _REPO.parent / "data" / "ufc_raw"          # blissful-edison/data/ufc_raw
_ALL  = _REPO / "data" / "ufc_all_fights.json"

# ── Supabase credentials ──────────────────────────────────────────────────────
class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wt.DWORD),("Type", wt.DWORD),("TargetName", wt.LPWSTR),
                ("Comment", wt.LPWSTR),("LastWritten", wt.FILETIME),
                ("CredentialBlobSize", wt.DWORD),("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wt.DWORD),("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p),("TargetAlias", wt.LPWSTR),("UserName", wt.LPWSTR)]

def _read_cred(target: str) -> str | None:
    ptr = ctypes.c_void_p()
    if ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(ptr)):
        c = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
        b = bytes(c.CredentialBlob[i] for i in range(c.CredentialBlobSize))
        ctypes.windll.advapi32.CredFree(ptr)
        return b.decode("utf-8", errors="replace")
    return None

SUPA_URL = "https://cxvtipiogkgpqiksakld.supabase.co/rest/v1"
SUPA_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN4dnRpcGlvZ2tncHFpa3Nha2xkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDc0ODAzNywiZXhwIjoyMDkwMzI0MDM3fQ.4VR7AB701DMRD-g8KFntVlCucr9GQITqYDXddqWHFrk"
REST_HDRS = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation,resolution=merge-duplicates",
}
MGMT_TOKEN = _read_cred("Supabase CLI:supabase") or os.environ.get("SUPABASE_ACCESS_TOKEN")
MGMT_URL  = "https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query"
MGMT_HDRS = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}


# ── HTML parsing helpers (corrected selectors) ───────────────────────────────
def _parse_fight_outcome(html: str) -> dict:
    """Extract winner_name, method, rounds_scheduled, weight_class from fight page HTML."""
    soup = BeautifulSoup(html, "html.parser")

    winner_name: str | None = None
    # Each .b-fight-details__person has a status div ('W' or 'L')
    for person in soup.select(".b-fight-details__person"):
        status_el = person.select_one(".b-fight-details__person-status")
        name_el   = person.select_one(".b-fight-details__person-name")
        if status_el and name_el and status_el.get_text(strip=True) == "W":
            winner_name = name_el.get_text(strip=True)
            break

    # Method is in .b-fight-details__content — first non-label word after "Method:"
    method: str | None = None
    content = soup.select_one(".b-fight-details__content")
    if content:
        raw = content.get_text(" ", strip=True)
        m = re.search(r"Method[:\s]+([A-Za-z/]+)", raw)
        if m:
            method = m.group(1).strip()

    # Rounds scheduled from "Time format: 3 Rnd (5-5-5)" or "5 Rnd (...)"
    rounds_scheduled: int | None = None
    for item in soup.select(".b-fight-details__text-item"):
        txt = item.get_text(" ", strip=True)
        if "Time format" in txt:
            m2 = re.search(r"(\d+)\s+Rnd", txt)
            if m2:
                rounds_scheduled = int(m2.group(1))
            break

    # Weight class is in .b-fight-details__fight-title
    weight_class: str | None = None
    wc_el = soup.select_one(".b-fight-details__fight-title")
    if wc_el:
        weight_class = wc_el.get_text(strip=True) or None

    return {
        "winner": winner_name,
        "method": method,
        "rounds_scheduled": rounds_scheduled,
        "weight_class": weight_class,
    }


def _normalize_method(method: str | None) -> str | None:
    if not method:
        return None
    m = method.lower()
    if "tko" in m or "technical" in m: return "tko"
    if "ko" in m or "knockout" in m:   return "ko"
    if "sub" in m or "submission" in m: return "sub"
    if "unanimous" in m or "u dec" in m: return "ud"
    if "split" in m or "s dec" in m:    return "sd"
    if "majority" in m or "m dec" in m: return "md"
    if "dec" in m or "decision" in m:   return "ud"  # fallback
    return None


# ── Async fetch with semaphore ────────────────────────────────────────────────
CONCURRENCY = 15
DELAY       = 0.3   # seconds between requests per worker

async def _fetch_outcome(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    fight_url: str,
    idx: int,
    total: int,
) -> tuple[str, dict]:
    """Fetch a fight page and return (fight_url, outcome_dict)."""
    async with sem:
        try:
            r = await client.get(fight_url, timeout=20)
            outcome = _parse_fight_outcome(r.text)
        except Exception as exc:
            outcome = {"winner": None, "method": None, "rounds_scheduled": None, "weight_class": None}
        await asyncio.sleep(DELAY)
        if idx % 500 == 0:
            print(f"  fetched {idx}/{total}", flush=True)
        return fight_url, outcome


# ── Main recovery logic ───────────────────────────────────────────────────────
async def main() -> None:
    # Load assembled fights JSON
    all_fights: list[dict] = json.loads(_ALL.read_text("utf-8"))
    print(f"Loaded {len(all_fights)} fights from ufc_all_fights.json")

    # Build fight_url → event_date mapping from events cache
    events_cache = _RAW / "events.json"
    event_date_map: dict[str, str] = {}
    if events_cache.exists():
        events = json.loads(events_cache.read_text())
        print(f"Loaded {len(events)} events from cache")

    # Identify fights that need fixing (winner is None / method is None)
    to_fetch = [
        f["fight_url"] for f in all_fights
        if not f.get("winner") or not f.get("method")
    ]
    print(f"{len(to_fetch)} fights need winner/method re-fetch")

    if not to_fetch:
        print("All fights already have winner/method — nothing to do")
    else:
        # Parallel fetch
        sem = asyncio.Semaphore(CONCURRENCY)
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        ) as client:
            tasks = [
                _fetch_outcome(sem, client, url, i, len(to_fetch))
                for i, url in enumerate(to_fetch, 1)
            ]
            results = await asyncio.gather(*tasks)

        url_to_outcome: dict[str, dict] = dict(results)
        print(f"Fetched {len(url_to_outcome)} outcomes")

        # Merge outcomes back into all_fights
        fixed = 0
        for f in all_fights:
            outcome = url_to_outcome.get(f["fight_url"])
            if outcome:
                if outcome["winner"]:
                    f["winner"] = outcome["winner"]
                    fixed += 1
                if outcome["method"]:
                    f["method"] = outcome["method"]
                if outcome["rounds_scheduled"]:
                    f["rounds_scheduled"] = outcome["rounds_scheduled"]
                if outcome["weight_class"] and not f.get("weight_class"):
                    f["weight_class"] = outcome["weight_class"]

        print(f"Fixed winner for {fixed}/{len(to_fetch)} fights")
        _ALL.write_text(json.dumps(all_fights, indent=2, ensure_ascii=False))
        print(f"Updated ufc_all_fights.json")

    # ── Now DB-update winner_id, method_normalized, was_finish, went_to_decision ──
    # Build lookup: fight_url -> {winner_name, method, rounds_scheduled}
    print("\nBuilding DB update payloads ...")

    # Fetch current fighters (name -> id) from DB
    sync_client = httpx.Client(timeout=30)
    r = sync_client.get(
        f"{SUPA_URL}/ufc_fighters?select=id,name",
        headers={**REST_HDRS, "Prefer": ""},
    )
    name_to_id = {row["name"]: row["id"] for row in r.json()}
    print(f"  loaded {len(name_to_id)} fighter name→id from DB")

    # Fetch all fights from DB (ufcstats_fight_url, fighter_a_name, fighter_b_name, id)
    r = sync_client.get(
        f"{SUPA_URL}/ufc_fights?select=id,ufcstats_fight_url,fighter_a_name,fighter_b_name",
        headers={**REST_HDRS, "Prefer": ""},
    )
    db_fights = r.json()
    url_to_db = {row["ufcstats_fight_url"]: row for row in db_fights}
    print(f"  loaded {len(url_to_db)} fights from DB")

    # Build update payloads
    updates_sql_parts = []
    updated = 0
    skipped = 0

    for f in all_fights:
        url = f.get("fight_url")
        if not url:
            continue
        db_row = url_to_db.get(url)
        if not db_row:
            continue

        winner_name = f.get("winner")
        method_raw  = f.get("method")
        method_norm = _normalize_method(method_raw)
        rounds_sched = f.get("rounds_scheduled")

        # Determine winner_id
        a_name = db_row["fighter_a_name"]
        b_name = db_row["fighter_b_name"]
        if winner_name:
            winner_id = name_to_id.get(winner_name)
            fighter_a_won = (winner_name == a_name)
        else:
            winner_id = None
            fighter_a_won = False

        # is_finish and went_to_decision
        is_finish = method_norm in ("ko", "tko", "sub") if method_norm else None
        went_to_decision = method_norm in ("ud", "sd", "md") if method_norm else None

        fight_id = db_row["id"]
        if winner_name or method_norm:
            updates_sql_parts.append(
                f"('{fight_id}', "
                f"{'NULL' if not winner_id else chr(39)+winner_id+chr(39)}, "
                f"{'NULL' if not winner_name else chr(39)+winner_name.replace(chr(39), chr(39)+chr(39))+chr(39)}, "
                f"{'NULL' if not method_raw else chr(39)+method_raw.replace(chr(39), chr(39)+chr(39))+chr(39)}, "
                f"{'NULL' if not method_norm else chr(39)+method_norm+chr(39)}, "
                f"{'NULL' if is_finish is None else str(is_finish).lower()}, "
                f"{'NULL' if went_to_decision is None else str(went_to_decision).lower()}, "
                f"{'NULL' if not rounds_sched else str(rounds_sched)})"
            )
            updated += 1
        else:
            skipped += 1

    print(f"  {updated} fights to update, {skipped} still missing winner/method")

    if not updates_sql_parts:
        print("Nothing to update in DB.")
        return

    # Bulk UPDATE via Management API (batch by 500 rows)
    BATCH = 500
    total_updated = 0
    for i in range(0, len(updates_sql_parts), BATCH):
        batch_parts = updates_sql_parts[i:i + BATCH]
        values_str = ",\n  ".join(batch_parts)
        sql = f"""
        UPDATE ufc_fights AS f SET
            winner_id          = v.winner_id::uuid,
            winner_name        = v.winner_name,
            method             = v.method_raw,
            method_normalized  = v.method_norm,
            was_finish         = v.is_finish,
            went_to_decision   = v.went_to_decision,
            rounds_scheduled   = v.rounds_sched::integer
        FROM (VALUES
          {values_str}
        ) AS v(fight_id, winner_id, winner_name, method_raw, method_norm,
               is_finish, went_to_decision, rounds_sched)
        WHERE f.id = v.fight_id::uuid
        RETURNING f.id
        """
        resp = sync_client.post(
            MGMT_URL, headers=MGMT_HDRS,
            content=json.dumps({"query": sql}),
            timeout=120,
        )
        out = resp.json()
        rows_updated = len(out) if isinstance(out, list) else len(out.get("rows", []))
        total_updated += rows_updated
        print(f"  DB batch {i//BATCH + 1}: {rows_updated} rows updated ({total_updated} total)", flush=True)

    print(f"\n[DONE] {total_updated}/{updated} fights updated in DB")

    # ── Correct winner_id for fights where fighter_a_won was wrongly set ──────
    # The original pipeline always set winner_id=fighter_b_id (since winner was None).
    # Now we UPDATE with the CORRECT winner_id from re-fetch.
    print("\n[REFRESH] Refreshing simulation_calibration ...")
    mgmt = httpx.Client(timeout=60)
    mgmt.post(MGMT_URL, headers=MGMT_HDRS,
              content=json.dumps({"query": "REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_calibration"}))
    cnt = mgmt.post(MGMT_URL, headers=MGMT_HDRS,
                    content=json.dumps({"query": "SELECT COUNT(*) AS n FROM simulation_calibration"}))
    print(f"[REFRESH] sim_calibration rows: {cnt.json()[0]['n']}")

    # Sample results
    sample = mgmt.post(MGMT_URL, headers=MGMT_HDRS, content=json.dumps({"query": """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE was_ko IS TRUE) AS ko,
            COUNT(*) FILTER (WHERE was_sub IS TRUE) AS sub,
            COUNT(*) FILTER (WHERE was_decision IS TRUE) AS dec,
            COUNT(*) FILTER (WHERE fighter_a_won IS TRUE) AS a_won
        FROM simulation_calibration
    """}))
    stats = sample.json()
    if stats and isinstance(stats, list):
        print(f"[VERIFY] {stats[0]}")
    elif stats and isinstance(stats, dict):
        print(f"[VERIFY] {stats.get('rows', stats)}")


if __name__ == "__main__":
    asyncio.run(main())
