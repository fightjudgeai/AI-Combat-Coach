"""One-shot script: fix ufc_appearances counts then print career FPS for top fighters."""
import sys, os, ctypes, ctypes.wintypes as wt, httpx
sys.path.insert(0, str(__file__.rsplit("\\", 2)[0]))  # AI-Combat-Coach/

class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wt.DWORD), ("Type", wt.DWORD), ("TargetName", wt.LPWSTR),
                ("Comment", wt.LPWSTR), ("LastWritten", wt.FILETIME),
                ("CredentialBlobSize", wt.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wt.DWORD), ("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p), ("TargetAlias", wt.LPWSTR), ("UserName", wt.LPWSTR)]

def read_cred(target):
    ptr = ctypes.c_void_p()
    if ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(ptr)):
        c = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
        b = bytes(c.CredentialBlob[i] for i in range(c.CredentialBlobSize))
        ctypes.windll.advapi32.CredFree(ptr)
        return b.decode("utf-8", errors="replace")
    return None

token = read_cred("Supabase CLI:supabase") or os.environ.get("SUPABASE_ACCESS_TOKEN")
if not token:
    sys.exit("No Management API token found")

url = "https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query"
hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def sql(q):
    r = httpx.post(url, headers=hdrs, json={"query": q}, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(r.text[:400])
    d = r.json()
    return d if isinstance(d, list) else d.get("rows", [])

# ── Fix appearances ──────────────────────────────────────────────────────────
print("[APPEARANCES] Updating ufc_appearances via UNION ALL join ...")
result = sql("""
    UPDATE ufc_fighters f
    SET ufc_appearances = counts.cnt
    FROM (
        SELECT fighter_id, COUNT(*) AS cnt
        FROM (
            SELECT fighter_a_id AS fighter_id FROM ufc_fights WHERE fighter_a_id IS NOT NULL
            UNION ALL
            SELECT fighter_b_id AS fighter_id FROM ufc_fights WHERE fighter_b_id IS NOT NULL
        ) all_fighters
        GROUP BY fighter_id
    ) counts
    WHERE f.id = counts.fighter_id
    RETURNING f.id
""")
print(f"[APPEARANCES] {len(result)} fighters updated")

# ── Verify ───────────────────────────────────────────────────────────────────
rows = sql("""
    SELECT
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE meets_5_fight_threshold = TRUE) AS eligible,
        MAX(ufc_appearances) AS max_apps
    FROM ufc_fighters
""")
r = rows[0]
print(f"[VERIFY] total={r['total']} eligible={r['eligible']} max_appearances={r['max_apps']}")

# ── Compute career FPS for eligible fighters ─────────────────────────────────
from scripts.scoring_engine.fps_calculator import get_fps_tier

print("\n[CAREER] Computing career FPS ...")
RECENCY_WEIGHTS = [0.35, 0.25, 0.18, 0.12, 0.10]

fighters = sql("""
    SELECT id, name FROM ufc_fighters
    WHERE meets_5_fight_threshold = TRUE
    ORDER BY name
""")
print(f"[CAREER] {len(fighters)} eligible fighters")

updated = 0
for fighter in fighters:
    fid = fighter["id"]
    # Last 5 fights' FPS scores
    fights = sql(f"""
        SELECT
            CASE WHEN fighter_a_id = '{fid}' THEN fighter_a_fps
                 ELSE fighter_b_fps END AS fps,
            fight_date
        FROM ufc_fights
        WHERE (fighter_a_id = '{fid}' OR fighter_b_id = '{fid}')
          AND CASE WHEN fighter_a_id = '{fid}' THEN fighter_a_fps
                   ELSE fighter_b_fps END IS NOT NULL
        ORDER BY fight_date DESC NULLS LAST
        LIMIT 5
    """)
    if len(fights) < 5:
        continue

    fps_scores = [float(f["fps"]) for f in fights]
    n = min(len(fps_scores), len(RECENCY_WEIGHTS))
    w = RECENCY_WEIGHTS[:n]
    career_fps = sum(s * wt for s, wt in zip(fps_scores, w)) / sum(w)
    tier = get_fps_tier(career_fps)

    sql(f"""
        UPDATE ufc_fighters SET
            career_fps          = {round(career_fps, 2)},
            career_fps_tier     = '{tier}',
            fps_fight_count     = {n},
            fps_last_calculated = NOW()
        WHERE id = '{fid}'
    """)
    updated += 1

print(f"[CAREER] {updated} fighters updated with career FPS")

# ── Refresh mat view ──────────────────────────────────────────────────────────
print("\n[REFRESH] Refreshing simulation_calibration ...")
sql("REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_calibration")
rows = sql("SELECT COUNT(*) AS n FROM simulation_calibration")
print(f"[REFRESH] simulation_calibration now has {rows[0]['n']} rows")

print("\n[DONE] All stages complete")
