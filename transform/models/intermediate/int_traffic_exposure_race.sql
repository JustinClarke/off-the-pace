-- int_traffic_exposure_race.sql · intermediate · grain: one row per race_id
--
-- MEASUREMENT ONLY. Field-level roll-up of int_traffic_exposure_driver_race: how bunched the race was and how
-- much of it could not be measured cleanly. Descriptive columns only: no time loss, no dirty-air seconds,
-- no tax. Shares are pooled over laps (or measured seconds), not averages of driver shares.
-- identity_flip_rate is the known car-ahead flip rate (experiments 26-28), carried so a reader can see it.
-- Not wired to any page.
{{ config(materialized='table') }}

SELECT
    race_id,
    MIN(season) AS season,
    COUNT(*) AS n_drivers,
    SUM(n_laps) AS n_laps,
    SUM(n_laps_measured) AS n_laps_measured,
    SUM(n_laps_neutralised) AS n_laps_neutralised,
    SUM(n_laps_lap1) AS n_laps_lap1,
    SUM(n_laps_side_by_side) AS n_laps_side_by_side,
    SUM(n_laps_overlapping) AS n_laps_overlapping,
    SUM(n_laps_lapped) AS n_laps_lapped,
    SUM(n_laps_unknown) AS n_laps_unknown,

    ROUND(SUM(time_close_behind_s), 3) AS time_close_behind_s,
    ROUND(SUM(time_measured_s), 3) AS time_measured_s,
    ROUND(SUM(time_close_behind_s) / NULLIF(SUM(time_measured_s), 0), 4) AS share_time_close_behind,
    SUM(n_laps_within_1s) AS n_laps_within_1s,
    ROUND(SUM(n_laps_within_1s)::DOUBLE / NULLIF(SUM(n_laps_measured), 0), 4) AS bunching_share,

    ROUND(SUM(n_laps_lapped)::DOUBLE / SUM(n_laps), 4) AS share_laps_lapped,
    ROUND(SUM(n_laps_overlapping)::DOUBLE / SUM(n_laps), 4) AS share_laps_overlapping,
    ROUND(SUM(n_laps_unknown)::DOUBLE / SUM(n_laps), 4) AS share_laps_unknown,
    ROUND(SUM(n_laps_measured)::DOUBLE / SUM(n_laps), 4) AS share_laps_measured,

    SUM(n_ahead_flips) AS n_ahead_flips,
    SUM(n_ahead_pairs) AS n_ahead_pairs,
    ROUND(SUM(n_ahead_flips)::DOUBLE / NULLIF(SUM(n_ahead_pairs), 0), 5) AS identity_flip_rate
FROM {{ ref('int_traffic_exposure_driver_race') }}
GROUP BY race_id
