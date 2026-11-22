-- Regression for the explicit no-telemetry reason allow-list used by
-- assert_every_lap_race_rated_or_explained. Reads the real mart output; no
-- rows are fabricated.
WITH cov AS (
    SELECT * FROM {{ ref('mart_race_coverage') }}
),

-- Explicit allow-list of coverage reasons that explain a missing telemetry race.
allowed AS (
    SELECT reason FROM (VALUES ('NO_TELEMETRY'), ('NO_USABLE_LAPS')) AS a (reason)
)

-- Vacuity guard: 2025_6 (Miami) must be present with has_telemetry FALSE.
SELECT '2025_6_not_present_without_telemetry' AS failure, '2025_6' AS race_id, NULL AS coverage_reason
WHERE NOT EXISTS (
    SELECT 1 FROM cov WHERE race_id = '2025_6' AND NOT has_telemetry
)

UNION ALL

SELECT 'no_telemetry_reason_not_allowed' AS failure, c.race_id, c.coverage_reason
FROM cov AS c
WHERE
    NOT c.has_telemetry
    AND c.n_lap_rows > 0
    AND c.coverage_reason NOT IN (SELECT reason FROM allowed)

UNION ALL

SELECT '2025_6_reason_not_allowed' AS failure, c.race_id, c.coverage_reason
FROM cov AS c
WHERE
    c.race_id = '2025_6'
    AND (c.coverage_reason IS NULL OR c.coverage_reason NOT IN (SELECT reason FROM allowed))
