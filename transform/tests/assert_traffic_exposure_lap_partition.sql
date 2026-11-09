-- int_traffic_exposure_driver_race: the lap classes partition every lap of the driver's race exactly once,
-- the row count matches int_lap_physical_ahead, and close-behind time never exceeds measured time.
WITH src AS (
    SELECT race_id, driver_id, COUNT(*) AS n
    FROM {{ ref('int_lap_physical_ahead') }}
    GROUP BY race_id, driver_id
)
SELECT d.race_id, d.driver_id, d.n_laps, s.n
FROM {{ ref('int_traffic_exposure_driver_race') }} AS d
FULL OUTER JOIN src AS s
    ON d.race_id = s.race_id AND d.driver_id = s.driver_id
WHERE
    d.n_laps IS DISTINCT FROM s.n
    OR d.n_laps <> d.n_laps_measured + d.n_laps_neutralised + d.n_laps_lap1 + d.n_laps_side_by_side
        + d.n_laps_overlapping + d.n_laps_lapped + d.n_laps_unknown
    OR d.time_close_behind_s > d.time_measured_s + 1e-6
