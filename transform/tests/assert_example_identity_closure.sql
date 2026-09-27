-- Reference example for the assert_additive_identity macro, using the current
-- (WI-01, 5-term) identity. Superseded as the canonical test by
-- assert_lap_7term_identity.sql. Kept here as a usage example for the macro
-- pattern -- updated alongside it so this example test cannot itself go stale
-- and fail on a real fix (as it did on WI-01's rubber/ambient de-duplication).

{{ assert_additive_identity(
     ref('int_lap_residual_decomposed'),
     'pace_delta_s',
     ['fuel_component_s', 'compound_component_s', 'constructor_component_s', 'dirty_air_tax_s'],
     'driver_skill_residual_s',
     tolerance=0.0001
) }}
