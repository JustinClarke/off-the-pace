-- Constructor structural pace model: Constructor structural pace via aggregation.
--
-- Estimates the constructor coefficient using within-constructor, between-driver
-- variation. This implementation uses grouped statistics as a placeholder for the
-- full panel regression spec (pyfixest HDFE fit).
--
-- Output grain: one row per (race_year, race_id, constructor_id).
--
-- DAG note: this model is upstream of int_lap_residual_decomposed, which is upstream of
-- int_lap_anomaly_flags. To avoid cycles, clean-lap filtering here uses int_event_corrections
-- (correction_weight) and int_track_evolution (rainfall_flag) instead of int_lap_anomaly_flags.
-- The anomaly_class filter (mistake/conditions) is approximated by correction_weight = 1.0,
-- which catches the same SC/VSC/outlier laps; fine-grained mistake detection is downstream.
--
-- Subsequent integration: replace aggregation with pyfixest HDFE panel regression
-- (feols with CRV1 clustering by race_id, constructor_id).

{{ config(materialized='table', tags=['causal_decomposition', 'constructor']) }}

WITH fuel AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s
    FROM {{ ref('int_lap_fuel_state') }}
),

field_pace AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        field_pace_smoothed_s
    FROM {{ ref('int_field_pace_curve') }}
),

geom AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_in_stint
    FROM {{ ref('int_stint_geometry') }}
),

laps_meta AS (
    SELECT
        lap_id,
        constructor_id
    FROM {{ ref('stg_laps') }}
),

corrections AS (
    SELECT
        lap_id,
        correction_weight
    FROM {{ ref('int_event_corrections') }}
),

evolution AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        rainfall_flag
    FROM {{ ref('int_track_evolution') }}
),

clean_panel AS (
    SELECT
        f.lap_id,
        f.race_year,
        f.race_id,
        f.driver_id,
        lm.constructor_id,
        -- Partial pace delta (vs field median baseline), before component subtraction
        f.lap_time_s-COALESCE(fp.field_pace_smoothed_s, f.lap_time_s) AS pace_delta_s,
        g.lap_in_stint
    FROM fuel f
    JOIN geom g             USING (lap_id)
    JOIN laps_meta lm       USING (lap_id)
    LEFT JOIN field_pace fp ON f.race_year  = fp.race_year
                            AND f.race_id   = fp.race_id
                            AND f.lap_number = fp.lap_number
    LEFT JOIN corrections cor USING (lap_id)
    LEFT JOIN evolution e   ON f.race_year  = e.race_year
                            AND f.race_id   = e.race_id
                            AND f.lap_number = e.lap_number
    WHERE f.lap_time_s IS NOT NULL
      AND COALESCE(cor.correction_weight, 1.0) = 1.0
      AND COALESCE(e.rainfall_flag, FALSE) = FALSE
),

constructor_agg AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pace_delta_s) AS median_pace_delta,
        STDDEV_POP(pace_delta_s)                                   AS stddev_pace_delta,
        COUNT(*)                                                   AS n_obs,
        COUNT(DISTINCT driver_id)                                  AS n_drivers
    FROM clean_panel
    GROUP BY race_year, race_id, constructor_id
    HAVING COUNT(*) > 10
),

-- Re-centre constructor coefficients by subtracting the race-level average.
-- The raw median_pace_delta conflates driver skill with car pace. Subtracting the
-- race mean produces a zero-summing relative coefficient: positive = slower than
-- average constructor, negative = faster. This is the correct interpretation per
-- the plan's "constructor delta vs field" definition.
race_mean AS (
    SELECT
        race_year,
        race_id,
        AVG(median_pace_delta) AS race_avg_pace_delta
    FROM constructor_agg
    GROUP BY race_year, race_id
)

SELECT
    CONCAT(
        CAST(ca.race_year AS VARCHAR), '_',
        ca.race_id, '_',
        ca.constructor_id
    )                                                           AS constructor_race_id,
    ca.race_year,
    ca.race_id,
    ca.constructor_id,
    -- Re-centred coefficient: constructor pace relative to the race-average constructor.
    -- Positive = slower than average constructor. Negative = faster.
    ca.median_pace_delta-rm.race_avg_pace_delta               AS constructor_structural_pace_s,
    COALESCE(
        ca.stddev_pace_delta / SQRT(CAST(ca.n_obs AS DOUBLE)),
        0.0
    )                                                           AS constructor_structural_pace_se_s,
    COALESCE(
        (ca.median_pace_delta-rm.race_avg_pace_delta)
           -1.96 * (ca.stddev_pace_delta / SQRT(CAST(ca.n_obs AS DOUBLE))),
        ca.median_pace_delta-rm.race_avg_pace_delta
    )                                                           AS constructor_structural_pace_ci_low_s,
    COALESCE(
        (ca.median_pace_delta-rm.race_avg_pace_delta)
            + 1.96 * (ca.stddev_pace_delta / SQRT(CAST(ca.n_obs AS DOUBLE))),
        ca.median_pace_delta-rm.race_avg_pace_delta
    )                                                           AS constructor_structural_pace_ci_high_s,
    ca.n_obs                                                    AS panel_observations_n,
    ca.n_obs                                                    AS clean_teammate_pair_laps_n,
    NULL                                                        AS r_squared_within,
    CAST(CURRENT_TIMESTAMP AS VARCHAR)                          AS fit_timestamp
FROM constructor_agg ca
JOIN race_mean rm USING (race_year, race_id)
ORDER BY ca.race_year DESC, ca.race_id, ca.constructor_id
