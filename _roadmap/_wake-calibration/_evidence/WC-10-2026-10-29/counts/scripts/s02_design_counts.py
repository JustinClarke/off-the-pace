"""Outcome-blind counts for candidate identification designs, on the registered pass table (pass d).
Reads ONLY structural columns: season, race_id, driver, lap, stint, compound, tyre_life, corner_id,
corner_class, segment_basis, leader, leader_lap, gap_s, clear_ahead, behind_1s, tag, reason, clean.
Reads no outcome column (no time, speed, delta or reference value)."""
import duckdb, sys
PT = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/pass_table_*.parquet"
B = "/Users/justin/github/off-the-pace/data/bronze"
OUT = sys.argv[1]
c = duckdb.connect()
c.sql(f"""create table p as select season, race_id, driver, lap, stint, compound, tyre_life, corner_id,
  corner_class, segment_basis, leader, leader_lap, gap_s, clear_ahead, behind_1s, tag, reason, clean, ref_status
  from read_parquet('{PT}')""")
# kept braking passes, not yielding
c.sql("""create table k as select *, (clear_ahead or gap_s>3) as free_ahead,
  (gap_s>=0 and gap_s<1.0) as close1, (gap_s>=0 and gap_s<3.0) as follow3
  from p where reason is null and segment_basis='brake_onset' and coalesce(tag,'') not like '%yielding%'""")
print(c.sql("select count(*), sum(follow3::int), sum(close1::int), sum(free_ahead::int) from k").fetchall())

# lap-level states
c.sql("""create table lap as select season, race_id, driver, lap, any_value(stint) stint, any_value(compound) compound,
  any_value(tyre_life) tyre_life, count(*) n_corners,
  sum(close1::int) n_close1, sum(free_ahead::int) n_free, sum(follow3::int) n_follow3,
  sum((close1 and corner_class='fast')::int) n_close_fast, sum((close1 and corner_class='slow')::int) n_close_slow,
  sum((free_ahead and corner_class='fast')::int) n_free_fast,
  median(case when clear_ahead then 30 else gap_s end) med_gap, any_value(leader) lead_any,
  count(distinct leader) n_leaders, bool_or(behind_1s) any_behind
  from k group by all""")
c.sql("""create table lap2 as select *,
  case when med_gap<1.0 and n_leaders=1 then 'close' when med_gap<1.5 then 'following' when n_free=n_corners then 'free'
       when med_gap>=3 then 'mostly_free' else 'mid' end state from lap""")
s = c.sql("""select case when season<=2021 then '2018-21' else '2022-25' end era, state, count(*) laps
  from lap2 group by all order by 1,2""").df()
print(s.to_string()); s.to_csv(f"{OUT}/lap_states_by_era.csv", index=False)

# (A) within-lap contrast: laps with >=2 close corners (<1 s) AND >=2 free corners
wl = c.sql("""select season, count(*) laps_all,
  sum((n_close1>=2 and n_free>=2)::int) laps_close_and_free,
  sum((n_close_fast>=1 and n_close_slow>=1)::int) laps_close_fast_and_slow,
  sum((n_close_fast>=1 and n_free_fast>=1)::int) laps_fast_close_and_fast_free
  from lap group by season order by season""").df()
print(wl.to_string()); wl.to_csv(f"{OUT}/within_lap_contrasts.csv", index=False)

# (B) mixed stints: lap-level state within (race, driver, stint, compound)
ms = c.sql("""with st as (select season, race_id, driver, stint, compound,
   sum((state in ('close','following'))::int) n_follow, sum((state='free')::int) n_free,
   sum((state='close')::int) n_close, count(*) n_laps,
   max(tyre_life)-min(tyre_life) life_span from lap2 where stint is not null group by all)
  select season, count(*) stints, sum((n_follow>=3 and n_free>=3)::int) mixed3,
   sum((n_follow>=5 and n_free>=5)::int) mixed5, sum((n_close>=3 and n_free>=3)::int) mixed_close3,
   sum((n_free=0)::int) no_free_lap, sum(n_follow) follow_laps, sum(n_free) free_laps,
   sum(case when n_follow>=3 and n_free>=3 then n_follow else 0 end) follow_laps_in_mixed3
  from st group by season order by season""").df()
