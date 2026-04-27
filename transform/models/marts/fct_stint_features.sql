-- Second Model Sequence #9 Part 2 (Third iteration backfill): Stint-grain feature table for pit strategy modelling.
-- Grain: stint_id one row per stint.
-- PK: stint_id (from int_stint_geometry).
--
-- Aggregates: stint length, compound, starting tyre age, end-of-stint thermal load,
-- cumulative dirty air tax, first cliff lap, and OLS pace falloff slope (last 3 laps).
--
-- Third iteration backfill:
--   pit_decision_class: from int_pit_strategy_value (strategy_verdict).
--   tyre_management_score: actual end-of-stint residual / expected (from int_pit_strategy_value context).

{{ config(materialized='table', tags=['marts', 'feature_engineering', 'simulation']) }}

WITH stint_aggregates AS (
    SELECT
        stint_id,
        race_year,
        race_id,
        driver_id,
        MAX(lap_in_stint)           AS stint_length_laps,
        MAX(compound_in_stint)      AS compound,
        MIN(age_in_stint)-1       AS starting_tyre_age_laps
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY stint_id, race_year, race_id, driver_id
),

constructor_per_stint AS (
    SELECT
        sg.stint_id,
        sl.constructor_id
    FROM {{ ref('int_stint_geometry') }} sg
    JOIN {{ ref('stg_laps') }} sl USING (lap_id)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY sg.stint_id ORDER BY sg.lap_in_stint) = 1
),

thermal_last AS (
    SELECT
        sg.stint_id,
        tp.cumulative_push_load_bulk AS cumulative_thermal_load_end
    FROM {{ ref('int_stint_geometry') }} sg
    LEFT JOIN {{ ref('int_lap_thermal_proxy') }} tp USING (lap_id)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY sg.stint_id ORDER BY sg.lap_in_stint DESC) = 1
),

dirty_air_agg AS (
    SELECT
        sg.stint_id,
        SUM(da.dirty_air_tax_s) AS cumulative_dirty_air_tax_s
    FROM {{ ref('int_stint_geometry') }} sg
    LEFT JOIN {{ ref('int_dirty_air_tax_component') }} da USING (lap_id)
    GROUP BY sg.stint_id
),

cliff_agg AS (
    SELECT
        sg.stint_id,
        MIN(CASE WHEN af.cliff_candidate_flag = TRUE THEN sg.lap_in_stint ELSE NULL END)
            AS cliff_lap_in_stint
    FROM {{ ref('int_stint_geometry') }} sg
    LEFT JOIN {{ ref('int_lap_anomaly_flags') }} af USING (lap_id)
    GROUP BY sg.stint_id
),

last_3_laps AS (
    SELECT
        sg.stint_id,
        sg.lap_in_stint,
        lr.driver_skill_residual_s
    FROM {{ ref('int_stint_geometry') }} sg
    JOIN {{ ref('int_lap_residual_decomposed') }} lr USING (lap_id)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY sg.stint_id ORDER BY sg.lap_in_stint DESC) <= 3
),

slope_means AS (
    SELECT
        stint_id,
        AVG(lap_in_stint)              AS mean_x,
        AVG(driver_skill_residual_s)   AS mean_y,
        COUNT(*)                       AS n_laps
    FROM last_3_laps
    GROUP BY stint_id
),

-- End-of-stint driver residual (last valid lap)
last_lap_residual AS (
    SELECT
        sg.stint_id,
        lr.driver_skill_residual_s AS end_residual_s
    FROM {{ ref('int_stint_geometry') }} sg
    JOIN {{ ref('int_lap_residual_decomposed') }} lr USING (lap_id)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY sg.stint_id ORDER BY sg.lap_in_stint DESC) = 1
),

-- Pit strategy verdicts from Third iteration #1
pit_strategy AS (
    SELECT
        stint_id,
        strategy_verdict                         AS pit_decision_class,
        opportunity_cost_s,
        optimal_pit_lap,
        actual_pit_lap
    FROM {{ ref('int_pit_strategy_value') }}
),

slope_calc AS (
    SELECT
        l.stint_id,
        sm.n_laps,
        CASE
            WHEN sm.n_laps < 3
                THEN NULL
            ELSE
                SUM((l.lap_in_stint-sm.mean_x) * (l.driver_skill_residual_s-sm.mean_y))
                / NULLIF(SUM(POWER(l.lap_in_stint-sm.mean_x, 2)), 0)
        END AS end_of_stint_pace_falloff_s_per_lap
    FROM last_3_laps l
    JOIN slope_means sm USING (stint_id)
    GROUP BY l.stint_id, sm.n_laps
)

SELECT
    sa.stint_id,
    sa.driver_id,
    sa.race_id,
    sa.race_year,
    cs.constructor_id,
    sa.stint_length_laps,
    sa.compound,
    sa.starting_tyre_age_laps,
    ta.cumulative_thermal_load_end,
    COALESCE(da.cumulative_dirty_air_tax_s, 0.0) AS cumulative_dirty_air_tax_s,
    ca.cliff_lap_in_stint,
    -- tyre_management_score: actual end-of-stint residual normalised to opportunity cost.
    -- Low score = good management (held pace well). NULL when no pit strategy data.
    CASE
        WHEN ps.opportunity_cost_s IS NOT NULL AND ps.opportunity_cost_s > 0
            THEN LEAST(llr.end_residual_s / NULLIF(ps.opportunity_cost_s, 0), 3.0)
        ELSE NULL
    END                                           AS tyre_management_score,
    sc.end_of_stint_pace_falloff_s_per_lap,
    sa.stint_length_laps < 3                      AS short_stint_flag,
    ps.pit_decision_class
FROM stint_aggregates sa
LEFT JOIN constructor_per_stint cs    USING (stint_id)
LEFT JOIN thermal_last ta             USING (stint_id)
LEFT JOIN dirty_air_agg da            USING (stint_id)
LEFT JOIN cliff_agg ca                USING (stint_id)
LEFT JOIN slope_calc sc               USING (stint_id)
LEFT JOIN last_lap_residual llr       USING (stint_id)
LEFT JOIN pit_strategy ps             USING (stint_id)
ORDER BY race_year, race_id, driver_id
