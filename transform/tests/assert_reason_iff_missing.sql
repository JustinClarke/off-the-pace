-- TX-02. mart_race_driver_summary's reason columns are set exactly when the
-- value they explain is missing, both directions:
--   ci_unavailable_reason       non-NULL <=> ci_low IS NULL
--   residual_unavailable_reason non-NULL <=> n_clean_laps IS NULL
-- Fails per offending row. No vacuity guard: a build with no missing CI or
-- residual (the CI fixture may be one) has nothing to explain.
WITH m AS (
    SELECT * FROM {{ ref('mart_race_driver_summary') }}
)

SELECT 'ci_reason_mismatch' AS failure, race_id, driver_id
FROM m
WHERE (ci_unavailable_reason IS NULL) <> (ci_low IS NOT NULL)

UNION ALL

SELECT 'residual_reason_mismatch' AS failure, race_id, driver_id
FROM m
WHERE (residual_unavailable_reason IS NULL) <> (n_clean_laps IS NOT NULL)
