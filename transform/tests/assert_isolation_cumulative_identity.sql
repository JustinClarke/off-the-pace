-- T42 (WI-16a; three-term since W63 design 2, 2026-10-03): the cumulative identity closes.
--
-- Tier 3 decomposes into tier 1 plus the car and traffic, because p = car_iso - y and
-- y = x - (the lap's field median), which two cars on the same lap share. x has the
-- compound seed's C removed, while relative pace is the raw gap (no tyre-age
-- adjustment; peers are matched within var('isolation_peer_age_tolerance') laps of tyre
-- age instead), so
--   pair lap    relative = pace_gap + car_advantage + traffic_advantage + (C(peer) - C(driver))
-- The last term is the tyre-age bias the peer match leaves. It is not published, and it
-- is exactly 0 when both cars are on the same tyre age (C is a function of race,
-- compound and age), so:
--   (1) same-age pair rows   relative = pace_gap + car_advantage + traffic_advantage
--   (2) teammates            car_advantage = 0                 (same car, same race)
--   (3) lap mart             identity_relative - (the three identity_* contributions)
--                            = the lap's mean of (relative - pace_gap - car - traffic)
--                            over its closed pair rows, recomputed here from the pairs
--   (4) lap, stint, race     a non-NULL identity_relative_pace_gain_s has all three
--                            contributions non-NULL
--   (5) vacuity              closed pair rows exist but none is same-age: (1) checks nothing
-- (pure = p + a declared per-season offset since W33, 2026-09-30; it cancels inside a
-- race, so the pair identity is written on pace_gap and never sees it.)
-- All to 1e-6 s. A failure means an identity term was re-derived somewhere instead of
-- carried, or a NULL was COALESCEd into one side only.

WITH pair AS (
    SELECT * FROM {{ ref('fct_driver_isolation_pair_lap') }}
),

agg AS (
    SELECT
        'fct_driver_isolation_lap' AS model,
        lap_id AS row_id,
        identity_relative_pace_gain_s,
        identity_pace_gap_gain_s,
        identity_car_advantage_gain_s,
        identity_traffic_advantage_gain_s
    FROM {{ ref('fct_driver_isolation_lap') }}
    UNION ALL
    SELECT
        'fct_driver_isolation_stint' AS model,
        stint_phase_id AS row_id,
        identity_relative_pace_gain_s,
        identity_pace_gap_gain_s,
        identity_car_advantage_gain_s,
        identity_traffic_advantage_gain_s
    FROM {{ ref('fct_driver_isolation_stint') }}
    UNION ALL
    SELECT
        'fct_driver_isolation_race' AS model,
        driver_race_id AS row_id,
        identity_relative_pace_gain_s,
        identity_pace_gap_gain_s,
        identity_car_advantage_gain_s,
        identity_traffic_advantage_gain_s
    FROM {{ ref('fct_driver_isolation_race') }}
),

-- The lap's tyre-age bias, recomputed from the pair rows the lap mart aggregates.
lap_bias AS (
    SELECT
        lap_id,
        AVG(
            relative_pace_gain_s
            - (pace_gap_gain_s + car_advantage_gain_s + traffic_advantage_gain_s)
        ) AS mean_bias_s
    FROM pair
    WHERE pace_gap_gain_s IS NOT NULL
    GROUP BY lap_id
)

SELECT 'pair (same tyre age): relative != pace_gap + car + traffic' AS issue, lap_id || '|' || peer_lap_id AS row_id
FROM pair
WHERE
    pace_gap_gain_s IS NOT NULL
    AND age_in_stint = peer_age_in_stint
    AND COALESCE(
        ABS(
            relative_pace_gain_s
            - (pace_gap_gain_s + car_advantage_gain_s + traffic_advantage_gain_s)
        ),
        1.0
    ) > 1e-6

UNION ALL

SELECT 'pair: teammates with a car advantage' AS issue, lap_id || '|' || peer_lap_id AS row_id
FROM pair
WHERE is_teammate AND ABS(car_advantage_gain_s) > 1e-6

UNION ALL

SELECT 'fct_driver_isolation_lap: contributions + tyre-age bias != identity_relative' AS issue, l.lap_id AS row_id
FROM {{ ref('fct_driver_isolation_lap') }} AS l
LEFT JOIN lap_bias AS b ON l.lap_id = b.lap_id
WHERE
    l.identity_relative_pace_gain_s IS NOT NULL
    AND COALESCE(
        ABS(
            l.identity_relative_pace_gain_s
            - (
                l.identity_pace_gap_gain_s
                + l.identity_car_advantage_gain_s + l.identity_traffic_advantage_gain_s
                + b.mean_bias_s
            )
        ),
        1.0
    ) > 1e-6

UNION ALL

SELECT model || ': NULL identity contribution next to a non-NULL total' AS issue, row_id
FROM agg
WHERE
    identity_relative_pace_gain_s IS NOT NULL
    AND (
        identity_pace_gap_gain_s IS NULL
        OR identity_car_advantage_gain_s IS NULL
        OR identity_traffic_advantage_gain_s IS NULL
    )

UNION ALL

SELECT 'vacuity: closed pair rows exist but none is same-age' AS issue, CAST(COUNT(*) AS VARCHAR) AS row_id
FROM pair
WHERE pace_gap_gain_s IS NOT NULL
HAVING COUNT(*) > 0 AND COUNT(*) FILTER (WHERE age_in_stint = peer_age_in_stint) = 0
