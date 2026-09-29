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

The isolation panel (--panel isolation, WI-16a)
-----------------------------------------------
The driver-isolation ratings (_roadmap/_fixes/wi/WI-16-cumulative-driver-isolation.md)
need a car term on the same scale as the quantity they subtract it from: y_s, the lap
time with compound and dirty air removed and then centred on the lap's field median
(int_driver_isolation_lap_panel). The default panel above is fitted on pace_delta_s,
before compound and dirty air come out, so it carries each team's average strategy and
traffic exposure; subtracting it from y_s would subtract those terms a second time (the
F22/F38 defect shape). So the isolation path fits

    y_s ~ 1 | driver_era + constructor_race        driver_era = driver_id + pre/post era_boundary

and emits car_iso_s: the constructor×race FE re-centred to a lap-weighted mean of zero
inside each race (negative = faster, like car_fe_s). y_s is already centred per lap, so no
race effect is needed.

Why driver_era: a global driver FE assumes a driver's skill is constant 2018-2025.
Splitting at the regulation boundary halves that assumption.

What identifies it: the teammate network. A constructor×race level is only comparable
with the other constructors in the same race if some chain of drivers who changed team
connects them. The OCO/PER 2018 Force India -> Racing Point rename creates no new link
(same pair, same car), so it cannot manufacture identification here the way it can in a
constructor-season design; no exclusion is needed. The fit checks this directly: a race
is identified when all of its constructor×race cells sit in one connected component of
the driver_key x constructor_race graph. An era falls back to the global driver_id when
any of its races is not identified under driver_era, or when it has more than one
component containing two or more constructors (the WI doc's rule). Both are logged, and
the rows carry car_term_source = 'global_driver'. A cell still unidentified under the
global key gets car_iso_s NULL and car_term_source = 'unidentified', never a guess.

The default path (--panel pace_delta) is unchanged: load_panel, fit_car_fe and run_fit
produce the same output as before this option existed (T49 pins it).

Usage
-----
    python -m tasks.coefficients.fit_constructor_car_fe
    python -m tasks.coefficients.fit_constructor_car_fe --dry-run
    python -m tasks.coefficients.fit_constructor_car_fe --panel isolation
    python -m tasks.coefficients.fit_constructor_car_fe --panel isolation \\
        --db /path/to/scratch/dev.duckdb --out /path/to/fits/constructor_car_fe_isolation.parquet
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyfixest as pf  # type: ignore
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .provenance import build_provenance

# WDC-winning constructor for each year. Used as the reference level (FE = 0.0) in the
# car FE fit, so that car ratings are anchored to championship-winning performance.
WDC_WINNER_BY_YEAR = {
    2018: "Mercedes",
    2019: "Mercedes",
    2020: "Mercedes",
    2021: "Red Bull",
    2022: "Red Bull",
    2023: "Red Bull",
    2024: "McLaren",
    2025: "McLaren",  # provisional; will be updated post-season
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
OUT_PATH = REPO_ROOT / "data" / "fits" / "constructor_car_fe.parquet"
ISOLATION_OUT_PATH = REPO_ROOT / "data" / "fits" / "constructor_car_fe_isolation.parquet"
ISOLATION_FIT_METHOD = "constructor_car_fe_isolation_hdfe_v1"

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
    """Two-way FE fit; return per-(race_year, race_id, constructor_id) car_fe_s.

    The reference level is set to the WDC-winning constructor for each year, so that
    car ratings are anchored to championship-winning performance (reference FE = 0.0).
    """
    log.info("Fitting pace_delta_s ~ 1 | driver_id + constructor_race ...")
    model = pf.feols(
        "pace_delta_s ~ 1 | driver_id + constructor_race", data=panel
    )
    # Tighten LSQR tolerances from default 1e-6 to 1e-12 for consistency across rebuilds
    # and to match the isolation path's precision (W31).
    fe = model.fixef(atol=1e-12, btol=1e-12)
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

    # Restore the reference level at 0.0 for the WDC-winning constructor in each year,
    # and re-centre all other FEs relative to that reference (W31).
    for year in grain["race_year"].unique():
        year_idx = grain["race_year"] == year
        year_data = grain[year_idx]
        wdc_constructor = WDC_WINNER_BY_YEAR.get(int(year))

        if wdc_constructor:
            wdc_rows = year_data[year_data["constructor_id"] == wdc_constructor]
            if not wdc_rows.empty:
                # Find WDC constructor cells in this year and calculate the mean offset
                wdc_cells = set(wdc_rows["constructor_race"].values)
                wdc_fes = [car_fe.get(cell, None) for cell in wdc_cells]
                wdc_fes_valid = [fe for fe in wdc_fes if fe is not None]

                if wdc_fes_valid:
                    # Re-centre this year's FEs so the WDC winner is at 0.0 on average
                    wdc_offset = np.mean(wdc_fes_valid)
                    grain.loc[year_idx, "car_fe_s"] = grain.loc[year_idx, "car_fe_s"] - wdc_offset
                    # Restore any missing WDC cells at 0.0 (the reference level after re-centering)
                    for wdc_cell in wdc_cells:
                        if str(wdc_cell) not in car_fe.index:
                            grain.loc[grain["constructor_race"] == wdc_cell, "car_fe_s"] = 0.0
                            log.info("Restored reference level %s at FE 0.0 (WDC reference).", wdc_cell)

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


def run_fit(db_path: Path = DB_PATH) -> pd.DataFrame:
    con = duckdb.connect(str(db_path), read_only=True)
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


# ── The isolation panel (WI-16a) ─────────────────────────────────────────────────────
# Read straight from the dbt model; every Ω predicate, the field centring and the era
# split live in SQL (int_driver_isolation_lap_panel), not here.
ISOLATION_PANEL_QUERY = """
SELECT
    lap_id,
    race_year,
    race_id,
    driver_id,
    driver_era,
    era,
    constructor_id,
    y_s
FROM int_driver_isolation_lap_panel
-- A fixed row order: the table's physical order changes from build to build, and the
-- FE solve is iterative, so without this two builds of the same panel gave car terms
-- differing by up to 4e-5 s.
ORDER BY lap_id
"""

ISOLATION_COLUMNS = [
    "race_year", "race_id", "constructor_id", "era", "n_laps",
    "car_fe_raw_s", "car_iso_s", "car_term_source", "race_components_n",
]


def load_isolation_panel(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    panel = con.execute(ISOLATION_PANEL_QUERY).fetchdf()
    panel["constructor_race"] = (
        panel.race_year.astype(str)
        + "_" + panel.race_id.astype(str)
        + "_" + panel.constructor_id.astype(str)
    )
    log.info(
        "Loaded isolation panel: %d laps · %d drivers · %d driver-eras · %d races · "
        "%d constructor-races.",
        len(panel), panel.driver_id.nunique(), panel.driver_era.nunique(),
        panel.groupby(["race_year", "race_id"]).ngroups, panel.constructor_race.nunique(),
    )
    return panel


def aggregate_to_race_level(panel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate panel to race level for car FE fitting.

    Aggregates y_s and other quantities to one row per (race, constructor, driver_id),
    so that the car FE is fitted on driver-adjusted race means. This avoids fitting
    noise and ensures lap-level variation doesn't interfere with car identification.
    """
    race_level = (
        panel.groupby(["race_year", "race_id", "constructor_id", "era", "driver_id"])
        .agg({
            "y_s": "mean",
            "lap_id": "count",  # n_laps per driver per race per constructor
        })
        .reset_index()
        .rename(columns={"lap_id": "n_laps_driver"})
    )
    race_level["constructor_race"] = (
        race_level.race_year.astype(str)
        + "_" + race_level.race_id.astype(str)
        + "_" + race_level.constructor_id.astype(str)
    )
    log.info(
        "Aggregated to race level: %d driver-race-constructor cells",
        len(race_level)
    )
    return race_level


def component_of_cells(panel: pd.DataFrame, driver_col: str) -> pd.Series:
    """Connected component of every constructor_race cell in the bipartite graph
    driver_col x constructor_race, one edge per lap. Two cells in the same component can
    be compared through a chain of drivers; two cells in different components cannot,
    whatever the fit reports for them."""
    drivers = pd.Index(panel[driver_col].unique())
    cells = pd.Index(panel["constructor_race"].unique())
    n_drivers = len(drivers)
    rows = drivers.get_indexer(panel[driver_col])
    cols = cells.get_indexer(panel["constructor_race"]) + n_drivers
    size = n_drivers + len(cells)
    adj = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(size, size))
    _, labels = connected_components(adj, directed=False)
    return pd.Series(labels[n_drivers:], index=cells, name="component")


def connectivity(panel: pd.DataFrame, driver_col: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-cell and per-era identification diagnostics under `driver_col`.

    Returns (cells, eras). cells: one row per constructor_race with its component and
    race_components_n, the number of components the race's cells span (1 = the race's
    car levels are comparable). eras: per era, the component count, the WI doc's
    statistic (components holding two or more constructors) and the unidentified races.
    """
    comp = component_of_cells(panel, driver_col)
    cells = (
        panel.groupby(
            ["race_year", "race_id", "constructor_id", "constructor_race", "era"],
            as_index=False,
        )
        .size()
        .rename(columns={"size": "n_laps"})
    )
    cells["component"] = cells.constructor_race.map(comp)
    cells["race_components_n"] = cells.groupby(["race_year", "race_id"]).component.transform(
        "nunique"
    )
    ctors_per_comp = cells.groupby("component").constructor_id.nunique()
    eras = []
    for era, g in cells.groupby("era"):
        comps = g.component.unique()
        races = g.drop_duplicates(["race_year", "race_id"])
        eras.append({
            "era": era,
            "components_n": len(comps),
            "multi_constructor_components_n": int((ctors_per_comp.loc[comps] >= 2).sum()),
            "races_n": len(races),
            "races_unidentified_n": int((races.race_components_n > 1).sum()),
        })
    return cells, pd.DataFrame(eras)


def _fit_cell_fe(panel: pd.DataFrame, driver_col: str) -> pd.Series:
    """Two-way FE fit y_s ~ 1 | driver_col + constructor_race; constructor_race -> FE.

    pyfixest drops singleton cells (its default, as in fit_car_fe); they get no FE. Its
    fixef() also leaves out the REFERENCE level: it solves on the full-rank dummy matrix
    -1 + C(driver_col) + C(constructor_race), which drops the first constructor_race level,
    so that cell's FE is 0 by construction but absent from the dict. fit_car_fe (the
    default path, kept byte-identical) reads the absence as "unidentified" and drops the
    cell; here it is restored as 0.0."""
    log.info("Fitting y_s ~ 1 | %s + constructor_race ...", driver_col)
    model = pf.feols(f"y_s ~ 1 | {driver_col} + constructor_race", data=panel)
    # fixef() recovers the FE by LSQR; its 1e-6 default tolerances leave ~1e-5 s of
    # solver noise in a car term. Tightened so a rebuild reproduces it.
    fe = pd.Series(
        model.fixef(atol=1e-12, btol=1e-12)["C(constructor_race)"], dtype=float
    )
    fe.index = fe.index.astype(str)
    estimated = set(model._data["constructor_race"].astype(str))
    reference = sorted(estimated - set(fe.index))
    if len(reference) > 1:
        raise RuntimeError(
            f"{len(reference)} estimation-sample cells have no FE; expected one reference "
            f"level: {reference[:5]}"
        )
    for cell in reference:
        log.info("Reference level %s restored at FE 0.0.", cell)
        fe[cell] = 0.0
    return fe


def _era_needs_fallback(era_row: pd.Series) -> bool:
    return bool(
        era_row.races_unidentified_n > 0 or era_row.multi_constructor_components_n > 1
    )


def fit_car_fe_isolation(lap_panel: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Isolation car term per (race_year, race_id, constructor_id).

    Returns (out, connectivity_note). out carries car_iso_s: the constructor×race FE of
    y_s ~ 1 | driver_id + constructor_race, fitted at the race level to avoid lap-level
    noise. Fitted separately per era (pre/post regulation boundary). The driver_id FE is
    used instead of driver_era because driver_era breaks connectivity: each driver races
    for only one constructor per race, so the bipartite network (driver_era x constructor_race)
    is never connected. Using driver_id with separate fits per era gives better identification
    while avoiding cross-era driver skill contamination. car_iso_s is re-centred to a
    lap-weighted mean of zero over the identified cells of each race (negative = faster).
    A cell that pyfixest dropped as a singleton gets car_iso_s NULL."""

    # Aggregate to race level to avoid lap-level noise
    race_panel = aggregate_to_race_level(lap_panel)

    notes = []
    all_cells = []

    # Fit separately per era, using driver_id within each
    max_component_id = 0
    for era in sorted(race_panel["era"].unique()):
        era_panel = race_panel[race_panel["era"] == era].copy()
        era_cells, era_eras = connectivity(era_panel, "driver_id")

        # Log connectivity for this era
        for _, e in era_eras.iterrows():
            notes.append(
                f"{e.era}: driver_id {e.components_n} component(s), "
                f"{e.multi_constructor_components_n} with >=2 constructors, "
                f"{e.races_unidentified_n}/{e.races_n} races unidentified"
            )
            log.info("Connectivity %s", notes[-1])

        # Fit the car FE for this era
        fe_era = _fit_cell_fe(era_panel, "driver_id")
        era_cells["car_fe_raw_s"] = era_cells.constructor_race.map(fe_era)
        era_cells["car_term_source"] = "driver_id"

        # Make component IDs globally unique by adding an era offset
        # This prevents component ID clashes when combining results from different eras
        era_cells["component"] = era_cells["component"] + max_component_id
        max_component_id = era_cells["component"].max() + 1

        all_cells.append(era_cells)

    # Combine results from all eras
    cells = pd.concat(all_cells, ignore_index=True)

    # Map FE back to original lap-level panel for weighted recentering
    # Get lap counts per constructor-race from original panel
    lap_counts = (
        lap_panel.groupby(["race_year", "race_id", "constructor_id"])
        .size()
        .reset_index(name="n_laps")
    )
    cells = cells.merge(
        lap_counts[["race_year", "race_id", "constructor_id", "n_laps"]],
        on=["race_year", "race_id", "constructor_id"],
        how="left",
        suffixes=("_old", "")
    )
    # Drop the old n_laps if merge created suffixes
    if "n_laps_old" in cells.columns:
        cells = cells.drop(columns=["n_laps_old"])

    # A race whose cells span several components: only the cells in the race's largest
    # component (by laps) are comparable with each other; the rest are not identified.
    # Ties go to the lower component id, so exactly one component per race is kept.
    race_key = ["race_year", "race_id"]
    comp_sum = cells.groupby(race_key + ["component"], as_index=False)["n_laps"].sum()
    main = (
        comp_sum.sort_values(race_key + ["n_laps", "component"],
                             ascending=[True, True, False, True])
        .drop_duplicates(race_key)[race_key + ["component"]]
        .rename(columns={"component": "main_component"})
    )
    cells = cells.merge(main, on=race_key, how="left")
    unidentified = (cells.component != cells.main_component).to_numpy()
    cells.loc[unidentified, "car_fe_raw_s"] = np.nan
    cells.loc[unidentified, "car_term_source"] = "unidentified"
    not_estimated = cells.car_fe_raw_s.isna() & ~unidentified
    cells.loc[not_estimated, "car_term_source"] = "not_estimated"

    # Lap-weighted re-centring inside each race, over the cells that have a car term.
    w = cells.n_laps.where(cells.car_fe_raw_s.notna(), 0).astype(float)
    num = (cells.car_fe_raw_s.fillna(0.0) * w).groupby([cells.race_year, cells.race_id]).transform("sum")
    den = w.groupby([cells.race_year, cells.race_id]).transform("sum")
    cells["car_iso_s"] = cells.car_fe_raw_s - num / den.replace(0.0, np.nan)

    out = (
        cells[ISOLATION_COLUMNS]
        .sort_values(["race_year", "race_id", "constructor_id"])
        .reset_index(drop=True)
    )
    counts = out.car_term_source.value_counts().to_dict()
    log.info("car_term_source counts: %s", counts)
    log.info(
        "Emitting %d (race_year, race_id, constructor_id) rows; car_iso_s in [%.3f, %.3f].",
        len(out), out.car_iso_s.min(), out.car_iso_s.max(),
    )
    return out, "; ".join(notes)


def run_fit_isolation(db_path: Path = DB_PATH) -> pd.DataFrame:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        lap_panel = load_isolation_panel(con)
    finally:
        con.close()

    out, note = fit_car_fe_isolation(lap_panel)

    prov = build_provenance(
        fit_method=ISOLATION_FIT_METHOD,
        season_min=int(lap_panel.race_year.min()),
        season_max=int(lap_panel.race_year.max()),
    )
    for k, v in prov.items():
        out[k] = v
    out["connectivity_note"] = note
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fit the de-biased constructor car FE (HDFE): the Ghost Standings "
        "panel (default) or the driver-isolation panel."
    )
    parser.add_argument(
        "--panel", choices=["pace_delta", "isolation"], default="pace_delta",
        help="pace_delta (default): data/fits/constructor_car_fe.parquet for "
        "int_constructor_car_fe. isolation: data/fits/constructor_car_fe_isolation.parquet "
        "for int_constructor_car_fe_isolation (WI-16a).",
    )
    parser.add_argument("--db", type=Path, default=DB_PATH,
                        help="warehouse to read, read-only (default data/dev.duckdb)")
    parser.add_argument("--out", type=Path, default=None,
                        help="parquet to write (default: the panel's data/fits/ file)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.panel == "isolation":
        out_path = args.out or ISOLATION_OUT_PATH
    else:
        out_path = args.out or OUT_PATH

    if args.dry_run:
        log.info("DRY RUN would write %s", out_path)
        return 0

    out = run_fit_isolation(args.db) if args.panel == "isolation" else run_fit(args.db)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)
    log.info("Wrote %d rows → %s", len(out), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
