"""WC-10d B2 fix: counts of locally bracketed passes (a free pass of the same group within 5 laps before AND within 5 laps after).
Structural columns only (season, race_id, driver, lap, stint, compound, corner_id, corner_class, segment_basis, gap_s, clear_ahead, tag, reason).
Counts are before outcome trims."""
import duckdb
R = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts"
PT = [f"{R}/WC-03-run/pass-table/pass_table_{s}.parquet" for s in (2022, 2023)]
c = duckdb.connect()
c.sql(f"""create table k as select race_id, driver, lap, stint, compound, corner_id, corner_class, gap_s,
  (clear_ahead or gap_s>=3) free from read_parquet({PT})
  where reason is null and segment_basis='brake_onset' and coalesce(tag,'') not like '%yielding%' and stint is not null""")
c.sql("""create table g as select race_id, driver, stint, compound, corner_id, sum(free::int) n_free from k group by all""")
c.sql("""create table t as select k.*, g.n_free,
  (select count(*) from k f where f.free and f.race_id=k.race_id and f.driver=k.driver and f.stint=k.stint and f.compound=k.compound
     and f.corner_id=k.corner_id and f.lap between k.lap-5 and k.lap-1) nb,
  (select count(*) from k f where f.free and f.race_id=k.race_id and f.driver=k.driver and f.stint=k.stint and f.compound=k.compound
     and f.corner_id=k.corner_id and f.lap between k.lap+1 and k.lap+5) na
  from k join g using (race_id, driver, stint, compound, corner_id) where not k.free and k.gap_s>=0 and k.gap_s<3 and g.n_free>=2""")
print(c.sql("""select corner_class,
  count(*) supported_following,
  sum((nb>0 and na>0)::int) local_bracketed,
  sum((gap_s>=0.5 and gap_s<1.0)::int) near_supported,
  sum((gap_s>=0.5 and gap_s<1.0 and nb>0 and na>0)::int) near_local_bracketed,
  sum((gap_s>=2.0 and gap_s<3.0)::int) far_supported,
  sum((gap_s>=2.0 and gap_s<3.0 and nb>0 and na>0)::int) far_local_bracketed
  from t group by rollup(corner_class) order by 1""").df().to_string(index=False))
