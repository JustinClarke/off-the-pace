-- T41 (WI-16a): the FD1 proof, mechanically. The isolation ratings do not depend on the
-- base a lap is compared against.
--
-- The residual chain writes
--   driver_skill_residual_s + constructor_component_s
--     = lap_time - base - fuel - rubber - ambient - compound - dirty_air
--     = x_s - (base + fuel + rubber + ambient)
-- and base, fuel, rubber and ambient each depend on (race, lap) alone. So centring
-- (residual + constructor) on the lap's Ω median must give back y_s exactly. The panel
-- builds y_s from lap time and never reads the base or those three components; this test
-- re-derives it from the residual chain, which does. Whatever FD1 does to the base (Option A
-- or B, F1's fabricated base, F22's double subtraction, F38's field-average compound
-- cost), it is per (race, lap), so it cannot move y_s -- and if a future change makes one of
-- those terms vary by driver on a lap (per-driver fuel, say), this test fails and the
-- invariance claim in the WI doc stops being true.
--
-- Scope: (race, lap) cells where every Ω lap has a measured base (base_track_pace_s NOT
-- NULL). With the base NULL the residual chain COALESCEs pace_delta_s to 0, so the
-- identity above does not hold there by construction. Tolerance 1e-6 s.
--
-- Vacuity guard: the check must cover at least 90% of Ω laps (96.3% on the 2026-09-26
-- build), so a base that went NULL everywhere cannot make this pass by checking nothing.

WITH chain AS (
    SELECT
        p.lap_id,
        p.race_year,
        p.race_id,
        p.lap_number,
        p.y_s,
        r.base_track_pace_s,
        r.driver_skill_residual_s + r.constructor_component_s AS chain_x_s
    FROM {{ ref('int_driver_isolation_lap_panel') }} AS p
    INNER JOIN {{ ref('int_lap_residual_decomposed') }} AS r
        ON p.lap_id = r.lap_id
),

cells AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        MEDIAN(chain_x_s) AS chain_median_s
    FROM chain
    GROUP BY race_year, race_id, lap_number
    HAVING BOOL_AND(base_track_pace_s IS NOT NULL)
),

checked AS (
    SELECT
        ch.lap_id,
        ch.y_s,
        ch.chain_x_s - c.chain_median_s AS y_from_chain_s
    FROM chain AS ch
    INNER JOIN cells AS c
        ON
            ch.race_year = c.race_year
            AND ch.race_id = c.race_id
            AND ch.lap_number = c.lap_number
)

SELECT
    'y_s differs from the residual-chain centring' AS issue,
    lap_id,
    y_s - y_from_chain_s AS diff_s
FROM checked
WHERE ABS(y_s - y_from_chain_s) > 1e-6

UNION ALL

SELECT
    'check covers under 90% of Ω laps' AS issue,
    NULL AS lap_id,
    (SELECT COUNT(*) FROM checked) * 1.0 / COUNT(*) AS diff_s
FROM chain
HAVING (SELECT COUNT(*) FROM checked) < 0.9 * COUNT(*)
