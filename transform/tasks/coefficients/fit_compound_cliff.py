"""
Fit compound cliff parameters from historical stint data.

Reads from dev.duckdb (dbt-built warehouse). Writes fitted params to
seeds/_pending/compound_cliff_params_pending.csv for human review.

Usage:
    python -m tasks.coefficients.fit_compound_cliff
    python -m tasks.coefficients.fit_compound_cliff --dry-run
    python -m tasks.coefficients.fit_compound_cliff --seasons 2022 2023 2024
    python -m tasks.coefficients.fit_compound_cliff --circuits bahrain_grand_prix

The fitter operates per (circuit_key, compound_code, season) group.
Groups with fewer than MIN_STINTS stints fall back to the cross-season
circuit+compound average, then to compound-class defaults.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from .provenance import build_provenance
from .seed_writer import write_pending
from .survival import (
    build_survival_dataset,
    estimate_cliff_severity,
    estimate_wear_gradient,
    fit_cliff_onset_median,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
SEED_NAME = "compound_cliff_params"

MIN_STINTS = 8

# Compound-class defaults when data is insufficient.
# Values are conservative (later onset, milder severity) to avoid overcorrecting.
COMPOUND_DEFAULTS = {
    "SOFT":         {"cliff_onset_laps": 22, "cliff_severity": 2.0, "wear_gradient": 0.070, "grip_peak": 1.03},
    "MEDIUM":       {"cliff_onset_laps": 33, "cliff_severity": 1.6, "wear_gradient": 0.040, "grip_peak": 1.00},
    "HARD":         {"cliff_onset_laps": 50, "cliff_severity": 1.2, "wear_gradient": 0.022, "grip_peak": 0.97},
    "INTERMEDIATE": {"cliff_onset_laps": 25, "cliff_severity": 1.5, "wear_gradient": 0.055, "grip_peak": 0.98},
    "WET":          {"cliff_onset_laps": 20, "cliff_severity": 1.8, "wear_gradient": 0.080, "grip_peak": 0.95},
}

OPTIMAL_TEMP_RANGES = {
    "SOFT":         (82, 108),
    "MEDIUM":       (78, 105),
    "HARD":         (76, 108),
    "INTERMEDIATE": (15,  50),
    "WET":          (10,  40),
}


def load_stint_data(con: duckdb.DuckDBPyConnection, seasons: list[int]) -> pd.DataFrame:
    """
    Build the per-lap stint dataset from dev.duckdb.

    Joins int_stint_geometry + stg_laps + stg_weather + stg_events.
    Filters to dry, valid, non-SC laps on slick compounds.
    """
    season_filter = ", ".join(str(s) for s in seasons)
    query = f"""
        SELECT
            sg.stint_id,
            sg.lap_id,
            sg.race_year,
            sg.race_id,
            sg.driver_id,
            sg.lap_in_stint,
            sg.age_in_stint,
            -- compound_code in int_stint_geometry is NULL; source from stg_laps
            l.compound                          AS compound_code,
            sg.stint_length_actual,
            -- stg_laps.circuit_key is the numeric race_id; resolve to friendly name via race_to_track
            COALESCE(rtt.track_id, l.circuit_key) AS circuit_key,
            l.lap_time_s,
            l.is_valid_lap,
            l.is_safety_car_lap,
            l.is_vsc_lap,
            l.is_pit_lap,
            COALESCE(w.track_temp_c, 30.0)     AS track_temp_c,
            COALESCE(w.rainfall_flag, FALSE)    AS rainfall_flag,
            -- A forced stop is a DNF or retirement (driver didn't choose to pit)
            COALESCE(
                (SELECT TRUE FROM stg_events e
                 WHERE e.driver_id = sg.driver_id
                   AND e.race_id = sg.race_id
                   AND e.event_type = 'DNF'
                 LIMIT 1),
                FALSE
            ) AS forced_stop_flag
        FROM int_stint_geometry sg
        JOIN stg_laps l ON sg.lap_id = l.lap_id
        LEFT JOIN stg_weather w ON sg.lap_id = w.lap_id
        LEFT JOIN race_to_track rtt
          ON CAST(SPLIT_PART(l.race_id, '_', 1) AS INTEGER) * 100
           + CAST(SPLIT_PART(l.race_id, '_', 2) AS INTEGER) = rtt.race_id
        WHERE sg.race_year IN ({season_filter})
          AND l.compound IN ('SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET')
          AND l.is_valid_lap = TRUE
          AND l.is_safety_car_lap = FALSE
          AND l.is_vsc_lap = FALSE
          AND l.is_pit_lap = FALSE
          AND l.lap_time_s > 0
          AND l.lap_time_s < 200
    """
    log.info("Loading stint lap data for seasons %s...", seasons)
    df = con.execute(query).df()
    log.info("Loaded %d lap rows from %d stints", len(df), df["stint_id"].nunique())
    return df


def fit_group(
    stints_df: pd.DataFrame,
    circuit_key: str,
    compound_code: str,
    season: int,
    fallback_df: pd.DataFrame | None = None,
) -> dict:
    """
    Fit cliff parameters for a single (circuit_key, compound_code, season) group.

    Falls back to cross-season circuit+compound average, then to compound defaults.
    Returns a result dict with all columns needed for the seed CSV.
    """
    defaults = COMPOUND_DEFAULTS.get(compound_code, COMPOUND_DEFAULTS["MEDIUM"])
    opt_temp_low, opt_temp_high = OPTIMAL_TEMP_RANGES.get(compound_code, (78, 108))

    group_df = stints_df[
        (stints_df["circuit_key"] == circuit_key) &
        (stints_df["compound_code"] == compound_code) &
        (stints_df["race_year"] == season)
    ]

    survival_df = build_survival_dataset(group_df) if len(group_df) > 0 else pd.DataFrame()
    n_stints = len(survival_df)
    fit_notes = ""

    if n_stints >= MIN_STINTS:
        cliff_onset = fit_cliff_onset_median(survival_df)
        cliff_severity = estimate_cliff_severity(group_df, cliff_onset or defaults["cliff_onset_laps"])
        wear_gradient = estimate_wear_gradient(group_df, cliff_onset or defaults["cliff_onset_laps"])
        source = "cox_km_survival"
    elif fallback_df is not None and len(fallback_df) >= MIN_STINTS:
        # Cross-season fallback: all seasons for this circuit+compound
        cross_survival = build_survival_dataset(fallback_df)
        cliff_onset = fit_cliff_onset_median(cross_survival)
        cliff_severity = estimate_cliff_severity(fallback_df, cliff_onset or defaults["cliff_onset_laps"])
        wear_gradient = estimate_wear_gradient(fallback_df, cliff_onset or defaults["cliff_onset_laps"])
        source = "cross_season_fallback"
        fit_notes = f"insufficient season stints ({n_stints}); used {len(cross_survival)} cross-season stints"
        log.warning(
            "%s / %s / %d: only %d stints, falling back to cross-season (%s)",
            circuit_key, compound_code, season, n_stints, fit_notes,
        )
    else:
        cliff_onset = None
        cliff_severity = None
        wear_gradient = None
        source = "compound_class_default"
        fit_notes = f"insufficient data ({n_stints} stints); used class defaults"
        log.warning(
            "%s / %s / %d: using class defaults (%s)",
            circuit_key, compound_code, season, fit_notes,
        )

    # Clamp to physically plausible ranges   survival/regression can produce
    # outliers for thin groups; fall back to defaults when out of range.
    onset_val = float(cliff_onset or defaults["cliff_onset_laps"])
    onset_val = max(5.0, min(100.0, onset_val))

    severity_val = float(cliff_severity or defaults["cliff_severity"])
    if severity_val < 0.1 or severity_val > 8.0:
        severity_val = defaults["cliff_severity"]

    gradient_val = float(wear_gradient or defaults["wear_gradient"])
    if gradient_val < 0.005 or gradient_val > 0.300:
        gradient_val = defaults["wear_gradient"]

    return {
        "circuit_key": circuit_key,
        "compound_code": compound_code,
        "season": season,
        "compound_grip_peak": defaults["grip_peak"],
        "compound_wear_gradient": round(gradient_val, 4),
        "compound_optimal_temp_low": opt_temp_low,
        "compound_optimal_temp_high": opt_temp_high,
        "compound_cliff_onset_laps": round(onset_val, 1),
        "compound_cliff_severity": round(severity_val, 2),
        "fit_source": source,
        "n_stints": n_stints,
        "notes": fit_notes or f"fitted from {n_stints} stints via {source}",
    }


def run_fit(
    seasons: list[int],
    circuits: list[str] | None,
    dry_run: bool,
) -> pd.DataFrame:
    log.info("Connecting to %s", DB_PATH)
    con = duckdb.connect(str(DB_PATH), read_only=True)

    stints_df = load_stint_data(con, seasons)

    if circuits:
        stints_df = stints_df[stints_df["circuit_key"].isin(circuits)]
        log.info("Filtered to %d circuits: %s", len(circuits), circuits)

    groups = (
        stints_df.groupby(["circuit_key", "compound_code", "race_year"])
        .size()
        .reset_index(name="n_laps")
    )
    log.info("Fitting %d circuit/compound/season groups...", len(groups))

    results = []
    for _, row in groups.iterrows():
        circuit_key = row["circuit_key"]
        compound_code = row["compound_code"]
        season = int(row["race_year"])

        # Cross-season data for this circuit+compound (fallback pool)
        cross_df = stints_df[
            (stints_df["circuit_key"] == circuit_key) &
            (stints_df["compound_code"] == compound_code)
        ]

        result = fit_group(stints_df, circuit_key, compound_code, season, fallback_df=cross_df)
        results.append(result)
        log.info(
            "  %-35s %-12s %d  onset=%.1f  severity=%.2f  gradient=%.4f  [%s]",
            circuit_key, compound_code, season,
            result["compound_cliff_onset_laps"],
            result["compound_cliff_severity"],
            result["compound_wear_gradient"],
            result["fit_source"],
        )

    out_df = pd.DataFrame(results)

    prov = build_provenance(
        fit_method="km_survival_v1",
        season_min=min(seasons),
        season_max=max(seasons),
    )
    for k, v in prov.items():
        out_df[k] = v

    # Reorder columns to match the existing seed schema
    col_order = [
        "circuit_key", "compound_code", "season",
        "compound_grip_peak", "compound_wear_gradient",
        "compound_optimal_temp_low", "compound_optimal_temp_high",
        "compound_cliff_onset_laps", "compound_cliff_severity",
        "fit_date", "data_window", "fit_method", "git_sha", "fit_timestamp",
        "fit_source", "n_stints", "notes",
    ]
    out_df = out_df[[c for c in col_order if c in out_df.columns]]
    out_df = out_df.sort_values(["circuit_key", "compound_code", "season"])

    return out_df


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit compound cliff parameters from F1 stint data.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing output.")
    parser.add_argument(
        "--seasons", nargs="+", type=int,
        default=list(range(2018, 2025)),
        help="Seasons to fit (default: 2018-2024).",
    )
    parser.add_argument(
        "--circuits", nargs="+", default=None,
        help="Limit fit to these circuit_keys (default: all).",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        log.info("DRY RUN   will connect to duckdb and show plan without writing output.")
        log.info("Seasons: %s", args.seasons)
        log.info("Circuits: %s", args.circuits or "all")
        con = duckdb.connect(str(DB_PATH), read_only=True)
        stints_df = load_stint_data(con, args.seasons)
        if args.circuits:
            stints_df = stints_df[stints_df["circuit_key"].isin(args.circuits)]
        groups = stints_df.groupby(["circuit_key", "compound_code", "race_year"]).size()
        log.info("Would fit %d groups across %d unique circuits.", len(groups), stints_df["circuit_key"].nunique())
        log.info("Output: seeds/_pending/%s_pending.csv", SEED_NAME)
        return 0

    out_df = run_fit(
        seasons=args.seasons,
        circuits=args.circuits,
        dry_run=args.dry_run,
    )

    write_pending(out_df, SEED_NAME)
    log.info("Done. Pending seed written. Review then run: make coefficients-promote")
    return 0


if __name__ == "__main__":
    sys.exit(main())
