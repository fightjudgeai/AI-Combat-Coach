-- ============================================================================
-- 010_simulation_calibration.sql
-- Materialised view: one row per fight where both fighters have a computed
-- career FPS.  Used as the ground-truth dataset for fight simulation
-- calibration (win probability tables, finish-rate lookup, delta-bucket
-- accuracy measurement).
--
-- Target size: 2,000–3,000 rows once the ufc_data_pipeline finishes scoring.
--
-- Refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY simulation_calibration;
-- (The unique index on fight_id makes CONCURRENTLY safe.)
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS simulation_calibration AS
SELECT
    f.id                            AS fight_id,
    f.fight_date,
    f.weight_class,
    f.rounds_scheduled,
    f.method_normalized             AS actual_method,
    f.finish_round                  AS actual_finish_round,
    f.was_finish,
    f.went_to_decision,

    -- ── Fighter A ─────────────────────────────────────────────────────────
    uf_a.id                         AS fighter_a_id,
    uf_a.name                       AS fighter_a_name,
    f.fighter_a_fps,                                   -- per-fight score (outcome)
    uf_a.career_fps                 AS a_career_fps,   -- pre-fight predictor
    uf_a.career_fps_tier            AS a_career_fps_tier,
    uf_a.style_archetype            AS a_style,
    uf_a.finish_rate                AS a_finish_rate,
    uf_a.ko_rate                    AS a_ko_rate,
    uf_a.sub_rate                   AS a_sub_rate,
    uf_a.avg_offensive_efficiency   AS a_off_eff,
    uf_a.avg_defensive_response     AS a_def_resp,
    uf_a.avg_control_dictation      AS a_ctrl,
    uf_a.avg_finish_threat          AS a_fin_threat,
    uf_a.avg_cardio_pace            AS a_cardio,
    uf_a.avg_durability             AS a_durability,
    uf_a.avg_fight_iq               AS a_iq,
    uf_a.avg_dominance              AS a_dom,

    -- ── Fighter B ─────────────────────────────────────────────────────────
    uf_b.id                         AS fighter_b_id,
    uf_b.name                       AS fighter_b_name,
    f.fighter_b_fps,                                   -- per-fight score (outcome)
    uf_b.career_fps                 AS b_career_fps,   -- pre-fight predictor
    uf_b.career_fps_tier            AS b_career_fps_tier,
    uf_b.style_archetype            AS b_style,
    uf_b.finish_rate                AS b_finish_rate,
    uf_b.ko_rate                    AS b_ko_rate,
    uf_b.sub_rate                   AS b_sub_rate,
    uf_b.avg_offensive_efficiency   AS b_off_eff,
    uf_b.avg_defensive_response     AS b_def_resp,
    uf_b.avg_control_dictation      AS b_ctrl,
    uf_b.avg_finish_threat          AS b_fin_threat,
    uf_b.avg_cardio_pace            AS b_cardio,
    uf_b.avg_durability             AS b_durability,
    uf_b.avg_fight_iq               AS b_iq,
    uf_b.avg_dominance              AS b_dom,

    -- ── Outcome labels ────────────────────────────────────────────────────
    -- Per-fight FPS gap (actual result — what the model produced)
    f.fps_delta                     AS fight_fps_delta,
    -- Career FPS gap going INTO the fight (pre-fight predictor)
    (uf_a.career_fps - uf_b.career_fps) AS career_fps_delta,

    CASE WHEN f.winner_id = uf_a.id THEN 1 ELSE 0 END  AS fighter_a_won,
    CASE WHEN f.method_normalized IN ('ko','tko') THEN 1 ELSE 0 END  AS was_ko,
    CASE WHEN f.method_normalized = 'sub'         THEN 1 ELSE 0 END  AS was_sub,
    CASE WHEN f.method_normalized IN ('ud','sd','md') THEN 1 ELSE 0 END AS was_decision,

    -- ── Delta bucket (keyed on career FPS spread — the pre-fight predictor)
    -- Use this for win-probability lookup tables and calibration queries.
    CASE
        WHEN (uf_a.career_fps - uf_b.career_fps) >=  20 THEN 'massive_favorite'
        WHEN (uf_a.career_fps - uf_b.career_fps) >=  10 THEN 'big_favorite'
        WHEN (uf_a.career_fps - uf_b.career_fps) >=   5 THEN 'moderate_favorite'
        WHEN (uf_a.career_fps - uf_b.career_fps) >=   0 THEN 'slight_favorite'
        WHEN (uf_a.career_fps - uf_b.career_fps) >=  -5 THEN 'slight_underdog'
        WHEN (uf_a.career_fps - uf_b.career_fps) >= -10 THEN 'moderate_underdog'
        WHEN (uf_a.career_fps - uf_b.career_fps) >= -20 THEN 'big_underdog'
        ELSE 'massive_underdog'
    END AS delta_bucket

FROM ufc_fights f
JOIN ufc_fighters uf_a ON f.fighter_a_id = uf_a.id
JOIN ufc_fighters uf_b ON f.fighter_b_id = uf_b.id
WHERE uf_a.meets_5_fight_threshold = TRUE
  AND uf_b.meets_5_fight_threshold = TRUE
  AND uf_a.career_fps  IS NOT NULL
  AND uf_b.career_fps  IS NOT NULL
  AND f.fighter_a_fps  IS NOT NULL
  AND f.fighter_b_fps  IS NOT NULL;

-- ── Indexes ───────────────────────────────────────────────────────────────────
-- fight_id is unique per row — required for REFRESH CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS uix_sim_cal_fight
    ON simulation_calibration (fight_id);

-- Win-probability calibration queries filter heavily on delta_bucket + weight_class
CREATE INDEX IF NOT EXISTS idx_sim_cal_delta_bucket
    ON simulation_calibration (delta_bucket);

CREATE INDEX IF NOT EXISTS idx_sim_cal_weight_class
    ON simulation_calibration (weight_class);

-- Time-series slicing (evaluate model accuracy over calendar periods)
CREATE INDEX IF NOT EXISTS idx_sim_cal_fight_date
    ON simulation_calibration (fight_date DESC);

-- Style-matchup queries
CREATE INDEX IF NOT EXISTS idx_sim_cal_styles
    ON simulation_calibration (a_style, b_style);

-- ── Row count check ───────────────────────────────────────────────────────────
SELECT COUNT(*) AS calibration_rows FROM simulation_calibration;
-- Target: 2,000–3,000 once ufc_data_pipeline finishes scoring
