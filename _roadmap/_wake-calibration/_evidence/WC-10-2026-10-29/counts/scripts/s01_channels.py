"""Outcome-blind channel inventory: bronze telemetry, laps, weather. Counts/coverage only.
No segment time, lap time value or loss is summarised."""
import duckdb, sys
B = "/Users/justin/github/off-the-pace/data/bronze"
OUT = sys.argv[1]
c = duckdb.connect()
c.sql("SET threads=8")
rows = []
# Telemetry: one race per season (sample) for dt / source; whole-season non-null shares
tel = c.sql(f"""
select season,
  count(*) n,
  avg((throttle_pct is not null)::int) thr_nn,
  avg((brake is not null)::int) brk_nn,
  avg((DRS is not null)::int) drs_nn,
  avg((RPM is not null)::int) rpm_nn,
  avg((nGear is not null)::int) gear_nn,
  avg((Z is not null)::int) z_nn,
  avg((DriverAhead is not null and DriverAhead<>'')::int) da_nn,
  count(distinct race_id) races,
  string_agg(distinct Source, ',') sources
from read_parquet('{B}/telemetry/season=*/race=*/telemetry.parquet', hive_partitioning=false, union_by_name=true)
group by season order by season""").df()
print(tel.to_string())
tel.to_csv(f"{OUT}/tel_channels_by_season.csv", index=False)

# Sample spacing per source, one race per season (Italian GP, Monza = fastest)
dt = c.sql(f"""
with t as (
 select season, driver_id, Source, SessionTime/1e9 st, throttle_pct, DRS
 from read_parquet('{B}/telemetry/season=*/race=italian_grand_prix/telemetry.parquet', hive_partitioning=false, union_by_name=true)
), d as (
 select season, Source, st - lag(st) over (partition by season, driver_id order by st) dts,
        throttle_pct, DRS from t)
select season, Source, count(*) n, median(dts) med_dt_s, quantile_cont(dts,0.9) p90_dt_s,
  count(distinct throttle_pct) n_thr_values, string_agg(distinct DRS::varchar, ',') drs_codes
from d group by season, Source order by season, Source""").df()
print(dt.to_string())
dt.to_csv(f"{OUT}/tel_sample_spacing_monza.csv", index=False)

# Car-only sample spacing (car data rows), all-season sample
car = c.sql(f"""
with t as (select season, race_id, driver_id, SessionTime/1e9 st from read_parquet('{B}/telemetry/season=*/race=*/telemetry.parquet', hive_partitioning=false, union_by_name=true) where Source='car'),
d as (select season, st - lag(st) over (partition by season, race_id, driver_id order by st) dts from t)
select season, median(dts) med_car_dt, quantile_cont(dts, 0.9) p90 from d group by season order by season""").df()
print(car.to_string())
car.to_csv(f"{OUT}/tel_car_spacing_by_season.csv", index=False)

laps = c.sql(f"""
select season, count(*) n,
 avg((TyreLife is not null)::int) tyrelife_nn,
 avg((Compound is not null and Compound<>'UNKNOWN')::int) compound_known,
 avg((SpeedST is not null)::int) speedST_nn, avg((SpeedI1 is not null)::int) speedI1_nn, avg((SpeedFL is not null)::int) speedFL_nn,
 avg((FreshTyre is not null)::int) fresh_nn, avg(coalesce(IsAccurate,false)::int) accurate_share,
 avg((Position is not null)::int) position_nn
from read_parquet('{B}/laps/season=*/race=*/*_laps.parquet', hive_partitioning=false, union_by_name=true)
group by season order by season""").df()
print(laps.to_string())
laps.to_csv(f"{OUT}/laps_channels_by_season.csv", index=False)

w = c.sql(f"""
select season, count(*) n, count(distinct race_id) races, avg((track_temp_c is not null)::int) tt_nn,
 avg((wind_speed_ms is not null)::int) wind_nn, median(dts) med_dt from (
 select *, session_time_s - lag(session_time_s) over (partition by season, race_id order by session_time_s) dts
 from read_parquet('{B}/weather/season=*/race=*/weather.parquet', hive_partitioning=false, union_by_name=true)) group by season order by season""").df()
print(w.to_string())
w.to_csv(f"{OUT}/weather_by_season.csv", index=False)
