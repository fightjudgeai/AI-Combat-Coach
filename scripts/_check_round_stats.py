"""Check ufc_round_stats schema."""
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

cols = sql("""SELECT column_name, data_type
              FROM information_schema.columns
              WHERE table_name = 'ufc_round_stats'
              ORDER BY ordinal_position""")
print("ufc_round_stats columns:")
for c in cols:
    print(f"  {c['column_name']} - {c['data_type']}")

print()
sample = sql("SELECT * FROM ufc_round_stats LIMIT 1")
if sample:
    for k, v in sample[0].items():
        print(f"  {k}: {v}")
