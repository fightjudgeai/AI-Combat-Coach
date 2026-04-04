"""Check ufc_all_fights.json winner/method coverage after recovery."""
import json
from pathlib import Path

fights = json.loads(
    Path("c:/lovable-Emergent-Full/.claude/worktrees/blissful-edison/AI-Combat-Coach/data/ufc_all_fights.json")
    .read_bytes().decode("utf-8", errors="replace")
)
winners = sum(1 for f in fights if f.get("winner"))
methods = sum(1 for f in fights if f.get("method"))
print(f"Total: {len(fights)}, with winner: {winners}, with method: {methods}")
# Check Adesanya fight
for f in fights:
    if "Adesanya" in str(f.get("fighter_a_name", "")):
        print(f"Adesanya fight: winner={f.get('winner')!r} method={f.get('method')!r}")
        break
# Sample 5 with winner set
with_winner = [f for f in fights if f.get("winner")][:5]
for f in with_winner:
    print(f"  {f.get('fighter_a_name')} vs {f.get('fighter_b_name')}: winner={f.get('winner')!r} method={f.get('method')!r}")
