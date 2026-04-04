import os, json, ctypes, ctypes.wintypes as wt, httpx

class _CREDENTIAL(ctypes.Structure):
    _fields_ = [('Flags',wt.DWORD),('Type',wt.DWORD),('TargetName',wt.LPWSTR),
                ('Comment',wt.LPWSTR),('LastWritten',wt.FILETIME),
                ('CredentialBlobSize',wt.DWORD),('CredentialBlob',ctypes.POINTER(ctypes.c_ubyte)),
                ('Persist',wt.DWORD),('AttributeCount',wt.DWORD),
                ('Attributes',ctypes.c_void_p),('TargetAlias',wt.LPWSTR),('UserName',wt.LPWSTR)]

def sql(q):
    ptr = ctypes.c_void_p()
    ctypes.windll.advapi32.CredReadW('Supabase CLI:supabase', 1, 0, ctypes.byref(ptr))
    c = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
    token = bytes(c.CredentialBlob[i] for i in range(c.CredentialBlobSize)).decode()
    ctypes.windll.advapi32.CredFree(ptr)
    r = httpx.post('https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query',
        headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'},
        content=json.dumps({'query':q}), timeout=30)
    d = r.json()
    return d if isinstance(d, list) else d.get('rows', [])

# Sample rows for grappling_control vs volume_striker  
rows = sql("""SELECT a_style, b_style, was_sub, was_ko, was_decision FROM simulation_calibration WHERE a_style IN ('grappling_control','volume_striker') AND b_style IN ('grappling_control','volume_striker') AND a_style != b_style LIMIT 10""")
print('Sample rows (grappling_control vs volume_striker):')
for r in rows:
    print(r)

# Count with sub breakdown
cnt = sql("""
SELECT
    SUM(CASE WHEN was_sub THEN 1 ELSE 0 END) sub_true,
    SUM(CASE WHEN was_ko THEN 1 ELSE 0 END) ko_true,
    SUM(CASE WHEN was_decision THEN 1 ELSE 0 END) dec_true,
    SUM(CASE WHEN NOT was_ko AND NOT was_sub AND NOT was_decision THEN 1 ELSE 0 END) null_method,
    COUNT(*) total
FROM simulation_calibration
WHERE a_style IN ('grappling_control','volume_striker')
  AND b_style IN ('grappling_control','volume_striker')
  AND a_style != b_style
""")
print('\ngrappling_control vs volume_striker counts:')
print(cnt[0] if cnt else 'no rows')
