"""WI-12 panel build: 06b's lap and corner panels, rebuilt on the WI-01 label.

Read-only against the warehouse. Three lap panels:

  wi01    -- the headline. int_dirty_air_tax_component's `calibration_panel` after WI-01,
             reproduced exactly: measured base only (INNER JOIN, smoothed value non-NULL),
             y = lap - base - fuel - the lap's own tyre cost, correction_weight = 1, dry,
             race_year <= theta_air_fit_season_max (2025). Plus the 06b design columns
             (stint, lap_in_stint, age bin, lead, boundary proximity) and two extra
             columns for the estimator comparison (compound and constructor terms).
             GATE: row count equals the shipped calibration_sample_n, the shipped
             theta_air equals the declared theta_air_label_value (the model applies the
             var since W40), and the panel's pooled OLS slope equals the value the model
             fitted on this panel before W40 (0.5033413666, a theta-independent
             fingerprint of the panel's y and x) to 1e-9, or the script stops.
             Before W40 the gate compared the pooled slope with the shipped theta_air
             directly, because the model shipped that slope.
  as06b_now    -- 06b's own PANEL_SQL, imported verbatim, run on the current warehouse
             (old estimator, new substrate: fabricated base via COALESCE, fuel only).
  as06b_0925 -- the same SQL on the pre-WI-15a, pre-WI-01 warehouse kept as WI-15a's
             evidence (dev_unfixed.duckdb, 2026-09-25). An intermediate arm only: it is NOT
             06b's substrate (WI-02a, WI-05, WI-09 and WI-13 had landed), so it does not
             reproduce 06b's table. The reproduction gate uses 06b's committed panel
             (implementations/06b/panel_06b_lap.parquet), in d2.

One corner panel: 06b's CORNER_SQL (verbatim) joined to the wi01 lap treatment.

Run from the repo root:
  ./.venv/bin/python _roadmap/_fixes/_evidence/wi-12-2026-09-27/d1_build_panels_wi12.py
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DB_NOW = REPO / "data/dev.duckdb"
DB_BEFORE = REPO / "_roadmap/_fixes/_evidence/wi-15a-2026-09-25/dev_unfixed.duckdb"
SCRATCH = Path(os.environ.get("WI12_SCRATCH", HERE))

_spec = importlib.util.spec_from_file_location(
    "d1_06b", REPO / "_roadmap/_improvements/implementations/06b/d1_build_panels_06b.py")
d1_06b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(d1_06b)

THETA_FIT_SEASON_MAX = 2025  # dbt_project.yml theta_air_fit_season_max
# The pooled OLS slope int_dirty_air_tax_component fitted on this panel before W40, when
# it shipped that slope as theta_air. The panel's y (lap - base - fuel - tyre cost) and x
# (the lagged bit) are upstream of theta, so this is a fingerprint of the panel itself
# and does not move when the declared theta does.
PANEL_POOLED_FINGERPRINT = 0.5033413665508061


def declared_theta() -> float:
    """theta_air_label_value from dbt_project.yml (the value the model applies)."""
    m = re.search(r"^\s*theta_air_label_value:\s*([0-9.]+)\s*$",
                  (REPO / "transform/dbt_project.yml").read_text(), re.M)
    if not m:
        sys.exit("theta_air_label_value not found in transform/dbt_project.yml")
    return float(m.group(1))

# int_dirty_air_tax_component (WI-01) calibration_panel, with the 06b design columns.
# Every join and filter below is the model's; the only additions are output columns.
WI01_PANEL_SQL = f"""
WITH fuel AS (
    SELECT lap_id, stint_id, race_year, race_id, driver_id, lap_number, lap_time_s,
           weight_penalty_s AS fuel_component_s
    FROM int_lap_fuel_state
),
field_pace AS (
    SELECT race_year, race_id, lap_number, field_pace_smoothed_s FROM int_field_pace_curve
),
compound AS (
    SELECT lap_id, expected_compound_pace_s AS compound_component_s
    FROM int_compound_cliff_predicted
),
geom AS (
    SELECT lap_id, stint_id, race_year, race_id, driver_id, lap_number, lap_in_stint,
           is_valid_lap, is_pit_lap, is_safety_car_lap, is_vsc_lap, is_red_flag_lap
    FROM int_stint_geometry
),
air_state AS (
    SELECT lap_id, dirty_air_share_lap, air_state_dominant FROM int_lap_air_state
),
full_sequence AS (
    SELECT g.lap_id,
           LAG(COALESCE(a.dirty_air_share_lap, 0.0), 1, 0.0)
               OVER (PARTITION BY g.stint_id ORDER BY g.lap_in_stint)  AS d_lag1,
           LEAD(COALESCE(a.dirty_air_share_lap, 0.0), 1, 0.0)
               OVER (PARTITION BY g.stint_id ORDER BY g.lap_in_stint)  AS d_lead1,
           COALESCE(a.dirty_air_share_lap, 0.0)                        AS d_now,
           MAX(CASE WHEN g.is_safety_car_lap OR g.is_vsc_lap
                          OR g.is_red_flag_lap OR g.is_pit_lap
                    THEN 1 ELSE 0 END)
               OVER (PARTITION BY g.stint_id ORDER BY g.lap_in_stint
                     ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING)         AS near_boundary
    FROM geom AS g
    LEFT JOIN air_state AS a ON g.lap_id = a.lap_id
),
panel_base AS (
    SELECT f.lap_id, g.stint_id, f.race_year, f.race_id, f.driver_id, f.lap_number,
           g.lap_in_stint,
           (f.lap_time_s - fp.field_pace_smoothed_s) - f.fuel_component_s
               - cc.compound_component_s                               AS partial_residual_s,
           (f.lap_time_s - fp.field_pace_smoothed_s) - f.fuel_component_s
                                                                       AS y_fuel_only_s,
           cc.compound_component_s,
           fs.d_lag1, fs.d_lead1, fs.d_now, fs.near_boundary,
           a.air_state_dominant,
           c.correction_weight, e.rainfall_flag
    FROM fuel AS f
    INNER JOIN geom AS g ON f.lap_id = g.lap_id
    INNER JOIN full_sequence AS fs ON f.lap_id = fs.lap_id
    INNER JOIN field_pace AS fp
        ON f.race_year = fp.race_year AND f.race_id = fp.race_id
       AND f.lap_number = fp.lap_number
    LEFT JOIN compound AS cc ON f.lap_id = cc.lap_id
    LEFT JOIN air_state AS a ON f.lap_id = a.lap_id
    LEFT JOIN int_event_corrections AS c ON f.lap_id = c.lap_id
    LEFT JOIN int_track_evolution AS e
        ON f.race_year = e.race_year AND f.race_id = e.race_id
       AND f.lap_number = e.lap_number
    WHERE f.lap_time_s IS NOT NULL
      AND fp.field_pace_smoothed_s IS NOT NULL
)
SELECT p.*,
       r.constructor_id,
       r.constructor_component_s,
       CASE WHEN p.lap_in_stint <= 5 THEN 'a01_05'
            WHEN p.lap_in_stint <= 10 THEN 'b06_10'
            WHEN p.lap_in_stint <= 15 THEN 'c11_15'
            WHEN p.lap_in_stint <= 20 THEN 'd16_20'
            WHEN p.lap_in_stint <= 25 THEN 'e21_25'
            ELSE 'f26_plus' END                                        AS age_bin,
       p.driver_id || '|' || p.race_id                                 AS driver_race
