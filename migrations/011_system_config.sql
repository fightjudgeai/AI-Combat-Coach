-- ============================================================================
-- 011_system_config.sql
-- Generic key/value store for runtime configuration and computed lookup tables.
-- Used by the simulation engine to read pre-built probability tables without
-- re-scanning fight history on every request.
-- ============================================================================

CREATE TABLE IF NOT EXISTS system_config (
    key         TEXT PRIMARY KEY,
    value       JSONB        NOT NULL,
    description TEXT,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Fast equality lookup (already covered by PRIMARY KEY, but make explicit)
CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config (key);

-- Seed the probability tables row as an empty placeholder so upserts work
-- even before build_probability_tables.py has been run.
INSERT INTO system_config (key, value, description)
VALUES (
    'simulation_probability_tables',
    '{}'::jsonb,
    'Win/finish probability lookup tables keyed by career-FPS delta bucket. '
    'Rebuilt by scripts/simulation/build_probability_tables.py.'
)
ON CONFLICT (key) DO NOTHING;
