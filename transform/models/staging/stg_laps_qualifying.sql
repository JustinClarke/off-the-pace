-- stg_laps_qualifying.sql · staging · grain: one row per recorded qualifying lap
-- Mirrors stg_laps for qualifying sessions (Q1/Q2/Q3). Renames Bronze columns,
-- casts nanoseconds → seconds, derives is_valid_lap. No joins, no aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_laps_qualifying') }}
),

renamed AS (
    SELECT
        -- Surrogate key
        CONCAT(
            CAST(season AS VARCHAR), '_',
            CAST(race_id  AS VARCHAR), '_Q_',
            CAST(Driver   AS VARCHAR), '_',
            CAST(CAST(LapNumber AS INTEGER) AS VARCHAR)
        ) AS lap_id,

        -- Session / circuit identifiers
        CAST(season   AS INTEGER) AS race_year,
        CAST(race_id  AS VARCHAR) AS circuit_key,
        CAST(race_id  AS VARCHAR) AS race_id,
        CAST('Q' AS VARCHAR) AS session_type,

        -- Driver / constructor
        CAST(Driver       AS VARCHAR) AS driver_id,
        CAST(DriverNumber AS VARCHAR) AS driver_number,
        CAST(Team         AS VARCHAR) AS constructor_id,

        -- Lap metadata
        CAST(LapNumber AS INTEGER) AS lap_number,
        CAST(Stint     AS INTEGER) AS stint_number,
        CAST(Compound AS VARCHAR) AS compound_raw,
        CAST(TyreLife   AS INTEGER) AS tyre_life,
        CAST(FreshTyre  AS BOOLEAN) AS is_fresh_tyre,
        CAST(IsPersonalBest AS BOOLEAN) AS is_personal_best,
        CAST(Position   AS INTEGER) AS position,

        -- Lap timing (nanoseconds → seconds)
        CASE WHEN LapTime   IS NOT NULL THEN CAST(LapTime   AS DOUBLE) / 1e9 ELSE NULL END AS lap_time_s,
        CASE WHEN LapStartTime IS NOT NULL THEN CAST(LapStartTime AS DOUBLE) / 1e9 ELSE NULL END AS lap_start_time_s,

        -- Sector times (nanoseconds → seconds)
        CASE WHEN Sector1Time IS NOT NULL THEN CAST(Sector1Time AS DOUBLE) / 1e9 ELSE NULL END AS sector1_time_s,
        CASE WHEN Sector2Time IS NOT NULL THEN CAST(Sector2Time AS DOUBLE) / 1e9 ELSE NULL END AS sector2_time_s,
        CASE WHEN Sector3Time IS NOT NULL THEN CAST(Sector3Time AS DOUBLE) / 1e9 ELSE NULL END AS sector3_time_s,

        -- Sector session timestamps (nanoseconds → seconds)
        CASE WHEN Sector1SessionTime IS NOT NULL THEN CAST(Sector1SessionTime AS DOUBLE) / 1e9 ELSE NULL END AS sector1_session_time_s,
        CASE WHEN Sector2SessionTime IS NOT NULL THEN CAST(Sector2SessionTime AS DOUBLE) / 1e9 ELSE NULL END AS sector2_session_time_s,
        CASE WHEN Sector3SessionTime IS NOT NULL THEN CAST(Sector3SessionTime AS DOUBLE) / 1e9 ELSE NULL END AS sector3_session_time_s,

        -- Speed traps (kph)
        CAST(SpeedI1 AS DOUBLE) AS speed_i1_kph,
        CAST(SpeedI2 AS DOUBLE) AS speed_i2_kph,
        CAST(SpeedFL AS DOUBLE) AS speed_fl_kph,
        CAST(SpeedST AS DOUBLE) AS speed_st_kph,

        -- Track / quality flags
        CAST(TrackStatus AS VARCHAR) AS track_status,
        CASE WHEN PitOutTime IS NOT NULL OR PitInTime IS NOT NULL THEN TRUE ELSE FALSE END AS is_pit_lap,
        CAST(Deleted        AS BOOLEAN) AS is_deleted,
        CAST(IsAccurate     AS BOOLEAN) AS is_accurate,
        CAST(FastF1Generated AS BOOLEAN) AS is_fastf1_generated,

        -- Normalise compound: treat None/nan/UNKNOWN as NULL
        CASE
            WHEN UPPER(CAST(Compound AS VARCHAR)) IN ('NONE', 'NAN', 'UNKNOWN', 'NULL', '')
                THEN NULL
            ELSE UPPER(CAST(Compound AS VARCHAR))
        END AS compound
    FROM source
),

flagged AS (
    SELECT
        lap_id, race_year, circuit_key, race_id, session_type, driver_id, driver_number, constructor_id,
        lap_number, stint_number, tyre_life, is_fresh_tyre, is_personal_best, position,
        lap_time_s, lap_start_time_s, sector1_time_s, sector2_time_s, sector3_time_s,
        sector1_session_time_s, sector2_session_time_s, sector3_session_time_s,
        speed_i1_kph, speed_i2_kph, speed_fl_kph, speed_st_kph, track_status,
        is_pit_lap, is_deleted, is_accurate, is_fastf1_generated, compound,

        REGEXP_MATCHES(track_status, '.*[467].*') AS is_safety_car_lap,
        REGEXP_MATCHES(track_status, '.*5.*')     AS is_vsc_lap,

        lap_time_s > 0
            AND NOT is_pit_lap
            AND NOT is_deleted
            AND is_accurate
            AND NOT REGEXP_MATCHES(track_status, '.*[4567].*')
            AND lap_number > 1
        AS is_valid_lap
    FROM renamed
)

SELECT * FROM flagged
