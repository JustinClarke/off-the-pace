"""
Assess F9 eligibility decoupling options without full retraining.

This script provides guidance for choosing between:
  A) Change-point detection: detect cliff from residual series analysis
  B) Sample weighting: keep mistake rows with reduced weight

The assessment is based on:
1. Population sizes and compositions
2. Statistical properties of rows in each category
3. Principled analysis of pros/cons
4. Historical precedent in the codebase

Usage:
    python -m tasks.coefficients.assess_f9_options
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from collections import defaultdict

import duckdb
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"

def assess_current_state(con: duckdb.DuckDBPyConnection) -> dict:
    """Assess the current (coupled) state."""
    log.info("Assessing CURRENT STATE (cliff_onset_passed coupled)...")

    query = """
    WITH eligible AS (
        SELECT
            lap_id,
            driver_skill_residual_s,
            mad_score,
            cliff_onset_passed,
            anomaly_class,
            correction_weight
        FROM int_lap_anomaly_flags
        WHERE correction_weight = 1.0
    )
    SELECT
        COUNT(*) as total_rows,
        SUM(CASE WHEN mad_score > 3.0 THEN 1 ELSE 0 END) as anomalous_rows,
        SUM(CASE WHEN anomaly_class = 'clean_cliff' THEN 1 ELSE 0 END) as clean_cliff_rows,
        SUM(CASE WHEN anomaly_class = 'mistake' THEN 1 ELSE 0 END) as mistake_rows_excluded,
        SUM(CASE WHEN anomaly_class = 'normal' THEN 1 ELSE 0 END) as normal_rows,
        -- Rows that are anomalous but would be in training (clean_cliff + normal)
        SUM(CASE WHEN anomaly_class IN ('clean_cliff', 'normal') THEN 1 ELSE 0 END) as in_training,
        -- Rows training-eligible (not anomalous, no conditions, no events)
        SUM(CASE WHEN anomaly_class NOT IN ('mistake', 'conditions', 'event_driven') THEN 1 ELSE 0 END) as final_training_count,
        AVG(driver_skill_residual_s) as mean_residual,
        STDDEV(driver_skill_residual_s) as stddev_residual
    FROM eligible
    """

    result = con.execute(query).fetchall()[0]

    stats = {
        'total_rows': result[0],
        'anomalous_rows': result[1],
        'clean_cliff': result[2],
        'mistake_excluded': result[3],
        'normal': result[4],
        'in_training': result[5],
        'final_training': result[6],
        'mean_residual': result[7],
        'stddev_residual': result[8],
    }

    log.info(f"  Total rows: {stats['total_rows']:,}")
    log.info(f"  Anomalous (mad_score > 3.0): {stats['anomalous_rows']:,}")
    log.info(f"    - clean_cliff (kept): {stats['clean_cliff']:,}")
    log.info(f"    - mistake (excluded): {stats['mistake_excluded']:,}")
    log.info(f"  Normal: {stats['normal']:,}")
    log.info(f"  Final training: {stats['final_training']:,}")
    log.info(f"  Mean residual: {stats['mean_residual']:.4f} s")

    return stats

def assess_mistake_rows(con: duckdb.DuckDBPyConnection) -> dict:
    """Analyze properties of mistake rows to guide weighting."""
    log.info("\nAnalyzing MISTAKE ROWS for Option B (sample weighting)...")

    query = """
    WITH mistake_rows AS (
        SELECT
            driver_skill_residual_s,
            next_5_lap_cumulative_jump_s as label_5lap,
            cliff_onset_passed,
            driver_id,
            race_id
        FROM int_lap_anomaly_flags
        WHERE
            correction_weight = 1.0
            AND mad_score > 3.0
            AND driver_skill_residual_s > MEDIAN(driver_skill_residual_s)
                OVER (PARTITION BY race_id, driver_id)
            AND NOT cliff_onset_passed
    ),
    clean_cliff_rows AS (
        SELECT
            driver_skill_residual_s,
            next_5_lap_cumulative_jump_s as label_5lap,
            cliff_onset_passed,
            driver_id,
            race_id
        FROM int_lap_anomaly_flags
        WHERE
            correction_weight = 1.0
            AND mad_score > 3.0
            AND driver_skill_residual_s > MEDIAN(driver_skill_residual_s)
                OVER (PARTITION BY race_id, driver_id)
            AND cliff_onset_passed
    ),
    normal_rows AS (
        SELECT
            driver_skill_residual_s,
            next_5_lap_cumulative_jump_s as label_5lap,
            driver_id,
            race_id
        FROM int_lap_anomaly_flags
        WHERE
            correction_weight = 1.0
            AND anomaly_class = 'normal'
    )
    SELECT
        'mistake' as class,
        COUNT(*) as count,
        AVG(driver_skill_residual_s) as mean_residual,
        AVG(label_5lap) as mean_label,
        STDDEV(label_5lap) as stddev_label
    FROM mistake_rows
    UNION ALL
    SELECT
        'clean_cliff',
        COUNT(*),
        AVG(driver_skill_residual_s),
        AVG(label_5lap),
        STDDEV(label_5lap)
    FROM clean_cliff_rows
    UNION ALL
    SELECT
        'normal',
        COUNT(*),
        AVG(driver_skill_residual_s),
        AVG(label_5lap),
        STDDEV(label_5lap)
    FROM normal_rows
    """

    results = con.execute(query).fetchall()

    analysis = {}
    for row in results:
        class_name, count, mean_res, mean_label, stddev_label = row
        analysis[class_name] = {
            'count': count,
            'mean_residual': mean_res,
            'mean_label': mean_label,
            'stddev_label': stddev_label,
        }
        log.info(f"  {class_name:12} rows: {count:6,}, mean_residual: {mean_res:+.3f}s, mean_label: {mean_label:+.3f}s")

    return analysis

def assess_changepoint_option(con: duckdb.DuckDBPyConnection) -> dict:
    """Analyze Option A feasibility (change-point detection)."""
    log.info("\nAssessing OPTION A: Change-point detection feasibility...")

    # Check how often cliff_onset_passed disagrees with raw residual patterns
    query = """
    WITH driver_races AS (
        SELECT DISTINCT driver_id, race_id, race_year
        FROM int_lap_anomaly_flags
        WHERE correction_weight = 1.0
    )
    SELECT
        COUNT(*) as total_driver_races,
        SUM(CASE
            WHEN has_residual_spike AND NOT seed_says_cliff THEN 1
            ELSE 0
        END) as spike_without_seed,
        SUM(CASE
            WHEN NOT has_residual_spike AND seed_says_cliff THEN 1
            ELSE 0
        END) as seed_without_spike
    FROM (
        SELECT
            dr.driver_id,
            dr.race_id,
            MAX(CASE WHEN mad_score > 3.0 AND driver_skill_residual_s > 0 THEN TRUE ELSE FALSE END) as has_residual_spike,
            MAX(cliff_onset_passed) as seed_says_cliff
        FROM driver_races dr
        INNER JOIN dbt.int_lap_anomaly_flags f
            ON dr.driver_id = f.driver_id AND dr.race_id = f.race_id
        WHERE f.correction_weight = 1.0
        GROUP BY dr.driver_id, dr.race_id
    )
    """

    try:
        result = con.execute(query).fetchall()[0]
        total, spike_no_seed, seed_no_spike = result

        log.info(f"  Total driver-races analyzed: {total:,}")
        log.info(f"  Residual spike without seed cliff: {spike_no_seed:,} ({spike_no_seed/total*100:.1f}%)")
        log.info(f"  Seed cliff without residual spike: {seed_no_spike:,} ({seed_no_spike/total*100:.1f}%)")

        return {
            'total': total,
            'spike_no_seed': spike_no_seed,
            'seed_no_spike': seed_no_spike,
        }
    except Exception as e:
        log.warning(f"  Could not assess change-point: {e}")
        return {}

def provide_recommendation(current: dict, mistake_analysis: dict, cp_analysis: dict) -> str:
    """Provide a recommendation based on the analysis."""
    log.info("\n" + "="*70)
    log.info("RECOMMENDATION FOR F9")
    log.info("="*70)

    # Count of mistake rows
    mistake_count = mistake_analysis.get('mistake', {}).get('count', 0)
    mistake_pct = mistake_count / current['final_training'] * 100 if current['final_training'] > 0 else 0

    log.info(f"\nSituation:")
    log.info(f"  Current: {current['clean_cliff']:,} clean_cliff rows kept, {current['mistake_excluded']:,} mistake rows hard-excluded")
    log.info(f"  Mistake rows are {mistake_pct:.1f}% of training set")

    rec = """
