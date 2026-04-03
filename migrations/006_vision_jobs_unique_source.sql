-- ============================================================================
-- 006_vision_jobs_unique_source.sql
-- Add a unique constraint on video_source so concurrent batch containers
-- cannot create duplicate jobs for the same video file.
-- Also removes any orphaned duplicate rows (keeping the newest per source).
-- ============================================================================

-- 1. Remove duplicate rows, keeping the most-recently-created per video_source.
--    This handles the race condition that may have already fired.
DELETE FROM vision_jobs
WHERE id NOT IN (
    SELECT DISTINCT ON (video_source) id
    FROM vision_jobs
    ORDER BY video_source, created_at DESC
);

-- 2. Add the unique constraint.
ALTER TABLE vision_jobs
    ADD CONSTRAINT uq_vision_jobs_video_source UNIQUE (video_source);

-- ROLLBACK:
-- ALTER TABLE vision_jobs DROP CONSTRAINT IF EXISTS uq_vision_jobs_video_source;
