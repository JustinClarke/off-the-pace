-- Per-stint linear drift of driver_skill_residual_s vs lap_in_stint, fit on
-- pre-cliff, clean (correction_weight = 1) laps.
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
--
-- Filter (2026-11-19): only laps with COALESCE(correction_weight, 0) = 1 enter
-- the slope and the 3-lap count, same as int_power_law_lap. int_lap_residual_decomposed
-- carries correction_weight but does not apply it, so SC / VSC / red-flag, pit
-- (in/out), deleted and outlier laps (weight 0.0), restart / pre-controlled laps
-- (0.3) and soft-outlier / local-yellow laps (0.6) used to leak into the OLS fit
-- whenever their residual was non-NULL, which may have inflated the -0.072
-- diagnostic above (that figure predates this filter). A stint left with
-- fewer than 3 clean laps with a residual gets 0.0, and the row is still emitted
-- only if the stint has a clean pre-cliff lap. The 0.0 default still conflates
-- "no data" with "zero slope"; that is a separate decision and is unchanged.
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
    AND COALESCE(correction_weight, 0) = 1
GROUP BY stint_id
