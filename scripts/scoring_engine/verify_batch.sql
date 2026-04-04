-- Verification query — run after batch processing completes

SELECT
    COUNT(*)                                             AS total_fighters,
    COUNT(*) FILTER (WHERE meets_5_fight_threshold)      AS eligible_fighters,
    COUNT(*) FILTER (WHERE career_fps IS NOT NULL)       AS fps_scored_fighters,
    ROUND(AVG(career_fps) FILTER (WHERE career_fps IS NOT NULL), 1) AS avg_career_fps,
    COUNT(*) FILTER (WHERE career_fps_tier = 'DOMINANT')     AS dominant,
    COUNT(*) FILTER (WHERE career_fps_tier = 'STRONG')       AS strong,
    COUNT(*) FILTER (WHERE career_fps_tier = 'COMPETITIVE')  AS competitive,
    COUNT(*) FILTER (WHERE career_fps_tier = 'MIXED')        AS mixed,
    COUNT(*) FILTER (WHERE career_fps_tier = 'LOSING')       AS losing,
    COUNT(*) FILTER (WHERE career_fps_tier = 'POOR')         AS poor
FROM ufc_fighters;

-- Expected output:
-- eligible_fighters:   850-1,100
-- fps_scored_fighters: 800-1,050  (some may have incomplete round data)
-- avg_career_fps:      ~58-65     (UFC average performer)
-- dominant:            ~50-80     (Khabib, Jones, Usman tier)
-- strong:              ~150-200
-- competitive:         ~300-400

-- Top 20 fighters by career FPS
SELECT
    name,
    weight_class,
    career_fps,
    career_fps_tier,
    style_archetype,
    fps_fight_count,
    ufc_appearances
FROM ufc_fighters
WHERE meets_5_fight_threshold = TRUE
  AND career_fps IS NOT NULL
ORDER BY career_fps DESC
LIMIT 20;
