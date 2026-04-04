"""Check actual distribution of fight rate stats to calibrate style thresholds."""
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

def sql(q, timeout=30):
    r = httpx.post(MGMT_URL, headers=MGMT_HDRS,
                   content=json.dumps({"query": q}), timeout=timeout)
    d = r.json()
    return d if isinstance(d, list) else d.get("rows", [])


stats = sql("""
    SELECT
        percentile_cont(0.25) WITHIN GROUP (ORDER BY strike_rate) AS p25_strike,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY strike_rate) AS p50_strike,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY strike_rate) AS p75_strike,
        percentile_cont(0.90) WITHIN GROUP (ORDER BY strike_rate) AS p90_strike,
        percentile_cont(0.25) WITHIN GROUP (ORDER BY td_rate) AS p25_td,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY td_rate) AS p50_td,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY td_rate) AS p75_td,
        percentile_cont(0.90) WITHIN GROUP (ORDER BY td_rate) AS p90_td,
        percentile_cont(0.25) WITHIN GROUP (ORDER BY ctrl_frac) AS p25_ctrl,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY ctrl_frac) AS p50_ctrl,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY ctrl_frac) AS p75_ctrl,
        percentile_cont(0.25) WITHIN GROUP (ORDER BY sub_rate_per_rnd) AS p25_sub,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY sub_rate_per_rnd) AS p50_sub,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY sub_rate_per_rnd) AS p75_sub,
        percentile_cont(0.90) WITHIN GROUP (ORDER BY sub_rate_per_rnd) AS p90_sub,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY kd_rate) AS p50_kd,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY kd_rate) AS p75_kd,
        percentile_cont(0.90) WITHIN GROUP (ORDER BY kd_rate) AS p90_kd
    FROM (
        SELECT
            fighter_id,
            SUM(sl)::float / NULLIF(SUM(sec), 0) * 300 AS strike_rate,
            SUM(kd_f)::float / NULLIF(SUM(sec), 0) * 300 AS kd_rate,
            SUM(td_f)::float / NULLIF(SUM(sec), 0) * 300 AS td_rate,
            SUM(ctrl_f)::float / NULLIF(SUM(sec), 0)     AS ctrl_frac,
            SUM(sub_att)::float / NULLIF(SUM(sec), 0) * 300 AS sub_rate_per_rnd
        FROM ufc_round_stats
        WHERE fighter_id IS NOT NULL
        GROUP BY fighter_id
        HAVING SUM(sec) >= 300
    ) rates
""")
if stats:
    s = stats[0]
    print("Strike rate  (SL/300s): p25={p25_strike:.1f} p50={p50_strike:.1f} p75={p75_strike:.1f} p90={p90_strike:.1f}".format(**s))
    print("TD rate      (TD/300s): p25={p25_td:.2f} p50={p50_td:.2f} p75={p75_td:.2f} p90={p90_td:.2f}".format(**s))
    print("Ctrl frac    (ctrl/sec):p25={p25_ctrl:.3f} p50={p50_ctrl:.3f} p75={p75_ctrl:.3f}".format(**s))
    print("Sub rate     (sub/300s):p25={p25_sub:.3f} p50={p50_sub:.3f} p75={p75_sub:.3f} p90={p90_sub:.3f}".format(**s))
    print("KD rate      (kd/300s): p50={p50_kd:.3f} p75={p75_kd:.3f} p90={p90_kd:.3f}".format(**s))
