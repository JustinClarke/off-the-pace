import duckdb
c = duckdb.connect("../data/dev.duckdb", read_only=True)
print(c.sql("select count(*) filter (where pit_duration_s <= 0) AS nonpos, count(*) filter (where pit_duration_s > 60) AS gt60, count(*) filter (where pit_duration_s is null) AS n_null, count(*) AS n from stg_pits").df())
q = """
with jm as (select distinct season, driver_id jid, driver_code from read_parquet('../data/bronze/reference/jolpica/driver_standings/**/*.parquet', union_by_name=1)),
jp as (select p.season, p.round, jm.driver_code, p.lap from read_parquet('../data/bronze/reference/jolpica/pit_stops/**/*.parquet', union_by_name=1) p join jm on jm.season=p.season and jm.jid=p.driver_id where p.season in (2018,2020)),
sp as (select race_year season, cast(split_part(race_id,'_',2) as int) round, driver_id driver_code, pit_in_lap_number lap from stg_pits)
select jp.season, jp.round, count(*) AS unmatched from jp anti join sp using (season, round, driver_code, lap) group by 1,2 order by 1,2"""
print(c.sql(q).df().to_string())
