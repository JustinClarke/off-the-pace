-- TX-27. Jolpica pit stops, one row per stop. race_id is 'YYYY_R' as in
-- race_to_track and stg_pits. driver_ergast_id is Jolpica's driver id; the
-- cross-check maps it to the FastF1 abbreviation through Bronze results
-- (DriverId -> Abbreviation). No joins, no aggregations.
{{ config(materialized='view') }}

SELECT
    CONCAT(CAST(season AS VARCHAR), '_', CAST(round AS VARCHAR)) AS race_id,
    CAST(season AS INTEGER) AS race_year,
    CAST(round AS INTEGER) AS round_number,
    CAST(race_name AS VARCHAR) AS race_name,
    CAST(driver_id AS VARCHAR) AS driver_ergast_id,
    CAST(stop AS INTEGER) AS stop_number,
    CAST(lap AS INTEGER) AS lap_number,
    CAST(time_of_day AS VARCHAR) AS time_of_day,
    CAST(duration_s AS DOUBLE) AS duration_s
FROM {{ source('bronze_jolpica', 'raw_jolpica_pit_stops') }}
