"""
build_style_modifiers.py

Add volume_striker to the style taxonomy (distinguishes from grappling_control
by having near-zero sub rate), then answers empirically:

  "Does a grappling_control vs. volume_striker matchup shift KO probability
   down and sub probability up compared to the baseline?"

Output:
  - Per-style-pairing breakdown: KO%, sub%, decision% vs. baseline
  - Style modifier table saved to system_config['style_modifiers']
"""
import os, json, ctypes, ctypes.wintypes as wt, httpx
from collections import defaultdict

class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wt.DWORD),("Type", wt.DWORD),("TargetName", wt.LPWSTR),
                ("Comment", wt.LPWSTR),("LastWritten", wt.FILETIME),
                ("CredentialBlobSize", wt.DWORD),("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wt.DWORD),("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p),("TargetAlias", wt.LPWSTR),("UserName", wt.LPWSTR)]

def _cred(t):
    ptr = ctypes.c_void_p()
    if ctypes.windll.advapi32.CredReadW(t, 1, 0, ctypes.byref(ptr)):
        c = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
        b = bytes(c.CredentialBlob[i] for i in range(c.CredentialBlobSize))
        ctypes.windll.advapi32.CredFree(ptr)
        return b.decode("utf-8", errors="replace")

token = _cred("Supabase CLI:supabase") or os.environ.get("SUPABASE_ACCESS_TOKEN")
URL   = "https://api.supabase.com/v1/projects/cxvtipiogkgpqiksakld/database/query"
HDR   = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def sql(q, timeout=90):
    r = httpx.post(URL, headers=HDR, content=json.dumps({"query": q}), timeout=timeout)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"SQL {r.status_code}: {r.text[:500]}")
    d = r.json()
    return d if isinstance(d, list) else d.get("rows", [])


# ══════════════════════════════════════════════════════════════════════════
# STEP 1: Reclassify fighters — add volume_striker
# ══════════════════════════════════════════════════════════════════════════
#
# Taxonomy (from highest finish-rate down):
#   pressure_finisher  — finish_rate >= P75, ko_rate > sub_rate   (KO-heavy)
#   submission_threat  — finish_rate >= P75, sub_rate >= ko_rate  (sub-heavy)
#   volume_striker     — finish_rate < P50, sub_rate <= 0.15     (decisions;
#                        no grappling finishing threat)
#   grappling_control  — finish_rate < P50, sub_rate >  0.15     (sub threat
#                        mixed into low-finish record)
#   balanced           — everything else (P50-P75 finish rate)
#
# Key distinction: volume_striker vs. grappling_control is purely sub_rate:
#   - grappler knows how to finish from bottom/top → sub_rate > 0.15
#   - striker goes to decision without sub threat → sub_rate <= 0.15
# ══════════════════════════════════════════════════════════════════════════

print("=" * 60)
print("STEP 1 — Add volume_striker to taxonomy")
print("=" * 60)

# Get P50 of finish_rate for splitting "high finisher" from "low finisher"
pcts = sql("""
    SELECT
        percentile_cont(0.50) WITHIN GROUP (ORDER BY finish_rate) p50,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY finish_rate) p75
    FROM ufc_fighters
    WHERE finish_rate IS NOT NULL
""")
p50 = float(pcts[0]["p50"])
p75 = float(pcts[0]["p75"])
print(f"finish_rate percentiles: p50={p50:.3f}  p75={p75:.3f}")

reclassified = sql(f"""
UPDATE ufc_fighters
SET style_archetype = CASE
    -- High-finish bracket (>= p75)
    WHEN finish_rate >= {p75}
         AND COALESCE(ko_rate, 0) >= COALESCE(sub_rate, 0)
        THEN 'pressure_finisher'
    WHEN finish_rate >= {p75}
        THEN 'submission_threat'
    -- Low-finish bracket (< p50)
    WHEN finish_rate < {p50}
         AND COALESCE(sub_rate, 0) <= 0.15
        THEN 'volume_striker'
    WHEN finish_rate < {p50}
        THEN 'grappling_control'
    -- Middle (p50–p75) → balanced
    ELSE 'balanced'
END
WHERE finish_rate IS NOT NULL
RETURNING id, style_archetype
""", timeout=60)

