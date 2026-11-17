-- TX-20 / HD16. stg_telemetry keeps 0 < distance_m < a per-circuit bound
-- (circuit length x 1.10, floored at 6500 m). Three ways it can go wrong:
--   spa_samples_dropped   a genuine Spa sample below 7704 m was dropped (the old
--                         fixed 6500 m cut lost ~10% of every Spa race)
--   runaway_retained      a runaway-distance sample (>= 7704 m anywhere, or
--                         >= 6500 m at a circuit outside the long-circuit list)
--                         got through
--   unlisted_long_circuit a circuit whose typical lap is over 6000 m has no row
--                         in stg_telemetry's circuit_bound list
-- Returns one row per violation; zero rows passes.

WITH raw AS (
    SELECT
        race AS race_slug,
        CAST(race_id AS VARCHAR) AS race_id,
        driver_id,
        lap_number,
        distance_m
    FROM {{ source('bronze_f1', 'raw_telemetry') }}
    WHERE distance_m > 0
),

raw_spa AS (
    SELECT race_id, COUNT(*) AS n_raw
    FROM raw
    WHERE race_slug = 'belgian_grand_prix' AND distance_m < 7704
    GROUP BY race_id
),

stg_spa AS (
    SELECT race_id, COUNT(*) AS n_stg
    FROM {{ ref('stg_telemetry') }}
    WHERE race_id IN (SELECT race_id FROM raw_spa)
    GROUP BY race_id
),

lap_max AS (
    SELECT race_slug, race_id, driver_id, lap_number, MAX(distance_m) AS max_d
    FROM raw
    GROUP BY ALL
),

typical AS (
    SELECT race_slug, MEDIAN(max_d) AS median_lap_max_m
    FROM lap_max
    GROUP BY race_slug
),

short_circuit_ids AS (
    SELECT DISTINCT race_id
    FROM raw
    WHERE race_slug NOT IN (
        'belgian_grand_prix', 'las_vegas_grand_prix',
        'saudi_arabian_grand_prix', 'azerbaijan_grand_prix'
    )
)

SELECT
    'spa_samples_dropped' AS check_name,
    r.race_id AS detail
FROM raw_spa AS r
LEFT JOIN stg_spa AS s USING (race_id)
WHERE COALESCE(s.n_stg, 0) <> r.n_raw

UNION ALL

SELECT
    'runaway_retained',
    race_id
FROM {{ ref('stg_telemetry') }}
GROUP BY race_id
HAVING
    MAX(distance_m) >= 7704
    OR (
        race_id IN (SELECT race_id FROM short_circuit_ids)
        AND MAX(distance_m) >= 6500
    )

UNION ALL

SELECT
    'unlisted_long_circuit',
    race_slug
FROM typical
WHERE
    median_lap_max_m > 6000
    AND race_slug NOT IN (
        'belgian_grand_prix', 'las_vegas_grand_prix',
        'saudi_arabian_grand_prix', 'azerbaijan_grand_prix'
    )
