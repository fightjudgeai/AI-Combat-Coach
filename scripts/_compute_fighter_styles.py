"""
Compute per-fighter stats from ufc_round_stats and assign style_archetype.

Uses aggregate round stats to populate:
  - avg_offensive_efficiency, avg_defensive_response, avg_control_dictation,
    avg_finish_threat, avg_cardio_pace, avg_durability, avg_fight_iq, avg_dominance
  - style_archetype (grappling_control | volume_striker | pressure_finisher |
                     counter_striker | balanced)
  - finish_rate, ko_rate, sub_rate (from ufc_fights once method_normalized is populated)
"""
import os, json, ctypes, ctypes.wintypes as wt, httpx

class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wt.DWORD),("Type", wt.DWORD),("TargetName", wt.LPWSTR),
                ("Comment", wt.LPWSTR),("LastWritten", wt.FILETIME),
                ("CredentialBlobSize", wt.DWORD),("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wt.DWORD),("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p),("TargetAlias", wt.LPWSTR),("UserName", wt.LPWSTR)]

def read_cred(target):
    ptr = ctypes.c_void_p()
    if ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(ptr)):
        c = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
        b = bytes(c.CredentialBlob[i] for i in range(c.CredentialBlobSize))
        ctypes.windll.advapi32.CredFree(ptr)
        return b.decode("utf-8", errors="replace")
    return None

token = read_cred("Supabase CLI:supabase") or os.environ.get("SUPABASE_ACCESS_TOKEN")
MGMT_URL  = "https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query"
MGMT_HDRS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def sql(q, timeout=120):
    r = httpx.post(MGMT_URL, headers=MGMT_HDRS,
                   content=json.dumps({"query": q}), timeout=timeout)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"SQL {r.status_code}: {r.text[:500]}")
    d = r.json()
    return d if isinstance(d, list) else d.get("rows", [])


# ── 1. Update avg component stats from round_stats ───────────────────────────
print("[STATS] Computing per-fighter avg component stats from round_stats ...")
rows = sql("""
WITH fighter_round_agg AS (
    SELECT
        fighter_id,
        COUNT(*) AS rounds_n,
        AVG(offensive_efficiency)  AS avg_off_eff,
        AVG(defensive_response)    AS avg_def_resp,
        AVG(control_dictation)     AS avg_ctrl,
        AVG(finish_threat)         AS avg_fin_threat,
        -- Cardio/pace: proxy = avg strikes attempted per second of fight
        AVG(CASE WHEN sec > 0 THEN (sa::numeric / sec) * 100 ELSE NULL END) AS avg_cardio,
        AVG(durability)            AS avg_durability,
        AVG(fight_iq)              AS avg_fight_iq,
        AVG(dominance)             AS avg_dominance,
        -- Raw rate stats for style inference
        SUM(sl)                    AS total_sl,
        SUM(sa)                    AS total_sa,
        SUM(kd_f)                  AS total_kd,
        SUM(td_f)                  AS total_td,
        SUM(ctrl_f)                AS total_ctrl_sec,
        SUM(sub_att)               AS total_sub_att,
        SUM(sec)                   AS total_sec
    FROM ufc_round_stats
    WHERE fighter_id IS NOT NULL
    GROUP BY fighter_id
    HAVING COUNT(*) >= 3
)
UPDATE ufc_fighters f
SET
    avg_offensive_efficiency = ROUND(r.avg_off_eff::numeric, 2),
    avg_defensive_response   = ROUND(r.avg_def_resp::numeric, 2),
    avg_control_dictation    = ROUND(r.avg_ctrl::numeric, 2),
    avg_finish_threat        = ROUND(r.avg_fin_threat::numeric, 2),
    avg_cardio_pace          = ROUND(LEAST(r.avg_cardio::numeric, 100), 2),
    avg_durability           = ROUND(r.avg_durability::numeric, 2),
    avg_fight_iq             = ROUND(r.avg_fight_iq::numeric, 2),
    avg_dominance            = ROUND(r.avg_dominance::numeric, 2)
FROM fighter_round_agg r
WHERE f.id = r.fighter_id
RETURNING f.id
""", timeout=120)
print(f"[STATS] {len(rows)} fighters updated with avg stats")


