"""07b covariate (deg_state_s) and outcome (forward pace window) construction, plus
coverage/cross-validation checks against 07a's published numbers. Still no
instrument-vs-outcome contrast is computed here -- this is pure construction +
coverage, the same kind of fact 07a established before writing its pre-registration
(row counts, NULL rates). Read-only against data/dev.duckdb.
"""
import duckdb
import numpy as np
import pandas as pd

DB = "/Users/justin/github/off-the-pace/data/dev.duckdb"
PANEL_IN = "/Users/justin/github/off-the-pace/scratchpad/panel_07b.parquet"
PANEL_OUT = "/Users/justin/github/off-the-pace/scratchpad/panel_07b_full.parquet"

panel = pd.read_parquet(PANEL_IN)

# ---------------------------------------------------------------------------
# deg_state_s: mean(residual) over last 3 valid laps strictly before ell,
# minus mean(residual) over the stint's own first 3 valid laps. Requires >=4
# valid laps strictly before ell (07a's exact rule). Computed within-stint only.
# ---------------------------------------------------------------------------
def deg_state_for_stint(g: pd.DataFrame) -> pd.Series:
    g = g.sort_values("lap_in_stint")
    valid_mask = g["driver_skill_residual_s"].notna().to_numpy()
    resid = g["driver_skill_residual_s"].to_numpy()
    n = len(g)
    out = np.full(n, np.nan)
    valid_idx = np.where(valid_mask)[0]  # positions (row order) of valid laps in this stint
    if len(valid_idx) >= 4:
        opening_mean = resid[valid_idx[:3]].mean()
    else:
        opening_mean = np.nan
    for i in range(n):
        # valid laps strictly before this row (by position, which is chronological
        # order within the stint since we sorted by lap_in_stint)
        prior_valid = valid_idx[valid_idx < i]
        if len(prior_valid) >= 4 and not np.isnan(opening_mean):
            trailing_mean = resid[prior_valid[-3:]].mean()
            out[i] = trailing_mean - opening_mean
    return pd.Series(out, index=g.index)

print("Computing deg_state_s per stint...")
deg_parts = []
for stint_id, g in panel.groupby("stint_id", sort=False):
    deg_parts.append(deg_state_for_stint(g))
panel["deg_state_s"] = pd.concat(deg_parts).reindex(panel.index)

n_deg_defined = panel["deg_state_s"].notna().sum()
print(f"deg_state_s defined on {n_deg_defined} / {len(panel)} moments "
      f"({100*n_deg_defined/len(panel):.1f}%) -- 07a reports 63,047 / 90,597 (69.6%)")

# ---------------------------------------------------------------------------
# Forward outcome Y: mean(driver_skill_residual_s) over the next up to 3 valid
# laps strictly after this moment's lap_number, within the SAME (race_year,
# race_id, driver_id) but crossing stint boundaries freely -- this is what lets
# a treated (pit-now) moment's outcome land on the new stint's tyre while a
# control (no-pit) moment's outcome lands on the continuing tyre. Needs the
# FULL geometry (including the driver's other stints, censored or not), not
# just the panel's uncensored-stint rows.
# ---------------------------------------------------------------------------
con = duckdb.connect(DB, read_only=True)
full_geom = con.execute("""
    SELECT lap_id, race_year, race_id, driver_id, lap_number
    FROM int_stint_geometry
    ORDER BY race_year, race_id, driver_id, lap_number
""").df()
resid = con.execute("SELECT lap_id, driver_skill_residual_s FROM int_lap_residual_decomposed").df()
con.close()

full_geom = full_geom.merge(resid, on="lap_id", how="left")

def forward_outcome_for_group(g: pd.DataFrame, k: int = 3):
    g = g.sort_values("lap_number")
    lap_numbers = g["lap_number"].to_numpy()
    resid = g["driver_skill_residual_s"].to_numpy()
    valid_mask = ~np.isnan(resid)
    valid_lap_numbers = lap_numbers[valid_mask]
    valid_resid = resid[valid_mask]
    n = len(g)
    y_mean = np.full(n, np.nan)
    y_n = np.zeros(n, dtype=int)
    for i in range(n):
        # first index in valid_lap_numbers strictly greater than lap_numbers[i]
        pos = np.searchsorted(valid_lap_numbers, lap_numbers[i], side="right")
        window = valid_resid[pos:pos + k]
        if len(window) > 0:
            y_mean[i] = window.mean()
            y_n[i] = len(window)
    return pd.DataFrame({"y_forward_mean": y_mean, "y_forward_n": y_n}, index=g.index)

print("Computing forward outcome Y per driver-race (this is the slow step)...")
y_parts = []
for key, g in full_geom.groupby(["race_year", "race_id", "driver_id"], sort=False):
    y_parts.append(forward_outcome_for_group(g))
y_df = pd.concat(y_parts)
full_geom = full_geom.join(y_df)

# map back onto the panel by lap_id
panel = panel.merge(full_geom[["lap_id", "y_forward_mean", "y_forward_n"]], on="lap_id", how="left")

print("\nForward-outcome coverage on the panel (90,597 uncensored risk-set moments):")
print(panel["y_forward_n"].value_counts(dropna=False).sort_index())
n_y_defined = panel["y_forward_n"].gt(0).sum()
print(f"y defined (>=1 forward valid lap) on {n_y_defined} / {len(panel)} "
      f"({100*n_y_defined/len(panel):.1f}%)")

panel.to_parquet(PANEL_OUT)
print("\nWrote", PANEL_OUT)
