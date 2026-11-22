-- int_lap_rain_state: the rain state is decided by the weather observation alone.
--   * rain_state is DRY / WET / NO_WEATHER, never NULL.
--   * NO_WEATHER if and only if rainfall_flag IS NULL; DRY is exactly FALSE, WET exactly TRUE.
--   * No lap that has a non-NULL stg_weather reading (any car) is NO_WEATHER: a
--     missing pace reference must not erase a weather reading.
--   * A lap without any reading is never DRY.
-- Returns offending rows; passes when empty.
WITH readings AS (
    SELECT DISTINCT race_year, race_id, lap_number
    FROM {{ ref('stg_weather') }}
    WHERE rainfall_flag IS NOT NULL
)

SELECT
    r.race_year,
    r.race_id,
    r.lap_number,
    r.rainfall_flag,
    r.rain_state,
    (w.lap_number IS NOT NULL) AS has_reading
FROM {{ ref('int_lap_rain_state') }} AS r
LEFT JOIN readings AS w
    ON
        r.race_year = w.race_year
        AND r.race_id = w.race_id
        AND r.lap_number = w.lap_number
WHERE
    r.rain_state IS NULL
    OR r.rain_state NOT IN ('DRY', 'WET', 'NO_WEATHER')
    OR (r.rain_state = 'NO_WEATHER') != (r.rainfall_flag IS NULL)
    OR (r.rain_state = 'DRY' AND r.rainfall_flag IS DISTINCT FROM FALSE)
    OR (r.rain_state = 'WET' AND r.rainfall_flag IS DISTINCT FROM TRUE)
    OR (r.rain_state = 'NO_WEATHER' AND w.lap_number IS NOT NULL)
    OR (r.rain_state = 'DRY' AND w.lap_number IS NULL)
