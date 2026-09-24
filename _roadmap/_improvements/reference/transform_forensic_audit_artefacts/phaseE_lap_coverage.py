"""§5.1: race-depth lap files vs official race length. Oracle = bronze results 'Laps' of P1 (FastF1) and
Jolpica laps table max lap per round. Also per-driver contiguity of lap_number."""
import duckdb
c = duckdb.connect("../data/dev.duckdb", read_only=True)
cols = [r[0] for r in c.sql("describe select * from read_parquet('../data/bronze/results/*/*/*.parquet', union_by_name=1)").fetchall()]
print("results cols has Laps:", "Laps" in cols)
jl = c.sql("describe select * from read_parquet('../data/bronze/reference/jolpica/laps/**/*.parquet', union_by_name=1)").df()["column_name"].tolist()
print("jolpica laps cols:", jl)
q = """
with w as (select r.race_year, r.race_id, max(l.lap_number) stg_max, count(*) stg_rows from stg_laps l join stg_results r using (race_year, race_id, driver_id) group by 1,2),
jl as (select season, round, max(lap_number) AS j_max from read_parquet('../data/bronze/reference/jolpica/laps/**/*.parquet', union_by_name=1) where season>=2018 group by 1,2)
select w.race_year, w.race_id, stg_max, j_max, stg_max - j_max AS diff from w left join jl on jl.season=w.race_year and jl.round=cast(split_part(w.race_id,'_',2) as int)
where j_max is null or stg_max <> j_max order by 1,2"""
print(c.sql(q).df().to_string())
q2 = """select count(*) AS drivers_races_noncontig from (select race_id, driver_id, max(lap_number)-min(lap_number)+1 AS span, count(*) AS n from stg_laps group by 1,2) where span<>n"""
print(c.sql(q2).df())
q3 = """select count(*) AS lap_lt1 from stg_laps where lap_number < 1"""
print(c.sql(q3).df())
