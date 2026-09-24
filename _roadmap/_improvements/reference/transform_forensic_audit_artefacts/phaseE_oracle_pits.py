"""Oracle 2: stg_pits vs Jolpica pit_stops. Jolpica driver_id is an ergast slug; map via driver_standings
(driver_id -> driver_code) per season. Compare (season, round, driver_code, lap): stg pit_in_lap_number vs jolpica lap."""
import duckdb
c = duckdb.connect("../data/dev.duckdb", read_only=True)
q = """
with jm as (select distinct season, driver_id jid, driver_code from read_parquet('../data/bronze/reference/jolpica/driver_standings/**/*.parquet', union_by_name=1)),
jp as (select p.season, p.round, jm.driver_code, p.lap from read_parquet('../data/bronze/reference/jolpica/pit_stops/**/*.parquet', union_by_name=1) p join jm on jm.season=p.season and jm.jid=p.driver_id where p.season>=2018),
sp as (select race_year season, cast(split_part(race_id,'_',2) as int) round, driver_id driver_code, pit_in_lap_number lap from stg_pits),
jc as (select season, count(*) j_stops from jp group by 1),
sc as (select season, count(*) s_stops from sp group by 1),
m as (select season, count(*) AS n_matched from sp join jp using (season, round, driver_code, lap) group by 1),
m1 as (select season, count(*) AS n_matched_pm1 from sp join jp using (season, round, driver_code) where abs(sp.lap - jp.lap) = 1 group by 1)
select * from jc join sc using(season) left join m using(season) left join m1 using(season) order by 1"""
df = c.sql(q).df(); df["match_rate_vs_jolpica"] = df.n_matched / df.j_stops
print(df.to_string())
q2 = """
with jm as (select distinct season, driver_id jid, driver_code from read_parquet('../data/bronze/reference/jolpica/driver_standings/**/*.parquet', union_by_name=1)),
jp as (select p.season, p.round, coalesce(jm.driver_code, 'UNMAPPED') driver_code, count(*) n from read_parquet('../data/bronze/reference/jolpica/pit_stops/**/*.parquet', union_by_name=1) p left join jm on jm.season=p.season and jm.jid=p.driver_id where p.season>=2018 group by all)
select season, sum(n) filter (where driver_code='UNMAPPED') unmapped_stops from jp group by 1 order by 1"""
print(c.sql(q2).df().to_string())
print(c.sql("select count(*) filter (where pit_duration_s <= 0) nonpos, count(*) filter (where pit_duration_s > 60) gt60, count(*) filter (where pit_duration_s is null) nulls, count(*) n from stg_pits").df())
