"""theta_air (global, all seasons) vs the same estimator restricted to <=2024.
Runs the COMPILED production SQL of int_dirty_air_tax_component with only the
theta_air_estimate CTE's FROM clause filtered. cwd must be transform/ (staging globs)."""
import duckdb, re
from pathlib import Path
sql = Path("target/compiled/off_the_pace/models/intermediate/int_dirty_air_tax_component.sql").read_text()
assert sql.count("FROM calibration_panel") == 1
c = duckdb.connect("../data/dev.duckdb", read_only=True)
def theta(filter_sql):
    s = sql.replace("FROM calibration_panel", f"FROM calibration_panel {filter_sql}")
    # replace final select with theta only
    head = s[: s.index("with_tax AS")]
    head = head.rstrip().rstrip(",")
    return c.sql(head + "\nSELECT theta_air, calibration_sample_n FROM theta_air_estimate").fetchone()
print("all seasons (as built):", theta(""))
print("race_year <= 2024     :", theta("WHERE race_year <= 2024"))
print("race_year <= 2023     :", theta("WHERE race_year <= 2023"))
print("built column value    :", c.sql("select distinct theta_air from int_dirty_air_tax_component").fetchall() if 'theta_air' in [r[0] for r in c.sql("describe int_dirty_air_tax_component").fetchall()] else "n/a")
