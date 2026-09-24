"""07b boundary-lap flags (conservative Z, unanimous-slice) merged onto the panel,
plus final coverage counts for the two robustness populations. Structural only --
still no instrument-vs-outcome contrast computed.
"""
import duckdb
import numpy as np
import pandas as pd

DB = "/Users/justin/github/off-the-pace/data/dev.duckdb"
PANEL_IN = "/Users/justin/github/off-the-pace/scratchpad/panel_07b_full.parquet"
PANEL_OUT = "/Users/justin/github/off-the-pace/scratchpad/panel_07b_final.parquet"

panel = pd.read_parquet(PANEL_IN)

con = duckdb.connect(DB, read_only=True)
full = con.execute("""
    SELECT lap_id, race_year, race_id, driver_id, lap_number,
           is_safety_car_lap, is_vsc_lap
    FROM int_stint_geometry
    ORDER BY race_year, race_id, driver_id, lap_number
""").df()
con.close()

full["Z"] = (full["is_safety_car_lap"] | full["is_vsc_lap"]).astype(int)
full = full.sort_values(["race_year", "race_id", "driver_id", "lap_number"])
full["Z_prev"] = full.groupby(["race_year", "race_id", "driver_id"])["Z"].shift(1)
full["Z_conservative"] = ((full["Z"] == 1) & (full["Z_prev"] == 1)).astype(int)
full["onset"] = ((full["Z"] == 1) & (full["Z_prev"].fillna(0) == 0)).astype(int)

grp = full.groupby(["race_year", "race_id", "lap_number"])["Z"]
n_cars = grp.transform("count")
z_sum = grp.transform("sum")
full["slice_unanimous"] = (z_sum == 0) | (z_sum == n_cars)
full["slice_n_cars"] = n_cars

panel = panel.merge(
    full[["lap_id", "Z_conservative", "onset", "slice_unanimous", "slice_n_cars"]],
    on="lap_id", how="left",
)

panel["stint_max_lap"] = panel.groupby("stint_id")["lap_in_stint"].transform("max")
panel["D"] = (panel["lap_in_stint"] == panel["stint_max_lap"]).astype(int)
panel["Z"] = (panel["is_safety_car_lap"] | panel["is_vsc_lap"]).astype(int)

excl_redflag_only = panel["is_red_flag_lap"] & ~(panel["is_safety_car_lap"] | panel["is_vsc_lap"])
excl_track = panel["track_id"].isna()
pop1 = panel[~excl_redflag_only & ~excl_track].copy()
pop2 = pop1[pop1["deg_state_s"].notna()].copy()
pop3 = pop2[pop2["y_forward_n"] > 0].copy()

print("Headline analytic population (pop3):", len(pop3), "Z=1:", pop3["Z"].sum(),
      "pit moments:", pop3["D"].sum())

# Robustness A: conservative Z (drop onset-lap moments entirely)
popA = pop3[pop3["onset"] == 0].copy()
popA["Z_use"] = popA["Z_conservative"]
print("\nRobustness A -- conservative Z (onset laps dropped):", len(popA),
      "rows dropped:", len(pop3) - len(popA),
      "Z_use=1:", popA["Z_use"].sum(), "pit moments:", popA["D"].sum())

# Robustness B: unanimous slices only
popB = pop3[pop3["slice_unanimous"] == True].copy()
print("\nRobustness B -- unanimous slices only:", len(popB),
      "rows dropped:", len(pop3) - len(popB),
      "Z=1:", popB["Z"].sum(), "pit moments:", popB["D"].sum())

panel.to_parquet(PANEL_OUT)
print("\nWrote", PANEL_OUT)
