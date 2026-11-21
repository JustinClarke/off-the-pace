-- int_lap_residual_stint_detrend must fit the per-stint slope on clean laps only
-- (correction_weight = 1), the same filter int_power_law_lap uses. Re-derives the
-- slope from int_lap_residual_decomposed with the filter written out and
-- compares it to the model: any stint where an excluded or down-weighted lap
-- (SC / VSC / red flag / pit / deleted / outlier = 0.0, restart = 0.3,
-- soft outlier / local yellow = 0.6) leaked into the fit gives a different slope.
-- Also fails if the model emits a stint with no clean pre-cliff lap.
{{ config(severity='error') }}

WITH expected AS (
    SELECT
        stint_id,
        CASE
            WHEN COUNT(driver_skill_residual_s) >= 3
                THEN COALESCE(REGR_SLOPE(driver_skill_residual_s, lap_in_stint), 0.0)
            ELSE 0.0
        END AS drift_s_per_lap
    FROM {{ ref('int_lap_residual_decomposed') }}
    WHERE cliff_onset_passed = FALSE
      AND COALESCE(correction_weight, 0) = 1
    GROUP BY stint_id
)

SELECT
    COALESCE(m.stint_id, e.stint_id) AS stint_id,
    m.drift_s_per_lap AS model_drift_s_per_lap,
    e.drift_s_per_lap AS clean_lap_drift_s_per_lap
FROM {{ ref('int_lap_residual_stint_detrend') }} AS m
FULL OUTER JOIN expected AS e ON m.stint_id = e.stint_id
WHERE m.stint_id IS NULL
   OR e.stint_id IS NULL
   OR ABS(m.drift_s_per_lap - e.drift_s_per_lap) > 1e-9
