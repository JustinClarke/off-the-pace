-- Driver skill residual sanity check: for ml_eligible laps, the residual (delta from
-- field pace after physics corrections) must be within ±16s of zero. Values outside
-- this range indicate a decomposition component has blown up (e.g., constructor or
-- compound component returning extreme values from thin samples).
-- The residual is field-relative: driver_skill_residual_s = (lap_time-field_pace)-components.
-- Typical range is ±3s; ±16s catches genuine blowups while allowing for wet races / unusual circuits.
--
-- Bound raised 15.0 -> 16.0 by WI-01 (2026-09-27): the label spine version bump
-- (fuel- AND compound-neutral base, no rubber/ambient double subtraction) moves
-- driver_skill_residual_s on every row, and 3 genuinely slow laps (2018_2:ALO lap 56,
-- 2024_12:LEC/PER lap 22 -- all with small, unremarkable fuel/compound/constructor/
-- dirty-air components and a large pace_delta_s, i.e. a real slow lap, not a blown-up
-- component) moved from just under the old bound to just over it (max observed
-- 15.87 s). Raised to clear the observed max with margin, matching
-- assert_ghost_recombination.sql's convention for a measured, documented bound move.
--
-- Raised 16.0 -> 17.0 in WI-01's verification pass (2026-09-27): F35 dropped the
-- circuit x constructor interaction from constructor_component_s, and the same
-- 2024_12:PER lap 22 lost Red Bull's +0.136 s interaction there, taking it from
-- 15.871 to 16.007 s. Components unchanged otherwise (compound 0.20 s,
-- constructor -0.37 s, dirty air 0); it is the same real slow lap (lap time
-- 104.9 s), not a blow-up. Max observed after the pass: 16.007 s.
SELECT *
FROM {{ ref('fct_lap_residuals') }}
WHERE ml_eligible = TRUE
  AND ABS(driver_skill_residual_s) > 17.0
