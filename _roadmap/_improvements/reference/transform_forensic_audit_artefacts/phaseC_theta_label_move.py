"""How far the 5-lap label moves between theta=0.1310 (v13, <=2024 panel) and 0.1521 (v14 build).
dirty_air_tax_s = clip(theta * x, 0, 5) with x = dirty_air_intensity_lag1 (compiled SQL lines 221-231).
Under the unclipped branch tax scales linearly in theta, so tax_v13 = tax_built * 0.1310/0.15212.
Label = sum_{i=1..5} res(t+i) - 5 res(t) - 15 drift ; res = ... - tax. drift (per-stint OLS of res)
also moves; this probe ignores the drift term's movement, so it is a lower-bound-shaped estimate."""
import duckdb
c = duckdb.connect("/Users/justin/github/off-the-pace/data/dev.duckdb", read_only=True)
T_NEW, T_OLD = 0.15212309010790792, 0.13100009613205
chk = c.sql("select count(*) n, count(*) filter (where dirty_air_intensity_lag1>0) n_pos, median(dirty_air_tax_s/dirty_air_intensity_lag1) filter (where dirty_air_intensity_lag1>0 and dirty_air_tax_s>0 and dirty_air_tax_s<5) implied_theta from int_dirty_air_tax_component").df()
print(chk.to_string())
df = c.sql(f"""
with m as (select f.lap_id, f.stint_id, f.lap_in_stint, f.race_year, f.is_training_eligible, f.next_5_lap_cumulative_jump_s y,
  coalesce(d.dirty_air_tax_s,0) tax from fct_cliff_prediction_features f left join int_dirty_air_tax_component d using(lap_id)),
w as (select *, 
  (lead(tax,1) over s + lead(tax,2) over s + lead(tax,3) over s + lead(tax,4) over s + lead(tax,5) over s - 5*tax) as dtax_sum
  from m window s as (partition by stint_id order by lap_in_stint))
select race_year, count(*) n, avg(abs(dtax_sum * ({T_OLD}/{T_NEW} - 1))) mean_abs_shift, 
  avg(case when abs(dtax_sum * ({T_OLD}/{T_NEW} - 1))>0.05 then 1.0 else 0 end) share_gt_50ms,
  stddev(y) sd_label
from w where is_training_eligible and y is not null group by 1 order by 1""").df()
print(df.to_string())
