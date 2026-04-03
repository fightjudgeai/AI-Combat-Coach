-- ============================================================================
-- 003_vision_jobs.sql
-- Tracks CV pipeline jobs and per-fighter analysis results.
-- ============================================================================

CREATE TABLE IF NOT EXISTS vision_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fighter_id      UUID REFERENCES fighters(id) ON DELETE SET NULL,
    video_source    TEXT NOT NULL,              -- local path, s3://, https:// (yt)
    source_type     TEXT NOT NULL               -- local | s3 | youtube
                    CHECK (source_type IN ('local', 's3', 'youtube')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'done', 'error')),
    error_msg       TEXT,
    frames_sampled  INTEGER,
    duration_secs   NUMERIC(10,2),
    raw_attributes  JSONB NOT NULL DEFAULT '{}'::jsonb,  -- full computed output
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vision_jobs_fighter_id ON vision_jobs (fighter_id);
CREATE INDEX IF NOT EXISTS idx_vision_jobs_status     ON vision_jobs (status);

CREATE TRIGGER vision_jobs_updated_at
    BEFORE UPDATE ON vision_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS
ALTER TABLE vision_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_vision_jobs" ON vision_jobs
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ROLLBACK:
-- DROP TABLE IF EXISTS vision_jobs;
