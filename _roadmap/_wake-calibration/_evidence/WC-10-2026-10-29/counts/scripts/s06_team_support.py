"""Outcome-blind: per team and season, share of following braking passes (0<=gap<3, kept, not yielding)
that (a) have a registered measured reference (ref_status) and (b) sit in a within-(driver, race, stint, compound,
corner) group that also holds >=2 free passes (the fixed-effects design's support). Structural columns only."""
import duckdb, sys
PT = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/pass_table_*.parquet"
B = "/Users/justin/github/off-the-pace/data/bronze"
OUT = sys.argv[1]
c = duckdb.connect()
c.sql(f"""create table team as select distinct race_id, Driver driver, Team team
  from read_parquet('{B}/laps/season=*/race=*/*_laps.parquet', union_by_name=true)""")
c.sql(f"""create table k as select season, race_id, driver, stint, compound, corner_id, gap_s, clear_ahead, ref_status
  from read_parquet('{PT}') where reason is null and segment_basis='brake_onset' and coalesce(tag,'') not like '%yielding%'
  and stint is not null""")
r = c.sql("""with g as (select race_id, driver, stint, compound, corner_id, sum((clear_ahead or gap_s>3)::int) n_free
   from k group by all)
  select k.season, t.team, count(*) n_following, avg((ref_status='measured')::int) share_own_clean,
   avg((g.n_free>=2)::int) share_fe_support
  from k join g using (race_id, driver, stint, compound, corner_id) join team t using (race_id, driver)
  where gap_s>=0 and gap_s<3 group by all order by 1,2""").df()
r.to_csv(f"{OUT}/team_support.csv", index=False)
s = r.groupby("season").agg(own_min=("share_own_clean","min"), own_max=("share_own_clean","max"),
    fe_min=("share_fe_support","min"), fe_max=("share_fe_support","max"))
print(s.to_string())
print(r[r.season==2025].to_string())
