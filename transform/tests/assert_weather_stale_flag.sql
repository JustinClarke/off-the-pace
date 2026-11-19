-- The stale-sample flag is exactly "sample more than var('wet_stale_sample_s') seconds before lap
-- start". It is a flag only, so it must never change the wet verdict relative to the vote itself.
-- Returns one row per lap where the flag disagrees with its definition.

SELECT
    lap_id AS key,
    'age ' || CAST(weather_sample_age_s AS VARCHAR) || ' s, stale flag '
        || CAST(weather_sample_stale AS VARCHAR) AS reason
FROM {{ ref('stg_weather') }}
WHERE weather_sample_stale
    != (weather_sample_age_s > {{ var('wet_stale_sample_s') }})
   OR weather_sample_stale IS NULL
