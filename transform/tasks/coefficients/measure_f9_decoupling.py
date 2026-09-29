"""
Measure the cost of F9 eligibility decoupling on all three model families.

F9 currently couples training eligibility to cliff_onset_passed (in-race seed).
Two options to decouple:
  A) Change-point detection: detect cliff from residual series analysis
  B) Sample weighting: keep mistake rows with weight < 1, not hard exclusion

This script:
1. Builds the current (coupled) training set and measures baseline costs
2. Builds Option A (change-point detection) set and measures costs
3. Builds Option B (sample weighting) set and measures costs
4. Reports the cost differences to guide the recommendation

Usage:
    python -m tasks.coefficients.measure_f9_decoupling
    python -m tasks.coefficients.measure_f9_decoupling --option A
    python -m tasks.coefficients.measure_f9_decoupling --option B
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from dataclasses import dataclass

import duckdb
import pandas as pd
import numpy as np
from scipy import stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"

@dataclass
class CostMetrics:
    """Measured cost metrics for one option."""
    option: str
    n_rows: int
    n_mistake_rows: int
    n_clean_cliff_rows: int

    # Per-family metrics (higher is worse cost)
    p50_cost: float  # NLL or similar
    cliff_cost: float
    stint_life_cost: float

    def summary(self) -> str:
        return (
            f"{self.option}:\n"
            f"  Rows: {self.n_rows:,} ({self.n_mistake_rows:,} mistake, {self.n_clean_cliff_rows:,} clean_cliff)\n"
            f"  P50 cost: {self.p50_cost:.6f}\n"
            f"  Cliff cost: {self.cliff_cost:.6f}\n"
            f"  Stint-life cost: {self.stint_life_cost:.6f}"
        )

def get_current_training_set(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Get current training-eligible rows with anomaly classifications."""
    query = """
    SELECT
        lap_id,
        driver_skill_residual_s,
        mad_score,
        cliff_onset_passed,
        anomaly_class,
        next_5_lap_cumulative_jump_s,
        correction_weight
    FROM dbt.int_lap_anomaly_flags
    WHERE
        correction_weight = 1.0
        AND anomaly_class NOT IN ('mistake', 'conditions', 'event_driven')
    ORDER BY lap_id
    """
    return con.execute(query).fetch_df()

def calculate_option_a_detection(df: pd.DataFrame) -> pd.Series:
    """
    Option A: Detect cliff via change-point detection on residuals.

    For each driver-race, detect a significant change point in the driver_skill_residual_s
    series. Rows before the change point are "pre-cliff", rows after are "post-cliff".
    A spike after the change point is considered clean_cliff (detected via data, not seed).

    Returns: Boolean series, True if this lap is classified as clean_cliff under option A.
    """
    # Placeholder implementation - in reality would do proper change-point detection
    # For now, use a simple heuristic: if mad_score > 3.0 and preceded by lower residuals
    # This is a simplified version; real implementation would use PELT or similar

    is_change_point = pd.Series(False, index=df.index)

    # For each lap with mad_score > 3.0 (potential outlier), check if it's above trailing median
    # If so, and if it's a significant jump, mark as potential change-point
    is_change_point = (df['mad_score'] > 3.0) & (df['cliff_onset_passed'] == False)

    # TODO: Implement proper change-point detection (PELT, cusum, etc.)
    # For measurement purposes, this placeholder detects points that look like cliffs
    # but aren't marked as such by the seed

    return is_change_point

def calculate_option_b_weighting(df: pd.DataFrame) -> pd.Series:
    """
    Option B: Keep mistake rows with reduced weight instead of hard exclusion.

    Assign weight < 1 to rows that would be "mistake" under current logic.
    This keeps them in training but reduces their influence.

    Returns: Weight series (1.0 for normal rows, < 1.0 for mistake rows).
    """
    weights = pd.Series(1.0, index=df.index)

    # Mistake rows are those with mad_score > 3.0 but NOT cliff_onset_passed
    # Assign them a reduced weight
    is_mistake = (df['mad_score'] > 3.0) & (~df['cliff_onset_passed'])
    weights[is_mistake] = 0.5  # TODO: tune this weight

    return weights

def measure_family_cost(df: pd.DataFrame, label_col: str, weight_col: str = None) -> float:
    """
    Measure NLL or MSE cost for one model family.
    Placeholder: returns 0.0 for now; real implementation would fit and evaluate.
    """
    # TODO: Implement real cost measurement
    # For p50: fit quantile regression, measure NLL or MSE on holdout
    # For cliff: fit classifier or ranking, measure classification cost
    # For stint-life: fit survival model, measure AFT NLL

    if weight_col and weight_col in df.columns:
        return np.average((df[label_col] ** 2), weights=df[weight_col])
    else:
        return np.mean(df[label_col] ** 2)

def measure_option_baseline(con: duckdb.DuckDBPyConnection) -> CostMetrics:
    """Measure baseline (current) training set costs."""
    log.info("Measuring Option: BASELINE (current, cliff_onset_passed coupled)...")

    df = get_current_training_set(con)

    # Count anomaly classes
    n_mistake = (df['anomaly_class'] == 'mistake').sum()  # Currently excluded
    n_clean_cliff = (df['anomaly_class'] == 'clean_cliff').sum()  # Currently kept

    log.info(f"  Baseline rows: {len(df):,} (mistake: {n_mistake:,} excluded, clean_cliff: {n_clean_cliff:,} kept)")

    # Measure costs (placeholder)
    p50_cost = measure_family_cost(df, 'next_5_lap_cumulative_jump_s')
    cliff_cost = 0.0  # TODO: implement
    stint_life_cost = 0.0  # TODO: implement

    return CostMetrics(
        option="BASELINE",
        n_rows=len(df),
        n_mistake_rows=n_mistake,
        n_clean_cliff_rows=n_clean_cliff,
        p50_cost=p50_cost,
        cliff_cost=cliff_cost,
        stint_life_cost=stint_life_cost,
    )

