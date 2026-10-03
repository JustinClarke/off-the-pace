"""Fit the isolation car term under candidate era structures (read-only on dev).
Writes one parquet per structure into this folder and prints identification counts."""
import sys, logging
from pathlib import Path
import duckdb, pandas as pd, numpy as np
sys.path.insert(0, "/Users/justin/github/off-the-pace/transform")
from tasks.coefficients import fit_constructor_car_fe as fc
logging.getLogger().setLevel(logging.WARNING)

OUT = Path(__file__).parent
STRUCTS = {
    "current": [(2018, 2021), (2022, 2025)],
    "opt1_per_season": [(y, y) for y in range(2018, 2026)],
    "opt2_technical": [(2018, 2018), (2019, 2020), (2021, 2021), (2022, 2024), (2025, 2025)],
    "opt3_hybrid": [(2018, 2019), (2020, 2021), (2022, 2024), (2025, 2025)],
}
def label(y, spans):
    for a, b in spans:
        if a <= y <= b:
            return f"e{a}_{b}"
con = duckdb.connect("/Users/justin/github/off-the-pace/data/dev.duckdb", read_only=True)
panel = fc.load_isolation_panel(con)
con.close()
rows = []
for name, spans in STRUCTS.items():
    p = panel.copy()
    p["era"] = p.race_year.map(lambda y: label(int(y), spans))
    out, note = fc.fit_car_fe_isolation(p)
    out["fit_method"] = f"scratch_{name}"
    out["fit_timestamp"] = "scratch"
    out["connectivity_note"] = note
    out.to_parquet(OUT / f"car_{name}.parquet", index=False)
    # driver-race identification on the fit sample
    dr = p.groupby(["race_year", "race_id", "constructor_id", "driver_id"]).size().reset_index()
    dr = dr.merge(out[["race_year", "race_id", "constructor_id", "car_term_source"]], how="left")
    by_year = dr.groupby("race_year").car_term_source.apply(lambda s: (s == "driver_id").mean())
    rows.append({"structure": name, "driver_races": len(dr),
                 "identified_share": (dr.car_term_source == "driver_id").mean(),
                 **{f"y{int(k)}": round(v, 3) for k, v in by_year.items()}})
    print(name, "|", note)
print(pd.DataFrame(rows).to_string(index=False))
