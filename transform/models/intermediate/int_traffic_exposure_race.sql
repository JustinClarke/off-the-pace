-- int_traffic_exposure_race.sql · intermediate · grain: one row per race_id
--
-- MEASUREMENT ONLY. Field-level roll-up of int_traffic_exposure_driver_race: how bunched the race was and how
-- much of it could not be measured cleanly. Descriptive columns only: no time loss, no dirty-air seconds,
-- no tax. Shares are pooled over laps (or measured seconds), not averages of driver shares.
-- identity_flip_rate is the known car-ahead flip rate (experiments 26-28), carried so a reader can see it.
-- Not wired to any page.
--
-- READ THE SHARES AS CONDITIONAL. share_time_close_behind and bunching_share are over MEASURED laps only
-- (valid_same_lap, not neutralised). Lapped, overlapping, side_by_side, lap1, neutralised and unknown laps are
-- outside the denominator and are published as their own share_laps_* columns; the headline is NOT adjusted for
-- them. Where lapped traffic dominates, the headline describes the lead-lap subset of the race.
--
-- Quality columns (added, nothing filtered): is_low_measured_share / quality_flag mark races whose measured-lap
-- share is below var traffic_exposure_min_measured_share (default 0.25, a provisional floor, not tuned).
-- zero_xy_guard_on records whether the unvalidated X=Y=0 guard was applied (default off; Singapore 2019 is
-- expected to be low-quality with it off). The model is NOT validated end to end: the 94% sample-grain gate is
-- only a script (scripts/check_physical_ahead_agreement.py) and 8 of 170 races failed it on 2026-11-09.
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
    ROUND(SUM(n_ahead_flips)::DOUBLE / NULLIF(SUM(n_ahead_pairs), 0), 5) AS identity_flip_rate,

    -- unmeasured shares not already above (all as a share of all laps)
    ROUND(SUM(n_laps_neutralised)::DOUBLE / SUM(n_laps), 4) AS share_laps_neutralised,
    ROUND(SUM(n_laps_lap1)::DOUBLE / SUM(n_laps), 4) AS share_laps_lap1,
    ROUND(SUM(n_laps_side_by_side)::DOUBLE / SUM(n_laps), 4) AS share_laps_side_by_side,

    -- race quality flag (measurement-only, no rows removed)
    SUM(n_laps_measured)::DOUBLE / SUM(n_laps) < {{ var('traffic_exposure_min_measured_share', 0.25) }}
        AS is_low_measured_share,
    CASE
        WHEN SUM(n_laps_measured) = 0 THEN 'no_measured_laps'
        WHEN SUM(n_laps_measured)::DOUBLE / SUM(n_laps) < {{ var('traffic_exposure_min_measured_share', 0.25) }}
            THEN 'low_measured_share'
        ELSE 'ok'
    END AS quality_flag,
    {{ var('traffic_exposure_min_measured_share', 0.25) }} AS min_measured_share_floor,
    BOOL_OR(zero_xy_guard_on) AS zero_xy_guard_on,

    -- LAPPED TAG (added; headline columns above are unchanged). See int_traffic_exposure_driver_race.
    ROUND(SUM(lapped_time_close_behind_s), 3) AS lapped_time_close_behind_s,
    ROUND(SUM(lapped_time_measured_s), 3) AS lapped_time_measured_s,
    ROUND(SUM(lapped_time_close_behind_s) / NULLIF(SUM(lapped_time_measured_s), 0), 4)
        AS lapped_share_time_close_behind,
    SUM(n_laps_lapped_within_1s) AS n_laps_lapped_within_1s
FROM {{ ref('int_traffic_exposure_driver_race') }}
GROUP BY race_id
