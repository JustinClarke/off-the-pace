-- Per-lap rain state, independent of the pace reference.
--
-- Grain: one row per (race_year, race_id, lap_number) for every lap in stg_laps.
-- The weather is shared by every car on a lap, so the race-lap key is the right
-- grain, and it is the key every dry-only consumer already joins on.
--
-- Why this model exists: the rainfall signal used to be read from
-- int_track_evolution, which only has a row for a lap whose pace cell is non-thin
-- (int_field_pace_curve, NOT low_sample_flag). A real lap with weather but no pace
-- cell therefore had a NULL flag and read as NO_WEATHER, and the strict dry-only
-- predicate (rainfall_flag = FALSE) dropped it. This model decides the rain state
-- from the weather observation alone: it never reads int_field_pace_curve.
--
-- rain_state:
--   DRY         a weather observation exists and rainfall_flag is FALSE
--   WET         a weather observation exists and rainfall_flag is TRUE
--   NO_WEATHER  no weather observation exists for any car on that lap
--               (rainfall_flag NULL). Never DRY: a missing observation is not an
--               inference of dry.
-- NO_WEATHER <=> rainfall_flag IS NULL. rainfall_flag keeps the meaning it has in
-- stg_weather (the wet-conditions verdict, not bronze Rainfall).
--
-- One weather row per lap. stg_weather is one row per lap_id (driver x lap);
-- cars on the same lap can ASOF-match different weather samples near a sample
-- boundary (verified: up to 20 rows per key, ~46% with differing track_temp_c),
-- so ties on the DISTINCT ON key are real. The ORDER BY is a total order, so the
-- pick does not depend on scan order or parallelism.
{{ config(materialized='table') }}

WITH race_laps AS (
    SELECT DISTINCT
        race_year,
        race_id,
        lap_number
    FROM {{ ref('stg_laps') }}
),

weather_per_lap AS (
    SELECT DISTINCT ON (race_year, race_id, lap_number)
        race_year,
        race_id,
        lap_number,
        track_temp_c,
        humidity_pct,
        rainfall_flag
    FROM {{ ref('stg_weather') }}
    ORDER BY
        race_year ASC,
        race_id ASC,
        lap_number ASC,
        weather_session_time_s DESC,
        driver_id ASC,
        lap_id ASC
)

SELECT
    l.race_year,
    l.race_id,
    l.lap_number,
    w.track_temp_c,
    w.humidity_pct,
    w.rainfall_flag,
    CASE
        WHEN w.rainfall_flag IS NULL THEN 'NO_WEATHER'
        WHEN w.rainfall_flag THEN 'WET'
        ELSE 'DRY'
    END AS rain_state
FROM race_laps AS l
LEFT JOIN weather_per_lap AS w
    ON
        l.race_year = w.race_year
        AND l.race_id = w.race_id
        AND l.lap_number = w.lap_number
