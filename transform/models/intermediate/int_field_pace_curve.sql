-- Layer 04: Field pace reference curve per race.
-- Trimmed mean (10%) of weight-corrected lap times over eligible laps at each
-- lap number, then smoothed with a 5-lap centred rolling average.
-- Eligible laps: not out/in-laps, within 107% of fastest lap, free or tow air.
-- Used downstream as the base against which rubber/ambient components are
-- extracted.
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

-- Fastest lap per race (for 107% filter)
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
        -- no out-laps
        g.valid_lap_in_stint > 1
        AND g.valid_lap_in_stint < g.stint_length_valid - 1        -- no in-laps
        -- no major incident laps
        AND f.lap_time_s < 1.07 * rf.race_fastest_lap_s
        AND a.air_state_dominant IN ('free_air', 'tow_zone')       -- clean air
        AND f.weight_corrected_lap_time IS NOT NULL
),

-- Pre-compute percent rank so it can be used as a filter in the aggregation
-- operation
eligible_ranked AS (
    SELECT
        *,
        PERCENT_RANK() OVER (
            PARTITION BY race_year, race_id, lap_number
            ORDER BY weight_corrected_lap_time
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
        AVG(weight_corrected_lap_time) FILTER (
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
