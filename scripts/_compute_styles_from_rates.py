"""
Compute per-fighter finish/ko/sub rates from ufc_fights where method_normalized IS NOT NULL,
then assign style_archetype based on those rates.
Uses only fighters with 3+ fights with known methods for reliable classification.
"""
import os, json, ctypes, ctypes.wintypes as wt, httpx

class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wt.DWORD),("Type", wt.DWORD),("TargetName", wt.LPWSTR),
                ("Comment", wt.LPWSTR),("LastWritten", wt.FILETIME),
                ("CredentialBlobSize", wt.DWORD),("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wt.DWORD),("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p),("TargetAlias", wt.LPWSTR),("UserName", wt.LPWSTR)]

def read_cred(t):
    ptr = ctypes.c_void_p()
    if ctypes.windll.advapi32.CredReadW(t, 1, 0, ctypes.byref(ptr)):
        c = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
        b = bytes(c.CredentialBlob[i] for i in range(c.CredentialBlobSize))
        ctypes.windll.advapi32.CredFree(ptr)
        return b.decode("utf-8", errors="replace")
    return None

token = read_cred("Supabase CLI:supabase") or os.environ.get("SUPABASE_ACCESS_TOKEN")
MGMT_URL  = "https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query"
MGMT_HDRS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def sql(q, timeout=120):
    r = httpx.post(MGMT_URL, headers=MGMT_HDRS, content=json.dumps({"query": q}), timeout=timeout)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"SQL {r.status_code}: {r.text[:400]}")
    d = r.json()
    return d if isinstance(d, list) else d.get("rows", [])


# ── 1. Compute per-fighter finish/ko/sub rates ────────────────────────────────
print("[RATES] Computing per-fighter finish/ko/sub rates from fight outcomes ...")
rows = sql("""
WITH fighter_fights AS (
    SELECT fighter_id, method_normalized
    FROM (
        SELECT fighter_a_id AS fighter_id,
               method_normalized
        FROM ufc_fights
        WHERE fighter_a_id IS NOT NULL
          AND method_normalized IS NOT NULL
        UNION ALL
        SELECT fighter_b_id,
               method_normalized
        FROM ufc_fights
        WHERE fighter_b_id IS NOT NULL
          AND method_normalized IS NOT NULL
    ) x
),
fighter_rates AS (
    SELECT
        fighter_id,
        COUNT(*)                                                       AS fights_with_method,
        ROUND(
            COUNT(*) FILTER (WHERE method_normalized IN ('ko','tko','sub'))::numeric
            / COUNT(*)::numeric, 3
        )                                                              AS finish_rate,
        ROUND(
            COUNT(*) FILTER (WHERE method_normalized IN ('ko','tko'))::numeric
            / NULLIF(COUNT(*) FILTER (WHERE method_normalized IN ('ko','tko','sub')), 0)::numeric, 3
        )                                                              AS ko_rate,
        ROUND(
            COUNT(*) FILTER (WHERE method_normalized = 'sub')::numeric
            / NULLIF(COUNT(*) FILTER (WHERE method_normalized IN ('ko','tko','sub')), 0)::numeric, 3
        )                                                              AS sub_rate,
        ROUND(
            COUNT(*) FILTER (WHERE method_normalized IN ('ud','sd','md'))::numeric
            / COUNT(*)::numeric, 3
        )                                                              AS decision_rate
    FROM fighter_fights
    GROUP BY fighter_id
    HAVING COUNT(*) >= 3
)
UPDATE ufc_fighters f
SET
    finish_rate = r.finish_rate,
    ko_rate     = r.ko_rate,
    sub_rate    = r.sub_rate
FROM fighter_rates r
WHERE f.id = r.fighter_id
RETURNING f.id
""", timeout=60)
print(f"[RATES] {len(rows)} fighters updated with finish/ko/sub rates")


# ── 2. Check rate distributions ──────────────────────────────────────────────
dist = sql("""
    SELECT
        percentile_cont(0.25) WITHIN GROUP (ORDER BY finish_rate) AS p25_finish,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY finish_rate) AS p50_finish,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY finish_rate) AS p75_finish,
        percentile_cont(0.90) WITHIN GROUP (ORDER BY finish_rate) AS p90_finish,
        AVG(finish_rate) AS avg_finish
    FROM ufc_fighters
    WHERE finish_rate IS NOT NULL
""")
if dist:
    d = dist[0]
    print(f"\nFinish rate distribution: p25={d['p25_finish']:.3f} p50={d['p50_finish']:.3f} "
          f"p75={d['p75_finish']:.3f} p90={d['p90_finish']:.3f} avg={float(d['avg_finish']):.3f}")


