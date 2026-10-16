-- CO-01 (T3). mart_driver_season_summary.teammate_gap_s equals rating_s (the
-- shrunk season gap to his teammate(s)), not rating_s minus the teammate's
-- rating (about twice the gap). NULL exactly when teammate_id is NULL.
SELECT 'gap_not_equal_rating' AS failure, driver_id, race_year, teammate_gap_s AS value_s
FROM {{ ref('mart_driver_season_summary') }}
WHERE (teammate_id IS NOT NULL AND ABS(teammate_gap_s - rating_s) > 1e-9)
    OR (teammate_id IS NULL AND teammate_gap_s IS NOT NULL)
