"""Oracle 1: FastF1 stg_results.points per race vs Jolpica per-round standings increments.
race_id = '<season>_<round>' (validated against bronze schedule EventName vs race_to_track below)."""
import duckdb
c = duckdb.connect("../data/dev.duckdb", read_only=True)
# validate race_id -> round mapping via schedule names
chk = c.sql("""
with s as (select season, RoundNumber rnd, lower(replace(replace(EventName,' ','_'),'-','_')) ev from read_parquet('../data/bronze/schedule/*/*.parquet', hive_partitioning=1, union_by_name=1))
select count(*) n, count(*) filter (where rt.track_id = s.ev) name_match
from race_to_track rt join s on rt.race_id = cast(s.season as varchar)||'_'||cast(s.rnd as varchar)""").fetchall()
print("race_id->round name agreement:", chk)
q = """
with j as (select season, round, driver_code, points from read_parquet('../data/bronze/reference/jolpica/driver_standings/**/*.parquet', hive_partitioning=0, union_by_name=1)),
jd as (select season, round, driver_code, points - coalesce(lag(points) over (partition by season, driver_code order by round), 0) jinc from j),
f as (select race_year season, cast(split_part(race_id,'_',2) as int) round, driver_id driver_code, points fpts from stg_results)
select f.season, count(*) n, sum(case when abs(coalesce(jinc,0)-fpts)<1e-9 then 1 else 0 end) exact,
  sum(case when jinc is null then 1 else 0 end) j_missing,
  sum(case when abs(coalesce(jinc,0)-fpts)>=1e-9 then 1 else 0 end) differ,
  count(distinct case when abs(coalesce(jinc,0)-fpts)>=1e-9 then f.round end) rounds_with_diff
from f left join jd using (season, round, driver_code) group by 1 order by 1"""
print(c.sql(q).df().to_string())
# season totals
q2 = """
with j as (select season, driver_code, max(points) jpts from read_parquet('../data/bronze/reference/jolpica/driver_standings/**/*.parquet', union_by_name=1) group by 1,2),
f as (select race_year season, driver_id driver_code, sum(points) fpts from stg_results group by 1,2),
app as (select race_year season, driver_id driver_code, sum(case finish_position when 1 then 25 when 2 then 18 when 3 then 15 when 4 then 12 when 5 then 10 when 6 then 8 when 7 then 6 when 8 then 4 when 9 then 2 when 10 then 1 else 0 end) apts from stg_results where is_classified group by 1,2)
select season, count(*) drivers, sum(case when abs(jpts-fpts)<1e-9 then 1 else 0 end) fastf1_total_eq_official,
  sum(case when abs(jpts-coalesce(apts,0))<1e-9 then 1 else 0 end) app_table_eq_official,
  max(abs(jpts-coalesce(apts,0))) max_gap_app_vs_official
from j join f using (season, driver_code) left join app using (season, driver_code) where season>=2018 group by 1 order by 1"""
print(c.sql(q2).df().to_string())
