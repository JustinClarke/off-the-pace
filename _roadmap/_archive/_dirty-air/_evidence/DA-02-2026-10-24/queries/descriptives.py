"""DA-02 descriptives. Usage (cwd = repo root): python descriptives.py <warehouse.duckdb> <out_dir>
Reads int_microsector_proximity / stg_telemetry_position / stg_laps read-only. Descriptive only:
no fixed effects, no fit (the registered fit is DA-03). Run from transform/ so the staging
views' relative bronze paths resolve."""
import sys, duckdb
db, out = sys.argv[1], sys.argv[2]
con = duckdb.connect(db, read_only=True)
Q = {
 "01_reason_funnel_by_season": """
   select race_year, count(*) rows_all,
     count(*) filter (where invalid_reason is null) n_valid,
     round(avg((invalid_reason is null)::int),4) valid_share_of_all,
     round(avg((invalid_reason is null)::int) filter (where timing_invalid_reason is null),4) valid_share_of_timed,
     count(*) filter (where invalid_reason='lap1') lap1, count(*) filter (where invalid_reason='pit_lane') pit_lane,
     count(*) filter (where invalid_reason='no_next_crossing') no_next, count(*) filter (where invalid_reason='off_track') off_track,
     count(*) filter (where invalid_reason='wide_bracket') wide_bracket, count(*) filter (where invalid_reason='non_green_flag') non_green,
     count(*) filter (where invalid_reason='post_restart') post_restart, count(*) filter (where invalid_reason='car_ahead_unknown') ahead_unknown,
     count(*) filter (where invalid_reason='lapped_ahead_within_window') lapped_within_3s
   from int_microsector_proximity group by 1 order by 1""",
 "02_loss_vs_gap_raw": """
   select gap_band, count(*) n, round(avg(y_s),4) mean_y_s, round(median(y_s),4) median_y_s,
     round(avg((y_s>0)::int),4) share_slower_than_field
   from int_microsector_proximity where invalid_reason is null and y_s is not null group by 1 order by 1""",
 "02b_loss_vs_gap_raw_by_era": """
   select case when race_year<2022 then 'pre2022' else 'post2022' end era, gap_band, count(*) n,
     round(avg(y_s),4) mean_y_s, round(median(y_s),4) median_y_s
   from int_microsector_proximity where invalid_reason is null and y_s is not null group by 1,2 order by 1,2""",
 "03_samples_per_slice": """
   with s as (select race_year, race_id, driver_id, cast(floor((lap_number+relative_distance)*20) as bigint) k, count(*) n,
        max(session_time_s)-min(session_time_s) span from stg_telemetry_position where lap_number>=2 group by all)
   select race_year, count(*) slices, quantile_cont(n,0.01) p01, quantile_cont(n,0.1) p10, quantile_cont(n,0.5) p50,
     quantile_cont(n,0.9) p90, round(quantile_cont(span,0.5),2) median_span_s, round(avg((n<10)::int),4) share_under10
   from s where span<30 group by 1 order by 1""",
 "04_lap_total_identity": """
   with laps as (select race_year, lap_id, sum(time_s) s, count(time_s) n from int_microsector_proximity group by all),
   j as (select l.*, sl.lap_time_s from laps l join stg_laps sl using(lap_id) where sl.lap_time_s is not null and l.n=20)
   select race_year, count(*) complete_laps, round(median(abs(s-lap_time_s)),4) median_abs_s,
     round(quantile_cont(abs(s-lap_time_s),0.95),4) p95_abs_s, round(median(s-lap_time_s),4) median_signed_s,
     count(*) filter (where abs(s-lap_time_s)>0.5) n_over_0p5s from j group by 1 order by 1""",
 "05_bracket_by_season": """
   select race_year, count(*) crossings, round(quantile_cont(bracket_s,0.5),3) p50, round(quantile_cont(bracket_s,0.99),3) p99,
     round(avg((bracket_s>1.0)::int),5) share_over_1s from int_microsector_crossings group by 1 order by 1""",
 "06_panel_for_fit": """
   select count(*) rows_valid, count(distinct race_id) races, count(distinct lap_id) laps,
     round(avg((ahead_y_s is null)::int),4) share_ahead_y_null
   from int_microsector_proximity where invalid_reason is null and y_s is not null""",
}
for name, q in Q.items():
    df = con.sql(q).df(); df.to_csv(f"{out}/{name}.csv", index=False)
    print("==", name); print(df.to_string(index=False))
