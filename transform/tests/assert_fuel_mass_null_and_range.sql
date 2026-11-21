-- Fuel inputs are never NULL by construction (inner joins to the scheduled-distance
-- seed and stg_laps), so a NULL input here is a broken join, not missing data.
-- Any NULL in fuel_mass_kg is therefore a failure: GREATEST(NULL, 0.0) is 0.0 in
-- DuckDB, so a NULL that reached the clamp would look like an empty tank.
--
-- A zero is legitimate only where the unclamped load is <= 0 (past the scheduled
-- distance). A zero on a lap that still has fuel left is a defect.
--
-- Returns a row for each violation.
SELECT
    lap_id,
    race_id,
    lap_number,
    initial_fuel_kg,
    fuel_consumption_rate_kg_per_lap,
    fuel_mass_kg
FROM {{ ref('int_lap_fuel_state') }}
WHERE initial_fuel_kg IS NULL
   OR fuel_consumption_rate_kg_per_lap IS NULL
   OR lap_number IS NULL
   OR fuel_mass_kg IS NULL
   OR fuel_mass_kg < 0
   OR fuel_mass_kg > initial_fuel_kg
   OR (fuel_mass_kg = 0
       AND initial_fuel_kg - fuel_consumption_rate_kg_per_lap * (lap_number - 1) > 0)
