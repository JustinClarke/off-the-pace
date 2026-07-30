-- Regression guard for a raw-vs-fuel-corrected baseline mismatch:
-- field_pace_smoothed_s is a trimmed mean of weight_corrected_lap_time over
-- the SAME "eligible" population defined here (mirrors
-- int_field_pace_curve.sql's `eligible` CTE exactly: no out/in-laps, within
-- 107% of the race's fastest lap, free/tow air). On that population,
-- weight_corrected_lap_time minus field_pace_smoothed_s must not trend with
-- race progress -- both sides are already in fuel-corrected space.
--
-- Diffing *raw* lap_time_s against this fuel-corrected curve instead would
-- bake a deterministic +3.3s -> +0.7s within-race fuel trend into
-- pace_delta_s. This test buckets the eligible panel into fifths of race
-- distance and fails if any fifth's mean deviates from the panel's global
-- mean by more than 0.15s.
--
-- Note: this intentionally uses the curve's own eligible population, not the
-- looser clean_panel filters in int_driver_race_skill_loro /
-- int_constructor_structural_pace (correction_weight + rainfall_flag only,
-- no air-state restriction). Those consumers show a separate, legitimate
-- residual trend driven by dirty-air/traffic share being higher early in the
-- race (more bunched running) -- a real signal, not a units bug -- which
-- would make this same check spuriously fail on their broader panel.
WITH fuel_state AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        lap_number,
        lap_time_s,
        weight_corrected_lap_time
    FROM {{ ref('int_lap_fuel_state') }}
),

geom AS (
    SELECT lap_id, lap_in_stint, stint_length_actual
    FROM {{ ref('int_stint_geometry') }}
),

air AS (
    SELECT lap_id, air_state_dominant
    FROM {{ ref('int_lap_air_state') }}
),

race_fastest AS (
    SELECT race_year, race_id, MIN(lap_time_s) AS race_fastest_lap_s
    FROM fuel_state
    GROUP BY race_year, race_id
),

eligible AS (
    SELECT
        f.race_year,
        f.race_id,
        f.lap_number,
        f.weight_corrected_lap_time
    FROM fuel_state AS f
    INNER JOIN geom AS g ON f.lap_id = g.lap_id
    INNER JOIN air AS a ON f.lap_id = a.lap_id
    INNER JOIN race_fastest AS rf
        ON f.race_year = rf.race_year AND f.race_id = rf.race_id
    WHERE
        g.lap_in_stint > 1
        AND g.lap_in_stint < g.stint_length_actual - 1
        AND f.lap_time_s < 1.07 * rf.race_fastest_lap_s
        AND a.air_state_dominant IN ('free_air', 'tow_zone')
        AND f.weight_corrected_lap_time IS NOT NULL
),

field_pace AS (
    SELECT race_year, race_id, lap_number, field_pace_smoothed_s
    FROM {{ ref('int_field_pace_curve') }}
    WHERE field_pace_smoothed_s IS NOT NULL
),

race_laps AS (
    SELECT race_year, race_id, MAX(lap_number) AS max_lap_number
    FROM eligible
    GROUP BY race_year, race_id
),

panel AS (
    SELECT
        e.weight_corrected_lap_time - fp.field_pace_smoothed_s AS pace_delta_s,
        LEAST(
            4,
            CAST(
                FLOOR(
                    5.0 * CAST(e.lap_number AS DOUBLE)
                    / NULLIF(rl.max_lap_number, 0)
                ) AS INTEGER
            )
        ) AS race_fifth
    FROM eligible AS e
    INNER JOIN field_pace AS fp
        ON
            e.race_year = fp.race_year
            AND e.race_id = fp.race_id
            AND e.lap_number = fp.lap_number
    INNER JOIN race_laps AS rl
        ON e.race_year = rl.race_year AND e.race_id = rl.race_id
),

by_fifth AS (
    SELECT race_fifth, AVG(pace_delta_s) AS mean_pace_delta_s
    FROM panel
    GROUP BY race_fifth
),

overall AS (
    SELECT AVG(pace_delta_s) AS global_mean_pace_delta_s
    FROM panel
)

SELECT
    b.race_fifth,
    b.mean_pace_delta_s,
    o.global_mean_pace_delta_s,
    ABS(b.mean_pace_delta_s - o.global_mean_pace_delta_s) AS deviation_s
FROM by_fifth AS b
CROSS JOIN overall AS o
WHERE ABS(b.mean_pace_delta_s - o.global_mean_pace_delta_s) > 0.15
