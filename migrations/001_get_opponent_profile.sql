-- ============================================================================
-- 001_get_opponent_profile.sql
-- Master opponent profile lookup function.
-- Checks verified fighters (FPS-scored) first, falls back to scraped_fighters.
--
-- Fixes applied vs. original draft:
--  1. fighters schema: uses full_name, record_wins/losses, no bare fps_score column
--  2. FPS data lives in fighter_fps_scores (joined, is_current=TRUE); correct
--     component column names (total_fps_score, damage_efficiency,
--     defensive_responsibility, control_effectiveness, chin_durability)
--  3. Recent fights sourced from fighter_recent_fights (has event_date),
--     not fight_stats (no date column)
--  4. scraped_fighters: only references columns that actually exist
--     (name, weight_class, nationality, source; wins/losses/draws from
--     015_scraped_fights.sql ALTER + migrate_supabase_to_crdb.py)
--  5. Removed style_tags / promotion / style_notes (not in schema)
--  6. Added STABLE volatility, explicit search_path, SECURITY DEFINER
--  7. ILIKE leading-wildcard note: requires pg_trgm GIN index (see below)
-- ============================================================================

-- Prerequisite: trigram extension for efficient ILIKE on large tables
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN trigram index on fighters.full_name (FPS table, small)
CREATE INDEX IF NOT EXISTS idx_fighters_full_name_trgm
    ON fighters USING GIN (full_name gin_trgm_ops);

-- GIN trigram index on scraped_fighters.name (32K rows — critical)
CREATE INDEX IF NOT EXISTS idx_scraped_fighters_name_trgm
    ON scraped_fighters USING GIN (name gin_trgm_ops);

-- ============================================================================
-- Function
-- ============================================================================
CREATE OR REPLACE FUNCTION get_opponent_profile(p_fighter_name TEXT)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_profile JSONB;
BEGIN
  -- -----------------------------------------------------------------------
  -- 1. Verified fighters — have an FPS score (is_current = TRUE)
  -- -----------------------------------------------------------------------
  SELECT jsonb_build_object(
    'source',     'verified',
    'name',       f.full_name,
    'weight_class', f.weight_class,
    'fps', fps.total_fps_score,
    'fps_components', jsonb_build_object(
      'win_quality',               fps.win_quality,
      'finish_threat',             fps.finish_threat,
      'damage_efficiency',         fps.damage_efficiency,
      'defensive_responsibility',  fps.defensive_responsibility,
      'control_effectiveness',     fps.control_effectiveness,
      'opponent_quality',          fps.opponent_quality,
      'career_momentum',           fps.career_momentum,
      'cardio_pace',               fps.cardio_pace,
      'chin_durability',           fps.chin_durability,
      'fight_iq',                  fps.fight_iq
    ),
    'record', jsonb_build_object(
      'wins',        f.record_wins,
      'losses',      f.record_losses,
      'draws',       f.record_draws,
      'no_contests', f.record_no_contests,
      'finish_rate', fps.finish_rate,
      'ko_rate',     fps.ko_rate,
      'sub_rate',    fps.sub_rate
    ),
    'style',       f.style_label,
    'style_tags',  f.style_tags,
    'stance',      f.stance,
    'tendencies', jsonb_build_object(
      'pressure_rating',  f.pressure_rating,
      'clinch_frequency', f.clinch_frequency,
      'grappling_first',  f.grappling_first,
      'late_round_fade',  f.late_round_fade,
      'finish_urgency',   f.finish_urgency
    ),
    'recent_fights', (
      SELECT jsonb_agg(
        jsonb_build_object(
          'result',        rf.result,
          'method',        rf.method,
          'opponent_name', rf.opponent_name,
          'event_name',    rf.event_name,
          'event_date',    rf.event_date
        )
        ORDER BY rf.sort_order ASC
      )
      FROM fighter_recent_fights rf
      WHERE rf.fighter_id = f.id
      LIMIT 5
    )
  ) INTO v_profile
  FROM fighters f
  JOIN fighter_fps_scores fps
    ON fps.fighter_id = f.id
   AND fps.is_current = TRUE
  WHERE f.full_name ILIKE '%' || p_fighter_name || '%'
  ORDER BY fps.total_fps_score DESC NULLS LAST
  LIMIT 1;

  -- -----------------------------------------------------------------------
  -- 2. Fallback — scraped_fighters (32K roster)
  --    Columns: id (TEXT), name, nickname, nationality, weight_class,
  --             source, wins, losses, draws (added via migration script),
  --             fps_confidence, fcs_confidence (added via 047)
  -- -----------------------------------------------------------------------
  IF v_profile IS NULL THEN
    SELECT jsonb_build_object(
      'source',          'scraped',
      'name',            sf.name,
      'nickname',        sf.nickname,
      'nationality',     sf.nationality,
      'weight_class',    sf.weight_class,
      'data_source',     sf.source,
      'record', jsonb_build_object(
        'wins',   sf.wins,
        'losses', sf.losses,
        'draws',  sf.draws
      ),
      'fps_confidence',  sf.fps_confidence,
      'fcs_confidence',  sf.fcs_confidence,
      'recent_fights', (
        SELECT jsonb_agg(
          jsonb_build_object(
            'result',      fr.result,
            'method',      fr.method,
            'opponent',    fr.opponent_name,
            'event',       fr.event_name,
            'fight_date',  fr.fight_date
          )
          ORDER BY fr.fight_date DESC NULLS LAST
        )
        FROM fight_records fr
        WHERE fr.fighter_id = sf.id
        LIMIT 5
      )
    ) INTO v_profile
    FROM scraped_fighters sf
    WHERE sf.name ILIKE '%' || p_fighter_name || '%'
    ORDER BY sf.fps_confidence DESC NULLS LAST
    LIMIT 1;
  END IF;

  RETURN v_profile;
END;
$$;

-- Usage:
--   SELECT get_opponent_profile('Jones');
--   SELECT get_opponent_profile('Conor McGregor');
