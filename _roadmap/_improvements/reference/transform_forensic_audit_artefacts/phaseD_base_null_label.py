"""int_lap_residual_decomposed.sql:294 pace_delta_s = lap_time_s - COALESCE(base_track_pace_s, lap_time_s)
=> 0 when the field curve is NULL. Does such a lap sit inside a training row's label window (t..t+5)?"""
import duckdb
c = duckdb.connect("/Users/justin/github/off-the-pace/data/dev.duckdb", read_only=True)
print(c.sql("""select count(*) n, count(*) filter (where base_track_pace_s is null) n_null,
  count(*) filter (where base_track_pace_s is null and pace_delta_s = 0) n_null_and_zero from int_lap_residual_decomposed""").df().to_string())
q = """
with r as (select lap_id, stint_id, lap_in_stint, (base_track_pace_s is null) as bnull, driver_skill_residual_s res, pace_delta_s from int_lap_residual_decomposed),
w as (select lap_id, bnull,
   (bnull or coalesce(lead(bnull,1) over s,false) or coalesce(lead(bnull,2) over s,false) or coalesce(lead(bnull,3) over s,false)
     or coalesce(lead(bnull,4) over s,false) or coalesce(lead(bnull,5) over s,false)) as win_has_null
   from r window s as (partition by stint_id order by lap_in_stint))
select f.race_year, count(*) n_labelled,
  avg(case when w.bnull then 1.0 else 0 end) share_t_null,
  avg(case when w.win_has_null then 1.0 else 0 end) share_window_has_null,
  avg(f.next_5_lap_cumulative_jump_s) filter (where not w.win_has_null) mean_y_clean,
  avg(f.next_5_lap_cumulative_jump_s) filter (where w.win_has_null) mean_y_contam,
  stddev(f.next_5_lap_cumulative_jump_s) filter (where not w.win_has_null) sd_clean,
  stddev(f.next_5_lap_cumulative_jump_s) filter (where w.win_has_null) sd_contam,
  avg(case when f.laps_until_cliff_class in ('0_to_2','3_to_5') then 1.0 else 0 end) filter (where not w.win_has_null) cliff5_clean,
  avg(case when f.laps_until_cliff_class in ('0_to_2','3_to_5') then 1.0 else 0 end) filter (where w.win_has_null) cliff5_contam
from fct_cliff_prediction_features f join w using(lap_id)
where f.is_training_eligible and f.next_5_lap_cumulative_jump_s is not null
group by rollup(f.race_year) order by 1 nulls last"""
print(c.sql(q).df().round(4).to_string())
print(c.sql("""select lap_number <= 3 early, count(*) from int_lap_residual_decomposed where base_track_pace_s is null group by 1""").df())
