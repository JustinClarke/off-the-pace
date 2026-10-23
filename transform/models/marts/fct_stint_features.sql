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
--
-- Survival columns: is_censored_stint, end_regime, stint_end_cause,
-- end_cause_confidence, is_stint_life_censored and reached_flag all come from
-- int_stint_end_regime -- see that model for the precedence rule that assigns
-- the cause and for the two label rules (CO-09, D5/D6).
--
-- CO-09 (D4): stint_id is a tyre run (int_stint_geometry), so a stint split by
-- a same-tyre drive-through or red-flag pause is one row here, and
-- stint_length_laps is the run's length.

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
        MIN(age_in_stint) - 1 AS starting_tyre_age_laps
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY stint_id, race_year, race_id, driver_id
),

-- Why each stint ended, and whether it is right-censored. Both come from
-- int_stint_end_regime, which owns the definitions: is_censored_stint (the
-- driver's last stint of the race, so it ended at the flag or at retirement
-- rather than at a tyre change) and the end-cause label built on top of it.
-- 28.8% of the stints this table calls uncensored ended under a safety car,
-- VSC or red flag rather than at a tyre limit, so a consumer fitting stint
-- life reads stint_end_cause as well as the censoring flag.
stint_end AS (
    SELECT
        stint_id,
        is_censored_stint,
        end_regime,
        stint_end_cause,
        end_cause_confidence,
        is_stint_life_censored,
        reached_flag
    FROM {{ ref('int_stint_end_regime') }}
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

-- CO-09 (owner-approved 2026-10-24): what a cut-short run showed before it
-- was cut. Since D6 a run that ended in a safety-car or VSC stop is censored
-- for stint life, so its length says nothing about the tyre's limit; what it
-- does say is how fast the tyre was going off when the stop came. These are
-- STORED ONLY -- no model reads them as a training feature in this change.
--
-- tyre_age_at_fit is the TyreLife age on the run's first lap (the age already
-- on the set when it was fitted, + 1 for the first lap), i.e. the same reading
-- starting_tyre_age_laps takes (MIN(age) - 1); it equals
-- starting_tyre_age_laps + 1 wherever the first lap carries an age. FastF1's
-- FreshTyre flag is unreliable, so fresh_at_fit is derived from the age and
-- the raw flag is carried separately as is_fresh_tyre_raw.
--
-- Pace on clean laps: "clean" is the existing is_valid_lap rule; the time is
-- int_lap_fuel_state.weight_corrected_lap_time (the project's fuel model:
-- season fuel limit burned evenly over the scheduled distance, times the
-- circuit's weight_penalty_factor), regressed on tyre age.
run_fit AS (
    SELECT
        sg.stint_id,
        MIN(CASE WHEN sg.lap_in_stint = 1 THEN sg.age_in_stint END)
            AS tyre_age_at_fit,
        BOOL_OR(CASE WHEN sg.lap_in_stint = 1 THEN sl.is_fresh_tyre END)
            AS is_fresh_tyre_raw,
        COUNT(*) FILTER (WHERE sg.is_valid_lap) AS clean_laps,
        REGR_SLOPE(fs.weight_corrected_lap_time, sg.age_in_stint) FILTER (
            WHERE sg.is_valid_lap
        ) AS clean_slope_s_per_lap,
        AVG(fs.weight_corrected_lap_time) FILTER (
            WHERE sg.is_valid_lap
        ) AS clean_mean_pace_s
    FROM {{ ref('int_stint_geometry') }} AS sg
    INNER JOIN {{ ref('stg_laps') }} AS sl ON sg.lap_id = sl.lap_id
    LEFT JOIN {{ ref('int_lap_fuel_state') }} AS fs ON sg.lap_id = fs.lap_id
    GROUP BY sg.stint_id
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
    -- clamp_or_null, not GREATEST(LEAST(...)): end_residual_s comes through a
    -- LEFT JOIN, and DuckDB's LEAST skips a NULL argument, so a stint with a
    -- cost and no residual row would have scored +3.0 rather than NULL (0 such
    -- stints on the 2026-09-24 dev build; WI-13).
    CASE
        WHEN ps.opportunity_cost_s IS NOT NULL AND ps.opportunity_cost_s > 0
            THEN
                {{ clamp_or_null(
                    'llr.end_residual_s / NULLIF(ps.opportunity_cost_s, 0)',
                    -3.0, 3.0) }}
    END AS tyre_management_score,
    sc.end_of_stint_pace_falloff_s_per_lap,
    sa.stint_length_laps < 3 AS short_stint_flag,
    ps.pit_decision_class,
    se.is_censored_stint,
    se.end_regime,
    se.stint_end_cause,
    se.end_cause_confidence,
    se.is_stint_life_censored,
    se.reached_flag,
    -- CO-09 cut-short fields (see run_fit). The first four are filled on every
    -- run; the pace fields only on a run cut short by a safety-car or VSC stop
    -- (stint_end_cause sc_pit / vsc_pit), NULL otherwise. Not model features.
    sa.stint_length_laps AS laps_completed,
    rf.tyre_age_at_fit,
    rf.tyre_age_at_fit <= 1 AS fresh_at_fit,
    rf.is_fresh_tyre_raw,
    CASE
        WHEN se.stint_end_cause IN ('sc_pit', 'vsc_pit') THEN rf.clean_laps
    END AS clean_laps_to_cut,
    CASE
        WHEN
            se.stint_end_cause IN ('sc_pit', 'vsc_pit') AND rf.clean_laps >= 5
            THEN rf.clean_slope_s_per_lap
    END AS slope_to_cut_s_per_lap,
    CASE
        WHEN se.stint_end_cause IN ('sc_pit', 'vsc_pit')
            THEN rf.clean_mean_pace_s
    END AS mean_clean_pace_s,
    CASE
        WHEN se.stint_end_cause IN ('sc_pit', 'vsc_pit')
            THEN se.stint_end_cause
    END AS cut_reason,
    -- clean_laps >= 5, and a slope exists: a quarantined unit (stg_lap_tyre_qa
    -- serves no tyre age) has clean laps but nothing to regress on (11 runs on
    -- the 2026-10-22 dev build), so it is not called reliable.
    CASE
        WHEN se.stint_end_cause IN ('sc_pit', 'vsc_pit')
            THEN
                rf.clean_laps >= 5
                AND rf.clean_slope_s_per_lap IS NOT NULL
    END AS slope_reliable
FROM stint_aggregates AS sa
LEFT JOIN constructor_per_stint AS cs ON sa.stint_id = cs.stint_id
LEFT JOIN thermal_last AS ta ON sa.stint_id = ta.stint_id
LEFT JOIN dirty_air_agg AS da ON sa.stint_id = da.stint_id
LEFT JOIN cliff_agg AS ca ON sa.stint_id = ca.stint_id
LEFT JOIN slope_calc AS sc ON sa.stint_id = sc.stint_id
LEFT JOIN last_lap_residual AS llr ON sa.stint_id = llr.stint_id
LEFT JOIN pit_strategy AS ps ON sa.stint_id = ps.stint_id
INNER JOIN stint_end AS se ON sa.stint_id = se.stint_id
LEFT JOIN run_fit AS rf ON sa.stint_id = rf.stint_id
ORDER BY sa.race_year, sa.race_id, sa.driver_id
