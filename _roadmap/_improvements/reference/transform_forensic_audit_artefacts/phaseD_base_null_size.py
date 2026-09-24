"""Size of the error injected when base_track_pace_s is NULL: residual is off by exactly -(lap_time - true base).
True base unknown; estimate with the nearest non-null base in the same race (by lap_number)."""
import duckdb
c = duckdb.connect("/Users/justin/github/off-the-pace/data/dev.duckdb", read_only=True)
q = """
with r as (select race_year, race_id, lap_number, lap_id, lap_time_s, base_track_pace_s b from int_lap_residual_decomposed),
fc as (select race_year, race_id, lap_number, field_pace_smoothed_s fb from int_field_pace_curve where field_pace_smoothed_s is not null),
nn as (select r.lap_id, r.lap_time_s, r.lap_number, arg_min(fc.fb, abs(fc.lap_number - r.lap_number)) b_est, min(abs(fc.lap_number-r.lap_number)) dist
       from r join fc using (race_year, race_id) where r.b is null group by all),
mx as (select race_year, race_id, max(lap_number) mxl from r group by all)
select count(*) n, median(abs(lap_time_s - b_est)) med_abs_err_s, avg(abs(lap_time_s - b_est)) mean_abs_err_s,
   quantile_cont(abs(lap_time_s-b_est), 0.9) p90_abs_err, median(dist) med_dist_laps
from nn"""
print(c.sql(q).df().round(3).to_string())
q2 = """
with r as (select race_year, race_id, lap_number, base_track_pace_s b from int_lap_residual_decomposed),
mx as (select race_year, race_id, max(lap_number) mxl from r group by all)
select case when r.lap_number<=3 then 'laps 1-3' when mx.mxl - r.lap_number < 3 then 'last 3 laps'
            else 'mid-race' end pos, count(*) n_null
from r join mx using (race_year, race_id) where r.b is null group by 1 order by 2 desc"""
print(c.sql(q2).df().to_string())
q3 = """select eligible_lap_count, count(*) from int_field_pace_curve where field_pace_smoothed_s is null group by 1 order by 1"""
print(c.sql(q3).df().head(10).to_string())
q4 = """with r as (select race_year, race_id, lap_number from int_lap_residual_decomposed where base_track_pace_s is null)
select count(*) filter (where fc.race_id is null) no_curve_row, count(*) filter (where fc.race_id is not null) curve_row_null_value
from r left join int_field_pace_curve fc using (race_year, race_id, lap_number)"""
print(c.sql(q4).df().to_string())
