-- stg_telemetry.sql · staging · grain: one row per telemetry sample (10 Hz)
-- Renames Bronze telemetry columns to snake_case, casts Distance from int →
-- double.
-- Source: raw_telemetry Bronze Parquet (race + qualifying sessions). No
-- aggregations.
-- Projects the powertrain channels (rpm / n_gear / drs_active) needed by the
-- per-lap
-- telemetry aggregates (int_lap_telemetry_aggregates). FastF1 DRS
-- codes:
-- 0/1 = off, 8 = eligible-but-inactive, 10/12/14 = active → drs_active.
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
        -- Sample clock. distance_m alone is NOT a total order within a lap:
        -- 982,303 car-channel samples (1.6%) share a
        -- (race, driver, lap, distance) key, because a stationary or crawling
        -- car keeps sampling at 10 Hz while distance does not advance. Any
        -- LAG/LEAD ordered on distance alone therefore picks an arbitrary
        -- neighbour, and the choice moves with DuckDB's scan parallelism.
        -- Adding this column makes (distance_m, session_time_s) unique across
        -- all 59.5M rows, with zero NULLs.
        CAST(sessiontime AS DOUBLE) / 1e9 AS session_time_s,
        CAST(speed_kph AS DOUBLE) AS speed_kph,
        CAST(throttle_pct AS DOUBLE) AS throttle_pct,
        CAST(brake AS BOOLEAN) AS brake_applied,

        CAST(rpm AS DOUBLE) AS rpm,
        CAST(ngear AS INTEGER) AS n_gear,
        (CAST(drs AS INTEGER) IN (10, 12, 14)) AS drs_active,

        -- FastF1 merges 'car' (true channel cadence) with forward-filled 'pos'
        -- /
        -- 'interpolation' samples. Projected un-filtered so existing consumers
        -- are
        -- unchanged; sample-level event detection filters to 'car' downstream.
        CAST(source AS VARCHAR) AS source_channel
    FROM source
    WHERE
        distance_m > 0
        AND distance_m < 6500
)

SELECT * FROM renamed
