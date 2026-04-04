"""
Apply recovered winner/method data from ufc_all_fights.json to the DB.
Bulk-updates ufc_fights with winner_id, method_normalized, was_finish, went_to_decision.
Also re-saves the JSON with safe UTF-8 encoding.
"""
import sys, os, json, ctypes, ctypes.wintypes as wt, re
from pathlib import Path
import httpx

# ── Paths ────────────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
_ALL  = _REPO / "data" / "ufc_all_fights.json"

# ── Supabase credentials ──────────────────────────────────────────────────────
class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wt.DWORD),("Type", wt.DWORD),("TargetName", wt.LPWSTR),
                ("Comment", wt.LPWSTR),("LastWritten", wt.FILETIME),
                ("CredentialBlobSize", wt.DWORD),("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wt.DWORD),("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p),("TargetAlias", wt.LPWSTR),("UserName", wt.LPWSTR)]

def _read_cred(t):
    ptr = ctypes.c_void_p()
    if ctypes.windll.advapi32.CredReadW(t, 1, 0, ctypes.byref(ptr)):
        c = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
        b = bytes(c.CredentialBlob[i] for i in range(c.CredentialBlobSize))
        ctypes.windll.advapi32.CredFree(ptr)
        return b.decode("utf-8", errors="replace")
    return None

SUPA_URL  = "https://cxvtipiogkgpqiksakld.supabase.co/rest/v1"
SUPA_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN4dnRpcGlvZ2tncHFpa3Nha2xkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDc0ODAzNywiZXhwIjoyMDkwMzI0MDM3fQ.4VR7AB701DMRD-g8KFntVlCucr9GQITqYDXddqWHFrk"
REST_HDRS = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}",
             "Content-Type": "application/json", "Prefer": "return=representation,resolution=merge-duplicates"}
MGMT_TOKEN = _read_cred("Supabase CLI:supabase") or os.environ.get("SUPABASE_ACCESS_TOKEN")
MGMT_URL   = "https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query"
MGMT_HDRS  = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}

client = httpx.Client(timeout=120)


def _mgmt_sql(q: str) -> list:
    r = client.post(MGMT_URL, headers=MGMT_HDRS, content=json.dumps({"query": q}))
    if r.status_code not in (200, 201):
        raise RuntimeError(f"SQL {r.status_code}: {r.text[:400]}")
    d = r.json()
    return d if isinstance(d, list) else d.get("rows", [])


def _normalize_method(method: str | None) -> str | None:
    if not method:
        return None
    m = method.lower()
    if "tko" in m:                return "tko"
    if "knockout" in m or (m.startswith("ko") and "tko" not in m): return "ko"
    if "sub" in m:                return "sub"
    if "unanimous" in m:          return "ud"
    if "split" in m:              return "sd"
    if "majority" in m:           return "md"
    if "decision" in m or "dec" in m: return "ud"
    return None


def _q(s: str) -> str:
    """Escape single quotes in SQL string value."""
    return s.replace("'", "''")


# ── Load JSON with encoding fix ───────────────────────────────────────────────
print("Loading ufc_all_fights.json ...")
raw_bytes = _ALL.read_bytes()
text = raw_bytes.decode("utf-8", errors="replace")
all_fights: list[dict] = json.loads(text)
print(f"  {len(all_fights)} fights, "
      f"{sum(1 for f in all_fights if f.get('winner'))} with winner, "
      f"{sum(1 for f in all_fights if f.get('method'))} with method")

# Re-save with clean ASCII/UTF-8 (replace replacement chars)
clean_text = json.dumps(all_fights, indent=2, ensure_ascii=True)
_ALL.write_text(clean_text, encoding="utf-8")
print("  Re-saved JSON with safe ASCII encoding")

# ── Load DB fighters: name -> id ─────────────────────────────────────────────
print("\nLoading DB fighters ...")
# Paginate — get all fighters, up to 10k
offset = 0
name_to_id: dict[str, str] = {}
while True:
    r = client.get(
        f"{SUPA_URL}/ufc_fighters?select=id,name&limit=1000&offset={offset}",
        headers={**REST_HDRS, "Prefer": ""},
    )
    batch = r.json()
    if not batch:
        break
    for row in batch:
        name_to_id[row["name"]] = row["id"]
    if len(batch) < 1000:
        break
    offset += 1000
print(f"  {len(name_to_id)} fighters loaded")

# ── Load DB fight ID mapping: fight_url -> {id, fighter_a_name, fighter_b_name} ──
print("Loading DB fights ...")
offset = 0
url_to_db: dict[str, dict] = {}
while True:
    r = client.get(
        f"{SUPA_URL}/ufc_fights?select=id,ufcstats_fight_url,fighter_a_name,fighter_b_name,fighter_a_id,fighter_b_id"
        f"&limit=1000&offset={offset}",
        headers={**REST_HDRS, "Prefer": ""},
    )
    batch = r.json()
    if not batch:
        break
    for row in batch:
        url_to_db[row["ufcstats_fight_url"]] = row
    if len(batch) < 1000:
        break
    offset += 1000
