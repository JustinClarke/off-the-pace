-- Weather snapshot nearest to each lap start.
-- Joins bronze weather samples (≈1Hz) to laps on lap_start_time_s using
-- ASOF semantics: for each lap we take the weather sample with the largest
-- session_time_s that is still ≤ lap_start_time_s (i.e. current conditions
-- at the moment the lap begins). Falls back to the first available sample
-- for laps that start before the first weather reading.
{{ config(materialized='view') }}

WITH weather_raw AS (
    SELECT
        CAST(season   AS INTEGER) AS race_year,
        CAST(race_id  AS VARCHAR) AS race_id,
        CAST(session_time_s       AS DOUBLE)  AS session_time_s,
        CAST(ambient_temp_c       AS DOUBLE)  AS ambient_temp_c,
        CAST(track_temp_c         AS DOUBLE)  AS track_temp_c,
        CAST(rainfall_flag        AS BOOLEAN) AS rainfall_flag,
        CAST(humidity_pct         AS DOUBLE)  AS humidity_pct,
        CAST(wind_speed_ms        AS DOUBLE)  AS wind_speed_ms,
        CAST(wind_direction       AS INTEGER) AS wind_direction
    FROM {{ source('bronze_f1', 'raw_weather') }}
),

laps AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_start_time_s
    FROM {{ ref('stg_laps') }}
    WHERE lap_start_time_s IS NOT NULL
),

-- For each lap, pick the weather sample immediately preceding or at lap start.
-- Using a lateral/window approach: rank weather samples per race that are
-- ≤ lap_start_time_s, take the closest one (MAX session_time_s ≤ lap_start).
lap_weather AS (
    SELECT
        l.lap_id,
        l.race_year,
        l.race_id,
        l.driver_id,
        l.lap_number,
        l.lap_start_time_s,
        -- Pick weather sample closest to (and not after) lap start
        MAX(w.session_time_s)   AS matched_session_time_s
    FROM laps l
    JOIN weather_raw w
        ON l.race_year = w.race_year
        AND l.race_id  = w.race_id
        AND w.session_time_s <= l.lap_start_time_s
    GROUP BY l.lap_id, l.race_year, l.race_id, l.driver_id, l.lap_number, l.lap_start_time_s
),

-- For laps before first weather sample, fall back to minimum session_time_s
lap_weather_fallback AS (
    SELECT
        l.lap_id,
        l.race_year,
        l.race_id,
        l.driver_id,
        l.lap_number,
        l.lap_start_time_s,
        MIN(w.session_time_s) AS matched_session_time_s
    FROM laps l
    JOIN weather_raw w
        ON l.race_year = w.race_year
        AND l.race_id  = w.race_id
    WHERE NOT EXISTS (
        SELECT 1 FROM weather_raw w2
        WHERE w2.race_year = l.race_year
          AND w2.race_id   = l.race_id
          AND w2.session_time_s <= l.lap_start_time_s
    )
    GROUP BY l.lap_id, l.race_year, l.race_id, l.driver_id, l.lap_number, l.lap_start_time_s
),

combined_matches AS (
    SELECT * FROM lap_weather
    UNION ALL
    SELECT * FROM lap_weather_fallback
)

SELECT
    m.lap_id,
    m.race_year,
    m.race_id,
    m.driver_id,
    m.lap_number,
    w.session_time_s         AS weather_session_time_s,
    w.ambient_temp_c,
    w.track_temp_c,
    w.rainfall_flag,
    w.humidity_pct,
    w.wind_speed_ms,
    w.wind_direction
FROM combined_matches m
JOIN weather_raw w
    ON m.race_year               = w.race_year
    AND m.race_id                = w.race_id
    AND m.matched_session_time_s = w.session_time_s