# ── 2. Assign style_archetype from raw rate stats ────────────────────────────
# Rates per 300 seconds (per round equivalent):
#   strike_rate  = sl / total_sec * 300
#   td_rate      = td_f / total_sec * 300
#   ctrl_rate    = ctrl_sec / total_sec (fraction of time in control)
#   sub_rate_raw = sub_att / total_sec * 300
#   kd_rate      = kd_f / total_sec * 300
#
# Style archetypes:
#   grappling_control:  ctrl_rate > 0.25 AND td_rate > 1.0
#   submission_threat:  sub_rate_raw > 0.3 AND td_rate > 0.5
#   volume_striker:     strike_rate > 6.0 AND ctrl_rate < 0.15
#   pressure_finisher:  kd_rate > 0.15 OR (finish_threat > 60 AND strike_rate > 4)
#   counter_striker:    def_resp > 55 AND strike_rate between 2-5
#   balanced:           everything else
#
# Note: "grappling_control" and "submission_threat" are merged into grappling_control
# when ctrl_rate dominates, sub_threat when sub_att dominates
print("[STYLE] Computing style_archetype from raw round stats ...")
style_rows = sql("""
WITH fighter_rates AS (
    SELECT
        fighter_id,
        SUM(sec)          AS total_sec,
        SUM(sl)::float / NULLIF(SUM(sec), 0) * 300 AS strike_rate,
        SUM(kd_f)::float / NULLIF(SUM(sec), 0) * 300 AS kd_rate,
        SUM(td_f)::float / NULLIF(SUM(sec), 0) * 300 AS td_rate,
        SUM(ctrl_f)::float / NULLIF(SUM(sec), 0)     AS ctrl_frac,
        SUM(sub_att)::float / NULLIF(SUM(sec), 0) * 300 AS sub_rate_per_rnd
    FROM ufc_round_stats
    WHERE fighter_id IS NOT NULL
    GROUP BY fighter_id
    HAVING SUM(sec) >= 300
),
labeled AS (
    SELECT
        fighter_id,
        CASE
            WHEN ctrl_frac > 0.25 AND td_rate > 1.0 AND sub_rate_per_rnd < 0.4
                THEN 'grappling_control'
            WHEN sub_rate_per_rnd >= 0.4 AND td_rate > 0.5
                THEN 'submission_threat'
            WHEN kd_rate > 0.2 AND strike_rate > 4.0
                THEN 'pressure_finisher'
            WHEN strike_rate > 6.0 AND ctrl_frac < 0.15
                THEN 'volume_striker'
            WHEN td_rate < 0.5 AND ctrl_frac < 0.10 AND strike_rate BETWEEN 2 AND 6
                THEN 'counter_striker'
            ELSE 'balanced'
        END AS archetype
    FROM fighter_rates
)
UPDATE ufc_fighters f
SET style_archetype = l.archetype
FROM labeled l
WHERE f.id = l.fighter_id
RETURNING f.id, style_archetype
""", timeout=120)
print(f"[STYLE] {len(style_rows)} fighters assigned style_archetype")

# Show distribution
dist: dict[str, int] = {}
for r in style_rows:
    dist[r["style_archetype"]] = dist.get(r["style_archetype"], 0) + 1
print("[STYLE] Distribution:")
for style, count in sorted(dist.items(), key=lambda x: -x[1]):
    print(f"  {style:<25} {count:>4}")


# ── 3. Refresh sim_calibration ───────────────────────────────────────────────
print("\n[REFRESH] Refreshing simulation_calibration ...")
sql("REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_calibration", timeout=60)
cnt = sql("SELECT COUNT(*) AS n FROM simulation_calibration")
print(f"[REFRESH] {cnt[0]['n']} rows in simulation_calibration")

# Check style coverage
style_cnt = sql("""
    SELECT a_style, COUNT(*) n
    FROM simulation_calibration
    WHERE a_style IS NOT NULL
    GROUP BY a_style ORDER BY n DESC
""")
print("[STYLE in sim_calibration]:")
for r in style_cnt:
    print(f"  {r['a_style']:<25} {r['n']:>4}")
