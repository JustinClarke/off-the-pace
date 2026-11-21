-- Per (race_id, follower, lap), seconds over leaders in int_physical_ahead_pairs_lapped must not exceed
-- int_lap_physical_ahead.lapped_seconds_within_1s (plus 1e-3 for 4 dp rounding).
{{ config(severity='error') }}
SELECT p.race_id, p.follower_driver_id, p.lap_number,
       SUM(p.seconds_within_1s) AS pair_seconds, MAX(l.lapped_seconds_within_1s) AS lap_seconds
FROM {{ ref('int_physical_ahead_pairs_lapped') }} AS p
LEFT JOIN {{ ref('int_lap_physical_ahead') }} AS l
    ON p.race_id = l.race_id AND p.follower_driver_id = l.driver_id AND p.lap_number = l.lap_number
GROUP BY p.race_id, p.follower_driver_id, p.lap_number
HAVING MAX(l.lapped_seconds_within_1s) IS NULL
    OR SUM(p.seconds_within_1s) > MAX(l.lapped_seconds_within_1s) + 1e-3
