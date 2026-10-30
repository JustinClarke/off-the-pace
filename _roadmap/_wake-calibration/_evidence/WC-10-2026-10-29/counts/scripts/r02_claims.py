"""WC-10 plan review, outcome-blind: causal-reference share, release events (with leader identity),
DRS by lap state 2023, telemetry car-row spacing in metres. Reads structural columns only
(gap, flags, classes, tyre life, DRS, distance_m, Source, lap_number). No speed/time outcome is summarised."""
import duckdb, sys
PT = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/pass_table_*.parquet"
B = "/Users/justin/github/off-the-pace/data/bronze"
OUT = sys.argv[1]
c = duckdb.connect()
def save(name, sql):
    df = c.sql(sql).df(); df.to_csv(f"{OUT}/{name}.csv", index=False); print(f"--- {name}\n{df.to_string()}\n")
c.sql(f"""create table p as select season, race_id, driver, lap, stint, compound, corner_id, segment_basis, gap_s,
  clear_ahead, tag, reason, clean, ref_status, leader from read_parquet('{PT}')""")
c.sql("""create table k as select *, (gap_s>=0 and gap_s<1) close1, (clear_ahead or gap_s>3) free from p
  where reason is null and segment_basis='brake_onset' and coalesce(tag,'') not like '%yielding%' and stint is not null""")
# causal (trailing L-4..L-1) reference share at 0.5-1 s, 2022-25: >=2 own clean passes same corner, stint, compound
c.sql("create table don as select race_id, driver, corner_id, stint, compound, lap from p where clean")
save("b1_trailing4_05_1s_2022_25", """with f as (select * from k where season>=2022 and gap_s>=0.5 and gap_s<1),
  j as (select f.race_id, f.driver, f.corner_id, f.lap, any_value(f.ref_status) rs, count(d.lap) n from f left join don d
   on d.race_id=f.race_id and d.driver=f.driver and d.corner_id=f.corner_id and d.stint=f.stint and d.compound=f.compound
   and d.lap between f.lap-4 and f.lap-1 group by all)
  select count(*) n, avg((rs='measured')::int) sym4, avg((n>=2)::int) trailing4 from j""")
# release events: lap-level state from median braking gap; follower close/following on L; car ahead on L (modal leader)
# pits on L+1 (pass reason pit_lap_leader on L+1) -- check whether the pitting leader IS the L car ahead.
c.sql("""create table lap as select season, race_id, driver, lap, any_value(stint) stint,
  median(case when clear_ahead then 30 else gap_s end) med_gap, mode(leader) lead_mode, count(distinct leader) n_lead,
  count(*) n, sum(free::int) n_free from k group by all""")
c.sql("""create table lap2 as select *, case when med_gap<1.5 then 'following' when n_free=n then 'free'
  when med_gap>=3 then 'mostly_free' else 'mid' end state from lap""")
c.sql("""create table pl as select race_id, driver, lap, bool_or(reason='pit_lap_leader') leader_pit,
  list_distinct(list(case when reason='pit_lap_leader' then leader end)) pit_leaders, bool_or(reason='pit_lap') own_pit from p group by all""")
save("b2_release_events", """select count(*) events,
  sum((l2.state in ('free','mostly_free'))::int) free_on_L2,
  sum((list_contains(pl.pit_leaders, l.lead_mode))::int) leader_is_car_ahead,
  sum((list_contains(pl.pit_leaders, l.lead_mode) and l2.state in ('free','mostly_free'))::int) leader_match_and_free_L2
  from lap2 l join pl on pl.race_id=l.race_id and pl.driver=l.driver and pl.lap=l.lap+1
  left join lap2 l2 on l2.race_id=l.race_id and l2.driver=l.driver and l2.lap=l.lap+2 and l2.stint=l.stint
  where l.state='following' and pl.leader_pit and not pl.own_pit""")
# DRS 2023 by lap state (median braking gap <1 s vs all-free lap)
c.sql("""create table s23 as select race_id, driver, lap, case when med_gap<1 then 'close<1s' when n_free=n then 'free' else 'other' end st
  from lap where season=2023""")
c.sql(f"""create table drs as select race_id, driver_id driver, cast(lap_number as int) lap, avg((DRS in (10,12,14))::int) sh
  from read_parquet('{B}/telemetry/season=2023/race=*/telemetry.parquet', union_by_name=true) where Source='car' group by all""")
save("b3_drs_2023", "select st, count(*) laps, avg((sh>0)::int) any_open, avg(sh) mean_open_share from s23 join drs using (race_id, driver, lap) group by 1 order by 1")
# telemetry: car-row spacing in metres and seconds (distance_m, SessionTime only), 2022-25
c.sql(f"""create table t as select season, race_id, driver_id, SessionTime, distance_m,
  distance_m - lag(distance_m) over w dd, (SessionTime - lag(SessionTime) over w)/1e9 dt
  from read_parquet('{B}/telemetry/season=202[2-5]/race=*/telemetry.parquet', union_by_name=true)
  where Source='car' window w as (partition by race_id, driver_id order by SessionTime)""")
save("b4_car_spacing_2022_25", """select season, count(*) n, median(dt) med_dt_s, quantile_cont(dt,0.9) p90_dt_s,
  median(dd) med_m, quantile_cont(dd,0.9) p90_m, quantile_cont(dd,0.99) p99_m
  from t where dt>0 and dt<2 and dd>0 group by 1 order by 1""")
