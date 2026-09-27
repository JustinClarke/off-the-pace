-- 5-term lap residual decomposition identity (WI-01, 2026-09-27; was 7-term).
--
-- Option A: base_track_pace_s is fuel- AND compound-neutral and already
-- contains rubber/ambient (int_track_evolution decomposes that same base),
-- so they are no longer subtracted a second time here (F22) -- they remain
-- informational columns on int_lap_residual_decomposed, not identity terms.
-- The identity is now:
--   pace_delta_s = fuel + compound + constructor + dirty_air_tax
--                + driver_skill
-- NOTE: track_unexplained_s is NOT in the closure it is an informational
-- field-level diagnostic (see int_lap_residual_decomposed header).
--
-- Uses the assert_additive_identity macro to enforce it. Fails if:
--   1. dirty_air_tax_s is not computed correctly
--   2. driver_skill_residual_s does not shrink by dirty_air_tax_s
--   3. Any component drifts out of the additive formula
--
-- Tolerance: 0.0001 s (float precision).
-- Gate: YES build fails if identity breaks.

{{ assert_additive_identity(
     ref('int_lap_residual_decomposed'),
     'pace_delta_s',
     ['fuel_component_s', 'compound_component_s', 'constructor_component_s', 'dirty_air_tax_s'],
     'driver_skill_residual_s',
     tolerance=0.0001
) }}
