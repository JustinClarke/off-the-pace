-- Regression guard for a raw-vs-fuel-corrected baseline mismatch:
-- field_pace_smoothed_s is a trimmed mean of fuel- AND compound-corrected
-- lap times (WI-01/F38) over the SAME "eligible" population defined here
-- (mirrors int_field_pace_curve.sql's `eligible` CTE: no out-laps, no
-- in-laps except the final stint (F1), within per-lap 107% of the fastest
-- lap at that lap_number (F1), free/tow air, known tyre cost). On that population,
-- compound-corrected weight_corrected_lap_time minus field_pace_smoothed_s
-- must not trend with race progress -- both sides are already in
-- fuel-AND-compound-corrected space.
--
-- Diffing *raw* lap_time_s (or fuel-only-corrected time) against this
-- fuel-and-compound-corrected curve instead would bake a deterministic
-- within-race trend into pace_delta_s (fuel burning off, or -- since WI-01 --
-- compound wear/cliff growing through a stint). This test buckets the
-- eligible panel into fifths of race distance and fails if any fifth's mean
-- deviates from the panel's global mean by more than 0.15s.
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
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        weight_corrected_lap_time
    FROM {{ ref('int_lap_fuel_state') }}
),

geom AS (
    SELECT lap_id, valid_lap_in_stint, stint_length_valid
    FROM {{ ref('int_stint_geometry') }}
),

air AS (
    SELECT lap_id, air_state_dominant
    FROM {{ ref('int_lap_air_state') }}
),

compound AS (
    SELECT lap_id, expected_compound_pace_s
    FROM {{ ref('int_compound_cliff_predicted') }}
),

per_lap_fastest AS (
    SELECT race_year, race_id, lap_number, MIN(lap_time_s) AS per_lap_fastest_lap_s
    FROM fuel_state
    GROUP BY race_year, race_id, lap_number
),

final_stint AS (
    SELECT race_year, race_id, driver_id, stint_id AS final_stint_id
    FROM {{ ref('int_lap_fuel_state') }}
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY race_year, race_id, driver_id
        ORDER BY lap_number DESC
    ) = 1
),

eligible AS (
    SELECT
        f.race_year,
        f.race_id,
        f.lap_number,
        f.weight_corrected_lap_time - c.expected_compound_pace_s
            AS compound_corrected_lap_time
    FROM fuel_state AS f
    INNER JOIN geom AS g ON f.lap_id = g.lap_id
    INNER JOIN air AS a ON f.lap_id = a.lap_id
    INNER JOIN per_lap_fastest AS plf
        ON f.race_year = plf.race_year
        AND f.race_id = plf.race_id
        AND f.lap_number = plf.lap_number
    LEFT JOIN final_stint AS fs
        ON f.race_year = fs.race_year
        AND f.race_id = fs.race_id
        AND f.driver_id = fs.driver_id
    LEFT JOIN compound AS c ON f.lap_id = c.lap_id
    WHERE
        g.valid_lap_in_stint > 1
        AND (f.stint_id = fs.final_stint_id OR g.valid_lap_in_stint < g.stint_length_valid - 1)
        AND f.lap_time_s < 1.07 * plf.per_lap_fastest_lap_s
        AND a.air_state_dominant IN ('free_air', 'tow_zone')
        AND f.weight_corrected_lap_time IS NOT NULL
        AND c.expected_compound_pace_s IS NOT NULL  -- unknown tyre cost stays out (WI-01)
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
        e.compound_corrected_lap_time - fp.field_pace_smoothed_s AS pace_delta_s,
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
