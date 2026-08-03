-- Phase C: normalize, don't discard.
--
-- Produces normalized_pace_s -- lap time with the dirty-air cost removed, so a
-- lap run in traffic is comparable to one run in clean air instead of being
-- thrown away:
--
--   normalized_pace_s = lap_time_s - theta_time * time_in_dirty_air_s
--
-- Output grain: lap_id, one row per lap carried by int_lap_air_state (the full
-- chronological sequence post-Phase-A, SC/VSC/pit laps included).
--
-- CONSUMED BY THE OFFLINE SOLVER ONLY. This model is a deliberate leaf: nothing
-- in the dbt graph refs it. The ratings/residual chain (int_lap_residual_
-- decomposed onward) must keep its own valid-lap gate and its own dirty-air
-- component -- feeding normalized pace into driver-skill residuals would
-- double-count the dirty-air term already modelled there. Keep it a leaf.
--
-- TWO DEVIATIONS FROM THE PHASE C PLAN, both forced by measurement against the
-- phase's own acceptance metric (per-stint wear-fit residual sigma, see
-- scripts/measure_wear_residual_sigma.py). Baseline median sigma 0.4139s:
--
--   1. NO TOW TERM. The plan's formula subtracts tow_benefit_lap_s. Doing so
--      makes the metric materially WORSE -- 0.4139 -> 0.4291, with 91% of
--      stints degraded. tow_benefit_lap_s is a heuristic constant (-0.15s per
--      sector classified tow_zone), not a fitted quantity, so adding it back
--      injects a step function of noise rather than removing a real effect.
--      It is still carried here as an output column for inspection, just not
--      applied. Fitting a real tow coefficient is the obvious follow-up.
--
--   2. NO STEP TERM. Bucketing the field by dirty-air exposure suggests a large
--      fixed cost for being in traffic at all (median partial residual -0.09s
--      at zero exposure vs +0.16s in the 0-5s bucket), and fitting step+slope
--      on the pooled cross-section puts that step at 0.294s. It is almost
--      entirely selection, not physics: re-estimated WITHIN stint (stint fixed
--      effects, which hold car, driver, circuit and tyre set constant) the step
--      collapses to 0.07s. Slower cars spend more time in traffic; a
--      cross-sectional step charges each lap for the car's own pace deficit.
--      Applying it within a stint made the metric worse (0.4180 vs 0.4139
--      baseline). A plain proportional penalty is both better-behaved and
--      physically honest: cost accrues with time spent in the wake.
--
-- theta_time is the OLS slope of partial_residual on time_in_dirty_air_s over
-- clean valid laps INCLUDING zero-exposure laps (they are the reference group;
-- dropping them, as int_dirty_air_tax_component does for its own share-based
-- coefficient, biases the slope toward the shallow within-traffic margin).
-- Measured value ~0.0042 s per second of exposure.
--
-- Independent check that this is signal and not just a shrunken correction: a
-- sweep of theta against the acceptance metric has an interior optimum at
-- ~0.005 (sigma 0.3925), with sigma rising again above 0.006 and reaching
-- 0.4904 by theta=0.020. The fitted 0.0042 sits beside that optimum without
-- having been tuned to it. The fitted value is what ships -- picking the
-- sigma-minimizing theta would be fitting the acceptance test.
--
-- Distinct from int_dirty_air_tax_component's dirty_air_tax_s, which is keyed
-- on a lagged per-lap *share* and feeds the causal decomposition. This one is
-- keyed on contemporaneous *seconds* (the B4 measurement) and feeds pace
-- normalization for wear/cliff fitting. Different inputs, different consumers.

{{ config(materialized='table', tags=['causal_decomposition', 'dirty_air']) }}

WITH air AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        time_in_dirty_air_s,
        tow_benefit_lap_s
    FROM {{ ref('int_lap_air_state') }}
),

laps AS (
    SELECT
        lap_id,
        lap_time_s,
        is_valid_lap
    FROM {{ ref('stg_laps') }}
),

fuel AS (
    SELECT
        lap_id,
        weight_penalty_s AS fuel_component_s
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

-- Calibration panel: clean, dry, valid laps. Same exclusions as
-- int_dirty_air_tax_component's panel so the two models' coefficients are
-- estimated off a consistent notion of a usable lap. Unlike that model, the
-- zero-exposure laps are KEPT -- see the header note on why.
calibration_panel AS (
    SELECT
        (l.lap_time_s - COALESCE(fp.field_pace_smoothed_s, l.lap_time_s))
        - f.fuel_component_s AS partial_residual_s,
        a.time_in_dirty_air_s
    FROM air AS a
    INNER JOIN laps AS l ON a.lap_id = l.lap_id
    INNER JOIN fuel AS f ON a.lap_id = f.lap_id
    LEFT JOIN field_pace AS fp
        ON
            a.race_year = fp.race_year
            AND a.race_id = fp.race_id
            AND a.lap_number = fp.lap_number
    LEFT JOIN corrections AS c ON a.lap_id = c.lap_id
    LEFT JOIN evolution AS e
        ON
            a.race_year = e.race_year
            AND a.race_id = e.race_id
            AND a.lap_number = e.lap_number
    WHERE
        l.is_valid_lap = TRUE
        AND l.lap_time_s IS NOT NULL
        AND COALESCE(c.correction_weight, 1.0) = 1.0
        AND COALESCE(e.rainfall_flag, FALSE) = FALSE
),

-- theta_time: seconds of lap time per second spent within 1.5s of the car
-- ahead. Fallback 0.004 (the measured order of magnitude) applies only if the
-- panel is empty or degenerate.
theta_time_estimate AS (
    SELECT
        COALESCE(
            COVAR_POP(partial_residual_s, time_in_dirty_air_s)
            / NULLIF(VAR_POP(time_in_dirty_air_s), 0),
            0.004
        ) AS theta_time,
        COUNT(*) AS calibration_sample_n
    FROM calibration_panel
    WHERE partial_residual_s IS NOT NULL
),

applied AS (
    SELECT
        a.lap_id,
        a.stint_id,
        a.race_year,
        a.race_id,
        a.driver_id,
        a.lap_number,
        l.lap_time_s,
        a.time_in_dirty_air_s,
        a.tow_benefit_lap_s,
        tt.theta_time,
        tt.calibration_sample_n,
        -- Bounded [0, 5.0], matching int_dirty_air_tax_component's clamp. The
        -- upper bound also contains the red-flag-stoppage tail in
        -- time_in_dirty_air_s (max observed 385s, 2020 Austrian GP), where the
        -- field genuinely sat bunched for minutes and an unbounded linear
        -- penalty would be nonsense.
        GREATEST(
            0.0,
            LEAST(
                5.0,
                tt.theta_time * COALESCE(a.time_in_dirty_air_s, 0.0)
            )
        ) AS dirty_air_penalty_s
    FROM air AS a
    INNER JOIN laps AS l ON a.lap_id = l.lap_id
    CROSS JOIN theta_time_estimate AS tt
)

SELECT
    lap_id,
    stint_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    lap_time_s,
    time_in_dirty_air_s,
    -- Carried for inspection only; deliberately NOT applied (see header).
    tow_benefit_lap_s,
    dirty_air_penalty_s,
    theta_time,
    calibration_sample_n,
    -- NULL lap_time_s (untimed lap) propagates to NULL rather than being
    -- coerced -- the solver filters those rows out, and a fabricated pace
    -- would be worse than a missing one.
    lap_time_s - dirty_air_penalty_s AS normalized_pace_s
FROM applied
ORDER BY race_year, race_id, driver_id, lap_number
