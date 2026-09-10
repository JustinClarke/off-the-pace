"""10c evaluation: cause-specific metrics with dependent-censoring sensitivity band.

The 10b-trained AFT model predicts tyre-limit survival under cause-specific censoring.
This script evaluates it with metrics that don't have the NLL scoring-mixture artefact:
IPCW-Brier and time-dependent AUC, with a sensitivity band for dependent censoring.

CLI:
  python -m ml.src.evaluate_10c
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import duckdb
from scipy.stats import linregress

from ml.src import features as F
from ml.src import schema as S
from ml.src import survival as SV
from ml.src import evaluate as EV

RESULTS_PATH = Path("ml/artefacts/10c_evaluation_results.json")


def load_10b_model_and_data():
    """Load the 10b-trained model and evaluation data."""
    # Load the 10b model (cause-specific censoring)
    booster_path = "ml/models/stint_life_regressor_v11.bst"
    booster = SV.load_booster(booster_path)
    params = SV.aft_params(booster)
    scale = params["scale"]

    # Load features and evaluation split
    bundle = F.load_features(target="stint_life_regressor", censoring_variant="10b")
    spec = S.TARGET_BY_NAME["stint_life_regressor"]

    # Use cv_final_fold (train 2018-2023, eval 2024)
    split = EV._evaluation_split(bundle)

    # Get predictions
    pred_margin = SV.margin(booster, split.X_ev)
    pred_median = SV.laps_from_margin(pred_margin, scale, q=None)

    y_ev = split.y_ev
    cens_ev = split.cens_ev
    lap_ids_ev = split.lap_ids_ev

    # Get eval metadata from training meta (since eval comes from train split)
    meta_ev = bundle.meta_train.loc[bundle.meta_train["lap_id"].isin(lap_ids_ev)].reset_index(drop=True)

    return {
        "spec": spec,
        "scale": scale,
        "y": y_ev,
        "pred": pred_median,
        "cens": cens_ev,
        "lap_ids": lap_ids_ev,
        "X": split.X_ev,
        "meta": meta_ev,
    }


def get_cause_labels(lap_ids: np.ndarray, meta: pd.DataFrame) -> np.ndarray:
    """Get cause label (green_pit, sc_pit, vsc_pit, red, race_end, retirement) for each lap."""
    con = duckdb.connect(S.DUCKDB_PATH, read_only=True)
    try:
        # Query stint_end_cause from the stint features, then map to laps via stint_id
        cause_df = con.execute(
            f"""SELECT DISTINCT m.lap_id, sf.stint_end_cause
               FROM {S.MART} m
               JOIN {S.STINT_FEATURES} sf ON m.stint_id = sf.stint_id
               WHERE m.lap_id = ANY(?)""", [lap_ids.tolist()]
        ).df()
    finally:
        con.close()

    # Map lap_ids to causes, handling missing values
    cause_map = dict(zip(cause_df["lap_id"], cause_df["stint_end_cause"]))
    causes = np.array([cause_map.get(lid, None) for lid in lap_ids], dtype=object)
    return causes


def get_causes_mask(cause_labels: np.ndarray, cause: str) -> np.ndarray:
    """Get boolean mask for a specific cause."""
    return cause_labels == cause


def compute_cause_specific_metrics(
    y: np.ndarray,
    pred: np.ndarray,
    cens: np.ndarray,
    scale: float,
    cause_mask: np.ndarray,
    cause_name: str,
) -> dict:
    """Compute IPCW-Brier, time-dependent AUC, and calibration for a specific cause."""
    y_sub = y[cause_mask]
    pred_sub = pred[cause_mask]
    cens_sub = cens[cause_mask]

    if len(y_sub) < 20:
        return {
            "cause": cause_name,
            "n": len(y_sub),
            "status": "insufficient_data",
        }

    results = {"cause": cause_name, "n": len(y_sub)}

    # IPCW-Brier
    try:
        mean_brier, per_time_brier = SV.ipcw_brier(y_sub, pred_sub, cens_sub, scale)
        results["ipcw_brier"] = float(mean_brier)
        results["ipcw_brier_per_time"] = [float(x) for x in per_time_brier]
    except Exception as e:
        results["ipcw_brier_error"] = str(e)

    # Time-dependent AUC
    try:
        mean_auc, per_time_auc = SV.time_dependent_auc(y_sub, pred_sub, cens_sub, scale)
        results["time_dependent_auc"] = float(mean_auc) if not np.isnan(mean_auc) else None
        results["time_dependent_auc_per_time"] = [float(x) if not np.isnan(x) else None for x in per_time_auc]
    except Exception as e:
        results["time_dependent_auc_error"] = str(e)

    # D-calibration
    try:
        cal = SV.d_calibration(y_sub, pred_sub, cens_sub, scale)
        results["calibration_slope"] = float(cal["calibration_slope"]) if not np.isnan(cal["calibration_slope"]) else None
        results["calibration"] = {
            "pred_quantiles": [float(x) for x in cal["pred_quantiles"]],
            "exp_event_rates": [float(x) for x in cal["exp_event_rates"]],
            "obs_event_rates": [float(x) for x in cal["obs_event_rates"]],
        }
    except Exception as e:
        results["calibration_error"] = str(e)

    return results


def dependent_censoring_sensitivity_band(
    y: np.ndarray,
    pred: np.ndarray,
    cens: np.ndarray,
    scale: float,
    cause_labels: np.ndarray,
) -> dict:
    """Compute sensitivity band across censoring dependencies.

    Since SC arrival correlates with race state (which correlates with tyre state),
    censoring is dependent. We bracket IPCW estimates across a band of assumed
    dependence strengths rather than assuming independence.
    """
    # Split by cause to measure dependence between cause and censoring
    causes = np.unique(cause_labels)
    cause_specific_censoring_rates = {}

    for cause in causes:
        mask = cause_labels == cause
        if np.sum(mask) > 10:
            cens_rate = np.mean(cens[mask])
            cause_specific_censoring_rates[cause] = cens_rate

    # Deliberately NOT reporting a "dependence strength" derived from these rates.
    # Under the 10b censoring variant a stint's cause *is* its censoring status
    # (green_pit uncensored, every other cause censored), so these rates are 0/1 by
    # construction. Any spread statistic over them measures the definition, not the
    # dependence between censoring and tyre state - which is what would actually
    # bias IPCW. Estimating that needs an instrument for SC arrival, which we do
    # not have here, so the caveat is stated qualitatively and left unresolved.
    return {
        "cause_specific_censoring_rates": cause_specific_censoring_rates,
        "dependence_strength": None,
        "dependence_strength_note": (
            "Not estimated. Cause determines censoring status under the 10b variant, "
            "so cause-specific censoring rates are 0/1 by construction and carry no "
            "information about censoring/tyre-state dependence."
        ),
        "sensitivity_interpretation": (
            "SC and VSC arrival is not independent of tyre state, so IPCW estimates "
            "here are biased by an unmeasured amount. The green-pit metrics are the "
            "least exposed (that stratum has no censoring at all); the overall row is "
            "the most exposed and should not be read as a survival headline. No "
            "copula sensitivity analysis has been run - quantifying the band is "
            "outstanding work, not a result of this item."
        ),
    }


def main():
    """Run 10c evaluation."""
    print("Loading 10b model and evaluation data...")
    data = load_10b_model_and_data()

    y = data["y"]
    pred = data["pred"]
    cens = data["cens"]
    scale = data["scale"]
    lap_ids = data["lap_ids"]
    meta = data["meta"]

    print(f"Evaluation set size: {len(y)} laps across {len(np.unique(data['meta']['stint_id']))} stints")

    # Get cause labels
    cause_labels = get_cause_labels(lap_ids, meta)
    causes = [c for c in np.unique(cause_labels) if pd.notna(c)]

    print(f"Causes: {causes}")
    print(f"Cause distribution:\n{pd.Series(cause_labels).value_counts()}")

    # Overall metrics
    results = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "model": "stint_life_regressor_v11",
        "framework": "cause-specific AFT with IPCW-Brier and time-dependent AUC",
        "headline_cause": "green_pit",
        "headline_note": (
            "The green_pit row is the headline. Under the 10b variant green_pit is the "
            "only uncensored cause, so the 'overall' row scores green-pit events against "
            "an at-risk pool that is majority non-green - and those causes differ in "
            "length by construction (race_end runs to the flag, red stops early). Its "
            "discrimination is therefore part cause-membership, which is the same "
            "mixture artefact 10c exists to remove. Diagnostic only."
        ),
        "overall": compute_cause_specific_metrics(
            y, pred, cens, scale, np.ones(len(y), dtype=bool), "overall"
        ),
        "by_cause": [],
    }
    results["overall"]["interpretation"] = "diagnostic_only_conflates_causes"

    # Per-cause metrics
    for cause in causes:
        mask = get_causes_mask(cause_labels, cause)
        if np.sum(mask) >= 10:
            cause_results = compute_cause_specific_metrics(
                y, pred, cens, scale, mask, cause
            )
            results["by_cause"].append(cause_results)

    # Dependent-censoring sensitivity band
    results["dependent_censoring_sensitivity"] = dependent_censoring_sensitivity_band(
        y, pred, cens, scale, cause_labels
    )

    # Save results
    print(f"\nSaving results to {RESULTS_PATH}...")
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("10c EVALUATION SUMMARY")
    print("=" * 60)
    print(f"\nOverall metrics:")
    if "ipcw_brier" in results["overall"]:
        print(f"  IPCW-Brier: {results['overall']['ipcw_brier']:.4f}")
    if "time_dependent_auc" in results["overall"]:
        print(f"  Time-dependent AUC: {results['overall']['time_dependent_auc']:.4f}")

    print(f"\nPer-cause metrics (n={len(results['by_cause'])} causes):")
    for cause_result in results["by_cause"]:
        print(f"\n  {cause_result['cause']} (n={cause_result['n']}):")
        if "ipcw_brier" in cause_result:
            print(f"    IPCW-Brier: {cause_result['ipcw_brier']:.4f}")
        if "time_dependent_auc" in cause_result:
            print(f"    Time-dependent AUC: {cause_result['time_dependent_auc']:.4f}")
        if "calibration_slope" in cause_result and cause_result["calibration_slope"] is not None:
            print(f"    Calibration slope: {cause_result['calibration_slope']:.4f}")

    print(f"\nDependent censoring sensitivity:")
    print(f"  {results['dependent_censoring_sensitivity']['sensitivity_interpretation']}")

    return results


if __name__ == "__main__":
    results = main()
