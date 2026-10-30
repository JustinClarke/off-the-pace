"""WC-10 plan review, outcome-blind. Independent re-derivation of the plan's design-A support counts
and the identification holes. Reads ONLY: season, race_id, driver, lap, stint, compound, tyre_life,
corner_id, corner_class, segment_basis, gap_s, clear_ahead, tag, reason, clean, ref_status, leader.
Reads no outcome column (no time, speed, delta or reference value)."""
import duckdb, sys
PT = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/pass_table_*.parquet"
B = "/Users/justin/github/off-the-pace/data/bronze"
OUT = sys.argv[1]
c = duckdb.connect()
c.sql(f"""create table k as select season, race_id, driver, lap, stint, compound, tyre_life, corner_id, corner_class,
  gap_s, clear_ahead, ref_status, leader,
  (gap_s>=0 and gap_s<1) close1, (clear_ahead or gap_s>3) free
  from read_parquet('{PT}') where reason is null and segment_basis='brake_onset'
  and coalesce(tag,'') not like '%yielding%' and stint is not null""")
c.sql("""create table g as select race_id, driver, stint, compound, corner_id,
  sum(close1::int) n_close, sum(free::int) n_free, min(case when free then lap end) f_min, max(case when free then lap end) f_max
  from k group by all""")
c.sql("create table kg as select k.*, g.n_close, g.n_free, g.f_min, g.f_max from k join g using (race_id, driver, stint, compound, corner_id)")

def save(name, sql):
    df = c.sql(sql).df(); df.to_csv(f"{OUT}/{name}.csv", index=False); print(f"--- {name}\n{df.to_string()}\n")

# 1. design A support, both definitions, 2022-25
save("a1_support_2022_25", """select corner_class, count(*) close_all,
  sum((n_free>=2)::int) id_free2, sum((n_free>=2 and n_close>=2)::int) id_free2_close2,
  sum((n_free=0)::int) grp_no_free, sum((n_free=1)::int) grp_one_free
  from kg where close1 and season>=2022 group by rollup(corner_class) order by 1""")
# 2. bracketing: identifying close passes with a free pass before AND after in the stint (vs one-sided -> tyre trend extrapolates)
save("a2_bracketing_2022_25", """select corner_class, count(*) id_close,
  sum((f_min<lap and f_max>lap)::int) bracketed, sum((f_max<lap)::int) free_only_before, sum((f_min>lap)::int) free_only_after
  from kg where close1 and n_free>=2 and n_close>=2 and season>=2022 group by rollup(corner_class) order by 1""")
# 3. tyre-age distance to nearest free pass of the same group (collinearity / extrapolation)
c.sql("create table fr as select race_id, driver, stint, compound, corner_id, lap flap, tyre_life ftl from k where free")
save("a3_tyre_gap_to_nearest_free_2022_25", """with j as (select kg.race_id, kg.driver, kg.corner_id, kg.lap, kg.corner_class,
   min(abs(kg.tyre_life-fr.ftl)) d from kg join fr using (race_id, driver, stint, compound, corner_id)
   where kg.close1 and kg.n_free>=2 and kg.n_close>=2 and kg.season>=2022 group by all)
  select count(*) n, median(d) med_laps, quantile_cont(d,0.9) p90_laps, avg((d>5)::int) share_gt5, avg((d>10)::int) share_gt10 from j""")
# 3b. within identifying groups, correlation of close indicator with tyre_life (collinearity of gap with tyre age)
save("a3b_close_vs_tyrelife_corr_2022_25", """with x as (select kg.*, tyre_life - avg(tyre_life) over w tl_c,
   close1::int - avg(close1::int) over w cl_c from kg where n_free>=2 and n_close>=2 and season>=2022
   window w as (partition by race_id, driver, stint, compound, corner_id))
  select corr(tl_c, cl_c) within_group_corr_close_tyrelife, count(*) n from x where close1 or free""")
# 4. field corner-lap effect support: free passes by OTHER drivers at same race, corner, lap
c.sql("create table fl as select race_id, corner_id, lap, driver fdrv from k where free")
save("a4_field_lap_support_2022_25", """with j as (select kg.race_id, kg.driver, kg.corner_id, kg.lap, kg.corner_class, count(fl.fdrv) n_other_free
   from kg left join fl on fl.race_id=kg.race_id and fl.corner_id=kg.corner_id and fl.lap=kg.lap and fl.fdrv<>kg.driver
   where kg.close1 and kg.n_free>=2 and kg.n_close>=2 and kg.season>=2022 group by all)
  select count(*) n, median(n_other_free) med_other_free, avg((n_other_free<3)::int) share_lt3, avg((n_other_free=0)::int) share_zero from j""")
# 5. previous-lap gap available at the same corner (lagged-gap catching check)
save("a5_prev_lap_gap_2022_25", """select count(*) n, avg((p.lap is not null)::int) share_prev_kept,
   avg((p.lap is not null and (p.clear_ahead or p.gap_s is not null))::int) share_prev_gap,
   avg((p.close1)::int) share_prev_also_close
  from kg left join k p on p.race_id=kg.race_id and p.driver=kg.driver and p.corner_id=kg.corner_id and p.lap=kg.lap-1
  where kg.close1 and kg.n_free>=2 and kg.n_close>=2 and kg.season>=2022""")
# 6. stuck-all-stint: driver-stints where >=80% of kept braking passes are close and whose close passes have no FE support
save("a6_stuck_stints_2022_25", """with s as (select race_id, driver, stint, compound, avg(close1::int) close_share, sum(close1::int) n_close,
   sum(free::int) n_free from k where season>=2022 group by all)
  select case when close_share>=0.8 then 'ge80' when close_share>=0.5 then '50-80' when close_share>=0.2 then '20-50' else 'lt20' end tier,
   count(*) stints, sum(n_close) close_passes,
   sum(n_close)::double / (select sum(close1::int) from k where season>=2022) share_of_all_close
  from s group by 1 order by 1""")
save("a6b_support_by_close_share_tier_2022_25", """with s as (select race_id, driver, stint, compound, avg(close1::int) close_share from k where season>=2022 group by all)
  select case when close_share>=0.8 then 'ge80' when close_share>=0.5 then '50-80' when close_share>=0.2 then '20-50' else 'lt20' end tier,
   count(*) close_passes, avg((n_free>=2 and n_close>=2)::int) share_identifying
  from kg join s using (race_id, driver, stint, compound) where kg.close1 and kg.season>=2022 group by 1 order by 1""")
# 7. per-team 2025, close <1 s (the plan quoted 0-3 s following)
c.sql(f"""create table team as select distinct race_id, Driver driver, Team team
  from read_parquet('{B}/laps/season=*/race=*/*_laps.parquet', union_by_name=true)""")
save("a7_team_2025", """select t.team, count(*) close_passes, avg((ref_status='measured')::int) own_clean_share,
   avg((n_free>=2)::int) id_free2, avg((n_free>=2 and n_close>=2)::int) id_free2_close2,
   (select avg((n_free>=2)::int) from kg k2 join team t2 using (race_id, driver) where k2.season=2025 and k2.gap_s>=0 and k2.gap_s<3 and t2.team=t.team) follow3_free2
  from kg join team t using (race_id, driver) where kg.season=2025 and close1 group by 1 order by 1""")
