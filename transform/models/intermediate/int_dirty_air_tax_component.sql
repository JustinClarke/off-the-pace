-- Dirty air tax model: Dirty air tax component.
--
-- Attributes per-second slowdown cost to dirty air following.
-- Uses lagged dirty-air share for identification:
-- same driver, same race, air state from previous lap ensures the causal arrow
-- runs prior-lap-position → current-lap-cost, not the reverse.
--
-- Output grain: lap_id (one row per lap, grain matches stg_laps).
--
-- Identity expansion (initial transform release):
--   pace_delta_s = fuel + compound + rubber + ambient + constructor
--               + dirty_air_tax + driver_skill + unexplained
--
-- Two-part estimation:
-- Part 1: Calibration θ_air estimated from (partial_residual ~ dirty_air_lag1)
--   partial_residual = lap_time_s-field_pace_smoothed_s-fuel_component_s
--   This avoids the circular reference: int_dirty_air_tax_component cannot ref
--   int_lap_residual_decomposed because that model refs this one.
-- Part 2: Apply per lap
--   dirty_air_tax_s = CLAMP(θ_air × dirty_air_share_lag1, 0, 5.0)

{{ config(materialized='table', tags=['causal_decomposition', 'dirty_air']) }}

WITH fuel AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        weight_penalty_s    AS fuel_component_s
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
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint
    FROM {{ ref('int_stint_geometry') }}
),

air_state AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        dirty_air_share_lap,
        air_state_dominant
    FROM {{ ref('int_lap_air_state') }}
),

corrections AS (
    -- Clean-lap filter: use correction_weight instead of int_lap_anomaly_flags to
    -- avoid the cycle: int_dirty_air_tax_component → int_lap_anomaly_flags →
    -- int_lap_residual_decomposed → int_dirty_air_tax_component.
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

panel AS (
    SELECT
        f.lap_id,
        g.stint_id,
        f.race_year,
        f.race_id,
        f.driver_id,
        f.lap_number,
        g.lap_in_stint,
        -- Partial residual: pace delta minus fuel only (avoids circular ref to int_lap_residual_decomposed).
        -- Compound, rubber, ambient, and constructor noise increases variance but θ_air remains identified
        -- via within-driver-race variation orthogonal to those components.
        (f.lap_time_s-COALESCE(fp.field_pace_smoothed_s, f.lap_time_s))-f.fuel_component_s
                                                    AS partial_residual_s,
        a.dirty_air_share_lap,
        a.air_state_dominant
    FROM fuel f
    JOIN geom g             USING (lap_id)
    LEFT JOIN field_pace fp ON f.race_year  = fp.race_year
                            AND f.race_id   = fp.race_id
                            AND f.lap_number = fp.lap_number
    LEFT JOIN air_state a   USING (lap_id)
    LEFT JOIN corrections c USING (lap_id)
    LEFT JOIN evolution e   ON f.race_year  = e.race_year
                            AND f.race_id   = e.race_id
                            AND f.lap_number = e.lap_number
    WHERE f.lap_time_s IS NOT NULL
      AND COALESCE(c.correction_weight, 1.0) = 1.0
      AND COALESCE(e.rainfall_flag, FALSE) = FALSE
),

with_lagged AS (
    SELECT
        *,
        -- Lag dirty_air_share within stint by 1 lap for causal identification
        LAG(dirty_air_share_lap, 1, 0.0) OVER (
            PARTITION BY race_year, race_id, driver_id, stint_id
            ORDER BY lap_in_stint
        ) AS dirty_air_share_lag1
    FROM panel
),

calibration_panel AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_in_stint,
        partial_residual_s,
        dirty_air_share_lag1
    FROM with_lagged
    WHERE dirty_air_share_lag1 > 0
      AND partial_residual_s IS NOT NULL
),

-- Global θ_air: weighted regression slope Σ(x·y)/Σ(x²)
-- In production this is a pyfixest HDFE regression; here a SQL OLS approximation.
theta_air_estimate AS (
    SELECT
        COALESCE(
            COVAR_POP(partial_residual_s, dirty_air_share_lag1) /
            NULLIF(VAR_POP(dirty_air_share_lag1), 0),
            0.5
        ) AS theta_air,
        COUNT(*) AS calibration_sample_n
    FROM calibration_panel
),

with_tax AS (
    SELECT
        wl.lap_id,
        wl.stint_id,
        wl.race_year,
        wl.race_id,
        wl.driver_id,
        wl.lap_number,
        wl.lap_in_stint,
        wl.dirty_air_share_lag1,
        wl.air_state_dominant,
        ta.theta_air,
        ta.calibration_sample_n,
        -- Dirty air tax: θ_air × lagged share, bounded [0, 5.0]
        CASE
            WHEN ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0) < 0 THEN 0.0
            WHEN ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0) > 5.0 THEN 5.0
            ELSE ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0)
        END AS dirty_air_tax_s,
        ABS(ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0) * 0.15) AS dirty_air_tax_se_s,
        -- Continuous shrinkage-towards-prior: n / (n + k) where k = 500 (prior equivalent sample).
        -- Approaches 1.0 asymptotically; stays honest near zero at small n.
        CAST(ta.calibration_sample_n AS DOUBLE)
            / (CAST(ta.calibration_sample_n AS DOUBLE) + 500.0) AS tax_calibration_confidence,
        SUM(
            CASE
                WHEN ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0) < 0 THEN 0.0
                WHEN ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0) > 5.0 THEN 5.0
                ELSE ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0)
            END
        ) OVER (
            PARTITION BY wl.race_year, wl.race_id, wl.driver_id
            ORDER BY wl.lap_number ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_dirty_air_tax_race_s
    FROM with_lagged wl
    CROSS JOIN theta_air_estimate ta
)

SELECT
    lap_id,
    dirty_air_share_lag1                AS dirty_air_intensity_lag1,
    dirty_air_tax_s,
    dirty_air_tax_se_s,
    tax_calibration_confidence,
    cumulative_dirty_air_tax_race_s,
    CASE
        WHEN dirty_air_tax_s = MAX(dirty_air_tax_s) OVER (
            PARTITION BY race_year, race_id, driver_id
        ) THEN TRUE
        ELSE FALSE
    END AS dirtiest_air_lap_in_race_flag
FROM with_tax
ORDER BY race_year, race_id, driver_id, lap_number
