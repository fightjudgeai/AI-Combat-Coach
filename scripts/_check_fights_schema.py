"""Check ufc_fights schema and winner/method data."""
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
    print("API error:", d)
    return []

# Check schema
schema = sql("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'ufc_fights'
    ORDER BY ordinal_position
""")
print("ufc_fights columns:")
for c in schema:
    print(f"  {c['column_name']} - {c['data_type']}")

# Sample a row
print()
sample = sql("SELECT * FROM ufc_fights LIMIT 1")
if sample:
    row = sample[0]
    keys = list(row.keys())
    print("Sample row keys:", keys)
    for k, v in row.items():
        if v is not None:
            print(f"  {k}: {v}")

# Count winner / method
print()
counts = sql("""
    SELECT
        COUNT(*) AS total,
        COUNT(winner) AS winner_not_null,
        COUNT(method_normalized) AS method_not_null,
        COUNT(*) FILTER (WHERE is_finish IS TRUE) AS finishes
    FROM ufc_fights
""")
if counts:
    print("Counts:", counts[0])
