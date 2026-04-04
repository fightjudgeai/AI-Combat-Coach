"""Check real fight winner/method data in ufc_fights."""
import sys, os, json, ctypes, ctypes.wintypes as wt, httpx

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
url = "https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query"
hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def sql(q, timeout=30):
    r = httpx.post(url, headers=hdrs, content=json.dumps({"query": q}), timeout=timeout)
    d = r.json()
    if isinstance(d, list):
        return d
    rows = d.get("rows")
    if rows is not None:
        return rows
    print("API error:", json.dumps(d)[:300])
    return []

# Count winner_id / method_normalized for real UFC fights (not test)
counts = sql("""
    SELECT
        COUNT(*) AS total,
        COUNT(winner_id) AS winner_id_set,
        COUNT(winner_name) AS winner_name_set,
        COUNT(method_normalized) AS method_norm_set,
        COUNT(*) FILTER (WHERE was_finish IS TRUE) AS was_finish_true,
        COUNT(*) FILTER (WHERE went_to_decision IS TRUE) AS decisions
    FROM ufc_fights
    WHERE ufcstats_fight_url NOT LIKE '%test%'
""")
print("ufc_fights real data counts:", counts[0] if counts else "error")

print()
# Show sample real fights with winner data
sample = sql("""
    SELECT fighter_a_name, fighter_b_name, winner_id, winner_name,
           method_normalized, was_finish, went_to_decision
    FROM ufc_fights
    WHERE ufcstats_fight_url NOT LIKE '%test%'
      AND winner_id IS NOT NULL
    LIMIT 5
""")
print("Fights with winner_id set:")
for r in sample:
    print(" ", r)

print()
# Show sample real fights WITHOUT winner data
no_winner = sql("""
    SELECT fighter_a_name, fighter_b_name, winner_id, winner_name,
           method_normalized, was_finish, went_to_decision
    FROM ufc_fights
    WHERE ufcstats_fight_url NOT LIKE '%test%'
      AND winner_id IS NULL
    LIMIT 5
""")
print("Fights WITHOUT winner_id:")
for r in no_winner:
    print(" ", r)

# Check method distribution
print()
methods = sql("""
    SELECT method_normalized, COUNT(*) n
    FROM ufc_fights
    WHERE ufcstats_fight_url NOT LIKE '%test%'
    GROUP BY method_normalized
    ORDER BY n DESC
""")
print("Method distribution (real fights):")
for r in methods:
    print(f"  {r['method_normalized']!r}: {r['n']}")
