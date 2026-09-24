"""R2-G: the bronze Rainfall flag contradicts the tyres the field actually ran.

Independent in-tree oracle: stg_laps.compound. A lap run on INTERMEDIATE/WET is wet-track
evidence; a race where >70% of laps are flagged rainfall but ~0% run on inters/wets is a
false-positive rain flag (2018_5 Spanish GP and 2019_6 Monaco GP were dry races).
The reverse (many inter/wet laps, no rain flag) is only SUGGESTIVE: FastF1's Rainfall means
"precipitation now", and a track can stay wet after rain stops.

Consumers of rainfall_flag: int_track_evolution -> int_lap_residual_decomposed.rainfall_flag
-> int_lap_anomaly_flags.is_rain_lap / anomaly_class 'conditions' (training eligibility),
int_constructor_structural_pace and int_dirty_air_tax_component (clean-panel filter),
fct_driver_skill_features.race_wet_flag (Wet-Race Specialist page).

DEFECT PRESENT while: any race has rain_share > 0.5 and inter_wet_share < 0.05.
"""
from _db import con, show

c = con()
show(c, r"""
with l as (
  select race_year, race_id, lap_id, compound in ('INTERMEDIATE','WET') wet_tyre from stg_laps),
w as (select lap_id, rainfall_flag from stg_weather),
s as (select distinct race_id, race_slug from stg_results)
select l.race_id, s.race_slug, count(*) laps,
  round(avg(case when w.rainfall_flag then 1.0 else 0 end), 3) rain_share,
  round(avg(case when l.wet_tyre then 1.0 else 0 end), 3) inter_wet_share
from l left join w using (lap_id) join s using (race_id)
group by all
having avg(case when w.rainfall_flag then 1.0 else 0 end) > 0.05 or avg(case when l.wet_tyre then 1.0 else 0 end) > 0.05
order by inter_wet_share - rain_share""", "races where rain flag or wet-tyre use exceeds 5% of laps (all laps, stg)", n=60)
show(c, r"""
select race_id, round(min(track_temp_c),1) min_track_c, round(max(track_temp_c),1) max_track_c,
  round(avg(track_temp_c) filter (where rainfall_flag),1) track_c_when_raining,
  round(avg(humidity_pct) filter (where rainfall_flag),1) humidity_when_raining
from stg_weather where race_id in ('2018_5','2019_6','2024_21','2022_18') group by 1 order by 1""",
     "weather while 'raining' (a 45 C track in rain is not plausible)")
show(c, r"""
select f.race_id, count(*) spine_rows,
  count(*) filter (where a.anomaly_class = 'conditions') conditions_rows,
  count(*) filter (where f.is_training_eligible) eligible_rows,
  count(*) filter (where f.compound in ('INTERMEDIATE','WET') and f.is_training_eligible) eligible_on_inter_wet
from fct_cliff_prediction_features f join int_lap_anomaly_flags a using (lap_id)
where f.race_id in ('2019_6','2018_5','2020_14','2021_16','2022_17','2022_4','2025_13')
group by 1 order by 1""", "training eligibility in false-positive (2018_5, 2019_6) and wet-no-flag races")
