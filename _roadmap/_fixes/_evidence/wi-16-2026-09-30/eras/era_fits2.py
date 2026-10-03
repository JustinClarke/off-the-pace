"""Placebo two-era splits: boundary B -> [2018..B-1 | B..2025]."""
import sys, logging
from pathlib import Path
import duckdb
sys.path.insert(0, "/Users/justin/github/off-the-pace/transform")
from tasks.coefficients import fit_constructor_car_fe as fc
logging.getLogger().setLevel(logging.WARNING)
import warnings; warnings.filterwarnings("ignore")
OUT = Path(__file__).parent
con = duckdb.connect("/Users/justin/github/off-the-pace/data/dev.duckdb", read_only=True)
panel = fc.load_isolation_panel(con); con.close()
for B in (2019, 2020, 2021, 2023, 2024):
    p = panel.copy()
    p["era"] = p.race_year.map(lambda y: f"pre{B}" if y < B else f"post{B}")
    out, note = fc.fit_car_fe_isolation(p)
    out["fit_method"] = f"scratch_two_era_{B}"; out["fit_timestamp"] = "scratch"; out["connectivity_note"] = note
    out.to_parquet(OUT / f"car_two_era_{B}.parquet", index=False)
    print(B, (out.car_term_source == "driver_id").mean().round(3), note)
