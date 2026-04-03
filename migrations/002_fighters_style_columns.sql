-- ============================================================================
-- 002_fighters_style_columns.sql
-- Adds combat-style and tendency columns to the fighters table.
-- All columns are nullable — no backfill required, safe on live data.
-- ============================================================================

ALTER TABLE fighters
    ADD COLUMN IF NOT EXISTS style_tags        TEXT[],
    ADD COLUMN IF NOT EXISTS stance            VARCHAR(20),            -- orthodox / southpaw / switch
    ADD COLUMN IF NOT EXISTS pressure_rating   NUMERIC(4,2)
        CHECK (pressure_rating  IS NULL OR (pressure_rating  BETWEEN 0 AND 100)),
    ADD COLUMN IF NOT EXISTS clinch_frequency  NUMERIC(4,2)
        CHECK (clinch_frequency IS NULL OR (clinch_frequency BETWEEN 0 AND 100)),
    ADD COLUMN IF NOT EXISTS grappling_first   BOOLEAN,
    ADD COLUMN IF NOT EXISTS late_round_fade   BOOLEAN,
    ADD COLUMN IF NOT EXISTS finish_urgency    NUMERIC(4,2)
        CHECK (finish_urgency   IS NULL OR (finish_urgency   BETWEEN 0 AND 100));

-- Index style_tags for array containment queries, e.g.:
--   WHERE style_tags @> ARRAY['wrestler']
CREATE INDEX IF NOT EXISTS idx_fighters_style_tags
    ON fighters USING GIN (style_tags);

-- Index stance for quick filter/group-by
CREATE INDEX IF NOT EXISTS idx_fighters_stance
    ON fighters (stance)
    WHERE stance IS NOT NULL;

-- ROLLBACK (uncomment to reverse):
-- ALTER TABLE fighters
--     DROP COLUMN IF EXISTS style_tags,
--     DROP COLUMN IF EXISTS stance,
--     DROP COLUMN IF EXISTS pressure_rating,
--     DROP COLUMN IF EXISTS clinch_frequency,
--     DROP COLUMN IF EXISTS grappling_first,
--     DROP COLUMN IF EXISTS late_round_fade,
--     DROP COLUMN IF EXISTS finish_urgency;
