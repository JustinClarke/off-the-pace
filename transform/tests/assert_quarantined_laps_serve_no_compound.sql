-- Stale or unverified tyre data is never served. Every lap whose tyre_qa_status is not 'ok'
-- (quarantined_race or quarantined_driver) must have NULL compound and NULL tyre_life.
-- The raw bronze values stay in bronze_compound / bronze_tyre_life for provenance.
-- Returns one row per violating lap.

SELECT
    lap_id AS key,
    tyre_qa_status || ': compound ' || COALESCE(compound, 'NULL')
        || ', tyre_life ' || COALESCE(CAST(tyre_life AS VARCHAR), 'NULL') AS reason
FROM {{ ref('stg_lap_tyre_qa') }}
WHERE tyre_qa_status != 'ok'
  AND (compound IS NOT NULL OR tyre_life IS NOT NULL)