# ── 3. Assign style_archetype from finish/ko/sub rates ────────────────────────
# Style logic:
#   pressure_finisher:   finish_rate >= 75th pctile AND ko_rate > 0.5
#   submission_threat:   finish_rate >= 75th pctile AND sub_rate >= 0.4
#   grappling_control:   finish_rate <= 25th pctile (goes to decision)
#   volume_striker:      decision_rate >= 75th pctile AND ko_rate < 0.2 (dec striker)
#   balanced:            everything else
# Using percentile thresholds relative to the data distribution

print("[STYLE] Assigning style_archetype from finish/ko/sub rates ...")
style_rows = sql("""
WITH rate_percentiles AS (
    SELECT
        percentile_cont(0.75) WITHIN GROUP (ORDER BY finish_rate) AS p75_finish,
        percentile_cont(0.25) WITHIN GROUP (ORDER BY finish_rate) AS p25_finish,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY decision_rate) AS p75_dec,
        percentile_cont(0.25) WITHIN GROUP (ORDER BY decision_rate) AS p25_dec
    FROM (
        SELECT
            fighter_id,
            SUM(CASE WHEN method_normalized IN ('ko','tko','sub') THEN 1 ELSE 0 END)::float
            / COUNT(*) AS finish_rate,
            SUM(CASE WHEN method_normalized IN ('ud','sd','md') THEN 1 ELSE 0 END)::float
            / COUNT(*) AS decision_rate
        FROM (
            SELECT fighter_a_id AS fighter_id, method_normalized FROM ufc_fights
             WHERE fighter_a_id IS NOT NULL AND method_normalized IS NOT NULL
            UNION ALL
            SELECT fighter_b_id, method_normalized FROM ufc_fights
             WHERE fighter_b_id IS NOT NULL AND method_normalized IS NOT NULL
        ) x
        GROUP BY fighter_id HAVING COUNT(*) >= 3
    ) rates
)
UPDATE ufc_fighters f
SET style_archetype = CASE
    WHEN f.finish_rate >= (SELECT p75_finish FROM rate_percentiles)
         AND COALESCE(f.ko_rate, 0) > 0.5
        THEN 'pressure_finisher'
    WHEN f.finish_rate >= (SELECT p75_finish FROM rate_percentiles)
         AND COALESCE(f.sub_rate, 0) >= 0.4
        THEN 'submission_threat'
    WHEN f.finish_rate >= (SELECT p75_finish FROM rate_percentiles)
        THEN 'pressure_finisher'
    WHEN COALESCE(f.ko_rate, 0) < 0.2
         AND f.finish_rate <= (SELECT p25_finish FROM rate_percentiles)
        THEN 'grappling_control'
    WHEN f.finish_rate <= (SELECT p25_finish FROM rate_percentiles)
         AND COALESCE(f.sub_rate, 0) >= 0.3
        THEN 'submission_threat'
    WHEN f.finish_rate <= (SELECT p25_finish FROM rate_percentiles)
        THEN 'grappling_control'
    ELSE 'balanced'
END
WHERE f.finish_rate IS NOT NULL
RETURNING f.id, f.style_archetype
""", timeout=60)
print(f"[STYLE] {len(style_rows)} fighters assigned style_archetype")

dist2: dict[str, int] = {}
for r in style_rows:
    dist2[r["style_archetype"]] = dist2.get(r["style_archetype"], 0) + 1
print("[STYLE] Distribution:")
for s, n in sorted(dist2.items(), key=lambda x: -x[1]):
    print(f"  {s:<25} {n:>4}")


# ── 4. Refresh simulation_calibration ────────────────────────────────────────
print("\n[REFRESH] Refreshing simulation_calibration ...")
sql("REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_calibration", timeout=60)
cnt = sql("SELECT COUNT(*) AS n FROM simulation_calibration")
print(f"[REFRESH] {cnt[0]['n']} rows in sim_calibration")

# Style coverage in sim_calibration
style_cov = sql("""
    SELECT a_style, COUNT(*) n
    FROM simulation_calibration
    GROUP BY a_style ORDER BY n DESC
""")
print("[a_style distribution in sim_calibration]:")
for r in style_cov:
    print(f"  {r['a_style'] or 'NULL':<25} {r['n']:>4}")

# Final verification
verify = sql("""
    SELECT
        SUM(was_ko) AS ko,
        SUM(was_sub) AS sub,
        SUM(was_decision) AS dec,
        SUM(fighter_a_won) AS a_won,
        COUNT(*) FILTER (WHERE a_style IS NOT NULL AND b_style IS NOT NULL) AS both_styles,
        COUNT(*) AS total
    FROM simulation_calibration
""")
if verify:
    print("\n[FINAL VERIFY] sim_calibration:", verify[0])
