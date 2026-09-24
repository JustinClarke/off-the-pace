"""R2-F: the Wet-Race Specialist page measures wet skill on DRY laps only.

fct_driver_skill_features.sql:99  race_wet_flag = BOOL_OR(rainfall_flag) over the race's laps.
fct_driver_skill_features.sql:137-140  driver_skill_proxy_mean_s keeps only laps with
    is_rain_lap = FALSE (int_lap_anomaly_flags.sql:216, = rainfall_flag).
app/src/features/wet-race-specialist/queries.ts:25-29  wet_skill_s = AVG(proxy) over races with
    race_wet_flag. So "wet skill" is the teammate proxy on the laps of a wet-flagged race on which
    it was NOT raining. By construction no rain lap reaches the page.

Also: methodology.tsx says "relative to the field model" (the proxy is vs the synthetic teammate)
and "2018-2024" (the data now runs to 2025).

DEFECT PRESENT while: rain_laps_in_proxy = 0 and wet races exist.
"""
from _db import con, show

c = con()
show(c, r"""
with laps as (
  select r.race_year, r.race_id, r.driver_id, coalesce(r.rainfall_flag, false) rain,
         (r.correction_weight = 1.0 and a.anomaly_class not in ('mistake','conditions') and a.is_rain_lap = false) in_proxy_filter
  from int_lap_residual_decomposed r left join int_lap_anomaly_flags a using (lap_id)),
race as (select race_year, race_id, bool_or(rain) wet, avg(case when rain then 1.0 else 0 end) rain_share
         from laps group by all)
select count(*) filter (where wet) wet_races, count(*) races,
  round(median(rain_share) filter (where wet), 3) median_rain_lap_share_in_wet_races,
  count(*) filter (where wet and rain_share < 0.10) wet_races_with_lt10pct_rain_laps,
  (select count(*) from laps where rain and in_proxy_filter) rain_laps_in_proxy
from race""", "wet-flagged races and how much of them was wet")
show(c, r"""
with laps as (
  select r.race_year, r.race_id, coalesce(r.rainfall_flag, false) rain from int_lap_residual_decomposed r)
select race_id, count(*) valid_laps, count(*) filter (where rain) rain_laps,
  round(avg(case when rain then 1.0 else 0 end), 3) rain_share
from laps group by 1 having bool_or(rain) order by rain_share""", "every wet-flagged race (valid laps only)", n=80)
