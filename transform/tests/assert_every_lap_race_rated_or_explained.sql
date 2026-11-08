-- TX-02. The one coverage test (TX-08 audits it and does not add a second).
-- Every race in fct_lap_residuals is in mart_race_driver_summary or carries a
-- non-OK coverage_reason; every race_to_track race has a coverage row; and
-- has_telemetry is FALSE on exactly the bronze KNOWN_TELEMETRY_GAPS races
-- present in the build (ingestion/src/bronze_checks.py), so the data-derived
-- flag cannot drift from the source list. No race id is required to exist:
-- on the CI fixture (2020 Monza, 2023 Bahrain, 2024 Sao Paulo) the gap list
-- intersects to nothing and the telemetry check must find no FALSE row.
WITH cov AS (
    SELECT * FROM {{ ref('mart_race_coverage') }}
),

rated AS (
    SELECT DISTINCT race_id FROM {{ ref('mart_race_driver_summary') }}
),

lap_races AS (
    SELECT DISTINCT race_id FROM {{ ref('fct_lap_residuals') }}
),

known_gaps AS (
    SELECT g.race_id
    FROM (VALUES ('2018_1'), ('2018_2')) AS g (race_id)
    INNER JOIN {{ ref('race_to_track') }} AS r ON g.race_id = r.race_id
)

SELECT 'lap_race_unrated_and_unexplained' AS failure, l.race_id
FROM lap_races AS l
LEFT JOIN rated AS r ON l.race_id = r.race_id
LEFT JOIN cov AS c ON l.race_id = c.race_id
WHERE r.race_id IS NULL AND COALESCE(c.coverage_reason, 'OK') = 'OK'

UNION ALL

SELECT 'race_without_coverage_row' AS failure, t.race_id
FROM {{ ref('race_to_track') }} AS t
LEFT JOIN cov AS c ON t.race_id = c.race_id
WHERE c.race_id IS NULL

UNION ALL

-- Scoped to races with lap rows (TX-08, 2026-11-08). On the CI fixture
-- race_to_track still lists all 173 races but only 3 have bronze data, so the
-- other 170 carry has_telemetry FALSE and 168 of them failed here (the fixture
-- build was red). On the full build the only race with no lap rows is 2021_12
-- (has_telemetry TRUE), so this scope changes nothing there; a race with no
-- laps is explained by NO_RACING_LAPS.
SELECT 'no_telemetry_not_a_known_gap' AS failure, c.race_id
FROM cov AS c
LEFT JOIN known_gaps AS k ON c.race_id = k.race_id
WHERE NOT c.has_telemetry AND k.race_id IS NULL AND c.n_lap_rows > 0

UNION ALL

SELECT 'known_gap_has_telemetry' AS failure, k.race_id
FROM known_gaps AS k
INNER JOIN cov AS c ON k.race_id = c.race_id
WHERE c.has_telemetry
