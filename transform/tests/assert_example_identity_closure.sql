-- Reference example for the assert_additive_identity macro (updated initial release: 7-term).
-- Superseded as the canonical test by assert_lap_7term_identity.sql.
-- Kept here as a usage example for the macro pattern.

{{ assert_additive_identity(
     ref('int_lap_residual_decomposed'),
     'pace_delta_s',
     ['fuel_component_s', 'compound_component_s', 'rubber_component_s',
      'ambient_component_s', 'constructor_component_s', 'dirty_air_tax_s'],
     'driver_skill_residual_s',
     tolerance=0.0001
) }}
