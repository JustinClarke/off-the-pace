-- stg_laps_qualifying.sql · staging · grain: one row per recorded qualifying
-- lap
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
            CAST(race_id AS VARCHAR), '_Q_',
            CAST(driver AS VARCHAR), '_',
            CAST(CAST(lapnumber AS INTEGER) AS VARCHAR)
        ) AS lap_id,

        -- Session / circuit identifiers
        CAST(season AS INTEGER) AS race_year,
        CAST(race_id AS VARCHAR) AS circuit_key,
        CAST(race_id AS VARCHAR) AS race_id,
        CAST('Q' AS VARCHAR) AS session_type,

        -- Driver / constructor
        CAST(driver AS VARCHAR) AS driver_id,
        CAST(drivernumber AS VARCHAR) AS driver_number,
        CAST(team AS VARCHAR) AS constructor_id,

        -- Lap metadata
        CAST(lapnumber AS INTEGER) AS lap_number,
        CAST(stint AS INTEGER) AS stint_number,
        CAST(compound AS VARCHAR) AS compound_raw,
        CAST(tyrelife AS INTEGER) AS tyre_life,
        CAST(freshtyre AS BOOLEAN) AS is_fresh_tyre,
        CAST(ispersonalbest AS BOOLEAN) AS is_personal_best,
        -- 'position' is the canonical column name consumed unquoted
        -- downstream; renaming has wide blast radius, so keep the keyword.
        CAST(position AS INTEGER) AS position,  -- noqa: RF04

        -- Lap timing (nanoseconds → seconds)
        CASE
            WHEN laptime IS NOT NULL THEN CAST(laptime AS DOUBLE) / 1e9
        END AS lap_time_s,
        CASE
            WHEN
                lapstarttime IS NOT NULL
                THEN CAST(lapstarttime AS DOUBLE) / 1e9
        END AS lap_start_time_s,

        -- Sector times (nanoseconds → seconds)
        CASE
            WHEN
                sector1time IS NOT NULL
                THEN CAST(sector1time AS DOUBLE) / 1e9
        END AS sector1_time_s,
        CASE
            WHEN
                sector2time IS NOT NULL
                THEN CAST(sector2time AS DOUBLE) / 1e9
        END AS sector2_time_s,
        CASE
            WHEN
                sector3time IS NOT NULL
                THEN CAST(sector3time AS DOUBLE) / 1e9
        END AS sector3_time_s,

        -- Sector session timestamps (nanoseconds → seconds)
        CASE
            WHEN
                sector1sessiontime IS NOT NULL
                THEN CAST(sector1sessiontime AS DOUBLE) / 1e9
        END AS sector1_session_time_s,
        CASE
            WHEN
                sector2sessiontime IS NOT NULL
                THEN CAST(sector2sessiontime AS DOUBLE) / 1e9
        END AS sector2_session_time_s,
        CASE
            WHEN
                sector3sessiontime IS NOT NULL
                THEN CAST(sector3sessiontime AS DOUBLE) / 1e9
        END AS sector3_session_time_s,

        -- Speed traps (kph)
        CAST(speedi1 AS DOUBLE) AS speed_i1_kph,
        CAST(speedi2 AS DOUBLE) AS speed_i2_kph,
        CAST(speedfl AS DOUBLE) AS speed_fl_kph,
        CAST(speedst AS DOUBLE) AS speed_st_kph,

        -- Track / quality flags
        CAST(trackstatus AS VARCHAR) AS track_status,
        COALESCE(pitouttime IS NOT NULL OR pitintime IS NOT NULL, FALSE)
            AS is_pit_lap,
        CAST(deleted AS BOOLEAN) AS is_deleted,
        CAST(isaccurate AS BOOLEAN) AS is_accurate,
        CAST(fastf1generated AS BOOLEAN) AS is_fastf1_generated,

        -- Normalise compound: treat None/nan/UNKNOWN as NULL
        CASE
            WHEN
                UPPER(CAST(compound AS VARCHAR)) IN (
                    'NONE', 'NAN', 'UNKNOWN', 'NULL', ''
                )
                THEN NULL
            ELSE UPPER(CAST(compound AS VARCHAR))
        END AS compound
    FROM source
),

flagged AS (
    SELECT
        lap_id,
        race_year,
        circuit_key,
        race_id,
        session_type,
        driver_id,
        driver_number,
        constructor_id,
        lap_number,
        stint_number,
        tyre_life,
        is_fresh_tyre,
        is_personal_best,
        position,
        lap_time_s,
        lap_start_time_s,
        sector1_time_s,
        sector2_time_s,
        sector3_time_s,
        sector1_session_time_s, sector2_session_time_s, sector3_session_time_s,
        speed_i1_kph, speed_i2_kph, speed_fl_kph, speed_st_kph, track_status,
        is_pit_lap, is_deleted, is_accurate, is_fastf1_generated, compound,

        -- FastF1 codes, ground-truthed against the bronze Message column:
        -- 4=SCDeployed, 5=Red, 6=VSCDeployed, 7=VSCEnding. Same decode as
        -- stg_track_status and stg_laps.
        REGEXP_MATCHES(track_status, '.*4.*') AS is_safety_car_lap,
        REGEXP_MATCHES(track_status, '.*[67].*') AS is_vsc_lap,
        REGEXP_MATCHES(track_status, '.*5.*') AS is_red_flag_lap,

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
