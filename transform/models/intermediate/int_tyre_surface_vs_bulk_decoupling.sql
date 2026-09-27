-- Tyre surface vs bulk thermal decoupling.
-- For each lap past the tyre cliff, attributes degradation to surface
-- (recoverable)
-- or bulk (structural) thermal damage using the two EW thermal signals with
-- different time constants:
--  -cumulative_push_load_surface (τ≈3 laps, fast-decaying)
--  -cumulative_push_load_bulk    (τ≈5 laps, slow-decaying)
--
-- Hypothesis: a higher surface/total ratio means damage is more recent and
-- potentially recoverable with conservative driving. Bulk-dominated damage
-- is structural the tyre must be pitted regardless.
--
-- Identification: within-driver contrast of τ=3 vs τ=5 signals captures
-- time-constant differences. If surface ratio predicts recovery (subsequent
-- residuals improve), the two signals carry separable physics information.
--
-- Null hypothesis:
--   H₀: surface_bulk_ratio does NOT predict subsequent lap recovery.
--   Rejected when logistic coefficient is positive at p < 0.01.
--
-- This SQL model computes surface_bulk_ratio and the classification.
-- The logistic recovery_probability is approximated in SQL via a linear
-- sigmoid approximation (no pyfixest dependency; a validation notebook fits
-- the logistic for the exact coefficients).
--
-- Output grain: lap_id (only laps where cliff_onset_passed = TRUE).
-- PK: lap_id (subset of stg_laps).

{{ config(materialized='table', tags=['simulation', 'thermal']) }}

WITH thermal AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        cumulative_push_load_surface,
        cumulative_push_load_bulk
    FROM {{ ref('int_lap_thermal_proxy') }}
),

residuals AS (
    -- All race laps with driver residual and cliff flags; includes non-cliff
    -- laps
    -- for the LEAD window to look ahead past the cliff.
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        compound,
        cliff_onset_passed,
        laps_past_cliff,
        compound_component_s,
        driver_skill_residual_s
    FROM {{ ref('int_lap_residual_decomposed') }}
),

-- Join thermal signals to all laps, then filter to post-cliff below
combined AS (
    SELECT
        r.lap_id,
        r.race_year,
        r.race_id,
        r.driver_id,
        r.lap_number,
        r.compound,
        r.cliff_onset_passed,
        r.laps_past_cliff,
        r.compound_component_s,
        r.driver_skill_residual_s,
        th.stint_id,
        th.lap_in_stint,
        COALESCE(th.cumulative_push_load_surface, 0.0) AS push_load_surface,
        COALESCE(th.cumulative_push_load_bulk, 0.0) AS push_load_bulk
    FROM residuals AS r
    INNER JOIN thermal AS th ON r.lap_id = th.lap_id
),

-- Compute surface-to-total ratio and next-2-lap recovery window
with_ratio AS (
    SELECT
        *,
        -- Surface share of the two loads, each divided by its own weight sum.
        -- F49 (WI-15b): both loads sum the same non-negative push_residual
        -- series and no surface weight exceeds the bulk weight at the same lag,
        -- so surface <= bulk always. The raw share surface/(surface+bulk) was
        -- therefore capped at 0.5 and read 0.394 at steady push. Normalised, a
        -- steady push reads 0.5 and the ceiling is
        -- bulk_sum/(surface_sum+bulk_sum) = 0.606, when all push is on this
        -- lap. It is a monotone function of the raw share (same ordering).
        (push_load_surface / {{ var('thermal_surface_weight_sum') }})
        / NULLIF(
            (push_load_surface / {{ var('thermal_surface_weight_sum') }})
            + (push_load_bulk / {{ var('thermal_bulk_weight_sum') }}),
            0.0
        ) AS surface_bulk_ratio,

        -- Next 2-lap driver_skill_residual: compare to current for recovery
        -- detection
        LEAD(driver_skill_residual_s, 1) OVER w AS next_lap_1_residual,
        LEAD(driver_skill_residual_s, 2) OVER w AS next_lap_2_residual
    FROM combined
    WINDOW w AS (
        PARTITION BY race_year, race_id, driver_id, stint_id
        ORDER BY lap_in_stint
    )
),

with_classification AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        compound,
        laps_past_cliff,
        compound_component_s,
        push_load_surface,
        push_load_bulk,
        COALESCE(surface_bulk_ratio, 0.5) AS surface_bulk_ratio,

        -- Degradation source classification.
        -- F49 (WI-15b): 'surface_driven' (ratio > 0.65) is removed. It never
        -- fired (0 of 41,437 laps): the ratio's ceiling is 0.606 even after
        -- normalisation (see surface_bulk_ratio above), so any threshold above
        -- that is dead code. assert_degradation_source_classes_reachable (T39)
        -- fails if a declared class has no rows.
        CASE
            WHEN COALESCE(surface_bulk_ratio, 0.5) < 0.35 THEN 'bulk_driven'
            ELSE 'mixed'
        END AS degradation_source,

        -- Recovery flag: TRUE if avg of next 2 laps' residuals is better than
        -- current
        -- (lower residual = faster relative to field = recovering)
        CASE
            WHEN
                next_lap_1_residual IS NOT NULL
                AND next_lap_2_residual IS NOT NULL
                THEN
                    (next_lap_1_residual + next_lap_2_residual) / 2.0
                    < driver_skill_residual_s
            WHEN next_lap_1_residual IS NOT NULL
                THEN next_lap_1_residual < driver_skill_residual_s
        END AS recovery_flag,

        -- Thermal attribution: share of compound degradation explained by
        -- thermal damage
        -- Approximation: surface ratio × compound_component_s
        COALESCE(surface_bulk_ratio, 0.5)
        * COALESCE(compound_component_s, 0.0) AS thermal_attribution_s,

        -- Recovery probability: sigmoid approximation over surface_bulk_ratio.
        -- Full logistic fit is in validation notebook; SQL approximation:
        --   P = 1 / (1 + exp(-2.0 × (ratio-0.5))) × decay_with_laps_past_cliff
        -- Bounded [0, 1].
        GREATEST(0.0, LEAST(
            1.0,
            (
                1.0
                / (1.0 + EXP(-2.0 * (COALESCE(surface_bulk_ratio, 0.5) - 0.5)))
            )
            * (1.0 / (1.0 + 0.1 * GREATEST(laps_past_cliff, 0.0)))
        )) AS recovery_probability
    FROM with_ratio
    WHERE cliff_onset_passed = TRUE
)

SELECT
    lap_id,
    race_year,
    race_id,
    driver_id,
    compound,
    laps_past_cliff,
    push_load_surface,
    push_load_bulk,
    surface_bulk_ratio,
    degradation_source,
    recovery_flag,
    recovery_probability,
    thermal_attribution_s,
    compound_component_s
FROM with_classification
ORDER BY race_year, race_id, driver_id, laps_past_cliff
