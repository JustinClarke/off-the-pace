-- int_traffic_exposure_driver_race / _race: lapped columns are bounded and roll up exactly. Returns violating rows.
--   * lapped_time_close_behind_s <= lapped_time_measured_s (driver-race);
--   * the race table's lapped sums equal the sums of its driver rows (to the 3 dp rounding).
WITH d AS (
    SELECT
        race_id,
        SUM(lapped_time_close_behind_s) AS s_close,
        SUM(lapped_time_measured_s) AS s_meas,
        SUM(n_laps_lapped_within_1s) AS s_n
    FROM {{ ref('int_traffic_exposure_driver_race') }}
    GROUP BY race_id
)

SELECT 'driver_race' AS grain, race_id, driver_id AS key
FROM {{ ref('int_traffic_exposure_driver_race') }}
WHERE lapped_time_close_behind_s > lapped_time_measured_s + 1e-6
UNION ALL
SELECT 'race', r.race_id, NULL
FROM {{ ref('int_traffic_exposure_race') }} AS r
INNER JOIN d ON r.race_id = d.race_id
WHERE ABS(COALESCE(r.lapped_time_close_behind_s, 0) - COALESCE(d.s_close, 0)) > 0.01
    OR ABS(COALESCE(r.lapped_time_measured_s, 0) - COALESCE(d.s_meas, 0)) > 0.01
    OR COALESCE(r.n_laps_lapped_within_1s, 0) <> COALESCE(d.s_n, 0)
