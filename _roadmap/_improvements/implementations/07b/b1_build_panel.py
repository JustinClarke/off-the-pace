"""07b panel builder. Read-only against data/dev.duckdb. Writes a cached parquet to
scratchpad/ for reuse by later stages (structural checks + estimation). No warehouse
writes, no model files touched.

Grain: (stint, lap) risk-set moment over every lap of every uncensored stint --
identical unit of observation to 07a. This script computes structural/coverage
quantities only; it does not compute any instrument-outcome contrast.
"""
import duckdb
import numpy as np
import pandas as pd

DB = "/Users/justin/github/off-the-pace/data/dev.duckdb"
OUT = "/Users/justin/github/off-the-pace/scratchpad/panel_07b.parquet"

con = duckdb.connect(DB, read_only=True)

print("Pulling int_stint_geometry (uncensored stints only)...")
geom = con.execute("""
    SELECT g.stint_id, g.lap_id, g.race_year, g.race_id, g.driver_id,
           g.lap_number, g.stint_number, g.lap_in_stint, g.valid_lap_in_stint,
           g.age_in_stint, g.compound_in_stint AS compound,
           g.is_valid_lap, g.is_pit_lap, g.is_safety_car_lap, g.is_vsc_lap,
           g.is_red_flag_lap
    FROM int_stint_geometry g
    JOIN int_stint_end_regime e ON g.stint_id = e.stint_id
    WHERE e.is_censored_stint = FALSE
    ORDER BY g.race_year, g.race_id, g.driver_id, g.lap_number
""").df()
print("geom rows:", len(geom))

print("Pulling driver_skill_residual_s (only exists for valid laps)...")
resid = con.execute("""
    SELECT lap_id, driver_skill_residual_s
    FROM int_lap_residual_decomposed
""").df()
print("resid rows:", len(resid))

print("Pulling race_to_track...")
r2t = con.execute("SELECT race_id, track_id FROM race_to_track").df()

print("Pulling race-level wet flag (MAX rainfall_flag over int_track_evolution)...")
wet = con.execute("""
    SELECT race_year, race_id, MAX(CAST(rainfall_flag AS INTEGER)) AS wet_race
    FROM int_track_evolution
    GROUP BY race_year, race_id
""").df()

con.close()

# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------
panel = geom.merge(resid, on="lap_id", how="left")
panel = panel.merge(r2t, on="race_id", how="left")
panel = panel.merge(wet, on=["race_year", "race_id"], how="left")

panel["era"] = np.where(panel["race_year"] < 2022, "pre2022", "post2022")

# tyre-age bin, matching 07a's L4 bins exactly
bins = [0, 5, 10, 15, 20, 25, np.inf]
labels = ["1-5", "6-10", "11-15", "16-20", "21-25", "26+"]
panel["age_bin"] = pd.cut(panel["age_in_stint"], bins=bins, labels=labels)

# race key for clustering later
panel["race_key"] = panel["race_year"].astype(str) + "_" + panel["race_id"]

panel.to_parquet(OUT)
print("Wrote", OUT, "rows:", len(panel))
print(panel.dtypes)
