-- Layer 04: Field pace reference curve per race.
-- Trimmed mean (10%) of fuel- and compound-corrected lap times over eligible
-- laps at each lap number, then smoothed with a 5-lap centred rolling average.
-- Eligible laps: not out-laps; not the last two valid laps of a non-final
-- stint (the in-lap rule: the pit in-lap itself is already not a valid lap, and
-- the lap before it is dropped as well; the final stint keeps every lap);
-- within per-lap 107% of fastest lap; free or tow air; known tyre cost.
-- Used downstream as the base against which driver skill residuals are
-- measured. The base is neutral to both fuel and compound (subtracted once
-- here, not again downstream).
{{ config(materialized='table') }}

WITH fuel_state AS (
    SELECT
        stint_id,
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        weight_corrected_lap_time
    FROM {{ ref('int_lap_fuel_state') }}
),

geom AS (
    SELECT
        stint_id,
        lap_id,
        valid_lap_in_stint,
        stint_length_valid
    FROM {{ ref('int_stint_geometry') }}
),

air AS (
    SELECT lap_id, air_state_dominant
    FROM {{ ref('int_lap_air_state') }}
),

-- Compound correction from the cliff model
compound AS (
    SELECT
        lap_id,
        expected_compound_pace_s
    FROM {{ ref('int_compound_cliff_predicted') }}
),

-- Fastest lap per race per lap_number (for per-lap 107% filter)
per_lap_fastest AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        MIN(lap_time_s) AS per_lap_fastest_lap_s
    FROM fuel_state
    GROUP BY race_year, race_id, lap_number
),

-- Identify final stint per driver per race (to preserve final-stint laps).
-- Picked by the stint_id that holds the driver's highest lap_number, not
-- MAX(stint_id): stint_id is 'YYYY_race_driver_N' (int_stint_geometry), a
-- string, so MAX() would pick stint_number 9 over 10 for any driver with
-- double-digit stops (rare, but a multi-stop chaos race is exactly where the
-- final-stint carve-out matters most).
final_stint_per_driver AS (
    SELECT race_year, race_id, driver_id, stint_id AS final_stint_id
    FROM fuel_state
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
        -- Compound-corrected lap time: weight-corrected minus compound cost.
        -- No COALESCE: a lap with an unknown tyre cost (F39, unknown tyre
        -- age) is dropped from the baseline below rather than entering it as
        -- a free 0 s tyre (2,756 laps on the 2026-09-27 build).
        f.weight_corrected_lap_time - c.expected_compound_pace_s
            AS compound_corrected_lap_time
    FROM fuel_state AS f
    INNER JOIN geom AS g ON f.lap_id = g.lap_id
    INNER JOIN air AS a ON f.lap_id = a.lap_id
    INNER JOIN per_lap_fastest AS plf
        ON
            f.race_year = plf.race_year
            AND f.race_id = plf.race_id
            AND f.lap_number = plf.lap_number
    LEFT JOIN final_stint_per_driver AS fsd
        ON
            f.race_year = fsd.race_year
            AND f.race_id = fsd.race_id
            AND f.driver_id = fsd.driver_id
    LEFT JOIN compound AS c ON f.lap_id = c.lap_id
    WHERE
        -- no out-laps
        g.valid_lap_in_stint > 1
        -- no in-laps, except for final stint which keeps all laps
        AND (
            f.stint_id = fsd.final_stint_id
            OR g.valid_lap_in_stint < g.stint_length_valid - 1
        )
        -- per-lap 107% of fastest lap for that lap_number (handles
        -- mixed-condition races)
        AND f.lap_time_s < 1.07 * plf.per_lap_fastest_lap_s
        AND a.air_state_dominant IN ('free_air', 'tow_zone')       -- clean air
        AND f.weight_corrected_lap_time IS NOT NULL
        -- WI-01: unknown tyre cost stays out of the baseline (see above)
        AND c.expected_compound_pace_s IS NOT NULL
),

-- Pre-compute percent rank so it can be used as a filter in the aggregation
-- operation
eligible_ranked AS (
    SELECT
        *,
        PERCENT_RANK() OVER (
            PARTITION BY race_year, race_id, lap_number
            ORDER BY compound_corrected_lap_time
        ) AS pct_rank
    FROM eligible
),

-- Trimmed mean per race × lap_number (10% trim = drop top and bottom 10%)
trimmed AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        COUNT(*) AS eligible_lap_count,
        AVG(compound_corrected_lap_time) FILTER (
            WHERE pct_rank BETWEEN 0.10 AND 0.90
        )
            AS field_pace_trimmed_mean_s
    FROM eligible_ranked
    GROUP BY race_year, race_id, lap_number
),

smoothed AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        eligible_lap_count,
        field_pace_trimmed_mean_s,
        -- 5-lap centred rolling average for rubber gradient extraction
        AVG(field_pace_trimmed_mean_s) OVER (
            PARTITION BY race_year, race_id
            ORDER BY lap_number
            ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING
        ) AS field_pace_smoothed_s
    FROM trimmed
)

SELECT
    race_year,
    race_id,
    lap_number,
    eligible_lap_count,
    field_pace_trimmed_mean_s,
    field_pace_smoothed_s,
    eligible_lap_count < 5 AS low_sample_flag
FROM smoothed
ORDER BY race_year, race_id, lap_number
