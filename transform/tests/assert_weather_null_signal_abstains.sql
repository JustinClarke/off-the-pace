-- A NULL field tyre share is no evidence, not a zero vote. Where the share is NULL only two
-- signals (bronze Rainfall and humidity) vote, so the verdict is a majority of two with a tie
-- broken by Rainfall. That makes the verdict equal bronze Rainfall on these laps. Returns one
-- row per violating lap.

SELECT
    lap_id AS key,
    'share NULL: available ' || CAST(wet_signal_available AS VARCHAR)
        || ', rainfall_flag ' || CAST(rainfall_flag AS VARCHAR)
        || ', bronze Rainfall ' || CAST(rainfall_flag_bronze AS VARCHAR) AS reason
FROM {{ ref('stg_weather') }}
WHERE field_wet_tyre_share IS NULL
  AND (wet_signal_available != 2 OR rainfall_flag != COALESCE(rainfall_flag_bronze, FALSE))
