"""
scripts/scouting/build_efps_model.py

Train an Estimated FPS (EFPS) regression model that predicts a fighter's
career FPS from record-derivable stats.  Once trained, this model can assign
a meaningful FPS estimate to any of the ~32K regional fighters in the DB who
have never had a round scored by the engine.

Architecture
============
  Input features = stats derivable from fight records + aggregate round data
                   (the same columns available for regional/Tapology fighters)
  Target         = career_fps column in ufc_fighters
                   (computed by the scoring engine from real rounds)

Known data-quality caveat
=========================
  ufc_round_stats.SL / SA / TD_F / TD_A / KD_F / KD_A are all 0 for real
  fights because _parse_round_table() used wrong selectors (session summary).
  The model therefore falls back to outcome-based features only.  Feature
  importances are reported at the end — zero-variance features are
  automatically ignored by GradientBoostingRegressor.

Usage
=====
  python -m scripts.scouting.build_efps_model
  python scripts/scouting/build_efps_model.py

Output
======
  ./models/efps_model_v1.pkl        — joblib Pipeline
  ./models/efps_feature_report.json — feature importances + metrics
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# ---------------------------------------------------------------------------
# Supabase Management API helper
# ---------------------------------------------------------------------------

SUPABASE_PROJECT_REF = "cxvtipiogkgpqiksakld"
SUPABASE_API_BASE    = "https://api.supabase.com/v1"


class _CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wt.DWORD), ("Type", wt.DWORD), ("TargetName", wt.LPWSTR),
        ("Comment", wt.LPWSTR), ("LastWritten", wt.FILETIME),
        ("CredentialBlobSize", wt.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wt.DWORD), ("AttributeCount", wt.DWORD),
        ("Attributes", ctypes.c_void_p), ("TargetAlias", wt.LPWSTR),
        ("UserName", wt.LPWSTR),
    ]


def _read_windows_credential(target: str) -> str | None:
    try:
        ptr = ctypes.c_void_p()
        ok = ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(ptr))
        if not ok:
            return None
        cred = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
        blob = bytes(cred.CredentialBlob[i] for i in range(cred.CredentialBlobSize))
        ctypes.windll.advapi32.CredFree(ptr)
        return blob.decode("utf-8", errors="replace")
    except Exception:
        return None


def _get_token() -> str:
    token = _read_windows_credential("Supabase CLI:supabase")
    if token:
        return token
    token = os.environ.get("SUPABASE_ACCESS_TOKEN")
    if token:
        return token
    raise SystemExit("No Supabase token — run `supabase login` or set SUPABASE_ACCESS_TOKEN.")


def _mgmt_query(sql: str, token: str) -> list[dict]:
    try:
        import httpx
    except ImportError:
        raise SystemExit("httpx not installed — pip install httpx")
    url  = f"{SUPABASE_API_BASE}/projects/{SUPABASE_PROJECT_REF}/database/query"
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = httpx.post(url, headers=hdrs, json={"query": sql}, timeout=60)
    if resp.status_code not in (200, 201):
        raise SystemExit(f"Management API {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    return data if isinstance(data, list) else data.get("rows", [])


# ---------------------------------------------------------------------------
# Training dataset builder
# ---------------------------------------------------------------------------

_TRAINING_SQL = """
WITH fighter_fight_fps AS (
    -- Per-fighter average fight FPS (both sides)
    SELECT fighter_id, AVG(fps) AS avg_fight_fps
    FROM (
        SELECT fighter_a_id AS fighter_id, fighter_a_fps AS fps
          FROM ufc_fights
         WHERE fighter_a_fps IS NOT NULL
        UNION ALL
        SELECT fighter_b_id, fighter_b_fps
          FROM ufc_fights
         WHERE fighter_b_fps IS NOT NULL
    ) x
    GROUP BY fighter_id
),
fighter_round_stats AS (
    -- Aggregate round stats per fighter.
    -- NOTE: SL/SA/TD_F etc. are currently all 0 due to broken scraper
    -- selectors.  These averages will be 0 until the scraper is fixed and
    -- re-run.  Retained here so the model automatically gains signal once
    -- round stats are repopulated.
    SELECT
        fighter_id,
        AVG(sl)      AS avg_sl,
        AVG(sa)      AS avg_sa,
        AVG(kd_f)    AS avg_kd_f,
        AVG(kd_a)    AS avg_kd_a,
        AVG(td_f)    AS avg_td_f,
        AVG(ta_f)    AS avg_ta_f,
        AVG(rps)     AS avg_rps,
        STDDEV(rps)  AS rps_consistency,
        -- Derived accuracy rates — guarded against divide-by-zero
        AVG(CASE WHEN sa  > 0 THEN sl::float  / sa  ELSE NULL END) AS avg_strike_acc,
        AVG(CASE WHEN ta_f > 0 THEN td_f::float / ta_f ELSE NULL END) AS avg_td_acc,
        AVG(CASE WHEN sa  > 0 THEN kd_f * 100.0 / sa ELSE NULL END) AS kd_per_100_strikes
    FROM ufc_round_stats
    GROUP BY fighter_id
)
SELECT
    uf.id                                                       AS fighter_id,
    uf.name,
    uf.career_fps                                               AS target_fps,
    uf.weight_class,
    uf.ufc_wins,
    uf.ufc_losses,
    uf.ufc_appearances,
    COALESCE(uf.finish_rate, 0)                                 AS finish_rate,
    COALESCE(uf.ko_rate,     0)                                 AS ko_rate,
    COALESCE(uf.sub_rate,    0)                                 AS sub_rate,

    -- Win rate (derived, safe from divide-by-zero)
    CASE WHEN uf.ufc_appearances > 0
         THEN uf.ufc_wins::float / uf.ufc_appearances
         ELSE 0
    END                                                         AS win_rate,

    -- Average per-fight FPS (outcome-based signal)
    COALESCE(fff.avg_fight_fps, uf.career_fps)                  AS avg_fight_fps,

    -- Round stat aggregates (currently 0 due to scraper issue; retained for future)
    COALESCE(frs.avg_sl,            0)                          AS avg_sl,
    COALESCE(frs.avg_sa,            0)                          AS avg_sa,
    COALESCE(frs.avg_kd_f,          0)                          AS avg_kd_f,
    COALESCE(frs.avg_kd_a,          0)                          AS avg_kd_a,
    COALESCE(frs.avg_td_f,          0)                          AS avg_td_f,
    COALESCE(frs.avg_ta_f,          0)                          AS avg_ta_f,
    COALESCE(frs.avg_rps,           0)                          AS avg_rps,
    COALESCE(frs.rps_consistency,   0)                          AS rps_consistency,
    COALESCE(frs.avg_strike_acc,    0)                          AS avg_strike_acc,
    COALESCE(frs.avg_td_acc,        0)                          AS avg_td_acc,
    COALESCE(frs.kd_per_100_strikes, 0)                         AS kd_per_100_strikes

