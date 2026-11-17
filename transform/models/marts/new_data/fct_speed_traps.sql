-- TX-25. Speed-trap readings per driver, race and session, race and
-- qualifying. NOT exported (scratch-only).
-- Each trap (st = speed trap, fl = finish line, i1, i2) has max, median and
-- n laps with a reading over valid laps (is_valid_lap); n_valid_laps is the
-- denominator. n_st_missing_all_laps counts every recorded lap (valid or not)
-- with no SpeedST, so the Bronze laps without a reading are counted as
-- missing; a missing reading stays NULL, never 0.
{{ config(materialized='table', tags=['marts', 'new_data']) }}

WITH laps AS (
    SELECT race_year, race_id, 'R' AS session_type, driver_id, constructor_id, is_valid_lap,
        speed_st_kph, speed_fl_kph, speed_i1_kph, speed_i2_kph
    FROM {{ ref('stg_laps') }}
    UNION ALL
    SELECT race_year, race_id, 'Q' AS session_type, driver_id, constructor_id, is_valid_lap,
        speed_st_kph, speed_fl_kph, speed_i1_kph, speed_i2_kph
    FROM {{ ref('stg_laps_qualifying') }}
)

SELECT
    CONCAT(race_id, '_', session_type, '_', driver_id) AS driver_session_id,
    race_year,
    race_id,
    session_type,
    driver_id,
    ANY_VALUE(constructor_id ORDER BY constructor_id) AS constructor_id,
    COUNT(*) AS n_laps_recorded,
    COUNT(*) FILTER (WHERE speed_st_kph IS NULL) AS n_st_missing_all_laps,
    COUNT(*) FILTER (WHERE is_valid_lap) AS n_valid_laps,
    MAX(speed_st_kph) FILTER (WHERE is_valid_lap) AS st_max_kph,
    MEDIAN(speed_st_kph) FILTER (WHERE is_valid_lap) AS st_median_kph,
    COUNT(speed_st_kph) FILTER (WHERE is_valid_lap) AS n_st_readings,
    COUNT(*) FILTER (WHERE is_valid_lap AND speed_st_kph IS NULL) AS n_st_missing,
    MAX(speed_fl_kph) FILTER (WHERE is_valid_lap) AS fl_max_kph,
    MEDIAN(speed_fl_kph) FILTER (WHERE is_valid_lap) AS fl_median_kph,
    COUNT(speed_fl_kph) FILTER (WHERE is_valid_lap) AS n_fl_readings,
    MAX(speed_i1_kph) FILTER (WHERE is_valid_lap) AS i1_max_kph,
    MEDIAN(speed_i1_kph) FILTER (WHERE is_valid_lap) AS i1_median_kph,
    COUNT(speed_i1_kph) FILTER (WHERE is_valid_lap) AS n_i1_readings,
    MAX(speed_i2_kph) FILTER (WHERE is_valid_lap) AS i2_max_kph,
    MEDIAN(speed_i2_kph) FILTER (WHERE is_valid_lap) AS i2_median_kph,
    COUNT(speed_i2_kph) FILTER (WHERE is_valid_lap) AS n_i2_readings
FROM laps
GROUP BY race_year, race_id, session_type, driver_id
ORDER BY race_year, race_id, session_type, driver_id
