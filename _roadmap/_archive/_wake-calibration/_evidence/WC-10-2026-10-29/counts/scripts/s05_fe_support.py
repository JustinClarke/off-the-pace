"""Outcome-blind: support for a within-(driver, race, stint, compound, corner) fixed-effects design.
A group 'identifies' if it has >=2 close passes (0<=gap<1 s) AND >=2 free passes (clear or gap>3 s).
Also: run lengths of consecutive 'close' laps (median braking gap <1 s) within a stint. Structural columns only."""
import duckdb, sys
PT = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/pass_table_*.parquet"
OUT = sys.argv[1]
c = duckdb.connect()
c.sql(f"""create table k as select season, race_id, driver, lap, stint, compound, corner_id, corner_class, gap_s, clear_ahead
  from read_parquet('{PT}') where reason is null and segment_basis='brake_onset' and coalesce(tag,'') not like '%yielding%'
  and stint is not null""")
r = c.sql("""with g as (select season, race_id, driver, stint, compound, corner_id, any_value(corner_class) cls,
   sum((gap_s>=0 and gap_s<1)::int) n_close, sum((clear_ahead or gap_s>3)::int) n_free,
   sum((gap_s>=0 and gap_s<3)::int) n_follow from k group by all)
  select case when season<=2021 then '2018-21' else '2022-25' end era, cls,
   sum(n_close) close_passes_all, sum(case when n_close>=2 and n_free>=2 then n_close else 0 end) close_passes_identifying,
   sum(case when n_follow>=2 and n_free>=2 then n_follow else 0 end) follow3_passes_identifying,
   count(distinct case when n_close>=2 and n_free>=2 then race_id end) races
  from g group by all order by 1,2""").df()
print(r.to_string()); r.to_csv(f"{OUT}/fe_support.csv", index=False)

c.sql("""create table lap as select season, race_id, driver, stint, lap,
  median(case when clear_ahead then 30 else gap_s end) med_gap from k group by all""")
r2 = c.sql("""with s as (select *, (med_gap<1.0)::int cl,
   lap - row_number() over (partition by race_id, driver, stint, (med_gap<1.0) order by lap) grp from lap),
  runs as (select season, race_id, driver, stint, grp, count(*) len from s where cl=1 group by all)
  select case when season<=2021 then '2018-21' else '2022-25' end era, count(*) episodes,
   median(len) med_len, quantile_cont(len,0.9) p90_len, sum((len>=5)::int) eps_ge5, sum(len) laps
  from runs group by 1 order by 1""").df()
print(r2.to_string()); r2.to_csv(f"{OUT}/close_episode_lengths.csv", index=False)
