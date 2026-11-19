-- Lineage check for NULL compounds on laps served 'ok'. A NULL compound on an 'ok' lap is only
-- acceptable when the bronze compound itself is NULL (source gap, e.g. FastF1 'None' on a stint).
-- If bronze has a compound and the served compound is NULL, a transformation dropped it.
-- Returns one row per violating lap.

SELECT
    lap_id AS key,
    'bronze compound ' || bronze_compound || ' dropped to NULL on an ok lap' AS reason
FROM {{ ref('stg_lap_tyre_qa') }}
WHERE tyre_qa_status = 'ok'
  AND compound IS NULL
  AND bronze_compound IS NOT NULL
