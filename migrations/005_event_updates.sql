-- ============================================================================
-- 005_event_updates.sql
-- Adds punch subtypes (jab/cross/hook/uppercut), KO, ground_strike.
-- Also adds punch_subtype + is_ground_strike columns to fight_events.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- A. Widen event_type CHECK constraint (drop old, add new)
-- ---------------------------------------------------------------------------
ALTER TABLE fight_events
    DROP CONSTRAINT IF EXISTS fight_events_event_type_check;

ALTER TABLE fight_events
    ADD CONSTRAINT fight_events_event_type_check
    CHECK (event_type IN (
        -- Strikes
        'punch', 'kick', 'elbow_strike', 'knee_strike',
        -- Finishing
        'knockdown', 'ko',
        -- Takedown game
        'takedown', 'takedown_stuffed',
        -- Clinch
        'clinch_entry', 'clinch_break',
        -- Position
        'position_change',
        -- Submission game
        'submission_attempt', 'submission',
        -- Scrambles
        'sweep', 'reversal',
        -- Cage
        'cage_control_start', 'cage_control_end',
        -- Ground
        'ground_strike'
    ));

-- ---------------------------------------------------------------------------
-- B. New columns on fight_events
-- ---------------------------------------------------------------------------

-- Punch subtype resolution
ALTER TABLE fight_events
    ADD COLUMN IF NOT EXISTS punch_subtype TEXT
        CHECK (punch_subtype IN ('jab', 'cross', 'hook', 'uppercut', NULL));

-- Whether striker or target was grounded
ALTER TABLE fight_events
    ADD COLUMN IF NOT EXISTS is_ground_strike BOOLEAN NOT NULL DEFAULT FALSE;

-- ---------------------------------------------------------------------------
-- C. Widen fight_event_summary with new counters
-- ---------------------------------------------------------------------------
ALTER TABLE fight_event_summary
    ADD COLUMN IF NOT EXISTS jabs_attempted          INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS jabs_landed             INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS crosses_attempted       INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS crosses_landed          INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS hooks_attempted         INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS hooks_landed            INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS uppercuts_attempted     INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS uppercuts_landed        INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ground_strikes_attempted INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ground_strikes_landed   INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ko_scored               INTEGER NOT NULL DEFAULT 0;

-- ---------------------------------------------------------------------------
-- D. Update career totals view
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
    SUM(elbow_strikes_attempted)                                        AS career_elbows_attempted,
    SUM(elbows_landed)                                                  AS career_elbows_landed,
    SUM(knee_strikes_attempted)                                         AS career_knees_attempted,
    SUM(knees_landed)                                                   AS career_knees_landed,
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
    AVG(aggression_score)                                               AS avg_aggression_score
FROM fight_event_summary
WHERE fighter_id IS NOT NULL
GROUP BY fighter_id;

-- ROLLBACK:
-- ALTER TABLE fight_events DROP COLUMN IF EXISTS punch_subtype;
-- ALTER TABLE fight_events DROP COLUMN IF EXISTS is_ground_strike;
