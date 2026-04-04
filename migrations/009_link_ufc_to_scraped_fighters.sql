-- ============================================================================
-- 009_link_ufc_to_scraped_fighters.sql
-- Link ufc_fighters → scraped_fighters via trigram name similarity, then
-- auto-insert any unmatched eligible fighters into scraped_fighters so
-- every FPS-eligible UFC fighter has a presence in the 32K roster.
--
-- Steps:
--   1. Enable pg_trgm + GIN index on ufc_fighters.name (idempotent)
--   2. UPDATE ufc_fighters.scraped_fighter_id using best similarity match
--   3. INSERT unmatched eligible fighters into scraped_fighters
--   4. Back-fill scraped_fighter_id for newly inserted rows
--   5. Match-rate report
--
-- Type note:
--   scraped_fighters.id is TEXT, ufc_fighters.scraped_fighter_id is UUID.
--   The cast sf.id::uuid is valid when scraped_fighters rows were created
--   with gen_random_uuid() on Supabase (standard 36-char UUID strings).
--   If the DB has non-UUID text IDs, Step 2 is gated by the regex guard.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Step 0 — Prerequisites (all idempotent)
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Index for fast similarity joins on the new table
CREATE INDEX IF NOT EXISTS idx_ufc_fighters_name_trgm
    ON ufc_fighters USING GIN (name gin_trgm_ops);

-- Verify prerequisite index from migration 001 exists
CREATE INDEX IF NOT EXISTS idx_scraped_fighters_name_trgm
    ON scraped_fighters USING GIN (name gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- Step 1 — Match ufc_fighters → scraped_fighters (similarity > 0.80)
--
-- Uses DISTINCT ON to pick the single highest-similarity scraped fighter
-- when multiple candidates exceed the 0.80 threshold (e.g. "Jose Aldo" vs
-- "Jose Juarez Aldo Silva"). Only rows whose id column is a valid UUID string
-- are considered — non-UUID IDs are silently skipped.
-- ---------------------------------------------------------------------------
UPDATE ufc_fighters uf
SET    scraped_fighter_id = best.sf_id::uuid,
       updated_at         = NOW()
FROM (
    SELECT DISTINCT ON (uf2.id)
        uf2.id   AS ufc_id,
        sf.id    AS sf_id
    FROM   ufc_fighters uf2
    JOIN   scraped_fighters sf
        ON similarity(uf2.name, sf.name) > 0.80
    WHERE  uf2.scraped_fighter_id IS NULL
      -- Guard against non-UUID text IDs (avoids cast errors)
      AND  sf.id ~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    ORDER  BY uf2.id, similarity(uf2.name, sf.name) DESC
) best
WHERE uf.id = best.ufc_id;

-- ---------------------------------------------------------------------------
-- Step 2 — Insert unmatched eligible fighters into scraped_fighters
--
-- Only inserts fighters that:
--   a) still have no scraped_fighter_id after Step 1
--   b) meet the 5-fight eligibility threshold
--   c) don't already exist in scraped_fighters by exact name (idempotent)
--
-- scraped_fighters.id is TEXT — generate a fresh UUID, store as text.
-- ---------------------------------------------------------------------------
WITH new_roster AS (
    INSERT INTO scraped_fighters (id, name, weight_class, source)
    SELECT
        gen_random_uuid()::text   AS id,
        uf.name                   AS name,
        uf.weight_class           AS weight_class,
        'ufc_data_pipeline'       AS source
    FROM ufc_fighters uf
    WHERE uf.scraped_fighter_id IS NULL
      AND uf.meets_5_fight_threshold = TRUE
      -- Skip if an exact-name match already exists (shouldn't after Step 1,
      -- but guards against re-runs or near-miss names that fell just below 0.80)
      AND NOT EXISTS (
          SELECT 1
          FROM   scraped_fighters sf
          WHERE  sf.name = uf.name
      )
    RETURNING id, name
)

-- ---------------------------------------------------------------------------
-- Step 3 — Back-fill scraped_fighter_id for the newly inserted rows
-- ---------------------------------------------------------------------------
UPDATE ufc_fighters uf
SET    scraped_fighter_id = nr.id::uuid,
       updated_at         = NOW()
FROM   new_roster nr
WHERE  uf.name = nr.name;

-- ---------------------------------------------------------------------------
-- Step 4 — Match-rate report
-- Run manually or check in application logs after migration.
-- Target: 70-85% matched in Step 1, remainder filled in by Step 2.
-- After both steps, unmatched should be 0 for meets_5_fight_threshold rows.
-- ---------------------------------------------------------------------------
SELECT
    COUNT(*)                                                            AS total_ufc_eligible,
    COUNT(scraped_fighter_id)                                           AS matched_to_scraped,
    COUNT(*) - COUNT(scraped_fighter_id)                                AS still_unmatched,
    ROUND(
        COUNT(scraped_fighter_id) * 100.0 / NULLIF(COUNT(*), 0),
    1)                                                                  AS match_pct,
    -- How many came from pre-existing scraped rows vs. newly inserted
    COUNT(CASE WHEN sf.source != 'ufc_data_pipeline' THEN 1 END)       AS matched_existing,
    COUNT(CASE WHEN sf.source  = 'ufc_data_pipeline' THEN 1 END)       AS auto_inserted
FROM  ufc_fighters uf
LEFT  JOIN scraped_fighters sf
    ON  sf.id = uf.scraped_fighter_id::text
WHERE uf.meets_5_fight_threshold = TRUE;
