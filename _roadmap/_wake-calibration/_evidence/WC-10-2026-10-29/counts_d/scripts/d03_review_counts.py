"""WC-10d review-fix structural counts, 2022-23 only. Reads ONLY structural columns:
season, race_id, race, driver, lap, stint, compound, tyre_life, corner_id, corner_class, segment_basis,
gap_s, clear_ahead, tag, reason (pass table). No time, speed, reference, delta, coast or throttle column.
Answers: B1 (free-pass share in groups with a supported following pass), B4 (race and circuit list),
S5 (thin compound cells: free passes from fewer than 3 distinct drivers per race x compound x class)."""
import sys, duckdb
sys.path.insert(0, "/Users/justin/github/off-the-pace/transform")
from tasks.wake_calibration import build_pass_table as bpt
R = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts"
PT = [f"{R}/WC-03-run/pass-table/pass_table_{s}.parquet" for s in (2022, 2023)]
c = duckdb.connect()
cal = bpt.race_calendar()
c.execute("create table cal(season int, race varchar, circuit varchar)")
c.executemany("insert into cal values (?,?,?)", [(s, r, v[0]) for (s, r), v in cal.items() if s in (2022, 2023)])
c.sql(f"""create table k as select season, race_id, race, driver, lap, stint, compound, tyre_life, corner_id, corner_class,
  (gap_s>=0 and gap_s<3) follow3, (clear_ahead or gap_s>=3) free from read_parquet({PT})
  where reason is null and segment_basis='brake_onset' and coalesce(tag,'') not like '%yielding%' and stint is not null""")
c.sql("""create table g as select race_id, driver, stint, compound, corner_id, sum(free::int) n_free, sum(coalesce(follow3,false)::int) n_fol
  from k group by all""")
def show(name, sql):
    print(f"--- {name}"); print(c.sql(sql).df().to_string(index=False)); print()
show("B1_free_passes_in_groups_with_supported_following", """select k.corner_class, count(*) free_passes,
  sum((g.n_fol>=1 and g.n_free>=2)::int) in_groups_with_supported_following,
  round(avg((g.n_fol>=1 and g.n_free>=2)::int),4) frac
  from k join g using (race_id, driver, stint, compound, corner_id) where k.free group by rollup(k.corner_class) order by 1""")
show("B1_groups", """select count(*) groups_with_free, sum((n_fol>=1 and n_free>=2)::int) with_supported_following,
  sum((n_fol=0)::int) no_following from g where n_free>=1""")
show("B4_race_list", """select k.season, k.race_id, k.race, cal.circuit, count(*) passes from k left join cal on cal.season=k.season and cal.race=k.race
  group by all order by 1,2""")
show("B4_circuit_list", """select cal.circuit, count(distinct k.race_id) races from k left join cal on cal.season=k.season and cal.race=k.race
  group by 1 order by 1""")
show("S5_thin_compound_cells", """with t as (select race_id, compound, corner_class, count(distinct driver) nd, count(*) nfree from k where free group by all)
  select count(*) cells, sum((nd<3)::int) cells_lt3_drivers, sum((nd<2)::int) cells_1_driver,
  sum(case when nd<3 then nfree else 0 end) free_passes_in_thin_cells, sum(nfree) free_passes_all from t""")
show("S5_following_in_thin_cells", """with t as (select race_id, compound, corner_class, count(distinct driver) nd from k where free group by all)
  select count(*) following_passes, sum((nd<3)::int) in_thin_cells from k left join t using (race_id, compound, corner_class) where follow3""")
