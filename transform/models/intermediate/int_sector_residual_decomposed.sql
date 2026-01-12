-- Second Model Sequence #4a: Sector-grain residual decomposition.
-- Allocates lap-level physics components proportionally to sector time.
-- Grain: (lap_id, sector) 3 rows per lap matching stg_sector_times.
-- PK: sector_id = lap_id || '_S' || sector (surrogate)
--
-- Identity (per sector):
--   sector_pace_delta_s = sector_fuel + sector_compound + sector_rubber
--                       + sector_ambient + sector_constructor + sector_dirty_air_tax
--                       + sector_driver_skill_residual_s
--
-- NOTE: constructor_component_s allocated proportionally (no power/aero split yet).
-- Subsequent integration: when int_constructor_structural_pace gains power_loading_s / aero_loading_s,
-- update allocation: power → S1+S3, aero → S2.
--
-- NOTE: dirty_air_share_lap is lap-level only (no per-sector breakdown available).
-- Proportional allocation used when > 0.

{{ config(materialized='table', tags=['intermediate', 'feature_engineering']) }}

WITH sector_times AS (
    SELECT
        st.sector_id,
        st.lap_id,
        st.race_year,
        st.race_id,
        st.driver_id,
        st.lap_number,
        st.sector,
        st.sector_time_s,
        sl.lap_time_s
    FROM {{ ref('stg_sector_times') }} st
    JOIN {{ ref('stg_laps') }} sl USING (lap_id)
    WHERE st.is_valid_lap = TRUE
      AND st.sector_time_s > 0
      AND sl.lap_time_s > 0
),

lap_components AS (
    SELECT
        lr.lap_id,
        lr.stint_id,
        lr.constructor_id,
        lr.fuel_component_s,
        lr.compound_component_s,
        lr.rubber_component_s,
        lr.ambient_component_s,
        lr.constructor_component_s,
        lr.dirty_air_tax_s,
        lr.correction_weight,
        COALESCE(air.dirty_air_share_lap, 0.0) AS dirty_air_share_lap
    FROM {{ ref('int_lap_residual_decomposed') }} lr
    LEFT JOIN {{ ref('int_lap_air_state') }} air USING (lap_id)
),

-- Self-join rolling ±3 lap median (DuckDB: MEDIAN not available as window function)
sector_all_drivers AS (
    SELECT
        race_year,
        race_id,
        sector,
        lap_number,
        sector_time_s
    FROM {{ ref('stg_sector_times') }}
    WHERE is_valid_lap = TRUE
      AND sector_time_s > 0
),

field_sector_pace AS (
    SELECT
        a.race_year,
        a.race_id,
        a.sector,
        a.lap_number,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY w.sector_time_s)
            AS field_sector_pace_smoothed_s,
        COUNT(w.sector_time_s) AS field_sector_sample_n
    FROM sector_all_drivers a
    JOIN sector_all_drivers w
        ON  a.race_year  = w.race_year
        AND a.race_id    = w.race_id
        AND a.sector     = w.sector
        AND w.lap_number BETWEEN a.lap_number-3 AND a.lap_number + 3
    GROUP BY a.race_year, a.race_id, a.sector, a.lap_number
),

joined AS (
    SELECT
        st.*,
        lc.stint_id,
        lc.constructor_id,
        lc.fuel_component_s,
        lc.compound_component_s,
        lc.rubber_component_s,
        lc.ambient_component_s,
        lc.constructor_component_s,
        lc.dirty_air_tax_s,
        lc.dirty_air_share_lap,
        fsp.field_sector_pace_smoothed_s
    FROM sector_times st
    JOIN lap_components lc ON st.lap_id = lc.lap_id
    LEFT JOIN field_sector_pace fsp
        ON  st.race_year  = fsp.race_year
        AND st.race_id    = fsp.race_id
        AND st.sector     = fsp.sector
        AND st.lap_number = fsp.lap_number
),

