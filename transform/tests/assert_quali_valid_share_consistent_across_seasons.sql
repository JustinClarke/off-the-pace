-- T25 (WI-05, F33). No season's qualifying laps are dropped by a technical gate
-- that the other seasons pass.
--
-- stg_laps_qualifying's validity gate required IsAccurate, FastF1's lap
-- start/end sync flag. 2018 largely does not populate it: 26% of 2018's timed
-- quali laps failed it against <= 0.4% for 2019-2025, leaving 2018 with 8% NULL
-- quali features (<= 2% elsewhere) and 2018_1 with 11 of 20 drivers on no valid
-- lap at all.
--
-- The share is taken over laps that pass every OTHER gate -- timed, not a pit
-- lap, not deleted, green track status, not lap 1 -- so a wet or red-flagged
-- session (legitimately few valid laps) cannot trip it; what is left is the loss
-- to technical gates alone. Each season must sit within 0.05 of the median of
-- the other seasons.
-- (The audit specified this as an extension of snapshot_data_profile.py; it is a
-- cross-season invariant rather than a build-over-build diff, and that script's
-- --check is red on an outdated baseline (F11), so it lives here, where it gates.)

WITH otherwise_valid AS (
    SELECT
        race_year,
        is_valid_lap
    FROM {{ ref('stg_laps_qualifying') }}
    WHERE
        lap_time_s > 0
        AND NOT is_pit_lap
        AND NOT COALESCE(is_deleted, FALSE)
        AND NOT REGEXP_MATCHES(track_status, '.*[4567].*')
        AND lap_number > 1
),

per_season AS (
    SELECT
        race_year,
        AVG(CASE WHEN is_valid_lap THEN 1.0 ELSE 0.0 END) AS valid_share
    FROM otherwise_valid
    GROUP BY race_year
),

against_others AS (
    SELECT
        s.race_year,
        s.valid_share,
        (
            SELECT MEDIAN(o.valid_share) FROM per_season AS o
            WHERE o.race_year <> s.race_year
        ) AS others_median
    FROM per_season AS s
)

SELECT
    'season_quali_valid_share_out_of_line' AS check_name,
    race_year || ': ' || ROUND(valid_share, 4) || ' vs other seasons '
    || ROUND(others_median, 4) AS detail
FROM against_others
WHERE others_median IS NOT NULL AND ABS(valid_share - others_median) > 0.05
