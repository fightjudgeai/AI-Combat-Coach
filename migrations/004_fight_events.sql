-- ============================================================================
-- 004_fight_events.sql
-- Per-timestamp event log for vision pipeline detections.
-- One row per detected event (not per frame).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- A. fight_events — timestamped action/event log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fight_events (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID    NOT NULL REFERENCES vision_jobs(id) ON DELETE CASCADE,
    fighter_id      UUID    REFERENCES fighters(id) ON DELETE SET NULL,

    -- Where in the video
    timestamp_secs  NUMERIC(10,3) NOT NULL,
    round_num       SMALLINT,                   -- NULL if round boundaries not supplied

    -- -----------------------------------------------------------------------
    -- Event classification
    -- -----------------------------------------------------------------------

    -- Top-level event category
    event_type      TEXT NOT NULL CHECK (event_type IN (
        -- Strikes (attempted — resolved by outcome)
        'punch', 'kick', 'elbow_strike', 'knee_strike',
        -- Finishing events
        'knockdown',
        -- Takedown game
        'takedown', 'takedown_stuffed',
        -- Clinch / grappling
        'clinch_entry', 'clinch_break',
        -- Body positions (state transitions)
        'position_change',
        -- Submission game
        'submission_attempt', 'submission',
        -- Guard scrambles
        'sweep', 'reversal',
        -- Cage
        'cage_control_start', 'cage_control_end'
    )),

    -- For strikes: which body part was used
    limb            TEXT CHECK (limb IN (
        'fist', 'glove', 'elbow', 'knee', 'foot', 'shin', NULL
    )),

    -- For strikes: target zone on the opponent
    target_zone     TEXT CHECK (target_zone IN (
        'head', 'body', 'leg', 'unknown', NULL
    )),

    -- For strikes: did it land?
    outcome         TEXT CHECK (outcome IN (
        'landed', 'missed', 'blocked', NULL
    )),

    -- For position events: which position
    position        TEXT CHECK (position IN (
        'standing', 'clinch',
        'half_guard', 'full_guard',
        'side_control', 'back_control',
        'cage_grappling',
        NULL
    )),

    -- Model confidence [0,1]
    confidence      NUMERIC(5,4) NOT NULL DEFAULT 0.0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fight_events_job_id
    ON fight_events (job_id);
CREATE INDEX IF NOT EXISTS idx_fight_events_fighter_id
    ON fight_events (fighter_id);
CREATE INDEX IF NOT EXISTS idx_fight_events_type_outcome
    ON fight_events (event_type, outcome);
CREATE INDEX IF NOT EXISTS idx_fight_events_timestamp
    ON fight_events (job_id, timestamp_secs);

ALTER TABLE fight_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all_fight_events" ON fight_events
    FOR ALL USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
CREATE POLICY "anon_read_fight_events" ON fight_events
    FOR SELECT USING (true);

-- ---------------------------------------------------------------------------
-- B. fight_event_summary — aggregated counts per job/fighter
--    Updated by trigger after each batch insert.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fight_event_summary (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                      UUID NOT NULL REFERENCES vision_jobs(id) ON DELETE CASCADE,
    fighter_id                  UUID REFERENCES fighters(id) ON DELETE SET NULL,

    -- Strike attempts
    punches_attempted           INTEGER NOT NULL DEFAULT 0,
    kicks_attempted             INTEGER NOT NULL DEFAULT 0,
    elbow_strikes_attempted     INTEGER NOT NULL DEFAULT 0,
    knee_strikes_attempted      INTEGER NOT NULL DEFAULT 0,

    -- Landed strikes
    punches_landed              INTEGER NOT NULL DEFAULT 0,
    kicks_landed_head           INTEGER NOT NULL DEFAULT 0,
    kicks_landed_body           INTEGER NOT NULL DEFAULT 0,
    kicks_landed_leg            INTEGER NOT NULL DEFAULT 0,
    elbows_landed               INTEGER NOT NULL DEFAULT 0,
    knees_landed                INTEGER NOT NULL DEFAULT 0,

    -- Missed strikes
    punches_missed              INTEGER NOT NULL DEFAULT 0,
    kicks_missed                INTEGER NOT NULL DEFAULT 0,
    elbows_missed               INTEGER NOT NULL DEFAULT 0,
    knees_missed                INTEGER NOT NULL DEFAULT 0,

    -- Finishing events
    knockdowns_scored           INTEGER NOT NULL DEFAULT 0,

    -- Takedown game
    takedowns_landed            INTEGER NOT NULL DEFAULT 0,
    takedowns_stuffed           INTEGER NOT NULL DEFAULT 0,

    -- Clinch / cage
    clinch_entries              INTEGER NOT NULL DEFAULT 0,
    cage_control_sequences      INTEGER NOT NULL DEFAULT 0,

    -- Grappling positions (time-on, in seconds)
    time_in_half_guard          NUMERIC(8,2) NOT NULL DEFAULT 0,
    time_in_full_guard          NUMERIC(8,2) NOT NULL DEFAULT 0,
    time_in_side_control        NUMERIC(8,2) NOT NULL DEFAULT 0,
    time_in_back_control        NUMERIC(8,2) NOT NULL DEFAULT 0,
    time_in_clinch              NUMERIC(8,2) NOT NULL DEFAULT 0,
    time_in_cage_grappling      NUMERIC(8,2) NOT NULL DEFAULT 0,

    -- Submission game
    submission_attempts         INTEGER NOT NULL DEFAULT 0,
    submissions_completed       INTEGER NOT NULL DEFAULT 0,

    -- Guard scrambles
    sweeps                      INTEGER NOT NULL DEFAULT 0,
    reversals                   INTEGER NOT NULL DEFAULT 0,

    -- Pressure + aggression (derived metrics 0-100)
    pressure_score              NUMERIC(5,2),
    aggression_score            NUMERIC(5,2),

    -- Derived accuracy rates
    strike_accuracy             NUMERIC(5,4)
        GENERATED ALWAYS AS (
            CASE WHEN (punches_attempted + kicks_attempted +
                       elbow_strikes_attempted + knee_strikes_attempted) = 0
                 THEN NULL
                 ELSE (punches_landed + kicks_landed_head + kicks_landed_body +
                       kicks_landed_leg + elbows_landed + knees_landed)::NUMERIC /
                      (punches_attempted + kicks_attempted +
                       elbow_strikes_attempted + knee_strikes_attempted)
            END
        ) STORED,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (job_id, fighter_id)
);

CREATE INDEX IF NOT EXISTS idx_fight_event_summary_job
    ON fight_event_summary (job_id);
CREATE INDEX IF NOT EXISTS idx_fight_event_summary_fighter
    ON fight_event_summary (fighter_id);

CREATE TRIGGER fight_event_summary_updated_at
    BEFORE UPDATE ON fight_event_summary
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fight_event_summary ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all_summary" ON fight_event_summary
    FOR ALL USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
CREATE POLICY "anon_read_summary" ON fight_event_summary
    FOR SELECT USING (true);

-- ---------------------------------------------------------------------------
-- C. Helper view: per-fighter career event totals
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW fighter_event_career_totals AS
SELECT
    fighter_id,
    COUNT(DISTINCT job_id)                      AS fights_analyzed,
    SUM(punches_attempted)                      AS career_punches_attempted,
    SUM(punches_landed)                         AS career_punches_landed,
    SUM(kicks_attempted)                        AS career_kicks_attempted,
    SUM(kicks_landed_head + kicks_landed_body + kicks_landed_leg) AS career_kicks_landed,
    SUM(elbow_strikes_attempted)                AS career_elbows_attempted,
    SUM(elbows_landed)                          AS career_elbows_landed,
    SUM(knee_strikes_attempted)                 AS career_knees_attempted,
    SUM(knees_landed)                           AS career_knees_landed,
    SUM(knockdowns_scored)                      AS career_knockdowns,
    SUM(takedowns_landed)                       AS career_takedowns_landed,
    SUM(takedowns_stuffed)                      AS career_takedowns_stuffed,
    SUM(submission_attempts)                    AS career_sub_attempts,
    SUM(submissions_completed)                  AS career_submissions,
    SUM(sweeps)                                 AS career_sweeps,
    SUM(reversals)                              AS career_reversals,
    AVG(strike_accuracy)                        AS avg_strike_accuracy,
    AVG(pressure_score)                         AS avg_pressure_score,
    AVG(aggression_score)                       AS avg_aggression_score
FROM fight_event_summary
WHERE fighter_id IS NOT NULL
GROUP BY fighter_id;

-- ROLLBACK:
-- DROP VIEW IF EXISTS fighter_event_career_totals;
-- DROP TABLE IF EXISTS fight_event_summary;
-- DROP TABLE IF EXISTS fight_events;
