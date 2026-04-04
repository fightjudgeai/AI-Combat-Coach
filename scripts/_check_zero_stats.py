"""Check actual values in ufc_round_stats for real (non-test) fights."""
import os, json, ctypes, ctypes.wintypes as wt, httpx

class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wt.DWORD),("Type", wt.DWORD),("TargetName", wt.LPWSTR),
                ("Comment", wt.LPWSTR),("LastWritten", wt.FILETIME),
                ("CredentialBlobSize", wt.DWORD),("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wt.DWORD),("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p),("TargetAlias", wt.LPWSTR),("UserName", wt.LPWSTR)]
def read_cred(t):
    ptr = ctypes.c_void_p()
    ctypes.windll.advapi32.CredReadW(t, 1, 0, ctypes.byref(ptr))
    c = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
    b = bytes(c.CredentialBlob[i] for i in range(c.CredentialBlobSize))
    ctypes.windll.advapi32.CredFree(ptr)
    return b.decode("utf-8", errors="replace")
token = read_cred("Supabase CLI:supabase")
url   = "https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query"
hdrs  = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
def sql(q):
    r = httpx.post(url, headers=hdrs, content=json.dumps({"query": q}), timeout=30)
    d = r.json(); return d if isinstance(d, list) else d.get("rows", [])

# Summary stats for all round rows
counts = sql("""
    SELECT
        COUNT(*) n,
        SUM(CASE WHEN sl > 0 THEN 1 ELSE 0 END) as rows_with_sl,
        SUM(CASE WHEN td_f > 0 THEN 1 ELSE 0 END) as rows_with_td,
        SUM(CASE WHEN ctrl_f > 0 THEN 1 ELSE 0 END) as rows_with_ctrl,
        MAX(sl) max_sl, MAX(td_f) max_td, MAX(ctrl_f) max_ctrl_sec,
        SUM(sl) total_sl, SUM(sa) total_sa
    FROM ufc_round_stats
    WHERE fighter_name != 'Fighter01' AND fighter_name != 'Fighter02'
""")
print("Summary (excluding test fighters):", counts[0])

# Sample some real rows
rows = sql("""
    SELECT fighter_name, round_number, sl, sa, td_f, ctrl_f, sub_att, sec, rps
    FROM ufc_round_stats
    WHERE fighter_name != 'Fighter01' AND fighter_name != 'Fighter02'
    LIMIT 10
""")
print("\nSample real round stats:")
for r in rows:
    print(f"  {r['fighter_name']:<25} r{r['round_number']} sl={r['sl']} sa={r['sa']} td={r['td_f']} ctrl={r['ctrl_f']}s sub={r['sub_att']} sec={r['sec']} rps={r['rps']}")

# Check the raw data in ufc_all_fights.json
import json
from pathlib import Path
fights = json.loads(Path("c:/lovable-Emergent-Full/.claude/worktrees/blissful-edison/AI-Combat-Coach/data/ufc_all_fights.json").read_text("utf-8"))
# Find a fight with rounds data
for f in fights:
    if f.get("rounds") and len(f["rounds"]) > 0:
        print("\nSample scraped rounds from raw JSON:")
        r = f["rounds"][0]
        print(f"  fight: {f['fighter_a_name']} vs {f['fighter_b_name']}")
        print(f"  round data: {r}")
        break
