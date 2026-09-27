-- T43 (WI-16a): the published sign is "positive = faster", checked from raw lap times.
--
-- This repo has shipped two sign inversions from the residual chain's opposite convention
-- (F50, F28), so the sign is pinned from outside the isolation chain. Take teammates on
-- the same lap, compound and tyre age (same car, same C), whose RAW lap times
-- (int_lap_residual_decomposed, not the isolation models) differ by more than 0.5 s,
-- with dirty-air taxes within 0.25 s of each other. The faster car must have the larger
-- pace_isolated_gain_s, and its pair row (focal = the faster car) must have
-- relative_pace_raw_gain_s > 0 and relative_pace_gain_s > 0. With the same car and the
-- same C, p_fast - p_slow = (t_slow - t_fast) + (D_fast - D_slow) > 0.5 - 0.25.
--
-- Vacuity guard: at least 100 such pairs must exist (thousands do on the full build), so
-- the test cannot pass by matching nothing.

WITH raw AS (
    SELECT
        lap_id,
        lap_time_s,
        dirty_air_tax_s
    FROM {{ ref('int_lap_residual_decomposed') }}
),

candidates AS (
    SELECT
        pl.lap_id,
        pl.peer_lap_id,
        pl.relative_pace_raw_gain_s,
        pl.relative_pace_gain_s,
        fa.pace_isolated_gain_s AS fast_p,
        sl.pace_isolated_gain_s AS slow_p
    FROM {{ ref('fct_driver_isolation_pair_lap') }} AS pl
    INNER JOIN raw AS rf
        ON pl.lap_id = rf.lap_id
    INNER JOIN raw AS rs
        ON pl.peer_lap_id = rs.lap_id
    INNER JOIN {{ ref('fct_driver_isolation_lap') }} AS fa
        ON pl.lap_id = fa.lap_id
    INNER JOIN {{ ref('fct_driver_isolation_lap') }} AS sl
        ON pl.peer_lap_id = sl.lap_id
    WHERE
        pl.is_teammate
        AND pl.age_in_stint = pl.peer_age_in_stint
        AND rs.lap_time_s - rf.lap_time_s > 0.5
        AND ABS(rf.dirty_air_tax_s - rs.dirty_air_tax_s) < 0.25
        -- Teammates share a car term, so both are NULL or neither is.
        AND fa.pace_isolated_gain_s IS NOT NULL
)

SELECT
    'wrong sign' AS issue,
    lap_id,
    peer_lap_id,
    relative_pace_raw_gain_s,
    relative_pace_gain_s,
    fast_p,
    slow_p
FROM candidates
WHERE
    NOT (fast_p > slow_p)
    OR NOT (relative_pace_raw_gain_s > 0)
    OR NOT (relative_pace_gain_s > 0)

UNION ALL

SELECT
    'fewer than 100 qualifying teammate pairs' AS issue,
    NULL AS lap_id,
    NULL AS peer_lap_id,
    COUNT(*) AS relative_pace_raw_gain_s,
    NULL AS relative_pace_gain_s,
    NULL AS fast_p,
    NULL AS slow_p
FROM candidates
HAVING COUNT(*) < 100
