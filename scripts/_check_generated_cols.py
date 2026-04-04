"""Check which columns in ufc_fights are generated."""
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
def sql(q):
    r = httpx.post(url, headers=hdrs, content=json.dumps({"query": q}), timeout=30)
    d = r.json(); return d if isinstance(d, list) else d.get("rows", [])

rows = sql("""
    SELECT column_name, is_generated, generation_expression, column_default
    FROM information_schema.columns
    WHERE table_name = 'ufc_fights'
    AND (is_generated != 'NEVER' OR column_default IS NOT NULL)
    ORDER BY ordinal_position
""")
print("Generated/default columns in ufc_fights:")
for r in rows:
    print(f"  {r['column_name']}: is_generated={r['is_generated']} expr={r['generation_expression']!r} default={r['column_default']!r}")
