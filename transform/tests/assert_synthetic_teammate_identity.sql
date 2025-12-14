-- Synthetic teammate identity test: when ego and teammate are on identical compound and age,
-- teammate_pace_adjusted_s must equal teammate_raw_lap_time_s within a tolerance of 0.001s.
SELECT
    *
FROM {{ ref('int_synthetic_teammate') }} t
-- Join ego and teammate stint geometry to ensure identical tyre state
JOIN {{ ref('int_stint_geometry') }} eg 
  ON eg.race_year = t.race_year 
  AND eg.race_id = t.race_id 
  AND eg.driver_id = t.ego_driver_id 
  AND eg.lap_number = t.lap_number
JOIN {{ ref('int_stint_geometry') }} tm 
  ON tm.race_year = t.race_year 
  AND tm.race_id = t.race_id 
  AND tm.driver_id = t.teammate_driver_id 
  AND tm.lap_number = t.lap_number
WHERE eg.compound_in_stint = tm.compound_in_stint
  AND eg.age_in_stint = tm.age_in_stint
  AND t.teammate_available_flag = TRUE
  AND ABS(t.teammate_pace_adjusted_s-t.tm_wc_lap_time_s) > 0.001
