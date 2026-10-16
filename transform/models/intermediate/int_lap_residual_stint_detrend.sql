-- Per-stint linear drift of driver_skill_residual_s vs lap_in_stint, fit on
-- pre-cliff laps.
-- Grain: stint_id, one row per stint with a pre-cliff lap; the slope is fit
-- where >= 3 of them have a measured residual (0.0 otherwise).
-- Output: drift_s_per_lap = OLS slope via REGR_SLOPE (negative = residual
-- trending faster,
--         i.e. fuel burn / track evolution leaking into the residual).
--
-- Used by fct_cliff_prediction_features to produce
-- next_lap_degradation_jump_detrended_s
-- (the per-lap first-difference with this per-stint drift removed). Stints with
-- fewer than
-- 3 pre-cliff laps get drift_s_per_lap = 0.0 (no detrending, no data).
--
-- Step 0 diagnostic (2026-06-15): pooled median slope = -0.072 s/lap across
-- 5952 stints.
--
-- CO-04 (2026-10-15): "3 pre-cliff laps" counts laps with a non-NULL
-- residual, the only ones REGR_SLOPE uses. It used to be COUNT(*), so a stint
-- with 3+ pre-cliff laps but only 2 measured residuals (a NULL base: thin
-- cell, W44; or FD6) was detrended on a line through two points.
{{ config(materialized='table') }}

SELECT
    stint_id,
    CASE
        WHEN COUNT(driver_skill_residual_s) >= 3
            THEN
                COALESCE(REGR_SLOPE(driver_skill_residual_s, lap_in_stint), 0.0)
        ELSE 0.0
    END AS drift_s_per_lap
FROM {{ ref('int_lap_residual_decomposed') }}
WHERE cliff_onset_passed = FALSE
GROUP BY stint_id
