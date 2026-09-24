"""R2-A: 2018 rounds 1-17 — bronze lap 1 has NULL Stint, so stint 1 starts at lap 2.

Effect: int_stint_geometry.lap_in_stint (ROW_NUMBER over stint) and age_in_stint
(bronze TyreLife, counted from the stint's first lap) are both 1 lower than the
true value on every stint-1 lap of those races. Both are contract features.
Lap 1 becomes a pseudo-stint '<year>_<race>_<drv>_' (CONCAT skips NULL).

DEFECT PRESENT while: races_lap1_null > 0 for 2018 AND age_lap2 for 2018-early is
~1 lower than 2018-late / 2019 in both grid groups.
"""
from _db import con, show

c = con()
show(c, r"""
select race_year,
  count(distinct race_id) filter (where lap_number=1 and stint_number is null) races_lap1_null,
  count(distinct race_id) races,
  avg(lap_in_stint) filter (where lap_number=2 and stint_number=1) mean_lap_in_stint_at_lap2
from int_stint_geometry group by 1 order by 1""", "lap-1 NULL stint by season (lap_in_stint at lap 2 should be 2)")

show(c, r"""
with g as (
  select g.*, r.grid_position from int_stint_geometry g
  join stg_results r using (race_year, race_id, driver_id)
  where g.lap_number = 2 and g.stint_number = 1)
select race_year,
  (race_year = 2018 and try_cast(split_part(race_id,'_',2) as int) <= 17) as r2018_early,
  grid_position between 1 and 10 as top10, count(*) n,
  round(avg(age_in_stint), 2) age_at_lap2, mode(age_in_stint) mode_age
from g where race_year <= 2021 group by all order by 1, 2, 3""",
     "tyre age at lap 2, stint 1 (independent check: same Q2-tyre rule 2018-2021)")

show(c, r"""
select count(*) rows_affected,
  count(*) filter (where f.is_training_eligible) eligible_affected,
  (select count(*) from fct_cliff_prediction_features where race_year = 2018 and is_training_eligible) eligible_2018,
  count(*) filter (where f.age_in_stint = 3) at_eligibility_boundary
from fct_cliff_prediction_features f join int_stint_geometry g using (lap_id)
where g.race_year = 2018 and try_cast(split_part(g.race_id,'_',2) as int) <= 17 and g.stint_number = 1""",
     "blast radius in the ML mart")