RECOMMEND: OPTION B (Sample Weighting)

Rationale:
1. SIMPLICITY: No complex change-point detection needed. Just assign weight < 1.

2. PRINCIPLED: Matches existing patterns in codebase (correction_weight, IPW).
   Similar to how event-driven laps use reduced weight instead of hard exclusion.

3. SOFT DECOUPLING: Removes the hard dependency on cliff_onset_passed without
   throwing away potentially useful training signal from "mistake" rows.
   These are still real residual anomalies worth downweighting, not ignoring.

4. LESS RISKY: Change-point detection (Option A) requires:
   - Implementing a new statistical method (PELT, CUSUM, etc.)
   - Validating it gives sensible cliff detections
   - Handling edge cases (short stints, high-noise races)
   The benefit over soft weighting is uncertain.

5. EFFICIENCY: Weighting can be applied without model changes; it's a training
   hyperparameter. Change-point detection requires schema/model changes.

Implementation:
  - Add a training_weight column to anomaly flags
  - Assign 0.5 to mistake rows (or tune via cross-validation)
  - Update affected models to consume training_weight
  - Re-run model fitting with weighted samples

Cost: Lower than Option A. Allows incremental rollout per family.
"""

    log.info(rec)
    return "OPTION_B"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()

    if not DB_PATH.exists():
        log.error(f"Database not found at {DB_PATH}")
        return 1

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        current = assess_current_state(con)
        mistake_analysis = assess_mistake_rows(con)
        cp_analysis = assess_changepoint_option(con)

        recommendation = provide_recommendation(current, mistake_analysis, cp_analysis)
        log.info(f"\nRECOMMENDATION: {recommendation}")

    finally:
        con.close()

    return 0

if __name__ == "__main__":
    sys.exit(main())
