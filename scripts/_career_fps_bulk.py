"""Bulk-compute career FPS for all eligible fighters in a single SQL UPDATE."""
import sys, os, json, ctypes, ctypes.wintypes as wt, httpx

class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wt.DWORD), ("Type", wt.DWORD), ("TargetName", wt.LPWSTR),
                ("Comment", wt.LPWSTR), ("LastWritten", wt.FILETIME),
                ("CredentialBlobSize", wt.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wt.DWORD), ("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p), ("TargetAlias", wt.LPWSTR), ("UserName", wt.LPWSTR)]

def read_cred(target: str) -> str | None:
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

MGMT_URL = "https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query"
MGMT_HDRS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def sql(query: str, timeout: int = 120) -> list:
    r = httpx.post(MGMT_URL, headers=MGMT_HDRS,
                   content=json.dumps({"query": query}), timeout=timeout)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"SQL {r.status_code}: {r.text[:500]}")
    d = r.json()
    return d if isinstance(d, list) else d.get("rows", [])


# ── Career FPS bulk update ───────────────────────────────────────────────────
CAREER_SQL = """
WITH all_fps AS (
    SELECT fighter_a_id AS fighter_id, fighter_a_fps AS fps, fight_date
      FROM ufc_fights
     WHERE fighter_a_id IS NOT NULL AND fighter_a_fps IS NOT NULL
    UNION ALL
    SELECT fighter_b_id, fighter_b_fps, fight_date
      FROM ufc_fights
     WHERE fighter_b_id IS NOT NULL AND fighter_b_fps IS NOT NULL
),
ranked AS (
    SELECT fighter_id, fps,
           ROW_NUMBER() OVER (
               PARTITION BY fighter_id ORDER BY fight_date DESC NULLS LAST
           ) AS rn
    FROM all_fps
),
top5 AS (
    SELECT fighter_id, fps, rn FROM ranked WHERE rn <= 5
),
weighted AS (
    SELECT
        fighter_id,
        COUNT(*) AS n,
        SUM(fps * CASE rn
            WHEN 1 THEN 0.35 WHEN 2 THEN 0.25 WHEN 3 THEN 0.18
            WHEN 4 THEN 0.12 WHEN 5 THEN 0.10
        END) /
        SUM(CASE rn
            WHEN 1 THEN 0.35 WHEN 2 THEN 0.25 WHEN 3 THEN 0.18
            WHEN 4 THEN 0.12 WHEN 5 THEN 0.10
        END) AS career_fps
    FROM top5
    GROUP BY fighter_id
    HAVING COUNT(*) >= 5
)
UPDATE ufc_fighters f
SET
    career_fps          = ROUND(w.career_fps::numeric, 2),
    career_fps_tier     = CASE
                              WHEN w.career_fps >= 75 THEN 'ELITE'
                              WHEN w.career_fps >= 60 THEN 'COMPETITIVE'
                              WHEN w.career_fps >= 45 THEN 'MIXED'
                              WHEN w.career_fps >= 30 THEN 'DEVELOPING'
                              ELSE 'EARLY_CAREER'
                          END,
    fps_fight_count     = w.n,
    fps_last_calculated = NOW()
FROM weighted w
WHERE f.id = w.fighter_id
RETURNING f.id
"""

print("[CAREER] Bulk-computing career FPS for all eligible fighters ...")
rows = sql(CAREER_SQL, timeout=120)
print(f"[CAREER] {len(rows)} fighters updated with career_fps")

# ── Verify ───────────────────────────────────────────────────────────────────
stats = sql("""
    SELECT
        COUNT(*) FILTER (WHERE career_fps IS NOT NULL) AS with_fps,
        COUNT(*) AS total,
        ROUND(MIN(career_fps)::numeric, 1) AS min_fps,
        ROUND(MAX(career_fps)::numeric, 1) AS max_fps,
        ROUND(AVG(career_fps)::numeric, 1) AS avg_fps
    FROM ufc_fighters
""")
s = stats[0]
print(f"[VERIFY] {s['with_fps']}/{s['total']} fighters have career_fps  "
      f"(min={s['min_fps']} avg={s['avg_fps']} max={s['max_fps']})")

# ── Refresh materialized view ────────────────────────────────────────────────
print("[REFRESH] Refreshing simulation_calibration ...")
sql("REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_calibration", timeout=60)
cnt = sql("SELECT COUNT(*) AS n FROM simulation_calibration")
print(f"[REFRESH] simulation_calibration now has {cnt[0]['n']} rows")

# ── Top 10 fighters by career FPS ────────────────────────────────────────────
top = sql("""
    SELECT name, career_fps, career_fps_tier, ufc_appearances
    FROM ufc_fighters
    WHERE career_fps IS NOT NULL
    ORDER BY career_fps DESC
    LIMIT 10
""")
print("\nTop 10 by career FPS:")
for f in top:
    print(f"  {f['name']:<30} {f['career_fps']:>6}  {f['career_fps_tier']:<12}  ({f['ufc_appearances']} fights)")
