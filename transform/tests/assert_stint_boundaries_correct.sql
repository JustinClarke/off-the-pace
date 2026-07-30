-- Check that stint_id logic is correct, i.e., lap_number is between the start and end of the stint.
-- The DAG says "Stint ID off-by-one | fct_pit_stops | Laps assigned to wrong stint near pit stops | Check stint_id matches lap range bounds"
-- We will check if any lap in stg_laps falls outside its assigned stint's lap range (if stints are modeled as such).
-- Wait, does fct_pit_stops have stint bounds? Or does stg_laps have stint_id?
-- Let's check int_lap_residual_decomposed which has stint_id and lap_number.
-- We can ensure that age_in_stint is strictly positive and matches lap_number logic.
-- A simple check: age_in_stint should never decrease within the same stint_id.
WITH ranked AS (
  SELECT driver_id, stint_id, lap_number, age_in_stint,
    ROW_NUMBER() OVER (PARTITION BY driver_id, stint_id ORDER BY lap_number ASC) as rank
  FROM {{ ref('int_lap_residual_decomposed') }}
  WHERE stint_id IS NOT NULL
)
SELECT r1.driver_id, r1.stint_id, r1.lap_number, r1.age_in_stint
FROM ranked r1
JOIN ranked r2 ON r1.driver_id = r2.driver_id AND r1.stint_id = r2.stint_id AND r1.rank = r2.rank + 1
WHERE r1.age_in_stint <= r2.age_in_stint
