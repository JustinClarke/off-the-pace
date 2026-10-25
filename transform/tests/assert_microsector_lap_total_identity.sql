-- DA-02 lap-total identity: the 20 micro-sector times of a lap add up to the
-- lap time. The micro-sector times telescope to the difference of the lap's two
-- lap-line crossings, so this ties the interpolated position-channel clock to
-- the timing feed's own lap time (stg_laps.lap_time_s). Measured on dev
-- 2026-10-24 over 133,685 complete laps: median |difference| 0.026-0.032 s per
-- season, p95 0.079-0.110 s, signed median 0.000 s (no bias). Sixteen laps
-- differ by more than 0.5 s (2019: 1, worst 3.05 s; 2020: 15, worst 358 s; none
-- in the other six seasons), 0.11% of 2020's complete laps.
--
-- A lap is complete when all 20 micro-sectors have a time_s (so it is green,
-- off the pit lane, with every boundary recorded).
--
-- One row per failure:
--   'lap_total_differs'    |sum - lap_time_s| > 0.5 s on more than 0.5% of a
--                          season's complete laps
--   'too_few_complete_laps' fewer than 50% of the laps with a lap time and any
--                          micro-sector row are complete (vacuity guard)
WITH laps AS (
    SELECT
        m.race_year,
        m.lap_id,
        SUM(m.time_s) AS sum_time_s,
        COUNT(m.time_s) AS n_timed
    FROM {{ ref('int_microsector_proximity') }} AS m
    GROUP BY m.race_year, m.lap_id
),

joined AS (
    SELECT
        l.race_year,
        l.lap_id,
        l.n_timed,
        l.sum_time_s,
        s.lap_time_s
    FROM laps AS l
    INNER JOIN {{ ref('stg_laps') }} AS s
        ON l.lap_id = s.lap_id
    WHERE s.lap_time_s IS NOT NULL
),

by_season AS (
    SELECT
        race_year,
        COUNT(*) FILTER (WHERE n_timed = {{ var('microsector_n') }}) AS n_complete,
        COUNT(*) FILTER (
            WHERE
                n_timed = {{ var('microsector_n') }}
                AND ABS(sum_time_s - lap_time_s) > 0.5
        ) AS n_off
    FROM joined
    GROUP BY race_year
)

SELECT
    'lap_total_differs' AS issue,
    CAST(race_year AS VARCHAR) AS detail
FROM by_season
WHERE n_off > 0.005 * n_complete

UNION ALL

SELECT
    'too_few_complete_laps' AS issue,
    CAST(COUNT(*) FILTER (WHERE n_timed = {{ var('microsector_n') }}) AS VARCHAR)
    AS detail
FROM joined
HAVING
    COUNT(*) FILTER (WHERE n_timed = {{ var('microsector_n') }})
    < 0.5 * COUNT(*)
