"""WC-10d structural support counts, 2022-23 only. Reads ONLY structural columns:
season, race_id, race, driver, lap, stint, compound, tyre_life, corner_id, corner_class, segment_basis,
leader, leader_lap, gap_s, clear_ahead, behind_1s, tag, reason (pass table) and drs_open_approach,
prev_lap_gap_s (sidecar). No time, speed, reference, delta, coast or throttle column."""
import sys, duckdb
sys.path.insert(0, "/Users/justin/github/off-the-pace/transform")
from tasks.wake_calibration import build_pass_table as bpt
R = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts"
PT = [f"{R}/WC-03-run/pass-table/pass_table_{s}.parquet" for s in (2022, 2023)]
SC = [f"{R}/WC-10/sidecar/sidecar_{s}.parquet" for s in (2022, 2023)]
c = duckdb.connect()
cal = bpt.race_calendar()
c.execute("create table cal(season int, race varchar, circuit varchar)")
c.executemany("insert into cal values (?,?,?)", [(s, r, v[0]) for (s, r), v in cal.items() if s in (2022, 2023)])
c.sql(f"""create table k as select p.season, p.race_id, p.race, p.driver, p.lap, p.stint, p.compound, p.tyre_life,
  p.corner_id, p.corner_class, p.leader, p.leader_lap, p.gap_s, p.clear_ahead, p.behind_1s,
  (p.gap_s>=0 and p.gap_s<3) follow3, (p.gap_s>=0 and p.gap_s<1) close1, (p.clear_ahead or p.gap_s>=3) free,
  case when p.gap_s>=0 and p.gap_s<3 then least(7, (case when p.gap_s<0.3 then 0 when p.gap_s<0.5 then 1 when p.gap_s<0.75 then 2
       when p.gap_s<1.0 then 3 when p.gap_s<1.5 then 4 when p.gap_s<2.0 then 5 when p.gap_s<2.5 then 6 else 7 end)) end bin,
  s.drs_open_approach, s.prev_lap_gap_s
  from read_parquet({PT}) p join read_parquet({SC}, union_by_name=true) s using (season, race_id, driver, lap, corner_id)
  where p.reason is null and p.segment_basis='brake_onset' and coalesce(p.tag,'') not like '%yielding%' and p.stint is not null""")
c.sql("""create table g as select race_id, driver, stint, compound, corner_id, sum(free::int) n_free, sum(close1::int) n_close,
  min(case when free then lap end) f_min, max(case when free then lap end) f_max from k group by all""")
c.sql("create table kg as select * from k join g using (race_id, driver, stint, compound, corner_id)")
def show(name, sql):
    print(f"--- {name}"); print(c.sql(sql).df().to_string(index=False)); print()
show("races_circuits", """select k.season, count(distinct k.race_id) races, count(distinct cal.circuit) circuits
  from k left join cal on cal.season=k.season and cal.race=k.race group by rollup(k.season) order by 1""")
show("unmapped_races", "select distinct k.season, k.race from k left join cal on cal.season=k.season and cal.race=k.race where cal.circuit is null")
show("passes", """select corner_class, count(*) kept_braking, sum(free::int) free, sum(follow3::int) follow3, sum((gap_s<0)::int) neg_gap,
  sum((follow3 and n_free>=2)::int) follow3_supported, sum((close1 and n_free>=2)::int) close_supported,
  sum((close1 and n_free>=2 and n_close>=2)::int) close_identifying_review,
  sum((follow3 and n_free>=2 and f_min<lap and f_max>lap)::int) follow3_bracketed,
  sum((close1 and n_free>=2 and f_min<lap and f_max>lap)::int) close_bracketed
  from kg group by rollup(corner_class) order by 1""")
show("supported_by_bin_class", """select bin, corner_class, count(*) n, sum((f_min<lap and f_max>lap)::int) bracketed
  from kg where follow3 and n_free>=2 group by all order by 1,2""")
show("races_with_supported_close_by_class", """select corner_class, count(distinct race_id) races,
  count(distinct case when f_min<lap and f_max>lap then race_id end) races_bracketed from kg where close1 and n_free>=2 group by 1 order by 1""")
# window support
c.sql("create table fr as select race_id, driver, stint, compound, corner_id, lap flap from k where free")
show("window_support_close_supported", """with j as (select kg.race_id, kg.driver, kg.corner_id, kg.lap, kg.corner_class, min(abs(kg.lap-fr.flap)) d
  from kg join fr using (race_id, driver, stint, compound, corner_id) where kg.close1 and kg.n_free>=2 group by all)
  select corner_class, count(*) n, sum((d<=4)::int) within4, sum((d<=8)::int) within8 from j group by rollup(corner_class) order by 1""")
# phi support tiers (distinct free drivers at corner-lap; else class-lap)
c.sql("create table fc as select race_id, corner_id, lap, count(distinct driver) nd from k where free group by all")
c.sql("create table fcl as select race_id, corner_class, lap, count(distinct driver) nd from k where free group by all")
show("phi_tier_close_supported", """select kg.corner_class,
  sum((coalesce(fc.nd,0)>=3)::int) corner_lap_ge3,
  sum((coalesce(fc.nd,0)<3 and coalesce(fcl.nd,0)>=3)::int) class_lap_ge3,
  sum((coalesce(fc.nd,0)<3 and coalesce(fcl.nd,0)<3)::int) neither, count(*) n
  from kg left join fc using (race_id, corner_id, lap) left join fcl using (race_id, corner_class, lap)
  where kg.close1 and kg.n_free>=2 group by rollup(kg.corner_class) order by 1""")
# leader support (car ahead's own group has >=2 free passes)
show("leader_support_close_supported", """select kg.corner_class, count(*) n,
  sum((lr.driver is not null)::int) leader_row_kept, sum((lg.n_free>=2)::int) leader_group_ge2_free
  from kg left join k lr on lr.race_id=kg.race_id and lr.driver=kg.leader and lr.lap=kg.leader_lap and lr.corner_id=kg.corner_id
  left join g lg on lg.race_id=lr.race_id and lg.driver=lr.driver and lg.stint=lr.stint and lg.compound=lr.compound and lg.corner_id=lr.corner_id
  where kg.close1 and kg.n_free>=2 group by rollup(kg.corner_class) order by 1""")
# stuck tiers 2022-23
show("stuck_tiers", """with s as (select race_id, driver, stint, compound, avg(close1::int) cs from k group by all)
  select case when cs>=0.8 then 'ge80' when cs>=0.5 then '50-80' when cs>=0.2 then '20-50' else 'lt20' end tier,
  sum(close1::int) close_passes, sum((close1 and n_free>=2)::int) close_supported
  from kg join s using (race_id, driver, stint, compound) group by 1 order by 1""")
# catching split (gap change vs previous lap, same corner), delta 0.1 s
show("gap_change_close_supported", """select corner_class, count(*) n, sum((prev_lap_gap_s is not null)::int) has_prev,
  sum((gap_s-prev_lap_gap_s < -0.1)::int) shrinking, sum((abs(gap_s-prev_lap_gap_s)<=0.1)::int) steady,
  sum((gap_s-prev_lap_gap_s > 0.1)::int) growing from kg where close1 and n_free>=2 group by rollup(corner_class) order by 1""")
show("drs_tag_close_supported", """select corner_class, count(*) n, sum((drs_open_approach)::int) drs_open,
  sum((drs_open_approach is null)::int) drs_null from kg where close1 and n_free>=2 group by rollup(corner_class) order by 1""")
show("groups", """select count(*) groups, sum((n_free>=2)::int) groups_ge2_free from g""")
