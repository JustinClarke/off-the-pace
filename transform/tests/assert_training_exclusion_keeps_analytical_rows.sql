-- The training-eligibility exclusion of non-MEASURED laps is a flag, not a filter.
-- fct_lap_residuals (analytical) must hold exactly the laps int_lap_residual_decomposed
-- holds (grain equal, lap_id set equal), and fct_cliff_prediction_features must hold
-- every one of those laps too. Returns one row per mismatch; passes when empty.
WITH d AS (
    SELECT lap_id FROM {{ ref('int_lap_residual_decomposed') }}
),

r AS (
    SELECT lap_id FROM {{ ref('fct_lap_residuals') }}
),

f AS (
    SELECT lap_id FROM {{ ref('fct_cliff_prediction_features') }}
),

counts AS (
    SELECT
        (SELECT COUNT(*) FROM d) AS n_decomposed,
        (SELECT COUNT(*) FROM r) AS n_residuals,
        (SELECT COUNT(*) FROM f) AS n_cliff
)

SELECT 'row_count_mismatch' AS issue, n_decomposed, n_residuals, n_cliff
FROM counts
WHERE n_decomposed <> n_residuals OR n_decomposed <> n_cliff

UNION ALL

SELECT 'lap_missing_from_residuals', NULL, NULL, NULL
FROM d ANTI JOIN r USING (lap_id)

UNION ALL

SELECT 'lap_missing_from_cliff', NULL, NULL, NULL
FROM d ANTI JOIN f USING (lap_id)
