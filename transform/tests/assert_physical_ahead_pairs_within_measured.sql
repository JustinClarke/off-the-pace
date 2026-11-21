-- int_physical_ahead_pairs: a follower-lap's pair seconds (summed over leaders) never exceed the seconds of that
-- lap the lap model measured (time_measured_s). Error level: close time is a subset of known time by
-- construction, so a breach is a bug, not a limit. Valid laps only (time_measured_s is NULL elsewhere).
-- Tolerance 1e-3 s covers the 4 dp rounding of both columns.
WITH pair_lap AS (
    SELECT race_id, follower_driver_id AS driver_id, lap_number, SUM(seconds_within_1s) AS pair_s
    FROM {{ ref('int_physical_ahead_pairs') }}
    GROUP BY race_id, follower_driver_id, lap_number
)
SELECT p.race_id, p.driver_id, p.lap_number, p.pair_s, l.time_measured_s
FROM pair_lap AS p
INNER JOIN {{ ref('int_lap_physical_ahead') }} AS l
    ON p.race_id = l.race_id AND p.driver_id = l.driver_id AND p.lap_number = l.lap_number
WHERE l.validity_class = 'valid_same_lap'
    AND p.pair_s > l.time_measured_s + 1e-3