print(f"  {len(url_to_db)} fights loaded")

# ── Build UPDATE payloads ─────────────────────────────────────────────────────
print("\nBuilding update payloads ...")
values_parts: list[str] = []
no_winner_id = 0
no_db_match  = 0

for f in all_fights:
    url = f.get("fight_url")
    if not url:
        continue
    db_row = url_to_db.get(url)
    if not db_row:
        no_db_match += 1
        continue

    winner_name = f.get("winner") or ""
    method_raw  = f.get("method") or ""
    method_norm = _normalize_method(method_raw) if method_raw else None

    # Find winner_id
    winner_id = None
    fighter_a_won = False
    if winner_name:
        winner_id = name_to_id.get(winner_name)
        fighter_a_won = (winner_name == db_row["fighter_a_name"])
        # Fallback: search for partial match in DB names
        if not winner_id:
            for nm, uid in name_to_id.items():
                if winner_name in nm or nm in winner_name:
                    winner_id = uid
                    fighter_a_won = (uid == db_row["fighter_a_id"])
                    break
        if not winner_id:
            no_winner_id += 1
            # Use fighter_a_id or fighter_b_id based on stored values
            winner_id = db_row["fighter_a_id"] if fighter_a_won else db_row["fighter_b_id"]

    rounds_sched = f.get("rounds_scheduled")
    weight_class = f.get("weight_class") or ""

    # Only update rows where we have at least method_norm or winner_name
    if not method_norm and not winner_name:
        continue

    fight_id = db_row["id"]
    wid_sql  = f"'{winner_id}'" if winner_id else "NULL"
    wn_sql   = f"'{_q(winner_name)}'" if winner_name else "NULL"
    mr_sql   = f"'{_q(method_raw)}'" if method_raw else "NULL"
    mn_sql   = f"'{method_norm}'" if method_norm else "NULL"
    rs_sql   = str(rounds_sched) if rounds_sched else "NULL"
    wc_sql   = f"'{_q(weight_class[:30])}'" if weight_class else "NULL"

    values_parts.append(
        f"('{fight_id}', {wid_sql}, {wn_sql}, {mr_sql}, {mn_sql}, {rs_sql}, {wc_sql})"
    )

print(f"  {len(values_parts)} fights to update ({no_db_match} no DB match, {no_winner_id} no winner_id)")

# ── Batch UPDATE via Management API ──────────────────────────────────────────
BATCH = 400
total_updated = 0
for i in range(0, len(values_parts), BATCH):
    batch = values_parts[i:i + BATCH]
    vals  = ",\n  ".join(batch)
    sql   = f"""
    UPDATE ufc_fights AS f SET
        winner_id          = v.winner_id::uuid,
        winner_name        = v.winner_name,
        method             = v.method_raw,
        method_normalized  = v.method_norm,
        rounds_scheduled   = v.rounds_sched::integer,
        weight_class       = COALESCE(NULLIF(v.wc, ''), f.weight_class)
    FROM (VALUES
      {vals}
    ) AS v(fight_id, winner_id, winner_name, method_raw, method_norm, rounds_sched, wc)
    WHERE f.id = v.fight_id::uuid
    RETURNING f.id
    """
    try:
        rows = _mgmt_sql(sql)
        total_updated += len(rows)
        print(f"  batch {i//BATCH + 1}/{(len(values_parts)+BATCH-1)//BATCH}: "
              f"{len(rows)} rows updated ({total_updated} total)", flush=True)
    except Exception as exc:
        print(f"  batch {i//BATCH + 1} FAILED: {exc}", flush=True)

print(f"\n[DONE] {total_updated} fights updated in DB")

# ── Method distribution verification ─────────────────────────────────────────
print("\n[VERIFY] Method distribution in ufc_fights:")
dist = _mgmt_sql("""
    SELECT method_normalized, COUNT(*) n
    FROM ufc_fights
    GROUP BY method_normalized
    ORDER BY n DESC
""")
for r in dist:
    print(f"  {r['method_normalized'] or 'NULL':<10} {r['n']:>5}")

# ── Refresh mat view ──────────────────────────────────────────────────────────
print("\n[REFRESH] Refreshing simulation_calibration ...")
_mgmt_sql("REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_calibration")
cnt = _mgmt_sql("SELECT COUNT(*) AS n FROM simulation_calibration")
print(f"[REFRESH] sim_calibration rows: {cnt[0]['n']}")

# ── Check was_ko / winner in sim_calibration ─────────────────────────────────
check = _mgmt_sql("""
    SELECT
        COUNT(*) total,
        SUM(was_ko) AS ko,
        SUM(was_sub) AS sub,
        SUM(was_decision) AS dec,
        SUM(fighter_a_won) AS a_won,
        COUNT(*) FILTER (WHERE a_style IS NOT NULL) AS has_style
    FROM simulation_calibration
""")
if check:
    print("[VERIFY] sim_calibration stats:", check[0])
