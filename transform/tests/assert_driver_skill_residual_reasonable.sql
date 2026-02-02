-- Driver skill residual sanity check: for ml_eligible laps, the residual (delta from
-- field pace after physics corrections) must be within ±15s of zero. Values outside
-- this range indicate a decomposition component has blown up (e.g., constructor or
-- compound component returning extreme values from thin samples).
-- The residual is field-relative: driver_skill_residual_s = (lap_time-field_pace)-components.
-- Typical range is ±3s; ±15s catches genuine blowups while allowing for wet races / unusual circuits.
SELECT *
FROM {{ ref('fct_lap_residuals') }}
WHERE ml_eligible = TRUE
  AND ABS(driver_skill_residual_s) > 15.0
