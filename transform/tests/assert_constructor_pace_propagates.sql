-- Initial transform release medium priority: constructor_component_s must reduce variance in
-- driver_skill_residual_s relative to the pre-initial-release baseline.
--
-- Companion to assert_residual_variance_shrinks.sql, targeting the constructor signal
-- specifically: the variance of constructor_component_s in the current model must be
-- strictly greater than zero (signal is non-trivial) and the residual variance must be
-- lower than baseline (constructor absorbs real variance, not noise).
--
-- Returns rows (FAILS) if either condition is violated.

WITH baseline AS (
    SELECT VAR_POP(driver_skill_residual_s) AS baseline_var
    FROM read_parquet(
        '../data/silver/_baseline_pre_phase_a/fct_lap_residuals.parquet'
    )
    WHERE driver_skill_residual_s IS NOT NULL
),

current_residuals AS (
    SELECT VAR_POP(driver_skill_residual_s) AS current_var
    FROM {{ ref('fct_lap_residuals') }}
    WHERE driver_skill_residual_s IS NOT NULL
),

constructor_signal AS (
    SELECT VAR_POP(constructor_structural_pace_s) AS constructor_var
    FROM {{ ref('int_constructor_structural_pace') }}
    WHERE constructor_structural_pace_s IS NOT NULL
)

SELECT
    b.baseline_var,
    c.current_var,
    cs.constructor_var,
    CASE
        WHEN cs.constructor_var <= 0 THEN 'constructor_component has zero variance (no signal)'
        WHEN c.current_var >= b.baseline_var THEN 'residual variance did not shrink after constructor component'
        ELSE NULL
    END AS failure_reason
FROM baseline b
CROSS JOIN current_residuals c
CROSS JOIN constructor_signal cs
WHERE cs.constructor_var <= 0
   OR c.current_var >= b.baseline_var