dist: dict[str,int] = {}
for r in reclassified:
    dist[r["style_archetype"]] = dist.get(r["style_archetype"], 0) + 1
print("Fighter style distribution after reclassification:")
for s, n in sorted(dist.items(), key=lambda x: -x[1]):
    print(f"  {s:<25} {n:>4}  ({n/len(reclassified)*100:.1f}%)")


# ══════════════════════════════════════════════════════════════════════════
# STEP 2: Refresh simulation_calibration
# ══════════════════════════════════════════════════════════════════════════
print("\nRefreshing simulation_calibration ...")
sql("REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_calibration", timeout=60)

style_check = sql("""
    SELECT a_style, COUNT(*) n
    FROM simulation_calibration
    WHERE a_style IS NOT NULL
    GROUP BY a_style ORDER BY n DESC
""")
print("a_style in sim_calibration:")
for r in style_check:
    print(f"  {r['a_style']:<25} {r['n']:>4}")


# ══════════════════════════════════════════════════════════════════════════
# STEP 3: Build style modifiers  (the core empirical question)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 3 — Build style modifiers from sim_calibration")
print("=" * 60)

rows = sql("""
    SELECT
        a_style,
        b_style,
        was_ko,
        was_sub,
        was_decision,
        fighter_a_won
    FROM simulation_calibration
    WHERE a_style IS NOT NULL AND b_style IS NOT NULL
""", timeout=60)
print(f"Total rows with both styles: {len(rows)}")

# ── Baseline across ALL fights ────────────────────────────────────────────
N = len(rows)
if N == 0:
    print("No data!")
    raise SystemExit(1)

baseline_ko  = sum(int(r["was_ko"])       for r in rows) / N
baseline_sub = sum(int(r["was_sub"])      for r in rows) / N
baseline_dec = sum(int(r["was_decision"]) for r in rows) / N

print(f"\nBASELINE (n={N}):")
print(f"  KO/TKO: {baseline_ko:.1%}  |  Sub: {baseline_sub:.1%}  |  Decision: {baseline_dec:.1%}")

# ── Per-pairing breakdown ─────────────────────────────────────────────────
by_pair: dict[tuple[str,str], list[dict]] = defaultdict(list)
for r in rows:
    pair = tuple(sorted([r["a_style"], r["b_style"]]))  # order-insensitive
    by_pair[pair].append(r)

MIN_N = 15  # minimum fights per pairing to report

print(f"\n{'MATCHUP':<50} {'N':>5} {'KO%':>6} {'SUB%':>6} {'DEC%':>6}  {'KO_diff':>7}  {'SUB_diff':>7}")
print("-" * 95)

style_modifiers: dict[str, dict] = {}
gvs_rows = None  # will hold grappling_control vs volume_striker

STYLES = ["grappling_control", "volume_striker", "submission_threat", "pressure_finisher", "balanced"]

# Print with a specific order (grappling_control pairs first)
all_pairs = sorted(by_pair.items(), key=lambda x: (
    0 if "grappling_control" in x[0] else 1,
    0 if "volume_striker"    in x[0] else 1,
    x[0]
))

for pair, fights in all_pairs:
    n = len(fights)
    if n < MIN_N:
        continue

    ko  = sum(int(f["was_ko"])       for f in fights) / n
    sub = sum(int(f["was_sub"])      for f in fights) / n
    dec = sum(int(f["was_decision"]) for f in fights) / n

    ko_diff  = ko  - baseline_ko
    sub_diff = sub - baseline_sub

    label = f"{pair[0]}  vs  {pair[1]}"
    ko_flag  = " <<<" if abs(ko_diff)  > 0.05 else ""
    sub_flag = " <<<" if abs(sub_diff) > 0.03 else ""

    print(f"{label:<50} {n:>5}  {ko:.1%}  {sub:.1%}  {dec:.1%}   "
          f"{ko_diff:+.1%}{ko_flag:5}  {sub_diff:+.1%}{sub_flag}")

    key = f"{pair[0]}_vs_{pair[1]}"
    style_modifiers[key] = {
        "sample_size":   n,
        "ko_rate":       round(ko,  3),
        "sub_rate":      round(sub, 3),
        "decision_rate": round(dec, 3),
        "ko_modifier":   round(ko  - baseline_ko,  3),
        "sub_modifier":  round(sub - baseline_sub, 3),
        "dec_modifier":  round(dec - baseline_dec, 3),
    }

    if set(pair) == {"grappling_control", "volume_striker"}:
        gvs_rows = fights


