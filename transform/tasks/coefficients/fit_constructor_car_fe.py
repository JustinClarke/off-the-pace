"""
Fit the de-biased constructor car pace (constructor×race fixed effect) for the
Ghost Car Standings "equal-car track record" leaderboard.

Background
----------
The leaderboard signal is
    driver_skill_field_s = driver_median_pace_delta_s − car_term
i.e. a driver's own pace minus the pace of the car he drove. The old car_term
(int_constructor_structural_pace.constructor_structural_pace_s) is just the
median of the car's *own* clean laps re-centred by the race average. With no
global driver anchor it equals (true car pace + that team's average driver
skill), so subtracting it strips the driver's own skill back out a weak
driver on a slow car floats to the top (the Albon/Sargeant @ Zandvoort bug).

This fitter estimates the car pace *net of who drove it* with a two-way fixed
effects regression on the clean lap panel:

    pace_delta_s ~ 1 | driver_id + constructor_race

The constructor×race fixed effect absorbs the car net of driver skill (the
driver FE is identified relative to the field because every constructor races
every event), which is exactly the HDFE that int_constructor_structural_pace's
header calls itself a placeholder for. We emit only the car FE the per-(race,
driver) `own_median − car_fe` keeps per-race/per-circuit signal for the
downstream affinity shrinkage.

Output
------
A parquet at data/fits/constructor_car_fe.parquet, one row per
(race_year, race_id, constructor_id) with column car_fe_s (negative = faster
than field), read by the int_constructor_car_fe dbt model. NOT a seed: this is
a per-build fit, not a hand-curated calibration, so it lives in data/ (a build
artifact) rather than churning a committed CSV every rebuild.

Usage
-----
    python -m tasks.coefficients.fit_constructor_car_fe
    python -m tasks.coefficients.fit_constructor_car_fe --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pyfixest as pf  # type: ignore

from .provenance import build_provenance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
OUT_PATH = REPO_ROOT / "data" / "fits" / "constructor_car_fe.parquet"

# The clean lap panel: lap_time vs the smoothed field median, restricted to
# correction_weight = 1.0 and dry laps. This mirrors the clean_panel CTE in
# int_driver_race_skill_loro / int_constructor_structural_pace exactly, so the
# fitted car FE is on the same scale as the median the downstream model subtracts.
PANEL_QUERY = """
WITH fuel AS (
    SELECT lap_id, race_year, race_id, driver_id, lap_number, lap_time_s
    FROM int_lap_fuel_state
),
field_pace AS (
    SELECT race_year, race_id, lap_number, field_pace_smoothed_s
    FROM int_field_pace_curve
),
laps_meta AS (
    SELECT lap_id, constructor_id FROM stg_laps
),
corrections AS (
    SELECT lap_id, correction_weight FROM int_event_corrections
),
evolution AS (
    SELECT race_year, race_id, lap_number, rainfall_flag
    FROM int_track_evolution
)
SELECT
    f.race_year,
    f.race_id,
    f.driver_id,
    lm.constructor_id,
    f.lap_time_s - COALESCE(fp.field_pace_smoothed_s, f.lap_time_s) AS pace_delta_s
FROM fuel f
JOIN laps_meta lm USING (lap_id)
LEFT JOIN field_pace fp
       ON f.race_year = fp.race_year
      AND f.race_id = fp.race_id
      AND f.lap_number = fp.lap_number
LEFT JOIN corrections cor USING (lap_id)
LEFT JOIN evolution e
       ON f.race_year = e.race_year
      AND f.race_id = e.race_id
      AND f.lap_number = e.lap_number
WHERE f.lap_time_s IS NOT NULL
  AND COALESCE(cor.correction_weight, 1.0) = 1.0
  AND COALESCE(e.rainfall_flag, FALSE) = FALSE
"""


def load_panel(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("Loading clean lap panel from %s ...", DB_PATH)
    panel = con.execute(PANEL_QUERY).fetchdf()
    panel["constructor_race"] = (
        panel.race_year.astype(str)
        + "_" + panel.race_id.astype(str)
        + "_" + panel.constructor_id.astype(str)
    )
    log.info(
        "Loaded %d clean laps · %d drivers · %d races · %d constructor-races.",
        len(panel),
        panel.driver_id.nunique(),
        panel.groupby(["race_year", "race_id"]).ngroups,
        panel.constructor_race.nunique(),
    )
    return panel


def fit_car_fe(panel: pd.DataFrame) -> pd.DataFrame:
    """Two-way FE fit; return per-(race_year, race_id, constructor_id) car_fe_s."""
    log.info("Fitting pace_delta_s ~ 1 | driver_id + constructor_race ...")
    model = pf.feols(
        "pace_delta_s ~ 1 | driver_id + constructor_race", data=panel
    )
    fe = model.fixef()
    car_fe = pd.Series(fe["C(constructor_race)"])
    car_fe.index = car_fe.index.astype(str)
    drv_fe = pd.Series(fe["C(driver_id)"])
    drv_fe.index = drv_fe.index.astype(str)

    # Sanity-log the global driver FE (neg = faster). A pyfixest singleton FE is
    # dropped, so a handful of (race, constructor) cells can be unidentified and
    # fall out below the same races drop today when a constructor has < 10
    # clean laps, so the downstream LEFT JOIN already tolerates the gap.
    drv_sorted = drv_fe.sort_values()
    log.info("Global driver FE (neg = faster) fastest 8:")
    for did, v in list(drv_sorted.items())[:8]:
        log.info("    %-6s %+.3f", did, v)
    log.info("  ... slowest 5:")
    for did, v in list(drv_sorted.items())[-5:]:
        log.info("    %-6s %+.3f", did, v)

    # Map the FE back onto the (race_year, race_id, constructor_id) grain via the
    # panel's own keys never parse the concatenated constructor_race string,
    # because race_id itself contains an underscore (e.g. '2018_5').
    grain = (
        panel[["race_year", "race_id", "constructor_id", "constructor_race"]]
        .drop_duplicates()
        .copy()
    )
    grain["car_fe_s"] = grain.constructor_race.map(car_fe)
    n_total = len(grain)
    out = (
        grain.dropna(subset=["car_fe_s"])[
            ["race_year", "race_id", "constructor_id", "car_fe_s"]
        ]
        .sort_values(["race_year", "race_id", "constructor_id"])
        .reset_index(drop=True)
    )
    n_dropped = n_total - len(out)
    if n_dropped:
        log.info(
            "%d/%d constructor-races unidentified (singleton FE) dropped.",
            n_dropped, n_total,
        )
    log.info(
        "Emitting %d (race_year, race_id, constructor_id) rows; car_fe_s ∈ [%.3f, %.3f].",
        len(out), out.car_fe_s.min(), out.car_fe_s.max(),
    )
    return out


def run_fit() -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        panel = load_panel(con)
    finally:
        con.close()

    out = fit_car_fe(panel)

    prov = build_provenance(
        fit_method="constructor_car_fe_hdfe_v1",
        season_min=int(panel.race_year.min()),
        season_max=int(panel.race_year.max()),
    )
    for k, v in prov.items():
        out[k] = v
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fit the de-biased constructor car FE (HDFE) for Ghost Standings."
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        log.info("DRY RUN would write %s", OUT_PATH)
        return 0

    out = run_fit()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)
    log.info("Wrote %d rows → %s", len(out), OUT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
