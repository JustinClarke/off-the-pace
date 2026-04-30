-- Residual decomposition identity: driver_skill_residual_s must equal
-- pace_delta_s minus total_explained_s (within 0.0001s floating-point tolerance).
--
-- Identity: pace_delta_s = total_explained_s + driver_skill_residual_s + track_unexplained_s
-- This test verifies the first two terms: pace_delta_s-total_explained_s = driver_skill_residual_s.
-- track_unexplained_s is informational and not part of the accountable closure.
--
-- Fails if the additive identity is broken in int_lap_residual_decomposed.
SELECT *
FROM {{ ref('int_lap_residual_decomposed') }}
WHERE lap_time_s IS NOT NULL
  AND base_track_pace_s IS NOT NULL
  AND ABS(
      driver_skill_residual_s
     -(pace_delta_s-total_explained_s)
  ) > 0.0001
