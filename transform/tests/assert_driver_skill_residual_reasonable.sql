-- Driver skill residual sanity check: for ml_eligible laps, the residual
-- (delta from field pace after physics corrections) must be within ±15 s of
-- zero. Values outside this range indicate a decomposition component has
-- blown up (e.g., constructor or compound component returning extreme values
-- from thin samples). The residual is field-relative:
-- driver_skill_residual_s = (lap_time - field_pace) - components. Typical
-- range is ±3 s; ±15 s catches genuine blowups while allowing for wet races
-- and unusual circuits.
--
-- RULE (TX-08, 2026-11-08). The bound is the original blow-up bound, 15.0 s,
-- fixed by what it guards and not by the observed maximum. It is never raised
-- to clear an observed lap. A lap that crosses it is reported (lap_id,
-- components, pace_delta_s) to the owner as a finding; if the owner rules it
-- a real slow lap, that lap leaves ml_eligible upstream (a modelled exclusion
-- with a reason), not this test.
--
-- History (why the rule exists): the bound was raised three times, each time
-- to clear the lap that had just crossed it: 15 -> 16 -> 17 (WI-01,
-- 2026-09-27: 2018_2 ALO lap 56, 2024_12 LEC/PER lap 22; max 15.87 s, then
-- 16.007 s after F35) and 17 -> 19 (2026-09-29: 2025_18 HAM lap 62,
-- 17.916 s). On the v16 build checked by TX-08 (2026-11-08) the max |residual|
-- on ml_eligible laps is 13.82 s (2024_12 PER lap 22), 8 laps exceed 10 s,
-- none exceeds 15 s, p99.99 is 9.54 s, and 2025_18 HAM lap 62 is 12.73 s, so
-- the original bound holds.
SELECT
    lap_id,
    race_id,
    driver_id,
    lap_number,
    pace_delta_s,
    fuel_component_s,
    compound_component_s,
    constructor_component_s,
    dirty_air_tax_s,
    driver_skill_residual_s
FROM {{ ref('fct_lap_residuals') }}
WHERE
    ml_eligible = TRUE
    AND ABS(driver_skill_residual_s) > 15.0
