"""R3 F39: a NULL tyre age becomes the 10 s wear cap, because DuckDB's LEAST() skips NULLs.

Defect. int_compound_cliff_predicted.sql:155-161 (compound_wear_s) and :194-202
(expected_compound_pace_s) compute
    LEAST(COALESCE(wear_gradient, 0) * age_in_stint + <cliff term>, var('compound_wear_max_s_per_lap', 10.0))
(the same shape as macros/compound_cliff_wear.sql:compound_cliff_wear_s). When
age_in_stint IS NULL the first argument is NULL, and DuckDB's LEAST ignores NULL
arguments, so the result is the cap itself: 10.0 s of "compound wear". That value is
subtracted into driver_skill_residual_s (int_lap_residual_decomposed.sql:199,311) and so
reaches every residual consumer. The correct value is NULL (age unknown), exactly as
int_lap_thermal_proxy.sql:114-117 already handles the same DuckDB behaviour for GREATEST.

Oracle. Part 1 shows DuckDB's NULL-skipping directly. Part 2 lists every spine lap whose
tyre age is NULL and its compound component / residual next to the same race's other
laps. Part 3 follows them into the app's skill table (fct_driver_skill_features).

DEFECT PRESENT while: any spine lap with NULL age_in_stint has compound_wear_s = 10.0.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show  # noqa: E402

c = con()
show(c, "select least(null::double, 10.0) least_null_10, greatest(null::double, 0.0) greatest_null_0",
     "Part 1: DuckDB LEAST/GREATEST skip NULL arguments")
show(c, """
select r.race_id, count(*) n_spine, count(*) filter (where r.age_in_stint is null) age_null,
  count(*) filter (where r.age_in_stint is null and c.compound_wear_s = 10.0) age_null_at_cap,
  count(*) filter (where r.age_in_stint is null and r.compound is null) of_which_compound_null,
  round(avg(r.compound_component_s) filter (where r.age_in_stint is null), 2) mean_cc_age_null,
  round(avg(r.compound_component_s) filter (where r.age_in_stint is not null), 2) mean_cc_other,
  round(avg(r.driver_skill_residual_s) filter (where r.age_in_stint is null), 2) mean_resid_age_null,
  round(avg(r.driver_skill_residual_s) filter (where r.age_in_stint is not null), 2) mean_resid_other
from int_lap_residual_decomposed r join int_compound_cliff_predicted c using (lap_id)
group by 1 having count(*) filter (where r.age_in_stint is null) > 0 order by 3 desc""",
     "Part 2: spine laps with NULL tyre age get the 10 s cap as compound wear")
show(c, """
select count(*) filter (where r.age_in_stint is null) total_age_null_spine_laps,
  count(*) filter (where r.age_in_stint is null and c.compound_wear_s = 10.0) at_cap,
  count(*) filter (where r.age_in_stint is null and f.is_training_eligible) training_eligible
from int_lap_residual_decomposed r join int_compound_cliff_predicted c using (lap_id)
join fct_cliff_prediction_features f using (lap_id)""", "Part 2b: totals (training eligibility requires age > 3, so none train)")
show(c, """
with bad as (select race_year, race_id, driver_id from int_lap_residual_decomposed where age_in_stint is null group by all)
select f.race_id, count(*) affected_driver_races, round(avg(f.driver_residual_mean_s), 2) mean_resid_affected,
  (select round(avg(x.driver_residual_mean_s), 2) from fct_driver_skill_features x
   where x.race_id = f.race_id and (x.race_year, x.race_id, x.driver_id) not in (select * from bad)) mean_resid_unaffected
from fct_driver_skill_features f join bad using (race_year, race_id, driver_id) group by 1 order by 2 desc""",
     "Part 3: the app's per-driver-race skill (fct_driver_skill_features) in the affected races")