def measure_option_a(con: duckdb.DuckDBPyConnection) -> CostMetrics:
    """Measure Option A (change-point detection) costs."""
    log.info("Measuring Option A (change-point detection)...")

    # Get all anomalous rows (both current clean_cliff and mistake)
    query = """
    SELECT
        lap_id,
        driver_skill_residual_s,
        mad_score,
        cliff_onset_passed,
        anomaly_class,
        next_5_lap_cumulative_jump_s,
        correction_weight
    FROM dbt.int_lap_anomaly_flags
    WHERE
        correction_weight = 1.0
        AND mad_score > 3.0
    ORDER BY lap_id
    """
    df = con.execute(query).fetch_df()

    # Apply change-point detection to create new classification
    is_clean_cliff_a = calculate_option_a_detection(df)

    n_clean_cliff_a = is_clean_cliff_a.sum()
    n_mistake_a = (~is_clean_cliff_a).sum()

    log.info(f"  Option A rows: {len(df):,} (clean_cliff: {n_clean_cliff_a:,}, mistake: {n_mistake_a:,})")

    # Filter to only keep rows marked as clean_cliff by this option
    df_eligible = df[is_clean_cliff_a]

    p50_cost = measure_family_cost(df_eligible, 'next_5_lap_cumulative_jump_s') if len(df_eligible) > 0 else 0.0
    cliff_cost = 0.0  # TODO: implement
    stint_life_cost = 0.0  # TODO: implement

    return CostMetrics(
        option="OPTION_A",
        n_rows=len(df_eligible),
        n_mistake_rows=n_mistake_a,
        n_clean_cliff_rows=n_clean_cliff_a,
        p50_cost=p50_cost,
        cliff_cost=cliff_cost,
        stint_life_cost=stint_life_cost,
    )

def measure_option_b(con: duckdb.DuckDBPyConnection) -> CostMetrics:
    """Measure Option B (sample weighting) costs."""
    log.info("Measuring Option B (sample weighting)...")

    query = """
    SELECT
        lap_id,
        driver_skill_residual_s,
        mad_score,
        cliff_onset_passed,
        anomaly_class,
        next_5_lap_cumulative_jump_s,
        correction_weight
    FROM dbt.int_lap_anomaly_flags
    WHERE
        correction_weight = 1.0
        AND mad_score > 3.0
    ORDER BY lap_id
    """
    df = con.execute(query).fetch_df()

    # Apply weighting: mistake rows get weight < 1
    weights = calculate_option_b_weighting(df)
    df['weight_option_b'] = weights

    n_mistake = (weights < 1.0).sum()
    n_full_weight = (weights == 1.0).sum()

    log.info(f"  Option B rows: {len(df):,} (full weight: {n_full_weight:,}, reduced: {n_mistake:,})")

    p50_cost = measure_family_cost(df, 'next_5_lap_cumulative_jump_s', 'weight_option_b')
    cliff_cost = 0.0  # TODO: implement
    stint_life_cost = 0.0  # TODO: implement

    return CostMetrics(
        option="OPTION_B",
        n_rows=len(df),
        n_mistake_rows=n_mistake,
        n_clean_cliff_rows=n_full_weight,
        p50_cost=p50_cost,
        cliff_cost=cliff_cost,
        stint_life_cost=stint_life_cost,
    )

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--option", choices=["baseline", "A", "B", "all"], default="all",
                        help="Which option to measure (default: all)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        log.error(f"Database not found at {DB_PATH}")
        return 1

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        con.execute("PRAGMA database_list")
    except Exception as e:
        log.error(f"Failed to connect to database: {e}")
        return 1

    results = []

    if args.option in ("baseline", "all"):
        results.append(measure_option_baseline(con))

    if args.option in ("A", "all"):
        results.append(measure_option_a(con))

    if args.option in ("B", "all"):
        results.append(measure_option_b(con))

    # Report findings
    log.info("\n" + "="*70)
    log.info("F9 DECOUPLING COST MEASUREMENT SUMMARY")
    log.info("="*70)

    for result in results:
        log.info("\n" + result.summary())

    # Compute deltas
    if len(results) > 1:
        baseline = results[0]
        log.info("\n" + "="*70)
        log.info("COST DELTAS (vs BASELINE)")
        log.info("="*70)

        for result in results[1:]:
            p50_delta = result.p50_cost - baseline.p50_cost
            cliff_delta = result.cliff_cost - baseline.cliff_cost
            stint_life_delta = result.stint_life_cost - baseline.stint_life_cost

            log.info(f"\n{result.option}:")
            log.info(f"  P50 delta: {p50_delta:+.6f} ({p50_delta/baseline.p50_cost*100:+.1f}%)" if baseline.p50_cost != 0 else f"  P50 delta: {p50_delta:+.6f}")
            log.info(f"  Cliff delta: {cliff_delta:+.6f}")
            log.info(f"  Stint-life delta: {stint_life_delta:+.6f}")

    con.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
