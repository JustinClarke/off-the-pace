-- Stint-grain feature table for pit strategy modelling.
-- Grain: stint_id one row per stint.
-- PK: stint_id (from int_stint_geometry).
--
-- Aggregates: stint length, compound, starting tyre age, end-of-stint thermal
-- load,
-- cumulative dirty air tax, first cliff lap, and OLS pace falloff slope (last 3
-- laps).
--
-- Strategy columns:
--   pit_decision_class: from int_pit_strategy_value (strategy_verdict).
--   tyre_management_score: actual end-of-stint residual / expected (from
--   int_pit_strategy_value context).

{{ config(
    materialized='table', tags=['marts', 'feature_engineering', 'simulation']
) }}

WITH stint_aggregates AS (
    SELECT
        stint_id,
        race_year,
        race_id,
        driver_id,
        MAX(lap_in_stint) AS stint_length_laps,
        MAX(compound_in_stint) AS compound,
        MIN(age_in_stint) - 1 AS starting_tyre_age_laps,
        -- Functionally determined by stint_id (which encodes it); MAX is just
        -- the aggregate that carries it past the GROUP BY.
        MAX(stint_number) AS stint_number
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY stint_id, race_year, race_id, driver_id
),

-- Right-censoring for stint-life modelling. A driver's last stint of a race
-- ends at the chequered flag or at retirement, not at a tyre change: the tyre
-- still had life we never observed, so remaining_stint_life_laps on those laps
-- is a LOWER BOUND, not the truth. 46.2% of training rows sit on such a stint,
-- which is why the stint-life model is fitted with survival:aft over an
-- interval rather than squared error against a point. Anything that fits or
-- scores stint life must read this flag -- see ml/src/features.py.
censoring AS (
    SELECT
        stint_id,
        -- COALESCE, not a bare comparison: 325 stints in 2018 carry a NULL
        -- stint_number (343 laps FastF1 never assigned to a stint, 338 of them
        -- already invalid). CONCAT folds the NULL to '' when stint_id is built,
        -- so a driver-race has at most one such stint, and sorting it below
        -- every real stint says the true thing -- an unassigned lap is not the
        -- stint the driver finished on. Two drivers (2018_2 RIC, 2018_10 HAR)
        -- have no other stint, so theirs is both first and last and is marked
        -- censored, which keeps the flag a total partition. Left NULL instead,
        -- the flag would be neither TRUE nor FALSE and every join downstream
        -- would quietly drop those rows.
        COALESCE(stint_number, -1)
        = MAX(COALESCE(stint_number, -1)) OVER (PARTITION BY race_id, driver_id)
            AS is_censored_stint
    FROM stint_aggregates
),

constructor_per_stint AS (
    SELECT
        sg.stint_id,
        sl.constructor_id
    FROM {{ ref('int_stint_geometry') }} AS sg
    INNER JOIN {{ ref('stg_laps') }} AS sl ON sg.lap_id = sl.lap_id
    QUALIFY
        ROW_NUMBER() OVER (PARTITION BY sg.stint_id ORDER BY sg.lap_in_stint)
        = 1
),

thermal_last AS (
    SELECT
        sg.stint_id,
        tp.cumulative_push_load_bulk AS cumulative_thermal_load_end
    FROM {{ ref('int_stint_geometry') }} AS sg
    LEFT JOIN {{ ref('int_lap_thermal_proxy') }} AS tp ON sg.lap_id = tp.lap_id
    -- int_stint_geometry now carries the pit-in lap too, and chronologically
    -- it's almost always last — but it's invalid (no int_lap_thermal_proxy
    -- row), so ordering by raw lap_in_stint DESC picked it and joined to
    -- NULL for nearly every stint. Restrict to valid laps and order by the
    -- valid ordinal so this picks the actual last valid lap.
    WHERE sg.is_valid_lap = TRUE
    QUALIFY
        ROW_NUMBER()
            OVER (PARTITION BY sg.stint_id ORDER BY sg.valid_lap_in_stint DESC)
        = 1
),

dirty_air_agg AS (
    SELECT
        sg.stint_id,
        SUM(da.dirty_air_tax_s) AS cumulative_dirty_air_tax_s
    FROM {{ ref('int_stint_geometry') }} AS sg
    LEFT JOIN
        {{ ref('int_dirty_air_tax_component') }} AS da
        ON sg.lap_id = da.lap_id
    GROUP BY sg.stint_id
),

cliff_agg AS (
    SELECT
        sg.stint_id,
        MIN(
            CASE
                WHEN af.cliff_candidate_flag = TRUE THEN sg.lap_in_stint
            END
        )
            AS cliff_lap_in_stint
    FROM {{ ref('int_stint_geometry') }} AS sg
    LEFT JOIN {{ ref('int_lap_anomaly_flags') }} AS af ON sg.lap_id = af.lap_id
    GROUP BY sg.stint_id
),