print(ms.to_string()); ms.to_csv(f"{OUT}/mixed_stints.csv", index=False)

# (C) transitions within stint (event study): consecutive kept laps where state changes free<->following
tr = c.sql("""with o as (select *, lag(state) over w ps, lag(lap) over w pl, lag(lead_any) over w plead
   from lap2 window w as (partition by race_id, driver, stint order by lap))
  select season,
   sum((ps='free' and state in ('close','following') and pl=lap-1)::int) free_to_follow,
   sum((ps in ('close','following') and state='free' and pl=lap-1)::int) follow_to_free
  from o group by season order by season""").df()
print(tr.to_string()); tr.to_csv(f"{OUT}/transitions.csv", index=False)

# (D) car-ahead-pits release events from the pass table:
# follower lap L state close/following behind X; on L+1 some follower pass has reason pit_lap_leader (X pitting);
# follower's own lap L+1/L+2 not a pit lap; L+2 kept and 'free' or 'mostly_free'.
c.sql("""create table pl as select race_id, driver, lap, bool_or(reason='pit_lap_leader') leader_pit,
  bool_or(reason='pit_lap') own_pit from p group by all""")
ev = c.sql("""select l.season, count(*) events,
  sum((l2.state in ('free','mostly_free'))::int) released_next,
  sum((lm.state in ('close','following'))::int) before_also_following
  from lap2 l join pl on pl.race_id=l.race_id and pl.driver=l.driver and pl.lap=l.lap+1
  left join lap2 l2 on l2.race_id=l.race_id and l2.driver=l.driver and l2.lap=l.lap+2 and l2.stint=l.stint
  left join lap2 lm on lm.race_id=l.race_id and lm.driver=l.driver and lm.lap=l.lap-1 and lm.stint=l.stint
  where l.state in ('close','following') and pl.leader_pit and not pl.own_pit
  group by l.season order by l.season""").df()
print(ev.to_string()); ev.to_csv(f"{OUT}/car_ahead_pits_release.csv", index=False)

# (E) teammate: driver lap 'close/following' while teammate same lap 'free', same compound
tm = c.sql(f"""create table team as select distinct race_id, Driver driver, Team team
  from read_parquet('{B}/laps/season=*/race=*/*_laps.parquet', union_by_name=true)""")
tmc = c.sql("""select a.season, count(*) pairs
  from lap2 a join team ta on ta.race_id=a.race_id and ta.driver=a.driver
  join team tb on tb.race_id=a.race_id and tb.team=ta.team and tb.driver<>a.driver
  join lap2 b on b.race_id=a.race_id and b.driver=tb.driver and b.lap=a.lap and b.compound=a.compound
  where a.state in ('close','following') and b.state='free' and abs(a.tyre_life-b.tyre_life)<=5
  group by a.season order by 1""").df()
print(tmc.to_string()); tmc.to_csv(f"{OUT}/teammate_pairs.csv", index=False)

# (F) causal reference: share of following braking passes with >=2 own clean passes in a TRAILING window
# (laps L-k..L-1, same stint+compound), vs the registered symmetric +-4 window (ref_status).
c.sql("""create table don as select race_id, driver, corner_id, stint, compound, lap from p where clean""")
for k in (4, 8, 99):
    r = c.sql(f"""with f as (select season, race_id, driver, corner_id, stint, compound, lap, gap_s, ref_status from k where follow3),
      j as (select f.season, f.race_id, f.driver, f.corner_id, f.lap, any_value(f.gap_s) gap_s, any_value(f.ref_status) ref_status,
            count(d.lap) n from f left join don d on d.race_id=f.race_id and d.driver=f.driver and d.corner_id=f.corner_id
            and d.stint=f.stint and d.compound=f.compound and d.lap between f.lap-{k} and f.lap-1 group by all)
      select case when season<=2021 then '2018-21' else '2022-25' end era,
        case when gap_s<0.5 then '0-0.5' when gap_s<1 then '0.5-1' when gap_s<2 then '1-2' else '2-3' end gapbin,
        count(*) n, avg((ref_status='measured')::int) sym4_measured, avg((n>=2)::int) trailing_measured
      from j group by all order by 1,2""").df()
    r["trailing_k"] = k
    print(r.to_string()); r.to_csv(f"{OUT}/causal_reference_k{k}.csv", index=False)
