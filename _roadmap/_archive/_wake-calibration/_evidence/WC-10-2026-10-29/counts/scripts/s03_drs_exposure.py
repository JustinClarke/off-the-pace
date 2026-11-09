"""Outcome-blind: DRS-open time per lap (a treatment/state channel, not an outcome) by lap traffic state.
Season 2023 only. DRS codes 10/12/14 = flap open (FastF1 convention). Reads no time/speed outcome."""
import duckdb, sys
PT = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/pass_table_2023.parquet"
B = "/Users/justin/github/off-the-pace/data/bronze"
OUT = sys.argv[1]
c = duckdb.connect()
c.sql(f"""create table lap as select race_id, driver, lap,
  median(case when clear_ahead then 30 else gap_s end) med_gap, count(*) n,
  sum(((clear_ahead or gap_s>3))::int) n_free
  from read_parquet('{PT}') where reason is null and segment_basis='brake_onset' group by all""")
c.sql("""create table st as select *, case when med_gap<1.0 then 'close<1s' when med_gap<1.5 then 'following1-1.5' when n_free=n then 'free'
  else 'other' end state from lap""")
c.sql(f"""create table drs as select race_id, driver_id driver, cast(lap_number as int) lap,
  avg((DRS in (10,12,14))::int) drs_open_share, count(*) n
  from read_parquet('{B}/telemetry/season=2023/race=*/telemetry.parquet', union_by_name=true)
  where Source='car' group by all""")
r = c.sql("""select state, count(*) laps, avg(drs_open_share) mean_open_share, avg((drs_open_share>0)::int) share_laps_any_drs
  from st join drs using (race_id, driver, lap) group by state order by state""").df()
print(r.to_string()); r.to_csv(f"{OUT}/drs_by_state_2023.csv", index=False)