FROM panel_base AS p
LEFT JOIN int_lap_residual_decomposed AS r ON p.lap_id = r.lap_id
WHERE p.partial_residual_s IS NOT NULL
  AND COALESCE(p.correction_weight, 1.0) = 1.0
  AND COALESCE(p.rainfall_flag, FALSE) = FALSE
  AND p.race_year <= {THETA_FIT_SEASON_MAX}
"""


def _cd_transform(fn):
    """Some views read parquet by a path relative to transform/; run from there."""
    root = os.getcwd()
    os.chdir(REPO / "transform")
    try:
        return fn()
    finally:
        os.chdir(root)


def build_wi01() -> pd.DataFrame:
    con = duckdb.connect(str(DB_NOW), read_only=True)
    lap = _cd_transform(lambda: con.execute(WI01_PANEL_SQL).df())
    shipped = con.execute(
        """SELECT DISTINCT theta_air_n, theta FROM (
             SELECT ROUND(500.0 * tax_calibration_confidence
                          / (1.0 - tax_calibration_confidence)) AS theta_air_n,
                    dirty_air_tax_s / dirty_air_intensity_lag1 AS theta
             FROM int_dirty_air_tax_component
             WHERE dirty_air_intensity_lag1 > 0 AND dirty_air_tax_s BETWEEN 0 AND 5)"""
    ).df()
    con.close()
    assert len(shipped) == 1, shipped
    n_ship = int(shipped["theta_air_n"].iloc[0])
    th_ship = float(shipped["theta"].iloc[0])
    x, y = lap["d_lag1"], lap["partial_residual_s"]
    th_mine = float(((x - x.mean()) * (y - y.mean())).mean() / x.var(ddof=0))
    th_decl = declared_theta()
    print(f"wi01 panel: {len(lap):,} rows (shipped calibration n {n_ship:,}); "
          f"pooled slope {th_mine:.10f} (pre-W40 fingerprint {PANEL_POOLED_FINGERPRINT:.10f}, "
          f"|d| {abs(th_mine - PANEL_POOLED_FINGERPRINT):.2e})")
    print(f"  shipped theta_air {th_ship:.10f}, declared theta_air_label_value {th_decl} "
          f"(|d| {abs(th_ship - th_decl):.2e})")
    print(f"  constructor term present on {lap['constructor_component_s'].notna().mean():.4%} of rows")
    if (len(lap) != n_ship or abs(th_mine - PANEL_POOLED_FINGERPRINT) > 1e-9
            or abs(th_ship - th_decl) > 1e-9):
        sys.exit("GATE 1 FAILED: the wi01 panel does not reproduce the shipped calibration panel, "
                 "or the model does not apply the declared theta_air_label_value")
    print("  GATE 1 PASS: row count and pooled-slope fingerprint reproduce the shipped "
          "calibration panel; the model applies the declared theta_air")
    return lap


def build_as06b(db: Path, tag: str) -> pd.DataFrame:
    con = duckdb.connect(str(db), read_only=True)
    lap = _cd_transform(lambda: con.execute(d1_06b.PANEL_SQL).df())
    base = con.execute(
        """SELECT f.lap_id, fp.field_pace_smoothed_s IS NULL AS base_null
           FROM int_lap_fuel_state f LEFT JOIN int_field_pace_curve fp
             ON f.race_year = fp.race_year AND f.race_id = fp.race_id
            AND f.lap_number = fp.lap_number""").df()
    con.close()
    lap = lap[lap["partial_residual_s"].notna()].merge(base, on="lap_id", how="left")
    print(f"{tag}: {len(lap):,} rows, fabricated-base rows {int(lap['base_null'].sum()):,}")
    return lap


def build_corner(lap: pd.DataFrame) -> pd.DataFrame:
    con = duckdb.connect(str(DB_NOW), read_only=True)
    corner = _cd_transform(lambda: con.execute(d1_06b.CORNER_SQL).df())
    con.close()
    keep = ["lap_id", "stint_id", "lap_in_stint", "age_bin", "d_lag1", "d_lead1",
            "near_boundary"]
    corner = corner.merge(lap[keep], on="lap_id", how="inner")
    print(f"corner panel joined to wi01 treatment: {len(corner):,} rows")
    return corner


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    wi01 = build_wi01()
    wi01.to_parquet(HERE / "panel_wi12_lap_wi01.parquet", index=False)
    build_as06b(DB_NOW, "as06b_now").to_parquet(
        HERE / "panel_wi12_lap_as06b_now.parquet", index=False)
    build_as06b(DB_BEFORE, "as06b_0925").to_parquet(
        HERE / "panel_wi12_lap_as06b_0925.parquet", index=False)
    build_corner(wi01).to_parquet(SCRATCH / "panel_wi12_corner.parquet", index=False)
    print(f"\nwrote lap panels to {HERE}, corner panel to {SCRATCH}")


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    main()
