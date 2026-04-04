-- ============================================================================
-- 008_ufc_fighters_fights_rounds.sql
-- UFC fighter/fight/round dataset for FPS computation and simulation.
-- Only fighters with 5+ UFC appearances are eligible for career FPS scoring.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- A. ufc_fighters
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ufc_fighters (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name                        TEXT NOT NULL,
    ufcstats_url                TEXT UNIQUE,
    -- Soft link to the 32K scraped_fighters table (may exist in a different DB)
    scraped_fighter_id          UUID,

    -- Career record
    weight_class                VARCHAR(30),
    stance                      VARCHAR(20),
    ufc_wins                    INT NOT NULL DEFAULT 0,
    ufc_losses                  INT NOT NULL DEFAULT 0,
    ufc_draws                   INT NOT NULL DEFAULT 0,
    ufc_nc                      INT NOT NULL DEFAULT 0,
    ufc_appearances             INT NOT NULL DEFAULT 0,

    -- Eligibility: fighter must have 5+ UFC appearances to receive career FPS
    meets_5_fight_threshold     BOOLEAN GENERATED ALWAYS AS (ufc_appearances >= 5) STORED,

    -- Career FPS (weighted average across last 5 UFC fights)
    career_fps                  NUMERIC(5,2),
    career_fps_tier             TEXT CHECK (career_fps_tier IN (
                                    'DOMINANT', 'STRONG', 'COMPETITIVE',
                                    'MIXED', 'LOSING', 'POOR'
                                )),
    fps_fight_count             INT,            -- number of fights FPS is based on
    fps_last_calculated         TIMESTAMPTZ,

    -- FPS component averages (career-weighted)
    avg_offensive_efficiency    NUMERIC(5,2),
    avg_defensive_response      NUMERIC(5,2),
    avg_control_dictation       NUMERIC(5,2),
    avg_finish_threat           NUMERIC(5,2),
    avg_cardio_pace             NUMERIC(5,2),
    avg_durability              NUMERIC(5,2),
    avg_fight_iq                NUMERIC(5,2),
    avg_dominance               NUMERIC(5,2),

    -- Style
    style_archetype             TEXT,
    style_tags                  TEXT[],
    finish_rate                 NUMERIC(4,3),
    ko_rate                     NUMERIC(4,3),
    sub_rate                    NUMERIC(4,3),

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ufc_fighters_eligible
    ON ufc_fighters (meets_5_fight_threshold)
    WHERE meets_5_fight_threshold = TRUE;

CREATE INDEX IF NOT EXISTS idx_ufc_fighters_weight_class
    ON ufc_fighters (weight_class);

CREATE INDEX IF NOT EXISTS idx_ufc_fighters_career_fps
    ON ufc_fighters (career_fps DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_ufc_fighters_style_tags
    ON ufc_fighters USING GIN (style_tags);

CREATE TRIGGER ufc_fighters_updated_at
    BEFORE UPDATE ON ufc_fighters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ---------------------------------------------------------------------------
-- B. ufc_fights
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ufc_fights (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    ufcstats_fight_url          TEXT UNIQUE NOT NULL,
    event_name                  TEXT,
    fight_date                  DATE,
    weight_class                VARCHAR(30),

    -- Participants (fighter_a = red corner, fighter_b = blue corner)
    fighter_a_id                UUID REFERENCES ufc_fighters(id) ON DELETE SET NULL,
    fighter_b_id                UUID REFERENCES ufc_fighters(id) ON DELETE SET NULL,
    fighter_a_name              TEXT,
    fighter_b_name              TEXT,

    -- Outcome
    winner_id                   UUID REFERENCES ufc_fighters(id) ON DELETE SET NULL,
    winner_name                 TEXT,
    method                      TEXT,
    method_normalized           TEXT CHECK (method_normalized IN (
                                    'ko', 'tko', 'sub', 'ud', 'sd', 'md', 'nc', 'dq'
                                )),
    finish_round                INT,
    finish_time                 TEXT,
    finish_time_seconds         INT,
    rounds_scheduled            INT,
    went_to_decision            BOOLEAN GENERATED ALWAYS AS (
                                    method_normalized IN ('ud', 'sd', 'md')
                                ) STORED,
    was_finish                  BOOLEAN GENERATED ALWAYS AS (
                                    method_normalized IN ('ko', 'tko', 'sub')
                                ) STORED,

    -- FPS for this fight
    fighter_a_fps               NUMERIC(5,2),
    fighter_b_fps               NUMERIC(5,2),
    fps_delta                   NUMERIC(5,2)
                                GENERATED ALWAYS AS (fighter_a_fps - fighter_b_fps) STORED,

    -- Context
    is_title_fight              BOOLEAN NOT NULL DEFAULT FALSE,
    is_main_event               BOOLEAN NOT NULL DEFAULT FALSE,

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ufc_fights_fighter_a    ON ufc_fights (fighter_a_id);
CREATE INDEX IF NOT EXISTS idx_ufc_fights_fighter_b    ON ufc_fights (fighter_b_id);
CREATE INDEX IF NOT EXISTS idx_ufc_fights_winner       ON ufc_fights (winner_id);
CREATE INDEX IF NOT EXISTS idx_ufc_fights_date         ON ufc_fights (fight_date DESC);
CREATE INDEX IF NOT EXISTS idx_ufc_fights_method       ON ufc_fights (method_normalized);
CREATE INDEX IF NOT EXISTS idx_ufc_fights_fps_delta    ON ufc_fights (fps_delta DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_ufc_fights_weight_class ON ufc_fights (weight_class);

-- ---------------------------------------------------------------------------
-- C. ufc_round_stats
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ufc_round_stats (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fight_id                    UUID NOT NULL REFERENCES ufc_fights(id) ON DELETE CASCADE,
    fighter_id                  UUID REFERENCES ufc_fighters(id) ON DELETE SET NULL,
    fighter_name                TEXT,

    round_number                INT NOT NULL,

    -- Raw ufcstats inputs
    sl                          INT NOT NULL DEFAULT 0,  -- sig strikes landed
    sa                          INT NOT NULL DEFAULT 0,  -- sig strikes attempted
    kd_f                        INT NOT NULL DEFAULT 0,  -- knockdowns scored
    kd_a                        INT NOT NULL DEFAULT 0,  -- knockdowns conceded
    td_f                        INT NOT NULL DEFAULT 0,  -- takedowns landed
    ta_f                        INT NOT NULL DEFAULT 0,  -- takedowns attempted
    td_a                        INT NOT NULL DEFAULT 0,  -- opponent takedowns landed
    ta_a                        INT NOT NULL DEFAULT 0,  -- opponent takedowns attempted
    ctrl_f                      INT NOT NULL DEFAULT 0,  -- control seconds
    ctrl_a                      INT NOT NULL DEFAULT 0,  -- opponent control seconds
    sub_att                     INT NOT NULL DEFAULT 0,  -- submission attempts

    -- Derived inputs
    nf                          INT NOT NULL DEFAULT 0   -- near finish (0/1/2)
                                CHECK (nf BETWEEN 0 AND 2),
    err                         INT NOT NULL DEFAULT 0   -- errors (0/1/2)
                                CHECK (err BETWEEN 0 AND 2),
    sec                         INT NOT NULL DEFAULT 300, -- round duration seconds
    is_finish_round             BOOLEAN NOT NULL DEFAULT FALSE,
    fighter_won_fight           BOOLEAN,

    -- Computed RPS components
    offensive_efficiency        NUMERIC(5,2),
    defensive_response          NUMERIC(5,2),
    control_dictation           NUMERIC(5,2),
    finish_threat               NUMERIC(5,2),
    durability                  NUMERIC(5,2),
    fight_iq                    NUMERIC(5,2),
    dominance                   NUMERIC(5,2),
    rps                         NUMERIC(5,2),

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (fight_id, fighter_id, round_number)
);

CREATE INDEX IF NOT EXISTS idx_ufc_round_stats_fight
    ON ufc_round_stats (fight_id);

CREATE INDEX IF NOT EXISTS idx_ufc_round_stats_fighter
    ON ufc_round_stats (fighter_id);

-- ---------------------------------------------------------------------------
-- RLS — service role full access, read-only for anon/authenticated
-- ---------------------------------------------------------------------------
ALTER TABLE ufc_fighters  ENABLE ROW LEVEL SECURITY;
ALTER TABLE ufc_fights    ENABLE ROW LEVEL SECURITY;
ALTER TABLE ufc_round_stats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_ufc_fighters" ON ufc_fighters
    FOR ALL USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "service_role_all_ufc_fights" ON ufc_fights
    FOR ALL USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "service_role_all_ufc_round_stats" ON ufc_round_stats
    FOR ALL USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ROLLBACK:
-- DROP TABLE IF EXISTS ufc_round_stats;
-- DROP TABLE IF EXISTS ufc_fights;
-- DROP TABLE IF EXISTS ufc_fighters;
