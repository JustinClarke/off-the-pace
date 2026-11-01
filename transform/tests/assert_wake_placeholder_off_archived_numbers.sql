-- Review R5 (WC-11..16): BUILD-ORDER rule 6 on the BUILT placeholder tables.
-- Returns every built value that equals a number from the archived dirty-air
-- fit at 3 dp. tasks/wake_calibration/tests/test_wc11_placeholder.py checks a
-- Python copy of the rules; this checks what dbt actually wrote, so a rounding
-- difference between Python and DuckDB (2020_9 is 0.90 x 0.45 = 0.405, exactly
-- halfway, and 0.40 is an archived number) cannot slip through.
--
-- Archived numbers: every number in the frozen fit.json with |x| >= 0.005,
-- rounded to 3 dp (the same set the pytest builds: 267 values on 2026-10-31).
-- Built values: the per-race assumed loss, the per-lap race x tyre x car
-- loss, and the tyre and car factors actually used on a lap.
-- Match rule: |value - archived| < 0.0005 (+1e-9), i.e. equal at 3 dp under
-- ANY rounding of a halfway value, so it is never looser than the pytest.
-- Vacuity guards: fails if the archive parses to no numbers or a table is
-- empty.
WITH fit AS (
    SELECT JSON(content) AS j
    FROM
        READ_TEXT(
            '../_roadmap/_archive/_dirty-air/_evidence/DA-03-2026-10-27/fit.json'  -- noqa: LT05
        )
),

fit_values AS (
    SELECT UNNEST(JSON_EXTRACT(j, '$..*')) AS v
    FROM fit
),

archived AS (
    SELECT DISTINCT ROUND(CAST(v AS DOUBLE), 3) AS archived_value
    FROM fit_values
    WHERE
        JSON_TYPE(v) IN ('DOUBLE', 'BIGINT', 'UBIGINT')
        AND ABS(CAST(v AS DOUBLE)) >= 0.005
),

built AS (
    SELECT DISTINCT
        'race loss_s_per_lap_within_1s' AS what,
        loss_s_per_lap_within_1s AS v
    FROM {{ ref('int_wake_placeholder_race_loss') }}
    UNION
    SELECT DISTINCT
        'lap loss_s_per_lap_within_1s' AS what,
        loss_s_per_lap_within_1s AS v
    FROM {{ ref('int_lap_wake_placeholder_cost') }}
    UNION
    SELECT DISTINCT
        'lap compound_factor' AS what,
        compound_factor AS v
    FROM {{ ref('int_lap_wake_placeholder_cost') }}
    UNION
    SELECT DISTINCT
        'lap constructor_factor' AS what,
        constructor_factor AS v
    FROM {{ ref('int_lap_wake_placeholder_cost') }}
)

SELECT
    b.what,
    CAST(b.v AS VARCHAR) AS built_value,
    CAST(a.archived_value AS VARCHAR) AS archived_value
FROM built AS b
INNER JOIN archived AS a ON ABS(b.v - a.archived_value) < 0.0005 + 1e-9
WHERE b.v IS NOT NULL
UNION ALL
SELECT
    'vacuity' AS what,
    'archived fit parsed to no numbers' AS built_value,
    NULL AS archived_value
WHERE NOT EXISTS (SELECT 1 FROM archived)
UNION ALL
SELECT
    'vacuity' AS what,
    'int_wake_placeholder_race_loss is empty' AS built_value,
    NULL AS archived_value
WHERE NOT EXISTS (SELECT 1 FROM {{ ref('int_wake_placeholder_race_loss') }})
UNION ALL
SELECT
    'vacuity' AS what,
    'int_lap_wake_placeholder_cost is empty' AS built_value,
    NULL AS archived_value
WHERE NOT EXISTS (SELECT 1 FROM {{ ref('int_lap_wake_placeholder_cost') }})
