-- stg_telemetry.sql · staging · grain: one row per telemetry sample (10 Hz)
-- Renames Bronze telemetry columns to snake_case, casts Distance from int → double.
-- Source: raw_telemetry Bronze Parquet (race + qualifying sessions). No aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_telemetry') }}
),

renamed AS (
    SELECT
        CONCAT(
            CAST(season AS VARCHAR), '_',
            CAST(race_id AS VARCHAR), '_',
            CAST(driver_id AS VARCHAR), '_',
            CAST(lap_number AS INTEGER)
        ) AS telemetry_id,

        CAST(season AS INTEGER) AS race_year,
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(driver_id AS VARCHAR) AS driver_id,
        CAST(lap_number AS INTEGER) AS lap_number,

        CAST(distance_m AS DOUBLE) AS distance_m,
        CAST(speed_kph AS DOUBLE) AS speed_kph,
        CAST(throttle_pct AS DOUBLE) AS throttle_pct,
        CAST(brake AS BOOLEAN) AS brake_applied
    FROM source
    WHERE
        distance_m > 0
        AND distance_m < 6500
)

SELECT * FROM renamed
