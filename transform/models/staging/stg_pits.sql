-- Extract pit-stop events from the laps parquet.
-- One row per pit stop (lap where PitInTime or PitOutTime is non-null).
-- pit_in_lap = lap on which the car entered the pit lane.
-- pit_out_lap = lap on which the car exited the pit lane (usually pit_in_lap + 1).
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_laps') }}
),

pit_laps AS (
    SELECT
        CONCAT(
            CAST(season AS VARCHAR), '_',
            CAST(race_id AS VARCHAR), '_',
            CAST(Driver  AS VARCHAR), '_',
            CAST(CAST(LapNumber AS INTEGER) AS VARCHAR)
        ) AS lap_id,

        CAST(season  AS INTEGER) AS race_year,
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(Driver  AS VARCHAR) AS driver_id,
        CAST(LapNumber AS INTEGER) AS lap_number,
        CAST(Stint     AS INTEGER) AS stint_number,
        UPPER(CAST(Compound AS VARCHAR)) AS compound_out,

        -- Pit times (nanoseconds → seconds)
        CASE WHEN PitInTime  IS NOT NULL THEN CAST(PitInTime  AS DOUBLE) / 1e9 ELSE NULL END AS pit_in_time_s,
        CASE WHEN PitOutTime IS NOT NULL THEN CAST(PitOutTime AS DOUBLE) / 1e9 ELSE NULL END AS pit_out_time_s

    FROM source
    WHERE PitInTime IS NOT NULL OR PitOutTime IS NOT NULL
),

with_duration AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number                        AS pit_in_lap_number,
        lap_number + 1                    AS pit_out_lap_number,
        stint_number,
        compound_out,
        pit_in_time_s,
        pit_out_time_s,
        CASE
            WHEN pit_in_time_s IS NOT NULL AND pit_out_time_s IS NOT NULL
            THEN pit_out_time_s-pit_in_time_s
            ELSE NULL
        END AS pit_duration_s
    FROM pit_laps
)

SELECT * FROM with_duration
