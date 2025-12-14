"""
Calibrate per-circuit weight_penalty_factor from first-stint clean laps.

The weight penalty captures the lap-time improvement as fuel burns off.
The formula-based prior in circuit_reference.csv is:
    weight_penalty_factor = 0.02 + 0.0002 * corner_count * avg_lateral_g

This fitter calibrates it empirically by regressing pace residual against
lap_number in clean first stints, after deconvolving compound wear using
fitted cliff params from fit_compound_cliff.

Usage:
    python -m tasks.coefficients.fit_weight_penalty
    python -m tasks.coefficients.fit_weight_penalty --dry-run
    python -m tasks.coefficients.fit_weight_penalty --circuits bahrain_grand_prix

Output: seeds/_pending/circuit_reference_pending.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd
from scipy import stats  # type: ignore

from .provenance import build_provenance
from .seed_writer import write_pending

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
SEED_NAME = "circuit_reference"

# Maximum deviation from formula prior before flagging for manual review
PRIOR_DEVIATION_THRESHOLD = 0.30

# Min laps across all first stints for a circuit to attempt calibration
MIN_CALIBRATION_LAPS = 40


def load_calibration_data(
    con: duckdb.DuckDBPyConnection,
    seasons: list[int],
    circuits: list[str] | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (lap_df, circuit_ref_df) for calibration."""
    season_filter = ", ".join(str(s) for s in seasons)
    circuit_filter = (
        f"AND rtt.track_id IN ({', '.join(repr(c) for c in circuits)})"
        if circuits else ""
    )

    query = f"""
        SELECT
            sg.stint_id,
            -- stg_laps.circuit_key is numeric; resolve via race_to_track
            COALESCE(rtt.track_id, l.circuit_key) AS circuit_key,
            l.race_year,
            l.race_id,
            l.driver_id,
            sg.lap_in_stint,
            sg.age_in_stint,
            l.compound                          AS compound_code,
            sg.stint_number,
            l.lap_number,
            l.lap_time_s,
            l.is_valid_lap,
            l.is_safety_car_lap,
            l.is_vsc_lap,
            l.is_pit_lap,
            COALESCE(w.rainfall_flag, FALSE) AS rainfall_flag,
            COALESCE(w.track_temp_c, 30.0)  AS track_temp_c,
            -- expected compound wear pace (from fitted int model)
            icp.expected_compound_pace_s
        FROM int_stint_geometry sg
        JOIN stg_laps l ON sg.lap_id = l.lap_id
        LEFT JOIN stg_weather w ON sg.lap_id = w.lap_id
        LEFT JOIN int_compound_cliff_predicted icp ON sg.lap_id = icp.lap_id
        LEFT JOIN race_to_track rtt
          ON CAST(SPLIT_PART(l.race_id, '_', 1) AS INTEGER) * 100
           + CAST(SPLIT_PART(l.race_id, '_', 2) AS INTEGER) = rtt.race_id
        WHERE l.race_year IN ({season_filter})
          {circuit_filter}
          AND sg.stint_number = 1
          AND sg.lap_in_stint <= 5
          AND l.compound IN ('SOFT', 'MEDIUM', 'HARD')
          AND l.is_valid_lap = TRUE
          AND l.is_safety_car_lap = FALSE
          AND l.is_vsc_lap = FALSE
          AND l.is_pit_lap = FALSE
          AND COALESCE(w.rainfall_flag, FALSE) = FALSE
          AND l.lap_time_s > 0
    """
    log.info("Loading first-stint calibration laps...")
    lap_df = con.execute(query).df()
    log.info("Loaded %d calibration laps across %d circuits.", len(lap_df), lap_df["circuit_key"].nunique())

    circuit_ref = con.execute("SELECT * FROM circuit_reference").df()
    return lap_df, circuit_ref


