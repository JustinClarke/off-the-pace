-- Ghost car model identity: ghost-car degenerate self-consistency
--
-- The ghost-car recombination formula must be a mathematical identity when the ego driver
-- is driving their own car:
--   predicted_lap_time_s(ego=D, host=constructor_of_D, race=R, lap=L)
--      = actual_lap_time_s(D, R, L) ± 0.0001 s
--
-- This is a strict consistency proof. If predicted ≠ actual for the self-case, the
-- recombination math is wrong and the entire model is invalid.
--
-- Tolerance: 0.0001 s (same as component identities).
-- Gate: YES build fails if the recombination formula is mathematically broken.
--
-- Verify that predicted_lap_time_s equals actual_lap_time_s when ego == host (self-consistency).
SELECT
    ghost_id,
    ego_driver_id,
    ego_constructor_id,
    host_constructor_id,
    lap_number,
    actual_lap_time_s,
    predicted_lap_time_s,
    ABS(predicted_lap_time_s-actual_lap_time_s) AS discrepancy
FROM {{ ref('fct_ghost_car_pace') }}
WHERE ego_constructor_id = host_constructor_id
  AND ABS(predicted_lap_time_s-actual_lap_time_s) > 0.0001
