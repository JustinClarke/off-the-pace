-- 2025 Miami (race_id 2025_6) stays quarantined. The race has stale FastF1 stint and
-- compound data (12 late stint changes, 12 of 18 racing stops unmatched), so every lap
-- must stay quarantined_race. If this fails, either the source was repaired (update the
-- KNOWN LIMIT note in stg_lap_tyre_qa.sql and this test on purpose) or a threshold was
-- loosened (not allowed; see assert_tyre_qa_thresholds_unchanged).

WITH miami AS (
    SELECT tyre_qa_status, COUNT(*) AS n_laps
    FROM {{ ref('stg_lap_tyre_qa') }}
    WHERE race_id = '2025_6'
    GROUP BY tyre_qa_status
)

SELECT '2025_6' AS key, 'status ' || tyre_qa_status || ' on ' || CAST(n_laps AS VARCHAR) || ' laps' AS reason
FROM miami
WHERE tyre_qa_status != 'quarantined_race'

UNION ALL

SELECT '2025_6' AS key, 'no laps served for 2025_6' AS reason
FROM (SELECT 1) AS one
WHERE NOT EXISTS (SELECT 1 FROM miami)
