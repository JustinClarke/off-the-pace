-- Sector residual decomposition model identity: sector-grain residual decomposition
--
-- After sector residual decomposition model (sector grain introduction), each sector must close its own identity:
--   sector_pace_delta_s = sector_fuel + sector_compound + sector_rubber
--                       + sector_ambient + sector_constructor
--                       + sector_dirty_air_tax + sector_driver_skill + sector_unexplained
--
-- Tolerance: 0.0001 s (same as lap grain; linear allocation introduces negligible error).
-- Gate: YES proof that the linear sector allocation is mathematically sound.
--
-- Verify that sector_pace_delta_s equals the sum of the components.
SELECT
    sector_id,
    lap_id,
    driver_id,
    race_id,
    lap_number,
    sector,
    sector_pace_delta_s,
    (
        sector_fuel_component_s + sector_compound_component_s + sector_rubber_component_s +
        sector_ambient_component_s + sector_constructor_component_s + sector_dirty_air_tax_s +
        sector_driver_skill_residual_s
    ) AS sum_components,
    ABS(
        sector_pace_delta_s-(
            sector_fuel_component_s + sector_compound_component_s + sector_rubber_component_s +
            sector_ambient_component_s + sector_constructor_component_s + sector_dirty_air_tax_s +
            sector_driver_skill_residual_s
        )
    ) AS discrepancy
FROM {{ ref('int_sector_residual_decomposed') }}
WHERE ABS(
    sector_pace_delta_s-(
        sector_fuel_component_s + sector_compound_component_s + sector_rubber_component_s +
        sector_ambient_component_s + sector_constructor_component_s + sector_dirty_air_tax_s +
        sector_driver_skill_residual_s
    )
) > 0.0001
