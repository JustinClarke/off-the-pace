-- Check that predicted ghost lap times are within a realistic bound of the actual lap time.
-- The DAG says "Ghost car laps implausibly fast/slow | Check fuel envelope bounds, interpolation logic"
-- A ghost car lap shouldn't be more than 10 seconds faster or slower than the actual lap time.
SELECT ghost_id, actual_lap_time_s, predicted_lap_time_s
FROM {{ ref('fct_ghost_car_pace') }}
WHERE ABS(predicted_lap_time_s - actual_lap_time_s) > 10.0
