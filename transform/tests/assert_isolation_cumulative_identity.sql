-- T42 (WI-16a): the cumulative identity closes, everywhere it is published.
--
-- Tier 3 decomposes exactly into tiers 1 and 2 plus the car and traffic, because
-- p = car_iso - y and y = x - (the lap's field median), which two cars on the same lap
-- share:
--   pair lap    relative = pace_gap + car_advantage + traffic_advantage
--               pace_gap = pure_gap + tactical_gap           (where both tacticals exist)
--               pure_gap is non-NULL exactly when tactical_gap is
--   lap         pure + tactical = p                          (where tactical is non-NULL)
--   teammates   car_advantage = 0                            (same car, same race)
--   aggregates  identity_relative = pure_gap + tactical_gap + pace_gap_unsplit + car +
--               traffic contributions, in fct_driver_isolation_lap, _stint and _race
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
        identity_pure_gap_gain_s,
        identity_tactical_gap_gain_s,
        identity_pace_gap_unsplit_gain_s,
        identity_car_advantage_gain_s,
        identity_traffic_advantage_gain_s
    FROM {{ ref('fct_driver_isolation_lap') }}
    UNION ALL
    SELECT
        'fct_driver_isolation_stint' AS model,
        stint_phase_id AS row_id,
        identity_relative_pace_gain_s,
        identity_pure_gap_gain_s,
        identity_tactical_gap_gain_s,
        identity_pace_gap_unsplit_gain_s,
        identity_car_advantage_gain_s,
        identity_traffic_advantage_gain_s
    FROM {{ ref('fct_driver_isolation_stint') }}
    UNION ALL
    SELECT
        'fct_driver_isolation_race' AS model,
        driver_race_id AS row_id,
        identity_relative_pace_gain_s,
        identity_pure_gap_gain_s,
        identity_tactical_gap_gain_s,
        identity_pace_gap_unsplit_gain_s,
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

SELECT 'pair: pace_gap != pure_gap + tactical_gap' AS issue, lap_id || '|' || peer_lap_id AS row_id
FROM pair
WHERE
    tactical_gap_gain_s IS NOT NULL
    AND ABS(pace_gap_gain_s - (pure_gap_gain_s + tactical_gap_gain_s)) > 1e-6

UNION ALL

SELECT 'pair: pure_gap and tactical_gap NULL on different rows' AS issue, lap_id || '|' || peer_lap_id AS row_id
FROM pair
WHERE (pure_gap_gain_s IS NULL) != (tactical_gap_gain_s IS NULL)

UNION ALL

SELECT 'pair: teammates with a car advantage' AS issue, lap_id || '|' || peer_lap_id AS row_id
FROM pair
WHERE is_teammate AND ABS(car_advantage_gain_s) > 1e-6

UNION ALL

SELECT 'lap: pure + tactical != p' AS issue, lap_id AS row_id
FROM {{ ref('int_driver_isolation_lap_values') }}
WHERE
    tactical_gain_s IS NOT NULL
    AND ABS(pure_skill_gain_s + tactical_gain_s - pace_isolated_gain_s) > 1e-6

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
                identity_pure_gap_gain_s + identity_tactical_gap_gain_s
                + identity_pace_gap_unsplit_gain_s + identity_car_advantage_gain_s
                + identity_traffic_advantage_gain_s
            )
        ),
        1.0
    ) > 1e-6
