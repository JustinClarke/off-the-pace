-- int_traffic_exposure_driver_race.sql · intermediate · grain: one row per (race_id, driver_id)
--
-- MEASUREMENT ONLY. How much of a driver's race was spent close behind the physical car ahead, and how much
-- of it could not be measured cleanly. Descriptive columns only: no time loss, no dirty-air seconds, no tax,
-- no column that says or implies traffic made a lap slow. Built only from int_lap_physical_ahead (X/Y
-- positions; never FastF1 DriverAhead / DistanceToDriverAhead, decision D2).
--
-- Which laps count where:
--   * Close-behind time and bunching are measured on MEASURED laps only: validity_class = 'valid_same_lap'
--     AND not neutralised (SC / VSC / red flag; the field bunches there at no racing pace, as in
--     int_lap_proximity).
--   * lapped / overlapping / side_by_side / lap1 / unknown laps are counted in their own columns and are
--     never counted as clear air or as following.
-- Not wired to any page (traffic_exposure_copy.md holds the draft wording).
{{ config(materialized='table') }}

WITH laps AS (
    SELECT * FROM {{ ref('int_lap_physical_ahead') }}
)

SELECT
    race_id,
    MIN(season) AS season,
    driver_id,
    COUNT(*) AS n_laps,

    -- lap partition (sums to n_laps; assert_traffic_exposure_lap_partition)
    COUNT(*) FILTER (WHERE validity_class = 'valid_same_lap' AND NOT is_neutralised_lap)
        AS n_laps_measured,
    COUNT(*) FILTER (WHERE validity_class = 'valid_same_lap' AND is_neutralised_lap)
        AS n_laps_neutralised,
    COUNT(*) FILTER (WHERE validity_class = 'lap1') AS n_laps_lap1,
    COUNT(*) FILTER (WHERE validity_class = 'side_by_side') AS n_laps_side_by_side,
    COUNT(*) FILTER (WHERE validity_class = 'overlapping') AS n_laps_overlapping,
    COUNT(*) FILTER (WHERE validity_class = 'lapped') AS n_laps_lapped,
    COUNT(*) FILTER (WHERE validity_class = 'unknown') AS n_laps_unknown,

    -- time close behind (seconds within 1 s of the car ahead), measured laps only
    ROUND(SUM(time_within_1s_phys_s) FILTER (
        WHERE validity_class = 'valid_same_lap' AND NOT is_neutralised_lap
    ), 3) AS time_close_behind_s,
    ROUND(SUM(time_measured_s) FILTER (
        WHERE validity_class = 'valid_same_lap' AND NOT is_neutralised_lap
    ), 3) AS time_measured_s,
    ROUND(
        SUM(time_within_1s_phys_s) FILTER (WHERE validity_class = 'valid_same_lap' AND NOT is_neutralised_lap)
        / NULLIF(SUM(time_measured_s) FILTER (
            WHERE validity_class = 'valid_same_lap' AND NOT is_neutralised_lap
        ), 0), 4
    ) AS share_time_close_behind,

    -- bunching: share of measured laps with any moment within 1 s of the car ahead
    COUNT(*) FILTER (
        WHERE validity_class = 'valid_same_lap' AND NOT is_neutralised_lap AND is_within_1s_of_car_ahead
    ) AS n_laps_within_1s,
    ROUND(
        COUNT(*) FILTER (
            WHERE validity_class = 'valid_same_lap' AND NOT is_neutralised_lap AND is_within_1s_of_car_ahead
        )::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE validity_class = 'valid_same_lap' AND NOT is_neutralised_lap), 0), 4
    ) AS bunching_share,

    -- what could not be measured cleanly, as a share of all laps
    ROUND(COUNT(*) FILTER (WHERE validity_class = 'lapped')::DOUBLE / COUNT(*), 4) AS share_laps_lapped,
    ROUND(COUNT(*) FILTER (WHERE validity_class = 'overlapping')::DOUBLE / COUNT(*), 4)
        AS share_laps_overlapping,
    ROUND(COUNT(*) FILTER (WHERE validity_class = 'unknown')::DOUBLE / COUNT(*), 4) AS share_laps_unknown,
    ROUND(COUNT(*) FILTER (WHERE validity_class = 'valid_same_lap' AND NOT is_neutralised_lap)::DOUBLE
        / COUNT(*), 4) AS share_laps_measured,

    -- known limit carried, not hidden: car-ahead identity flips between consecutive samples
    SUM(n_ahead_flips) AS n_ahead_flips,
    SUM(n_ahead_pairs) AS n_ahead_pairs,
    MAX(CAST(zero_xy_guard_on AS INTEGER)) = 1 AS zero_xy_guard_on
FROM laps
GROUP BY race_id, driver_id
