-- Initial transform identity: 7-term lap residual decomposition
--
-- After dirty air tax model (dirty_air_tax_s extraction), the identity becomes:
--   pace_delta_s = fuel + compound + rubber + ambient + constructor
--                + dirty_air_tax + driver_skill + unexplained
--
-- This test uses the assert_additive_identity macro to enforce it.
-- It will fail if:
--   1. dirty_air_tax_s is not computed correctly
--   2. driver_skill_residual_s is not updated to shrink by dirty_air_tax_s
--   3. Any component drifts out of the additive formula
--
-- Tolerance: 0.0001 s (same as 6-term identity; float precision).
-- Gate: YES build fails if identity breaks.

{{ assert_additive_identity(
     ref('int_lap_residual_decomposed'),
     'pace_delta_s',
     ['fuel_component_s', 'compound_component_s', 'rubber_component_s',
      'ambient_component_s', 'constructor_component_s', 'dirty_air_tax_s'],
     'driver_skill_residual_s',
     tolerance=0.0001
) }}
