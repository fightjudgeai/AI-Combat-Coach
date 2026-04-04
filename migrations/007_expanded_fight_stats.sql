-- ============================================================================
-- 007_expanded_fight_stats.sql
-- Adds:
--   • Missed-kick zone breakdown (head / body / leg)
--   • body_part_frames   JSONB — per-part visibility frame counts
--   • kinematic_features JSONB — per-part velocity stats (ML features)
--   • spatial_coverage   JSONB — fighter ring coverage (cx/cy range)
-- Also updates the career-totals view to include the new kick columns.
-- Apply in Supabase SQL editor.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- A. New columns on fight_event_summary
-- ---------------------------------------------------------------------------

ALTER TABLE fight_event_summary
    ADD COLUMN IF NOT EXISTS kicks_missed_head    INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS kicks_missed_body    INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS kicks_missed_leg     INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS body_part_frames     JSONB   NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS kinematic_features   JSONB   NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS spatial_coverage     JSONB   NOT NULL DEFAULT '{}'::jsonb;

-- ---------------------------------------------------------------------------
-- B. Update career totals view to include missed-kick zone breakdown
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW fighter_event_career_totals AS
SELECT
    fighter_id,
    COUNT(DISTINCT job_id)                                              AS fights_analyzed,
    SUM(punches_attempted)                                              AS career_punches_attempted,
    SUM(punches_landed)                                                 AS career_punches_landed,
    SUM(jabs_attempted)                                                 AS career_jabs_attempted,
    SUM(jabs_landed)                                                    AS career_jabs_landed,
    SUM(crosses_attempted)                                              AS career_crosses_attempted,
    SUM(crosses_landed)                                                 AS career_crosses_landed,
    SUM(hooks_attempted)                                                AS career_hooks_attempted,
    SUM(hooks_landed)                                                   AS career_hooks_landed,
    SUM(uppercuts_attempted)                                            AS career_uppercuts_attempted,
    SUM(uppercuts_landed)                                               AS career_uppercuts_landed,
    SUM(kicks_attempted)                                                AS career_kicks_attempted,
    SUM(kicks_landed_head + kicks_landed_body + kicks_landed_leg)       AS career_kicks_landed,
    SUM(kicks_missed)                                                   AS career_kicks_missed,
    SUM(kicks_missed_head)                                              AS career_kicks_missed_head,
    SUM(kicks_missed_body)                                              AS career_kicks_missed_body,
    SUM(kicks_missed_leg)                                               AS career_kicks_missed_leg,
    SUM(elbow_strikes_attempted)                                        AS career_elbows_attempted,
    SUM(elbows_landed)                                                  AS career_elbows_landed,
    SUM(elbows_missed)                                                  AS career_elbows_missed,
    SUM(knee_strikes_attempted)                                         AS career_knees_attempted,
    SUM(knees_landed)                                                   AS career_knees_landed,
    SUM(knees_missed)                                                   AS career_knees_missed,
    SUM(ground_strikes_attempted)                                       AS career_ground_strikes_attempted,
    SUM(ground_strikes_landed)                                          AS career_ground_strikes_landed,
    SUM(knockdowns_scored)                                              AS career_knockdowns,
    SUM(ko_scored)                                                      AS career_ko,
    SUM(takedowns_landed)                                               AS career_takedowns_landed,
    SUM(takedowns_stuffed)                                              AS career_takedowns_stuffed,
    SUM(submission_attempts)                                            AS career_sub_attempts,
    SUM(submissions_completed)                                          AS career_submissions,
    SUM(sweeps)                                                         AS career_sweeps,
    SUM(reversals)                                                      AS career_reversals,
    AVG(strike_accuracy)                                                AS avg_strike_accuracy,
    AVG(pressure_score)                                                 AS avg_pressure_score,
    AVG(aggression_score)                                               AS avg_aggression_score,
    SUM(time_in_clinch)                                                 AS career_time_in_clinch,
    SUM(time_in_half_guard)                                             AS career_time_in_half_guard,
    SUM(time_in_full_guard)                                             AS career_time_in_full_guard,
    SUM(time_in_side_control)                                           AS career_time_in_side_control,
    SUM(time_in_back_control)                                           AS career_time_in_back_control,
    SUM(cage_control_sequences)                                         AS career_cage_control_sequences
FROM fight_event_summary
WHERE fighter_id IS NOT NULL
GROUP BY fighter_id;

-- ---------------------------------------------------------------------------
-- C. Helper view: body part visibility averages per fighter
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW fighter_body_part_visibility AS
SELECT
    fighter_id,
    COUNT(DISTINCT job_id)                                              AS fights_analyzed,
    -- Average visibility % for key strike weapons
    ROUND(AVG((body_part_frames->'glove_l'->>'visibility_pct')::numeric), 1)
                                                                        AS avg_glove_l_pct,
    ROUND(AVG((body_part_frames->'glove_r'->>'visibility_pct')::numeric), 1)
                                                                        AS avg_glove_r_pct,
    ROUND(AVG((body_part_frames->'elbow_l'->>'visibility_pct')::numeric), 1)
                                                                        AS avg_elbow_l_pct,
    ROUND(AVG((body_part_frames->'elbow_r'->>'visibility_pct')::numeric), 1)
                                                                        AS avg_elbow_r_pct,
    ROUND(AVG((body_part_frames->'knee_l'->>'visibility_pct')::numeric), 1)
                                                                        AS avg_knee_l_pct,
    ROUND(AVG((body_part_frames->'knee_r'->>'visibility_pct')::numeric), 1)
                                                                        AS avg_knee_r_pct,
    ROUND(AVG((body_part_frames->'foot_l'->>'visibility_pct')::numeric), 1)
                                                                        AS avg_foot_l_pct,
    ROUND(AVG((body_part_frames->'foot_r'->>'visibility_pct')::numeric), 1)
                                                                        AS avg_foot_r_pct
FROM fight_event_summary
WHERE fighter_id IS NOT NULL
GROUP BY fighter_id;

-- ROLLBACK:
-- ALTER TABLE fight_event_summary
--     DROP COLUMN IF EXISTS kicks_missed_head,
--     DROP COLUMN IF EXISTS kicks_missed_body,
--     DROP COLUMN IF EXISTS kicks_missed_leg,
--     DROP COLUMN IF EXISTS body_part_frames,
--     DROP COLUMN IF EXISTS kinematic_features,
--     DROP COLUMN IF EXISTS spatial_coverage;
-- DROP VIEW IF EXISTS fighter_body_part_visibility;
