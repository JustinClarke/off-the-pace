-- Check that rating_confidence is not collapsing globally.
-- The DAG says "LORO collapse | int_driver_race_skill_loro | All drivers rated near average | Check shrinkage weights > 0.3"
-- While some drivers with 1 or 2 races will naturally have low confidence, if all drivers have low confidence, it's a collapse.
-- We will check if there are drivers with >= 5 races that have rating_confidence < 0.3
SELECT driver_id, season, races_completed_n, rating_confidence
FROM {{ ref('int_driver_season_ratings') }}
WHERE races_completed_n >= 5 AND rating_confidence < 0.3
