-- T42 (WI-16a): the cumulative identity closes, everywhere it is published.
--
-- Tier 3 decomposes exactly into tier 1 plus the car and traffic, because
-- p = car_iso - y and y = x - (the lap's field median), which two cars on the same lap
-- share:
--   pair lap    relative = pace_gap + car_advantage + traffic_advantage
--   lap         pure = p                                      (the driver's pace)
--   teammates   car_advantage = 0                            (same car, same race)
--   aggregates  identity_relative = pace_gap + car + traffic
--               contributions, in fct_driver_isolation_lap, _stint and _race
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
)

SELECT 'pair: relative != pace_gap + car + traffic' AS issue, lap_id || '|' || peer_lap_id AS row_id
FROM pair
WHERE
    pace_gap_gain_s IS NOT NULL
    AND ABS(
        relative_pace_gain_s
        - (pace_gap_gain_s + car_advantage_gain_s + traffic_advantage_gain_s)
    ) > 1e-6

UNION ALL

SELECT 'pair: teammates with a car advantage' AS issue, lap_id || '|' || peer_lap_id AS row_id
FROM pair
WHERE is_teammate AND ABS(car_advantage_gain_s) > 1e-6

UNION ALL

SELECT model || ': identity contributions do not sum' AS issue, row_id
FROM agg
WHERE
    identity_relative_pace_gain_s IS NOT NULL
    -- A NULL contribution next to a non-NULL total is a failure too, not a skip.
    AND COALESCE(
        ABS(
            identity_relative_pace_gain_s
            - (
                identity_pace_gap_gain_s
                + identity_car_advantage_gain_s + identity_traffic_advantage_gain_s
            )
        ),
        1.0
    ) > 1e-6
