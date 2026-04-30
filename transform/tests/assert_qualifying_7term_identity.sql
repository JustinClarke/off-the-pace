-- Qualifying decomposition model identity: qualifying 7-term residual decomposition
--
-- After qualifying decomposition model (qualifying decomposition), qualifying laps must close the 7-term identity
-- with their own (re-fit) coefficients:
--   quali_pace_delta_s = quali_fuel + quali_compound + quali_rubber
--                      + quali_ambient + quali_constructor + quali_dirty_air_tax
--                      + quali_driver_skill + quali_unexplained
--
-- Tolerance: 0.0001 s (same as race lap grain).
-- Gate: YES proof that qualifying coefficients are mathematically sound.
--
-- Verify that quali_pace_delta_s equals the sum of the components.
SELECT
    lap_id,
    driver_id,
    race_id,
    lap_number,
    quali_pace_delta_s,
    (
        fuel_component_s + compound_component_s + rubber_component_s +
        ambient_component_s + constructor_component_s + dirty_air_tax_s +
        quali_skill_residual_s
    ) AS sum_components,
    ABS(
        quali_pace_delta_s-(
            fuel_component_s + compound_component_s + rubber_component_s +
            ambient_component_s + constructor_component_s + dirty_air_tax_s +
            quali_skill_residual_s
        )
    ) AS discrepancy
FROM {{ ref('int_qualifying_decomposed') }}
WHERE ABS(
    quali_pace_delta_s-(
        fuel_component_s + compound_component_s + rubber_component_s +
        ambient_component_s + constructor_component_s + dirty_air_tax_s +
        quali_skill_residual_s
    )
) > 0.0001
