-- T21 (WI-05, F26). The wet-conditions flag agrees with the tyres the field ran.
--
-- Bronze Rainfall said 83% "raining" at the dry 2018 Spanish and 2019 Monaco GPs
-- (0% of laps on intermediates, 52% humidity) and never fired at the 2020 and
-- 2021 Turkish GPs (~100% on inters/wets). stg_weather.rainfall_flag is now a
-- two-of-three vote (bronze Rainfall, humidity, field tyre share); this checks
-- its outcome per race against the compounds actually run:
--
-- 1. a race flagged wet on most of its laps must have had cars on wet-weather
--    tyres (> 5% of laps);
-- 2. a race run mostly on inters/wets (> 50% of laps) must carry a wet flag.
--
-- The compound share here is read per race and per car-lap, a different
-- aggregate from the per-lap field majority the vote uses.

WITH per_race AS (
    SELECT
        l.race_id,
        AVG(CASE WHEN w.rainfall_flag THEN 1.0 ELSE 0.0 END) AS wet_flag_share,
        AVG(
            CASE WHEN l.compound IN ('INTERMEDIATE', 'WET') THEN 1.0 ELSE 0.0 END
        ) FILTER (WHERE l.compound IS NOT NULL) AS wet_tyre_share
    FROM {{ ref('stg_laps') }} AS l
    INNER JOIN {{ ref('stg_weather') }} AS w ON l.lap_id = w.lap_id
    GROUP BY l.race_id
)

SELECT
    'flagged_wet_but_field_on_slicks' AS check_name,
    race_id || ': wet flag ' || ROUND(wet_flag_share, 3) || ', wet tyres '
    || ROUND(wet_tyre_share, 3) AS detail
FROM per_race
WHERE wet_flag_share > 0.5 AND COALESCE(wet_tyre_share, 0.0) < 0.05

UNION ALL

SELECT
    'field_on_wets_but_never_flagged' AS check_name,
    race_id || ': wet flag ' || ROUND(wet_flag_share, 3) || ', wet tyres '
    || ROUND(wet_tyre_share, 3) AS detail
FROM per_race
WHERE wet_tyre_share > 0.5 AND wet_flag_share = 0
