-- rain_state is the three-valued reading of rainfall_flag on int_track_evolution:
-- DRY (flag FALSE), WET (flag TRUE), NO_WEATHER (flag NULL). A lap with no weather
-- reading must be NO_WEATHER, never DRY, and rainfall_flag itself is unchanged
-- (still NULL there, so dry-only consumers select rainfall_flag = FALSE).
-- Returns offending rows; passes when empty.
WITH evo AS (
    SELECT race_year, race_id, lap_number, rainfall_flag, rain_state
    FROM {{ ref('int_track_evolution') }}
),

weather_laps AS (
    SELECT DISTINCT race_year, race_id, lap_number
    FROM {{ ref('stg_weather') }}
    WHERE rainfall_flag IS NOT NULL
)

SELECT
    e.race_year,
    e.race_id,
    e.lap_number,
    e.rainfall_flag,
    e.rain_state,
    CASE
        WHEN e.rain_state IS NULL
            OR e.rain_state NOT IN ('DRY', 'WET', 'NO_WEATHER')
            THEN 'rain_state outside DRY/WET/NO_WEATHER'
        WHEN (e.rain_state = 'NO_WEATHER') != (e.rainfall_flag IS NULL)
            THEN 'NO_WEATHER is not exactly rainfall_flag IS NULL'
        WHEN e.rain_state = 'DRY' AND e.rainfall_flag IS DISTINCT FROM FALSE
            THEN 'DRY without rainfall_flag = FALSE'
        WHEN e.rain_state = 'WET' AND e.rainfall_flag IS DISTINCT FROM TRUE
            THEN 'WET without rainfall_flag = TRUE'
        WHEN e.rain_state = 'DRY' AND w.lap_number IS NULL
            THEN 'missing weather classified DRY'
    END AS reason
FROM evo AS e
LEFT JOIN weather_laps AS w
    ON
        e.race_year = w.race_year
        AND e.race_id = w.race_id
        AND e.lap_number = w.lap_number
WHERE
    e.rain_state IS NULL
    OR e.rain_state NOT IN ('DRY', 'WET', 'NO_WEATHER')
    OR (e.rain_state = 'NO_WEATHER') != (e.rainfall_flag IS NULL)
    OR (e.rain_state = 'DRY' AND e.rainfall_flag IS DISTINCT FROM FALSE)
    OR (e.rain_state = 'WET' AND e.rainfall_flag IS DISTINCT FROM TRUE)
    OR (e.rain_state = 'DRY' AND w.lap_number IS NULL)
