-- Check that fuel weight penalty monotonically strictly decreases as fuel burns off
WITH ranked AS (
  SELECT driver_id, stint_id, fuel_mass_kg, weight_penalty_s,
    ROW_NUMBER() OVER (PARTITION BY driver_id, stint_id ORDER BY fuel_mass_kg DESC) as rank
  FROM {{ ref('int_lap_fuel_state') }}
  WHERE weight_penalty_s IS NOT NULL
)
SELECT r1.driver_id, r1.stint_id, r1.fuel_mass_kg, r1.weight_penalty_s, r2.fuel_mass_kg, r2.weight_penalty_s
FROM ranked r1
JOIN ranked r2 ON r1.driver_id = r2.driver_id AND r1.stint_id = r2.stint_id AND r1.rank = r2.rank - 1
WHERE r1.weight_penalty_s <= r2.weight_penalty_s
