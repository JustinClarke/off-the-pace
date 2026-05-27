"""Inspect tuning results from Optuna studies + training logs.

CLI:
  python -m ml.src.inspect_trials                # all targets, production version
  python -m ml.src.inspect_trials --target degradation_regressor_p50
  python -m ml.src.inspect_trials --target all --verbose
  python -m ml.src.inspect_trials --version v2   # inspect a specific version's studies
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import optuna

from ml.src import schema as S

STUDIES_DIR = Path("ml/models/optuna_studies")
LOGS_DIR = Path("ml/models/training_logs")
MODELS_DIR = Path("ml/models")


def _param_importance(study: optuna.Study) -> dict[str, float]:
    """Return feature importance from completed trials (pruned trials excluded)."""
    try:
        # Compute importance across all completed (non-pruned) trials
        importance = optuna.importance.get_param_importances(study)
        return {k: float(v) for k, v in importance.items()}
    except Exception:
        return {}


def _fold_variance(target: str, version: str) -> tuple[list[float], float] | None:
    """Extract fold metrics and their variance from training log."""
    log_pattern = f"{target}_{version}_*.json"
    logs = sorted(LOGS_DIR.glob(log_pattern), reverse=True)
    if not logs:
        return None
    log = json.loads(logs[0].read_text())
    if "fold_metrics" not in log:
        return None
    fold_data = log["fold_metrics"]
    # Extract metric values (each fold_metrics entry is a dict with a metric key)
    metric_key = log.get("headline_metric", "pinball")
    metrics = [float(f[metric_key]) for f in fold_data]
    mean = sum(metrics) / len(metrics)
    variance = float(sum((m-mean) ** 2 for m in metrics) / len(metrics))
    return metrics, variance


def inspect_one(target: str, version: str, verbose: bool = False) -> None:
    spec = S.TARGET_BY_NAME[target]
    study_name = S.optuna_study_name(target, version)
    db_path = STUDIES_DIR / f"{study_name}.db"
    if not db_path.exists():
        print(f"[{target}] no study found ({db_path})")
        return

    # Load study from persistent DB
    storage = f"sqlite:///{db_path}"
    study = optuna.create_study(
        direction="maximize" if spec.kind == "classification" else "minimize",
        study_name=study_name,
        storage=storage,
        load_if_exists=True,
    )

    n_trials = len(study.trials)
    best_value = study.best_value
    best_params = study.best_params
    metric_name = "macro_f1" if spec.kind == "classification" else ("pinball" if spec.kind == "quantile" else "rmse")

    print(f"\n{'='*70}")
    print(f"[{target}] {n_trials} trials completed")
    print(f"  Best {metric_name}: {best_value:.6f}")
    print(f"  Best params:")
    for k, v in sorted(best_params.items()):
        print(f"    {k}: {v}")

    # Param importance
    importance = _param_importance(study)
    if importance:
        print(f"  Param importance (top 5):")
        for k, v in sorted(importance.items(), key=lambda x: -x[1])[:5]:
            print(f"    {k}: {v:.4f}")

    # Fold variance (from training log after tuning refitted)
    fold_data = _fold_variance(target, version)
    if fold_data:
        folds, variance = fold_data
        print(f"  Fold metrics (CV refit, full data):")
        for i, m in enumerate(folds, 1):
            print(f"    fold {i}: {m:.6f}")
        print(f"  Variance: {variance:.6f}")

    if verbose:
        pruned = len([t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED])
        print(f"  Pruned: {pruned}/{n_trials}")

    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="all")
    ap.add_argument("--version", default=S.MODEL_VERSION_DEFAULT,
                    help="model version whose studies to inspect (default: production version)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    targets = [t.name for t in S.PRODUCTION_TARGETS] if args.target == "all" else [args.target]
    for t in targets:
        inspect_one(t, args.version, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
