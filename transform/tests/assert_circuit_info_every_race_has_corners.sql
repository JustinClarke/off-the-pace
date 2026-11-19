-- Every race in the bronze circuit_info files (race or qualifying) must yield corners
-- in stg_circuit_info. Guards the race-vs-qualifying fallback: a race with only a
-- session=Q file used to disappear silently.
-- Returns one row per race with no corners.
WITH bronze_races AS (
    SELECT DISTINCT season, race_id FROM {{ source('bronze_f1', 'raw_circuit_info') }}
    UNION
    SELECT DISTINCT season, race_id FROM {{ source('bronze_f1', 'raw_circuit_info_quali') }}
)
SELECT b.season, b.race_id
FROM bronze_races b
WHERE NOT EXISTS (
    SELECT 1 FROM {{ ref('stg_circuit_info') }} s
    WHERE s.race_year = b.season AND s.race_id = b.race_id
)