last_3_laps AS (
    SELECT
        sg.stint_id,
        sg.valid_lap_in_stint,
        lr.driver_skill_residual_s
    FROM {{ ref('int_stint_geometry') }} AS sg
    INNER JOIN {{ ref('int_lap_residual_decomposed') }} AS lr
        ON sg.lap_id = lr.lap_id
    QUALIFY
        ROW_NUMBER()
            OVER (PARTITION BY sg.stint_id ORDER BY sg.lap_in_stint DESC)
        <= 3
),

slope_means AS (
    SELECT
        stint_id,
        AVG(valid_lap_in_stint) AS mean_x,
        AVG(driver_skill_residual_s) AS mean_y,
        COUNT(*) AS n_laps
    FROM last_3_laps
    GROUP BY stint_id
),

-- End-of-stint driver residual (last valid lap)
last_lap_residual AS (
    SELECT
        sg.stint_id,
        lr.driver_skill_residual_s AS end_residual_s
    FROM {{ ref('int_stint_geometry') }} AS sg
    INNER JOIN {{ ref('int_lap_residual_decomposed') }} AS lr
        ON sg.lap_id = lr.lap_id
    QUALIFY
        ROW_NUMBER()
            OVER (PARTITION BY sg.stint_id ORDER BY sg.lap_in_stint DESC)
        = 1
),

-- Pit strategy verdicts
pit_strategy AS (
    SELECT
        stint_id,
        strategy_verdict AS pit_decision_class,
        opportunity_cost_s,
        optimal_pit_lap,
        actual_pit_lap
    FROM {{ ref('int_pit_strategy_value') }}
),

slope_calc AS (
    -- Regress on valid_lap_in_stint, not chronological lap_in_stint: an SC
    -- gap between two of the trailing 3 laps would otherwise stretch the
    -- x-spacing and distort the fitted wear gradient.
    SELECT
        l.stint_id,
        sm.n_laps,
        CASE
            WHEN sm.n_laps < 3
                THEN NULL
            ELSE
                SUM(
                    (l.valid_lap_in_stint - sm.mean_x)
                    * (l.driver_skill_residual_s - sm.mean_y)
                )
                / NULLIF(SUM(POWER(l.valid_lap_in_stint - sm.mean_x, 2)), 0)
        END AS end_of_stint_pace_falloff_s_per_lap
    FROM last_3_laps AS l
    INNER JOIN slope_means AS sm ON l.stint_id = sm.stint_id
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
    -- tyre_management_score: actual end-of-stint residual normalised to
    -- opportunity cost.
    -- Low score = good management (held pace well). NULL when no pit strategy
    -- data.
    -- Clamped on BOTH sides. The ceiling was always here; the floor was not,
    -- and a ratio is unbounded in whichever direction its denominator
    -- approaches zero from. Once int_pit_strategy_value started returning a
    -- real argmin, small positive opportunity costs became ordinary (median
    -- 5.5 s where the overrun-only definition returned 0), and the score
    -- reached -3321.9 on a stint whose cost rounded to a few hundredths.
    -- Nothing tested it, because a one-sided clamp looks like a clamp.
    CASE
        WHEN ps.opportunity_cost_s IS NOT NULL AND ps.opportunity_cost_s > 0
            THEN
                GREATEST(
                    LEAST(
                        llr.end_residual_s
                        / NULLIF(ps.opportunity_cost_s, 0),
                        3.0
                    ),
                    -3.0
                )
    END AS tyre_management_score,
    sc.end_of_stint_pace_falloff_s_per_lap,
    sa.stint_length_laps < 3 AS short_stint_flag,
    ps.pit_decision_class,
    cen.is_censored_stint
FROM stint_aggregates AS sa
LEFT JOIN constructor_per_stint AS cs ON sa.stint_id = cs.stint_id
LEFT JOIN thermal_last AS ta ON sa.stint_id = ta.stint_id
LEFT JOIN dirty_air_agg AS da ON sa.stint_id = da.stint_id
LEFT JOIN cliff_agg AS ca ON sa.stint_id = ca.stint_id
LEFT JOIN slope_calc AS sc ON sa.stint_id = sc.stint_id
LEFT JOIN last_lap_residual AS llr ON sa.stint_id = llr.stint_id
LEFT JOIN pit_strategy AS ps ON sa.stint_id = ps.stint_id
INNER JOIN censoring AS cen ON sa.stint_id = cen.stint_id
ORDER BY sa.race_year, sa.race_id, sa.driver_id