-- Allocating lap-level physics components to individual sectors.
-- 
-- The proportional allocation methodology:
--   For each physics component C (fuel, tyre deg, weather, etc.), we allocate it
--   proportionally to a sector's time share:
--     sector_component = lap_component * (sector_time / lap_time)
-- 
--   Since Sum_{s=1}^{3} (sector_time / lap_time) = 1.0, this mathematical property ensures
--   that the sum of the sector-grain components exactly equals the lap-grain component:
--     Sum_{s=1}^{3} sector_component = lap_component
-- 
--   Note on sector_pace_delta_s and field baselines:
--     sector_pace_delta_s is computed as (sector_time_s field_sector_pace_smoothed_s),
--     where field_sector_pace_smoothed_s is based on sector medians. Because the median of a sum
--     does not equal the sum of medians, the sector baseline SUM does not perfectly equal the lap
--     trimmed-mean baseline. The driver sector residual captures this difference.
allocated AS (
    SELECT
        *,
        sector_time_s / NULLIF(lap_time_s, 0)                           AS sector_time_share,
        sector_time_s-field_sector_pace_smoothed_s                     AS sector_pace_delta_s,
        fuel_component_s      * (sector_time_s / NULLIF(lap_time_s, 0)) AS sector_fuel_component_s,
        COALESCE(compound_component_s, 0.0) * (sector_time_s / NULLIF(lap_time_s, 0)) AS sector_compound_component_s,
        rubber_component_s    * (sector_time_s / NULLIF(lap_time_s, 0)) AS sector_rubber_component_s,
        ambient_component_s   * (sector_time_s / NULLIF(lap_time_s, 0)) AS sector_ambient_component_s,
        constructor_component_s * (sector_time_s / NULLIF(lap_time_s, 0)) AS sector_constructor_component_s,
        CASE
            WHEN COALESCE(dirty_air_share_lap, 0.0) > 0
                THEN dirty_air_tax_s * (sector_time_s / NULLIF(lap_time_s, 0))
            ELSE 0.0
        END                                                               AS sector_dirty_air_tax_s
    FROM joined
    WHERE field_sector_pace_smoothed_s IS NOT NULL
),

with_residual AS (
    SELECT
        *,
        sector_fuel_component_s
            + sector_compound_component_s
            + sector_rubber_component_s
            + sector_ambient_component_s
            + sector_constructor_component_s
            + sector_dirty_air_tax_s                                     AS sector_total_explained_s,
        sector_pace_delta_s
           -sector_fuel_component_s
           -sector_compound_component_s
           -sector_rubber_component_s
           -sector_ambient_component_s
           -sector_constructor_component_s
           -sector_dirty_air_tax_s                                     AS sector_driver_skill_residual_s
    FROM allocated
)

SELECT
    sector_id,
    lap_id,
    stint_id,
    race_year,
    race_id,
    driver_id,
    constructor_id,
    lap_number,
    sector,
    sector_time_s,
    sector_pace_delta_s,
    sector_fuel_component_s,
    sector_compound_component_s,
    sector_rubber_component_s,
    sector_ambient_component_s,
    sector_constructor_component_s,
    sector_dirty_air_tax_s,
    sector_driver_skill_residual_s,
    sector_total_explained_s,

    -- Dominant component: the one with largest absolute value
    CASE
        WHEN ABS(sector_fuel_component_s) = GREATEST(
                ABS(sector_fuel_component_s),
                ABS(sector_compound_component_s),
                ABS(sector_rubber_component_s),
                ABS(sector_ambient_component_s),
                ABS(sector_constructor_component_s),
                ABS(sector_dirty_air_tax_s))
            THEN 'fuel'
        WHEN ABS(sector_compound_component_s) = GREATEST(
                ABS(sector_fuel_component_s),
                ABS(sector_compound_component_s),
                ABS(sector_rubber_component_s),
                ABS(sector_ambient_component_s),
                ABS(sector_constructor_component_s),
                ABS(sector_dirty_air_tax_s))
            THEN 'compound'
        WHEN ABS(sector_rubber_component_s) = GREATEST(
                ABS(sector_fuel_component_s),
                ABS(sector_compound_component_s),
                ABS(sector_rubber_component_s),
                ABS(sector_ambient_component_s),
                ABS(sector_constructor_component_s),
                ABS(sector_dirty_air_tax_s))
            THEN 'rubber'
        WHEN ABS(sector_ambient_component_s) = GREATEST(
                ABS(sector_fuel_component_s),
                ABS(sector_compound_component_s),
                ABS(sector_rubber_component_s),
                ABS(sector_ambient_component_s),
                ABS(sector_constructor_component_s),
                ABS(sector_dirty_air_tax_s))
            THEN 'ambient'
        WHEN ABS(sector_constructor_component_s) = GREATEST(
                ABS(sector_fuel_component_s),
                ABS(sector_compound_component_s),
                ABS(sector_rubber_component_s),
                ABS(sector_ambient_component_s),
                ABS(sector_constructor_component_s),
                ABS(sector_dirty_air_tax_s))
            THEN 'constructor'
        ELSE 'dirty_air'
    END AS dominant_component_class,

    -- Sector consistency: within-race stddev for this driver-sector
    STDDEV(sector_driver_skill_residual_s) OVER (
        PARTITION BY race_id, driver_id, sector
    ) AS sector_consistency_index

FROM with_residual
ORDER BY race_year, race_id, driver_id, lap_number, sector
