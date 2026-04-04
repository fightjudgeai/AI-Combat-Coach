"""Quick DB validation — checks vision_jobs counts and fight_event_summary strike data."""
import httpx

BASE = "https://cxvtipiogkgpqiksakld.supabase.co/rest/v1"
KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN4dnRpcGlvZ2tncHFpa3Nha2xkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDc0ODAzNywiZXhwIjoyMDkwMzI0MDM3fQ.4VR7AB701DMRD-g8KFntVlCucr9GQITqYDXddqWHFrk"
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

# vision_jobs counts
from collections import Counter
jobs = httpx.get(f"{BASE}/vision_jobs?select=status", headers=H).json()
counts = Counter(r["status"] for r in jobs)
print("vision_jobs:", dict(counts))

# Strike count validation — top 5 fighters by punches
rows = httpx.get(
    f"{BASE}/fight_event_summary"
    "?select=fighter_id,punches_attempted,punches_landed,kicks_attempted"
    "&order=punches_attempted.desc&limit=5",
    headers=H
).json()
print("\nTop 5 by punches_attempted:")
for r in rows:
    fid = str(r.get("fighter_id", ""))[:8]
    print(f"  {fid}... punches={r['punches_attempted']} "
          f"landed={r['punches_landed']} kicks={r['kicks_attempted']}")

# Migration 007 column check
col_check = httpx.get(
    f"{BASE}/fight_event_summary"
    "?select=kicks_missed_head,kicks_missed_body,kicks_missed_leg,"
    "body_part_frames,kinematic_features,spatial_coverage&limit=1",
    headers=H
)
print("\nMigration 007 columns:", "OK" if col_check.status_code == 200 else col_check.text[:200])