# ══════════════════════════════════════════════════════════════════════════
# STEP 4: Summary answer to the user's question
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ANSWER: grappling_control vs. volume_striker")
print("=" * 60)

if gvs_rows is None or len(gvs_rows) < MIN_N:
    n_gvs = len(gvs_rows) if gvs_rows else 0
    print(f"  Insufficient data for this pairing (n={n_gvs}, need {MIN_N})")
    print(f"  Current volume_striker count in sim_calibration: {dist.get('volume_striker','?')}")
    # Show grappling_control vs. balanced as a proxy
    proxy = by_pair.get(tuple(sorted(["grappling_control", "balanced"])), [])
    if len(proxy) >= MIN_N:
        n = len(proxy)
        ko  = sum(int(f["was_ko"]) for f in proxy)  / n
        sub = sum(int(f["was_sub"]) for f in proxy) / n
        dec = sum(int(f["was_decision"]) for f in proxy) / n
        print(f"\n  PROXY: grappling_control vs. balanced (n={n}):")
        print(f"    KO/TKO: {ko:.1%} (baseline {baseline_ko:.1%}, diff {ko-baseline_ko:+.1%})")
        print(f"    Sub:    {sub:.1%} (baseline {baseline_sub:.1%}, diff {sub-baseline_sub:+.1%})")
        print(f"    Dec:    {dec:.1%} (baseline {baseline_dec:.1%}, diff {dec-baseline_dec:+.1%})")
else:
    n = len(gvs_rows)
    ko  = sum(int(f["was_ko"]) for f in gvs_rows)  / n
    sub = sum(int(f["was_sub"]) for f in gvs_rows) / n
    dec = sum(int(f["was_decision"]) for f in gvs_rows) / n
    ko_diff  = ko  - baseline_ko
    sub_diff = sub - baseline_sub
    dec_diff = dec - baseline_dec
    print(f"  Sample: n={n} fights")
    print(f"  KO/TKO: {ko:.1%} vs baseline {baseline_ko:.1%}  =>  {ko_diff:+.1%}")
    print(f"  Sub:    {sub:.1%} vs baseline {baseline_sub:.1%}  =>  {sub_diff:+.1%}")
    print(f"  Dec:    {dec:.1%} vs baseline {baseline_dec:.1%}  =>  {dec_diff:+.1%}")
    print()
    if ko_diff < -0.02:
        print("  YES — KO probability is DEPRESSED in this matchup.")
    elif ko_diff > 0.02:
        print("  UNEXPECTED — KO probability is ELEVATED in this matchup.")
    else:
        print("  KO probability is near baseline for this matchup.")
    if sub_diff > 0.02:
        print("  YES — Sub probability is ELEVATED in this matchup.")
    elif sub_diff < -0.02:
        print("  UNEXPECTED — Sub probability is DEPRESSED in this matchup.")
    else:
        print("  Sub probability is near baseline for this matchup.")


# ══════════════════════════════════════════════════════════════════════════
# STEP 5: Persist style_modifiers to system_config
# ══════════════════════════════════════════════════════════════════════════
payload = json.dumps({
    "baseline": {
        "ko_rate":       round(baseline_ko,  3),
        "sub_rate":      round(baseline_sub, 3),
        "decision_rate": round(baseline_dec, 3),
        "sample_size":   N,
    },
    "pairings": style_modifiers,
}).replace("'","''")

sql(f"""
    INSERT INTO system_config (key, value, updated_at)
    VALUES ('style_modifiers', '{payload}'::jsonb, NOW())
    ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
""")
print(f"\n[SAVED] style_modifiers -> system_config  ({len(style_modifiers)} pairings)")
