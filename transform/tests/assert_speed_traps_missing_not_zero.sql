-- TX-25: every speed-trap value carries its n; a lap without SpeedST is
-- counted as missing, never stored as 0; the all-lap missing count matches
-- staging. Returns offending rows.
WITH staged AS (
    SELECT race_id, 'R' AS session_type, driver_id, COUNT(*) FILTER (WHERE speed_st_kph IS NULL) AS n_missing
    FROM {{ ref('stg_laps') }} GROUP BY race_id, driver_id
    UNION ALL
    SELECT race_id, 'Q', driver_id, COUNT(*) FILTER (WHERE speed_st_kph IS NULL)
    FROM {{ ref('stg_laps_qualifying') }} GROUP BY race_id, driver_id
)

SELECT t.driver_session_id, 'zero_speed_or_value_without_n' AS failure
FROM {{ ref('fct_speed_traps') }} AS t
WHERE t.st_max_kph = 0 OR t.fl_max_kph = 0
    OR (t.st_max_kph IS NOT NULL AND t.n_st_readings = 0)
    OR (t.st_max_kph IS NULL AND t.n_st_readings > 0)

UNION ALL

SELECT t.driver_session_id, 'missing_count_mismatch'
FROM {{ ref('fct_speed_traps') }} AS t
INNER JOIN staged AS s
    ON t.race_id = s.race_id AND t.session_type = s.session_type AND t.driver_id = s.driver_id
WHERE t.n_st_missing_all_laps <> s.n_missing

UNION ALL

SELECT season_entity_id, 'season_value_without_n'
FROM {{ ref('fct_speed_traps_season') }}
WHERE st_max_kph = 0 OR (st_max_kph IS NOT NULL AND n_st_readings = 0)