FROM ufc_fighters uf
LEFT JOIN fighter_fight_fps fff ON fff.fighter_id = uf.id
LEFT JOIN fighter_round_stats frs ON frs.fighter_id = uf.id
WHERE uf.meets_5_fight_threshold = TRUE
  AND uf.career_fps IS NOT NULL
"""


def build_training_dataset(token: str) -> pd.DataFrame:
    """
    Query Supabase for all eligible UFC fighters and return a clean DataFrame.

    Standalone (synchronous) version — uses the Management API directly
    rather than asyncpg so this script can be run without a running server.
    """
    print("Fetching training data from Supabase …")
    rows = _mgmt_query(_TRAINING_SQL, token)
    print(f"  Raw rows returned: {len(rows)}")

    if not rows:
        raise SystemExit(
            "No training rows — run the UFC data pipeline first.\n"
            "Need: meets_5_fight_threshold = TRUE and career_fps IS NOT NULL."
        )

    df = pd.DataFrame(rows)

    # Coerce numeric columns (Supabase Management API returns strings for some)
    numeric_cols = [c for c in df.columns if c not in ("fighter_id", "name", "weight_class")]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

    print(f"  Numeric fighters in training set: {len(df)}")
    print(f"  Target (career_fps) — mean={df['target_fps'].mean():.1f}  "
          f"std={df['target_fps'].std():.1f}  "
          f"min={df['target_fps'].min():.1f}  max={df['target_fps'].max():.1f}")
    return df


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

# Features in priority order (outcome-based first, round stats last).
# When round stats are populated post-scraper-fix the model will automatically
# use them; until then GBR assigns near-zero importance to constant-zero cols.
FEATURE_COLS: list[str] = [
    # Outcome-based (highest signal, available for any fighter)
    "win_rate",
    "finish_rate",
    "ko_rate",
    "sub_rate",
    "ufc_appearances",
    "avg_fight_fps",
    # Round stats (zero for now, but structurally correct for future)
    "avg_sl",
    "avg_sa",
    "avg_kd_f",
    "avg_kd_a",
    "avg_td_f",
    "avg_ta_f",
    "avg_rps",
    "rps_consistency",
    "avg_strike_acc",
    "avg_td_acc",
    "kd_per_100_strikes",
]


def train_efps_model(df: pd.DataFrame) -> tuple[Pipeline, dict]:
    """
    Train the EFPS regression model and return (pipeline, metrics_dict).

    Pipeline: SimpleImputer → StandardScaler → GradientBoostingRegressor
    The imputer handles any NaN that survived the COALESCE in SQL.
    """
    df_clean = df[FEATURE_COLS + ["target_fps", "name"]].copy()

    # Report features with zero variance before dropping rows
    zero_var_cols = [c for c in FEATURE_COLS if df_clean[c].std() == 0]
    if zero_var_cols:
        print(f"\n  [WARN] Zero-variance features (will contribute nothing):\n"
              f"    {zero_var_cols}\n"
              f"  This is expected while ufc_round_stats are all 0.\n"
              f"  Re-run after fixing _parse_round_table() to unlock these features.")

    # Drop rows where the target is missing
    df_clean = df_clean.dropna(subset=["target_fps"])
    print(f"\nClean training rows: {len(df_clean)}")

    if len(df_clean) < 30:
        raise SystemExit(
            f"Only {len(df_clean)} training rows — need at least 30. "
            "Check that meets_5_fight_threshold = TRUE and career_fps IS NOT NULL."
        )

    X = df_clean[FEATURE_COLS]
    y = df_clean["target_fps"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42
    )

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
        ("gbr", GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.8,
            min_samples_leaf=5,
            random_state=42,
        )),
    ])

    print("Training gradient boosted regressor …")
    model.fit(X_train, y_train)

    # ── Evaluation ────────────────────────────────────────────────────────
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="r2")
    test_r2   = model.score(X_test, y_test)
    preds     = model.predict(X_test)
    test_mae  = float(np.mean(np.abs(preds - y_test)))
    test_rmse = float(np.sqrt(np.mean((preds - y_test) ** 2)))

    # ── Feature importances ───────────────────────────────────────────────
    gbr: GradientBoostingRegressor = model.named_steps["gbr"]
    importances = {
        col: round(float(imp), 4)
        for col, imp in sorted(
            zip(FEATURE_COLS, gbr.feature_importances_),
            key=lambda x: -x[1],
        )
    }

    metrics = {
        "cv_r2_mean":       round(float(cv_scores.mean()), 3),
        "cv_r2_std":        round(float(cv_scores.std()),  3),
        "test_r2":          round(test_r2,  3),
        "test_mae":         round(test_mae,  2),
        "test_rmse":        round(test_rmse, 2),
        "training_samples": int(len(X_train)),
        "test_samples":     int(len(X_test)),
        "feature_importances": importances,
        "zero_variance_features": zero_var_cols,
        "round_stats_populated": len(zero_var_cols) == 0,
    }

    print(f"\nEFPS Model Performance")
    print(f"  CV R² (5-fold):   {metrics['cv_r2_mean']:.3f} ± {metrics['cv_r2_std']:.3f}")
    print(f"  Test R²:          {metrics['test_r2']:.3f}")
    print(f"  Test MAE:         {metrics['test_mae']:.1f} FPS points")
    print(f"  Test RMSE:        {metrics['test_rmse']:.1f} FPS points")
    print(f"  Training samples: {metrics['training_samples']}")
    print(f"\nTop feature importances:")
    for feat, imp in list(importances.items())[:8]:
        bar = "█" * int(imp * 40)
        print(f"  {feat:<25} {imp:.4f}  {bar}")

    # ── Target diagnostics ────────────────────────────────────────────────
    print(f"\nTarget: R² > 0.75, MAE < 8 FPS points")
    r2_pass  = "PASS" if metrics["test_r2"]  > 0.75 else "BELOW TARGET"
    mae_pass = "PASS" if metrics["test_mae"] < 8.0  else "BELOW TARGET"
    print(f"  R²:  {r2_pass}   ({metrics['test_r2']:.3f})")
    print(f"  MAE: {mae_pass}  ({metrics['test_mae']:.1f})")
    if not metrics["round_stats_populated"]:
        print(
            "\n  NOTE: Round stat features are all zero (scraper issue).\n"
            "  The model runs on outcome-based features only.\n"
            "  Expected R² once round stats are fixed: > 0.85."
        )

    return model, metrics


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_model(model: Pipeline, metrics: dict, models_dir: str = "./models") -> None:
    os.makedirs(models_dir, exist_ok=True)
    model_path   = os.path.join(models_dir, "efps_model_v1.pkl")
    metrics_path = os.path.join(models_dir, "efps_feature_report.json")

    joblib.dump(model, model_path)
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    print(f"\nSaved model  → {model_path}")
    print(f"Saved report → {metrics_path}")


# ---------------------------------------------------------------------------
# Public API  (import from other scripts as needed)
# ---------------------------------------------------------------------------

def build_and_save_efps_model(models_dir: str = "./models") -> tuple[Pipeline, dict]:
    """
    Full pipeline: fetch data → train → save.  Call this from other scripts
    or run directly.
    """
    token = _get_token()
    df    = build_training_dataset(token)
    model, metrics = train_efps_model(df)
    save_model(model, metrics, models_dir)
    return model, metrics


# ---------------------------------------------------------------------------
# Standalone entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Resolve ./models relative to this script's location, not the CWD
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    models_dir  = os.path.join(script_dir, "..", "..", "models")
    build_and_save_efps_model(models_dir=models_dir)
