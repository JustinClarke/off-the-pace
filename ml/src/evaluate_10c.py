"""10c evaluation: cause-specific metrics with dependent-censoring sensitivity band.

An AFT model fitted under cause-specific censoring predicts tyre-limit survival. This
script evaluates it with metrics that don't have the NLL scoring-mixture artefact:
IPCW-Brier and time-dependent AUC, with a sensitivity band for dependent censoring.

**The headline is the honest refit, and that is not a preference.** As first written this
script loaded the SHIPPED `stint_life_regressor_v11.bst` and scored it on the
`cv_final_fold` eval rows. `train.py` refits the shipped booster on EVERY training season
-- 2018 through 2024 -- and that fold's eval rows are 2024, so the eval set sat inside the
booster's own training data and every number the script produced was in-sample. It is not
a small effect: green-pit time-dependent AUC reads 0.844 in-sample and 0.691 out of it, and
the calibration slope does not merely shrink, it crosses 1.0 (1.232 in-sample, 0.666 out),
so the in-sample run reported the miscalibration with the wrong SIGN. 10c's published
headline was measured that way; 10d found it and this is the repair.

So `default_mode="honest"` refits on the training side of the split only -- the same thing
`evaluate.py::evaluate_target` already does, through the same `EV._fit` -- and the
shipped-booster path survives only as a labelled `in_sample` diagnostic that main() prints
beside the headline as a gap, never on its own.

CLI:
  python -m ml.src.evaluate_10c                       # honest headline + in-sample gap
  python -m ml.src.evaluate_10c --variant standard    # the other label construction
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import duckdb

from ml.src import features as F
from ml.src import schema as S
from ml.src import survival as SV
from ml.src import evaluate as EV

RESULTS_PATH = Path("ml/artefacts/10c_evaluation_results.json")
SHIPPED_BOOSTER = "ml/models/stint_life_regressor_v11.bst"

_BUNDLES: dict[str, F.FeatureBundle] = {}


def _bundle(censoring_variant: str) -> F.FeatureBundle:
    """Feature load is the expensive part; both modes score the identical eval rows."""
    if censoring_variant not in _BUNDLES:
        _BUNDLES[censoring_variant] = F.load_features(
            target="stint_life_regressor", censoring_variant=censoring_variant)
    return _BUNDLES[censoring_variant]


def load_model_and_data(censoring_variant: str = "10b", mode: str = "honest") -> dict:
    """Predictions on the eval fold, and how they were produced.

    mode="honest"    -- refit on split.X_tr (2018-2023) and score 2024. The headline.
    mode="in_sample" -- load the shipped booster, which was fitted on 2018-2024, and
                        score 2024. Diagnostic only: the eval rows are in its training
                        set, so it measures memorisation, not generalisation.
    """
    if mode not in ("honest", "in_sample"):
        raise ValueError(f"mode must be 'honest' or 'in_sample', got {mode!r}")

    bundle = _bundle(censoring_variant)
    spec = S.TARGET_BY_NAME["stint_life_regressor"]
    split = EV._evaluation_split(bundle)   # cv_final_fold: train 2018-2023, eval 2024

    if mode == "honest":
        params = EV._params_for("stint_life_regressor", S.MODEL_VERSION_DEFAULT)
        model = EV._fit(spec, params, split.X_tr, split.y_tr, split.cens_tr, split.w_tr)
        scale = model.scale
        pred_median = model.predict(split.X_ev)
        provenance = {
            "mode": "honest",
            "fitted_on": "training side of the split only (2018-2023)",
            "n_fit_rows": int(len(split.y_tr)),
            "params_source": f"ml/models/stint_life_regressor_best_params.json ({S.MODEL_VERSION_DEFAULT})",
        }
    else:
        booster = SV.load_booster(SHIPPED_BOOSTER)
        scale = SV.aft_params(booster)["scale"]
        pred_median = SV.laps_from_margin(SV.margin(booster, split.X_ev), scale, q=None)
        provenance = {
            "mode": "in_sample",
            "fitted_on": f"whatever wrote {SHIPPED_BOOSTER} -- train.py fits every "
                         f"training season, 2018-2024, so the 2024 eval rows are inside it",
            "n_fit_rows": int(len(bundle.X_train)),
            "params_source": SHIPPED_BOOSTER,
            "warning": "IN-SAMPLE. Diagnostic only; never quote as a headline.",
        }

    lap_ids_ev = split.lap_ids_ev
    meta_ev = bundle.meta_train.loc[
        bundle.meta_train["lap_id"].isin(lap_ids_ev)].reset_index(drop=True)

    return {
        "spec": spec,
        "scale": float(scale),
        "y": split.y_ev,
        "pred": pred_median,
        "cens": split.cens_ev,
        "lap_ids": lap_ids_ev,
        "X": split.X_ev,
        "meta": meta_ev,
        "censoring_variant": censoring_variant,
        "provenance": provenance,
    }


def load_10b_model_and_data():
    """Back-compat shim. Returns the HONEST refit, not the shipped booster the original
    name implied -- see the module docstring for why the original behaviour was a defect."""
    return load_model_and_data(censoring_variant="10b", mode="honest")


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


def evaluate_mode(censoring_variant: str, mode: str, cause_labels=None) -> tuple[dict, np.ndarray]:
    """Every cause-specific metric for one (variant, mode) pair."""
    data = load_model_and_data(censoring_variant, mode)
    y, pred, cens, scale = data["y"], data["pred"], data["cens"], data["scale"]

    if cause_labels is None:
        cause_labels = get_cause_labels(data["lap_ids"], data["meta"])
    causes = [c for c in np.unique(cause_labels) if pd.notna(c)]

    out = {
        "mode": mode,
        "censoring_variant": censoring_variant,
        "provenance": data["provenance"],
        "scale": scale,
        "n_eval_laps": int(len(y)),
        "overall": compute_cause_specific_metrics(
            y, pred, cens, scale, np.ones(len(y), dtype=bool), "overall"),
        "by_cause": [],
    }
    out["overall"]["interpretation"] = "diagnostic_only_conflates_causes"
    for cause in causes:
        mask = get_causes_mask(cause_labels, cause)
        if np.sum(mask) >= 10:
            out["by_cause"].append(
                compute_cause_specific_metrics(y, pred, cens, scale, mask, cause))
    out["dependent_censoring_sensitivity"] = dependent_censoring_sensitivity_band(
        y, pred, cens, scale, cause_labels)
    return out, cause_labels


def _green_pit(block: dict) -> dict:
    for row in block["by_cause"]:
        if row["cause"] == "green_pit":
            return row
    return {}


def main(censoring_variant: str = "10b"):
    """Run 10c evaluation: the honest headline, with the in-sample gap beside it."""
    print(f"Evaluating stint_life_regressor, censoring_variant={censoring_variant}")
    print("  headline  = refit on 2018-2023, scored on 2024 (out of sample)")
    print(f"  diagnostic = shipped {SHIPPED_BOOSTER}, which contains 2024 (IN SAMPLE)\n")

    honest, cause_labels = evaluate_mode(censoring_variant, "honest")
    in_sample, _ = evaluate_mode(censoring_variant, "in_sample", cause_labels)

    print(f"Evaluation set size: {honest['n_eval_laps']} laps")
    print(f"Cause distribution:\n{pd.Series(cause_labels).value_counts()}")

    gh, gi = _green_pit(honest), _green_pit(in_sample)
    optimism = {
        "time_dependent_auc": (gi.get("time_dependent_auc") or 0) - (gh.get("time_dependent_auc") or 0),
        "ipcw_brier": (gi.get("ipcw_brier") or 0) - (gh.get("ipcw_brier") or 0),
        "calibration_slope": (gi.get("calibration_slope") or 0) - (gh.get("calibration_slope") or 0),
    }

    results = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "model": "stint_life_regressor",
        "framework": "cause-specific AFT with IPCW-Brier and time-dependent AUC",
        "headline_cause": "green_pit",
        "headline_mode": "honest",
        "headline": honest,
        "in_sample_diagnostic": in_sample,
        "in_sample_optimism_green_pit": optimism,
        "in_sample_optimism_note": (
            "Shipped-booster minus honest-refit on the identical eval rows. This is the "
            "gap that made 10c's published headline wrong: the shipped booster is fitted "
            "on 2018-2024 and the eval fold IS 2024, so its numbers measure memorisation. "
            "The calibration slope does not merely shrink across the gap, it crosses 1.0, "
            "so the in-sample run reported the miscalibration with the wrong sign."
        ),
        "headline_note": (
            "The green_pit row is the headline. Under the 10b variant green_pit is the "
            "only uncensored cause, so the 'overall' row scores green-pit events against "
            "an at-risk pool that is majority non-green - and those causes differ in "
            "length by construction (race_end runs to the flag, red stops early). Its "
            "discrimination is therefore part cause-membership, which is the same "
            "mixture artefact 10c exists to remove. Diagnostic only."
        ),
    }

    print(f"\nSaving results to {RESULTS_PATH}...")
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 74)
    print("10c EVALUATION SUMMARY  (headline = honest refit; in-sample shown for the gap)")
    print("=" * 74)
    print(f"\n{'green_pit':<22}{'HONEST (headline)':>20}{'in-sample (diag)':>20}{'optimism':>12}")
    for key, fmt in (("time_dependent_auc", "{:.4f}"), ("ipcw_brier", "{:.4f}"),
                     ("calibration_slope", "{:.4f}")):
        h, i = gh.get(key), gi.get(key)
        print(f"  {key:<20}" + f"{fmt.format(h) if h is not None else 'n/a':>20}"
              + f"{fmt.format(i) if i is not None else 'n/a':>20}"
              + f"{optimism[key]:>+12.4f}")

    print(f"\n{'overall (DIAGNOSTIC ONLY -- do not quote)':<42}")
    for key in ("ipcw_brier", "time_dependent_auc"):
        print(f"  {key:<20}{honest['overall'].get(key, float('nan')):>20.4f}"
              f"{in_sample['overall'].get(key, float('nan')):>20.4f}")

    print(f"\nPer-cause (honest), n={len(honest['by_cause'])} causes:")
    for row in honest["by_cause"]:
        bits = [f"n={row['n']}"]
        for key, label in (("ipcw_brier", "Brier"), ("time_dependent_auc", "AUC"),
                           ("calibration_slope", "slope")):
            if row.get(key) is not None:
                bits.append(f"{label} {row[key]:.4f}")
        print(f"  {row['cause']:<12} " + "  ".join(bits))

    print(f"\nDependent censoring sensitivity:")
    print(f"  {honest['dependent_censoring_sensitivity']['sensitivity_interpretation']}")

    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variant", default="10b", choices=["standard", "10b"],
                    help="censoring variant for the stint-life label (default: 10b)")
    args = ap.parse_args()
    results = main(censoring_variant=args.variant)
