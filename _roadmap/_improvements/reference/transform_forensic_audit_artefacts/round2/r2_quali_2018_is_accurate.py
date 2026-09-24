"""R2-N: 2018 qualifying laps fail the validity gate on FastF1's IsAccurate flag.

stg_laps_qualifying.sql:146-151 is_valid_lap requires is_accurate. In 2018 FastF1 marks 26% of timed,
non-pit qualifying laps inaccurate (every other season < 0.5%), so the qualifying chain sees 1-2 laps per
driver or none: 2018_1 keeps 14 of 118 timed laps and 11 of 20 drivers get NULL quali features.
Consumers: the seven `qualifying` contract features (cliff_classifier only) and the app's quali pages.
Round-1 feature_null_by_season.csv already shows the symptom (8.0% NULL in 2018 vs <=2.0%) without a cause.

DEFECT PRESENT while: 2018 accurate share of timed non-pit quali laps << other seasons.
"""
from _db import con, show

c = con()
show(c, r"""
select race_year, count(*) timed_non_pit_laps,
  round(avg(case when is_accurate then 1.0 else 0 end), 3) accurate_share
from stg_laps_qualifying where lap_time_s is not null and not is_pit_lap group by 1 order by 1""",
     "IsAccurate on timed, non-pit qualifying laps")
show(c, r"""
select f.race_year, count(*) eligible_rows,
  round(avg(case when f.quali_skill_session_avg_s is null then 1.0 else 0 end), 3) quali_feature_null_share
from fct_cliff_prediction_features f where f.is_training_eligible group by 1 order by 1""",
     "consequence: NULL qualifying features on training rows")
show(c, r"""
select race_id, count(*) timed_non_pit, count(*) filter (where is_accurate) accurate,
  count(distinct driver_id) drivers, count(distinct driver_id) filter (where is_valid_lap) drivers_with_a_valid_lap
from stg_laps_qualifying where lap_time_s is not null and not is_pit_lap and race_year = 2018
group by 1 order by accurate limit 6""", "worst 2018 sessions")
