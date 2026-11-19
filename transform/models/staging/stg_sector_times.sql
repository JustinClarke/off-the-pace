-- Extract per-sector timing from the laps parquet.
-- One row per lap × sector (3 rows per lap).
-- SpeedI2 trap is associated with S2 exit; SpeedST with the main straight.
-- Flag, do not drop: a sector with no time keeps its row, with sector_time_s NULL
-- and sector_time_missing TRUE, so the 3-rows-per-lap grain holds and the speed
-- trap reading is not lost. Consumers that need a time filter on the flag or on
-- sector_time_s (both already do).
{{ config(materialized='view') }}

WITH laps AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        sector1_time_s,
        sector2_time_s,
        sector3_time_s,
        sector1_session_time_s,
        sector2_session_time_s,
        sector3_session_time_s,
        speed_i1_kph,
        speed_i2_kph,
        speed_fl_kph,
        speed_st_kph,
        is_valid_lap
    FROM {{ ref('stg_laps') }}
),

unpivoted AS (
    SELECT
        lap_id, race_year, race_id, driver_id, lap_number,
        1 AS sector,
        sector1_time_s AS sector_time_s,
        sector1_session_time_s AS sector_session_time_s,
        speed_i1_kph AS speed_trap_kph,
        is_valid_lap
    FROM laps

    UNION ALL

    SELECT
        lap_id, race_year, race_id, driver_id, lap_number,
        2 AS sector,
        sector2_time_s,
        sector2_session_time_s,
        speed_i2_kph,
        is_valid_lap
    FROM laps

    UNION ALL

    SELECT
        lap_id, race_year, race_id, driver_id, lap_number,
        3 AS sector,
        sector3_time_s,
        sector3_session_time_s,
        speed_fl_kph,   -- FL trap is S3 exit
        is_valid_lap
    FROM laps
)

SELECT
    CONCAT(lap_id, '_S', CAST(sector AS VARCHAR)) AS sector_id,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    sector,
    sector_time_s,
    sector_time_s IS NULL AS sector_time_missing,
    sector_session_time_s,
    speed_trap_kph,
    is_valid_lap
FROM unpivoted
