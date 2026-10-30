"""Outcome-blind: design-A support per class in the discovery seasons 2022-23 (all identifying, bracketed),
and identity-matched release events by season. Structural columns only."""
import duckdb, sys
PT = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/pass_table_*.parquet"
OUT = sys.argv[1]
c = duckdb.connect()
def save(name, sql):
    df = c.sql(sql).df(); df.to_csv(f"{OUT}/{name}.csv", index=False); print(f"--- {name}\n{df.to_string()}\n")
c.sql(f"""create table p as select season, race_id, driver, lap, stint, compound, corner_id, corner_class, segment_basis, gap_s,
  clear_ahead, tag, reason, leader from read_parquet('{PT}')""")
c.sql("""create table k as select *, (gap_s>=0 and gap_s<1) close1, (clear_ahead or gap_s>3) free from p
  where reason is null and segment_basis='brake_onset' and coalesce(tag,'') not like '%yielding%' and stint is not null""")
c.sql("""create table kg as select k.*, sum(close1::int) over w n_close, sum(free::int) over w n_free,
  min(case when free then lap end) over w f_min, max(case when free then lap end) over w f_max
  from k window w as (partition by race_id, driver, stint, compound, corner_id)""")
save("c1_support_by_split", """select case when season in (2022,2023) then 'disc 2022-23' when season>=2024 then 'conf 2024-25' else 'old' end split,
  corner_class, sum((n_free>=2 and n_close>=2)::int) identifying, sum((n_free>=2 and n_close>=2 and f_min<lap and f_max>lap)::int) bracketed,
  count(distinct case when n_free>=2 and n_close>=2 then race_id end) races
  from kg where close1 group by all order by 1,2""")
c.sql("""create table lap as select season, race_id, driver, lap, any_value(stint) stint,
  median(case when clear_ahead then 30 else gap_s end) med_gap, mode(leader) lead_mode, count(*) n, sum(free::int) n_free from k group by all""")
c.sql("""create table lap2 as select *, case when med_gap<1.5 then 'following' when n_free=n then 'free'
  when med_gap>=3 then 'mostly_free' else 'mid' end state from lap""")
c.sql("""create table pl as select race_id, driver, lap, bool_or(reason='pit_lap_leader') leader_pit,
  list_distinct(list(case when reason='pit_lap_leader' then leader end)) pit_leaders, bool_or(reason='pit_lap') own_pit from p group by all""")
save("c2_release_by_season", """select l.season, count(*) events, sum((list_contains(pl.pit_leaders, l.lead_mode) and l2.state in ('free','mostly_free'))::int) matched_free_L2
  from lap2 l join pl on pl.race_id=l.race_id and pl.driver=l.driver and pl.lap=l.lap+1
  left join lap2 l2 on l2.race_id=l.race_id and l2.driver=l.driver and l2.lap=l.lap+2 and l2.stint=l.stint
  where l.state='following' and pl.leader_pit and not pl.own_pit group by 1 order by 1""")
