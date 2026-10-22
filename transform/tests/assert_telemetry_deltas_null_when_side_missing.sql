-- CO-22: fct_telemetry_deltas must never fill a missing side with 0. Each
-- delta is re-derived from int_corner_metrics for both drivers; a row fails if
-- the published delta is non-NULL where either side's metric is missing (no
-- measurement for that corner and lap, or the metric itself NULL, e.g. no
-- braking point on a flat corner), or if a non-NULL delta disagrees with the
-- recomputed difference. The old COALESCE(..., 0) fill fails the first check
-- on every unmatched corner.
WITH d AS (
    SELECT * FROM {{ ref('fct_telemetry_deltas') }}
),

m AS (
    SELECT
        race_id,
        driver_id,
        corner_name,
        lap_number,
        braking_point_m,
        v_min_kph,
        throttle_point_m
    FROM {{ ref('int_corner_metrics') }}
),

joined AS (
    SELECT
        d.race_id,
        d.driver_a,
        d.driver_b,
        d.corner_name,
        d.lap_number,
        d.braking_point_delta_m,
        d.v_min_delta_kph,
        d.throttle_point_delta_m,
        ROUND(a.braking_point_m - b.braking_point_m, 1) AS exp_braking,
        ROUND(a.v_min_kph - b.v_min_kph, 2) AS exp_vmin,
        ROUND(a.throttle_point_m - b.throttle_point_m, 1) AS exp_throttle
    FROM d
    LEFT JOIN m AS a
        ON
            d.race_id = a.race_id
            AND d.driver_a = a.driver_id
            AND d.corner_name = a.corner_name
            AND d.lap_number = a.lap_number
    LEFT JOIN m AS b
        ON
            d.race_id = b.race_id
            AND d.driver_b = b.driver_id
            AND d.corner_name = b.corner_name
            AND d.lap_number = b.lap_number
)

SELECT
    race_id,
    driver_a,
    driver_b,
    corner_name,
    lap_number
FROM joined
WHERE
    braking_point_delta_m IS DISTINCT FROM exp_braking
    OR v_min_delta_kph IS DISTINCT FROM exp_vmin
    OR throttle_point_delta_m IS DISTINCT FROM exp_throttle
