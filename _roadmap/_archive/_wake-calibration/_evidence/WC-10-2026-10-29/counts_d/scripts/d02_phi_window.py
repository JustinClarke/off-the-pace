"""WC-10d structural count: field-effect support with lap windows, 2022-23. Structural columns only
(season, race_id, driver, lap, stint, compound, corner_id, corner_class, segment_basis, gap_s, clear_ahead, tag, reason)."""
import duckdb
R = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts"
PT = [f"{R}/WC-03-run/pass-table/pass_table_{s}.parquet" for s in (2022, 2023)]
c = duckdb.connect()
c.sql(f"""create table k as select race_id, driver, lap, stint, compound, corner_id, corner_class,
  (gap_s>=0 and gap_s<1) close1, (gap_s>=0 and gap_s<3) follow3, (clear_ahead or gap_s>=3) free
  from read_parquet({PT}) where reason is null and segment_basis='brake_onset' and coalesce(tag,'') not like '%yielding%' and stint is not null""")
c.sql("create table g as select race_id, driver, stint, compound, corner_id, sum(free::int) n_free from k group by all")
c.sql("create table t as select k.* from k join g using (race_id, driver, stint, compound, corner_id) where follow3 and n_free>=2")
c.sql("create table f as select race_id, corner_id, lap, driver from k where free")
c.sql("create table fl as select distinct race_id, lap, driver from k where free")
q = """with w as (select t.race_id, t.driver, t.lap, t.corner_id, t.corner_class, t.close1,
   count(distinct case when f.lap=t.lap then f.driver end) n0,
   count(distinct case when abs(f.lap-t.lap)<=1 then f.driver end) n1,
   count(distinct case when abs(f.lap-t.lap)<=2 then f.driver end) n2
   from t left join f on f.race_id=t.race_id and f.corner_id=t.corner_id and abs(f.lap-t.lap)<=2 and f.driver<>t.driver group by all),
  w2 as (select w.*, (select count(*) from fl where fl.race_id=w.race_id and fl.lap=w.lap and fl.driver<>w.driver) nlap from w)
  select corner_class, close1, count(*) n, sum((n0>=3)::int) w0, sum((n0<3 and n1>=3)::int) w1, sum((n1<3 and n2>=3)::int) w2,
   sum((n2<3)::int) unsupported, sum((n2<3 and nlap>=3)::int) unsupported_but_lap_ge3
  from w2 group by rollup(corner_class, close1) order by 1,2"""
print(c.sql(q).df().to_string(index=False))
