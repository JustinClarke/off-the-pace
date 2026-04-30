-- Initial release exit gate: driver_skill_residual_s variance must not regress significantly
-- versus the pre-initial baseline snapshot (SHA 7d4a58f).
--
-- Reads the baseline parquet directly; compares to the current fct_lap_residuals.
-- Returns rows (i.e. FAILS) if the variance ratio falls outside [0.95, 1.05].
-- A ratio < 0.95 suggests strong variance reduction (initial models extracted meaningful variance).
-- A ratio > 1.05 means initial release regression-new models made residuals noisier.
--
-- Baseline file: data/silver/_baseline_pre_initial/fct_lap_residuals.parquet

WITH baseline AS (
    SELECT
        VAR_POP(driver_skill_residual_s) AS baseline_variance
    FROM read_parquet(
        '../data/silver/_baseline_pre_phase_a/fct_lap_residuals.parquet'
    )
    WHERE driver_skill_residual_s IS NOT NULL
),

current_model AS (
    SELECT
        VAR_POP(driver_skill_residual_s) AS current_variance
    FROM {{ ref('fct_lap_residuals') }}
    WHERE driver_skill_residual_s IS NOT NULL
),

ratio AS (
    SELECT
        c.current_variance / NULLIF(b.baseline_variance, 0) AS variance_ratio,
        b.baseline_variance,
        c.current_variance
    FROM baseline b
    CROSS JOIN current_model c
)

-- Fail if variance did not shrink into the expected 1–15% band.
SELECT
    variance_ratio,
    baseline_variance,
    current_variance,
    'expected variance_ratio in [0.85, 0.99]' AS failure_reason
FROM ratio
WHERE variance_ratio IS NULL
   OR variance_ratio < 0.85
   OR variance_ratio > 0.99
