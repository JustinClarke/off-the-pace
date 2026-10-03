"""Replay the compiled isolation subtree into a SCRATCH copy of dev.duckdb.

Not dbt: executes transform/target/compiled/... SQL (compiled 2026-09-29 20:53, newer than
every isolation source file) as CREATE OR REPLACE TABLE in the copy, reading the car term
from a scratch parquet. data/dev.duckdb and data/fits/ are never opened for writing.

usage: python replay_isolation.py <scratch dev.duckdb> <car_fe parquet>
"""
import sys
import time
from pathlib import Path

import duckdb

REPO = Path("/Users/justin/github/off-the-pace")
COMPILED = REPO / "transform/target/compiled/off_the_pace/models"
ORDER = [
    "intermediate/int_constructor_car_fe_isolation",
    "intermediate/int_driver_isolation_lap_pace",
    "intermediate/int_driver_isolation_stint_tyre",
    "intermediate/int_driver_isolation_lap_values",
    "marts/fct_driver_isolation_pair_lap",
    "marts/fct_driver_isolation_lap",
    "marts/fct_driver_isolation_stint",
    "marts/fct_driver_isolation_race",
]

db, parquet = sys.argv[1], sys.argv[2]
assert Path(db).resolve() != (REPO / "data/dev.duckdb").resolve(), "refusing to write live dev"
con = duckdb.connect(db)
for rel in ORDER:
    name = rel.split("/")[1]
    sql = (COMPILED / f"{rel}.sql").read_text()
    if name == "int_constructor_car_fe_isolation":
        old = "'../data/fits/constructor_car_fe_isolation.parquet'"
        assert old in sql
        sql = sql.replace(old, f"'{parquet}'")
    t0 = time.time()
    before = con.execute(f'SELECT COUNT(*) FROM "dev"."main"."{name}"').fetchone()[0]
    con.execute(f'CREATE OR REPLACE TABLE "dev"."main"."{name}" AS (\n{sql}\n)')
    after = con.execute(f'SELECT COUNT(*) FROM "dev"."main"."{name}"').fetchone()[0]
    print(f"{name:40s} rows {before:>8d} -> {after:>8d}  ({time.time() - t0:.1f}s)")
con.close()