def calibrate_circuit(
    lap_df: pd.DataFrame,
    circuit_key: str,
    prior_wpf: float,
    fuel_rate: float,
) -> dict:
    """
    Fit weight_penalty_factor for one circuit.

    Strategy: regress (lap_time-expected_compound_pace) ~ lap_number.
    The slope is pace improvement per lap. Dividing by fuel_rate gives s/kg.
    """
    circuit_laps = lap_df[lap_df["circuit_key"] == circuit_key].copy()
    n_laps = len(circuit_laps)

    if n_laps < MIN_CALIBRATION_LAPS:
        log.warning(
            "%s: only %d laps, below minimum %d   retaining prior %.4f",
            circuit_key, n_laps, MIN_CALIBRATION_LAPS, prior_wpf,
        )
        return {
            "circuit_key": circuit_key,
            "weight_penalty_factor": prior_wpf,
            "calibration_source": "prior_insufficient_data",
            "n_calibration_laps": n_laps,
            "prior_weight_penalty_factor": prior_wpf,
            "calibration_delta_pct": 0.0,
            "calibration_flag": "INSUFFICIENT_DATA",
        }

    # Pace residual after removing compound contribution
    circuit_laps["pace_residual"] = (
        circuit_laps["lap_time_s"]-circuit_laps["expected_compound_pace_s"].fillna(0)
    )

    # Winsorise top/bottom 5% to reduce outlier influence
    p5 = circuit_laps["pace_residual"].quantile(0.05)
    p95 = circuit_laps["pace_residual"].quantile(0.95)
    clean = circuit_laps[circuit_laps["pace_residual"].between(p5, p95)]

    result = stats.linregress(
        clean["lap_number"].values,
        clean["pace_residual"].values,
    )

    # slope is s/lap; negate because pace improves (time decreases) as fuel burns
    # fuel_rate converts: (s/lap) / (kg/lap) = s/kg
    measured_wpf = max(-result.slope / fuel_rate, 0.005)

    delta_pct = abs(measured_wpf-prior_wpf) / prior_wpf
    flag = "OK"
    if delta_pct > PRIOR_DEVIATION_THRESHOLD:
        flag = "REVIEW_REQUIRED"
        log.warning(
            "%s: measured WPF %.4f deviates %.0f%% from prior %.4f   flag for review",
            circuit_key, measured_wpf, delta_pct * 100, prior_wpf,
        )
    else:
        log.info(
            "%s: WPF %.4f (prior %.4f, delta %.1f%%, r²=%.3f, n=%d)",
            circuit_key, measured_wpf, prior_wpf, delta_pct * 100,
            result.rvalue ** 2, len(clean),
        )

    # Use prior when measured deviates too far   regression is weak without
    # compound-wear deconvolution, so large deviations are noise not signal.
    adopted_wpf = prior_wpf if flag == "REVIEW_REQUIRED" else measured_wpf

    return {
        "circuit_key": circuit_key,
        "weight_penalty_factor": round(adopted_wpf, 5),
        "measured_weight_penalty_factor": round(measured_wpf, 5),
        "calibration_source": "first_stint_regression",
        "n_calibration_laps": n_laps,
        "prior_weight_penalty_factor": prior_wpf,
        "calibration_delta_pct": round(delta_pct * 100, 1),
        "calibration_flag": flag,
    }


def run_fit(
    seasons: list[int],
    circuits: list[str] | None,
) -> pd.DataFrame:
    log.info("Connecting to %s", DB_PATH)
    con = duckdb.connect(str(DB_PATH), read_only=True)

    lap_df, circuit_ref = load_calibration_data(con, seasons, circuits)

    results = []
    for _, ref_row in circuit_ref.iterrows():
        ckey = ref_row["circuit_key"]
        if circuits and ckey not in circuits:
            results.append({
                **ref_row.to_dict(),
                "weight_penalty_factor": ref_row["weight_penalty_factor"],
                "measured_weight_penalty_factor": ref_row["weight_penalty_factor"],
                "calibration_source": "not_calibrated",
                "n_calibration_laps": 0,
                "prior_weight_penalty_factor": ref_row["weight_penalty_factor"],
                "calibration_delta_pct": 0.0,
                "calibration_flag": "SKIPPED",
            })
            continue

        cal = calibrate_circuit(
            lap_df=lap_df,
            circuit_key=ckey,
            prior_wpf=float(ref_row["weight_penalty_factor"]),
            fuel_rate=float(ref_row["fuel_consumption_rate_kg_per_lap"]),
        )
        merged = {**ref_row.to_dict(), **cal}
        results.append(merged)

    out_df = pd.DataFrame(results)

    prov = build_provenance(
        fit_method="first_stint_regression_v1",
        season_min=min(seasons),
        season_max=max(seasons),
    )
    for k, v in prov.items():
        out_df[k] = v

    return out_df.sort_values("circuit_key")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate per-circuit weight penalty factors.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--seasons", nargs="+", type=int, default=list(range(2018, 2025)))
    parser.add_argument("--circuits", nargs="+", default=None)
    args = parser.parse_args(argv)

    if args.dry_run:
        log.info("DRY RUN   seasons: %s, circuits: %s", args.seasons, args.circuits or "all")
        log.info("Output would be: seeds/_pending/%s_pending.csv", SEED_NAME)
        return 0

    out_df = run_fit(seasons=args.seasons, circuits=args.circuits)

    review_rows = out_df[out_df["calibration_flag"] == "REVIEW_REQUIRED"]
    if len(review_rows) > 0:
        log.warning(
            "%d circuits require manual review (deviation > %d%%)   prior retained:",
            len(review_rows), int(PRIOR_DEVIATION_THRESHOLD * 100),
        )
        for _, r in review_rows.iterrows():
            log.warning(
                "  %-35s measured=%.4f  adopted(prior)=%.4f  delta=%.1f%%",
                r["circuit_key"], r["measured_weight_penalty_factor"],
                r["weight_penalty_factor"], r["calibration_delta_pct"],
            )

    write_pending(out_df, SEED_NAME)
    log.info("Done. Review seeds/_pending/%s_pending.csv then run: make coefficients-promote", SEED_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
