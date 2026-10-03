"""Experiment for W33 issue 4 (2018 level), on a SCRATCH copy only.

Variant: y_s centred on the median of the lap's PRE-CLIFF Ω laps (all-lap median when the
lap has none), instead of all Ω laps. Rebuilds the panel from the compiled SQL with that
one change, refits the car term with the working-tree fitter, and replays the downstream
models. data/dev.duckdb and data/fits/ are never written.

usage: python variant_precliff_median.py <scratch dev.duckdb> <scratch fits dir>
"""
import subprocess
import sys
from pathlib import Path

import duckdb

REPO = Path("/Users/justin/github/off-the-pace")
PANEL = REPO / "transform/target/compiled/off_the_pace/models/intermediate/int_driver_isolation_lap_panel.sql"
db, fits = sys.argv[1], Path(sys.argv[2])
assert Path(db).resolve() != (REPO / "data/dev.duckdb").resolve()

sql = PANEL.read_text()
old = "        MEDIAN(x_s) AS field_median_x_s,"
new = ("        COALESCE(MEDIAN(x_s) FILTER (WHERE laps_past_cliff = 0), MEDIAN(x_s))"
       " AS field_median_x_s,")
assert sql.count(old) == 1
sql = sql.replace(old, new)
con = duckdb.connect(db)
con.execute(f'CREATE OR REPLACE TABLE "dev"."main"."int_driver_isolation_lap_panel" AS (\n{sql}\n)')
print("panel rebuilt:", con.execute('SELECT COUNT(*) FROM "dev"."main"."int_driver_isolation_lap_panel"').fetchone())
con.close()

fits.mkdir(parents=True, exist_ok=True)
pq = fits / "constructor_car_fe_isolation.parquet"
subprocess.run([sys.executable, "-m", "tasks.coefficients.fit_constructor_car_fe", "--panel", "isolation",
                "--db", db, "--out", str(pq)], cwd=REPO / "transform", check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run([sys.executable, str(Path(__file__).parent / "replay_isolation.py"), db, str(pq)], check=True)
