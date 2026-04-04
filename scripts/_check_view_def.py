"""Check simulation_calibration view definition and ufc_fighters style column."""
import os, json, ctypes, ctypes.wintypes as wt, httpx

class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wt.DWORD),("Type", wt.DWORD),("TargetName", wt.LPWSTR),
                ("Comment", wt.LPWSTR),("LastWritten", wt.FILETIME),
                ("CredentialBlobSize", wt.DWORD),("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wt.DWORD),("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p),("TargetAlias", wt.LPWSTR),("UserName", wt.LPWSTR)]
def rc(t):
    ptr = ctypes.c_void_p()
    ctypes.windll.advapi32.CredReadW(t, 1, 0, ctypes.byref(ptr))
    c = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
    b = bytes(c.CredentialBlob[i] for i in range(c.CredentialBlobSize))
    ctypes.windll.advapi32.CredFree(ptr)
    return b.decode("utf-8", errors="replace")

token = rc("Supabase CLI:supabase")
url   = "https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query"
hdrs  = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def sql(q, t=30):
    r = httpx.post(url, headers=hdrs, content=json.dumps({"query": q}), timeout=t)
    d = r.json()
    return d if isinstance(d, list) else d.get("rows", [])

# Mat view definition
rows = sql("SELECT definition FROM pg_matviews WHERE matviewname = 'simulation_calibration'")
if rows:
    print("=== simulation_calibration DEFINITION ===")
    print(rows[0]["definition"])
else:
    rows = sql("SELECT definition FROM pg_views WHERE viewname = 'simulation_calibration'")
    if rows:
        print(rows[0]["definition"])

print()
# ufc_fighters columns
cols = sql("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'ufc_fighters'
    ORDER BY ordinal_position
""")
print("ufc_fighters columns:")
for c in cols:
    print(f"  {c['column_name']} - {c['data_type']}")

print()
# Check if ufc_round_stats has any data
cnt_stats = sql("SELECT COUNT(*) n FROM ufc_round_stats")
print(f"ufc_round_stats rows: {cnt_stats[0]['n'] if cnt_stats else 'error'}")
cnt_stats2 = sql("SELECT COUNT(*) n FROM ufc_round_stats WHERE fighter_id IS NOT NULL")
print(f"ufc_round_stats with fighter_id: {cnt_stats2[0]['n'] if cnt_stats2 else 'error'}")
