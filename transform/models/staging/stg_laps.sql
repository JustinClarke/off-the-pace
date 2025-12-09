-- stg_laps.sql · staging · grain: one row per recorded lap (race sessions)
-- Renames Bronze columns to snake_case, casts nanoseconds → seconds, derives
-- is_valid_lap and is_safety_car_lap. No joins, no aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_laps') }}
),

renamed AS (
    SELECT
        -- Surrogate key
        CONCAT(
            CAST(season AS VARCHAR), '_',
            CAST(race_id  AS VARCHAR), '_',
            CAST(Driver   AS VARCHAR), '_',
            CAST(CAST(LapNumber AS INTEGER) AS VARCHAR)
        ) AS lap_id,

        -- Session / circuit identifiers
        CAST(season   AS INTEGER) AS race_year,
        CAST(race_id  AS VARCHAR) AS circuit_key,
        CAST(race_id  AS VARCHAR) AS race_id,

        -- Driver / constructor
        CAST(Driver       AS VARCHAR) AS driver_id,
        CAST(DriverNumber AS VARCHAR) AS driver_number,
        CAST(Team         AS VARCHAR) AS constructor_id,

        -- Lap metadata
        CAST(LapNumber AS INTEGER) AS lap_number,
        CAST(Stint     AS INTEGER) AS stint_number,
        -- compound normalised in flagged CTE below
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

        -- Sector session timestamps (nanoseconds → seconds; used for air-gap join)
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
        * EXCLUDE (compound_raw),

        -- TrackStatus is a concatenated digit string (e.g. '41' = VSC+yellow, '124' = SC+yellow+DRS).
        -- Use REGEXP_MATCHES to check for presence of flag digits anywhere in the string.
        REGEXP_MATCHES(track_status, '.*[467].*') AS is_safety_car_lap,
        REGEXP_MATCHES(track_status, '.*5.*')     AS is_vsc_lap,

        -- Valid laps: timed, on-track, not deleted, accurate, not lap 1,
        -- and no SC/VSC flag anywhere in the multi-char TrackStatus string.
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
