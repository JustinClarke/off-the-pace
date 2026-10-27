"""DA-01 runner. Usage: python run_sql.py <file.sql> [<file.sql> ...]

Opens <scratch>/work.duckdb (read-write, scratch only) and ATTACHes the scratch
copy <scratch>/dev.duckdb READ_ONLY as `dev`. Must be run with cwd = repo
transform/ so the dbt staging views' relative '../data/bronze' paths resolve.
Statements are split on lines that are exactly ';;'. A statement whose first
line is '-- OUT: name' has its result printed and written to out/name.csv.
"""
import os
import sys
import time

import duckdb

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
con = duckdb.connect(os.path.join(S, "work.duckdb"))
con.execute("SET threads TO 10")
con.execute("SET memory_limit = '14GB'")
con.execute(f"SET temp_directory = '{S}/tmp'")
con.execute(f"ATTACH '{S}/dev.duckdb' AS dev (READ_ONLY)")
con.execute("USE work.main")  # writes go to work; dev views are read as dev.main.x

for path in sys.argv[1:]:
    text = open(path).read()
    for stmt in [s.strip() for s in text.split("\n;;\n") if s.strip()]:
        first = stmt.splitlines()[0]
        t0 = time.time()
        if first.startswith("-- OUT:"):
            name = first.split(":", 1)[1].strip()
            df = con.sql(stmt).df()
            df.to_csv(os.path.join(S, "out", name + ".csv"), index=False)
            print(f"== {name} ({time.time()-t0:.1f}s)")
            print(df.to_string(index=False, max_rows=200))
        else:
            con.execute(stmt)
            print(f"-- ran: {first[:90]} ({time.time()-t0:.1f}s)")
