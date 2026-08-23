"""Optuna hyperparameter search → best_params.json → chains the production refit.

CLI:
  python -m ml.src.tune --target all --trials 50              # canonical (refits MODEL_VERSION_DEFAULT)
  python -m ml.src.tune --target cliff_classifier --trials 20 --folds 3
  python -m ml.src.tune --target all --version v2 --trials 50 # tune a specific version

TPESampler + MedianPruner (seeded by RANDOM_STATE). The objective is the mean
season-grouped CV headline metric (pinball ↓ for quantiles, macro-F1 ↑ for the
classifier, RMSE ↓ for stint-life). The study DB and best_params.json are persisted;
the closing operation refits on the full training set via train.train_one(version=...).
The study namespace is keyed off the version (schema.optuna_study_name) so a fresh
tuning run per version gets its own study instead of overwriting v1.
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import optuna

from ml.src import features as F
from ml.src import schema as S
from ml.src import train as T

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

STUDIES_DIR = Path("ml/models/optuna_studies")
MODELS_DIR = Path("ml/models")


def _suggest(trial: optuna.Trial, spec: S.TargetSpec | None = None) -> dict:
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 200, 700, step=100),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 5.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
        "gamma": trial.suggest_float("gamma", 1e-3, 5.0, log=True),
    }
    if spec is not None and spec.kind == "survival":
        # The AFT scale is a fitted parameter of the likelihood, not a tree knob, and
        # the headline moves a lot with it: at the current production params the CV
        # NLL runs 3.06 at 0.30, 2.09 at 0.80 and back to 2.11 at 1.00. Leaving it
        # fixed would search the trees against the wrong noise model.
        params["aft_loss_distribution_scale"] = trial.suggest_float(
            "aft_loss_distribution_scale", 0.3, 1.2)
    return params


def tune_one(target: str, *, trials: int, folds: int, version: str, subsample_rows: int = 0) -> dict:
    spec = S.TARGET_BY_NAME[target]
    bundle = F.load_features(target=target)
    X, y = bundle.X_train, bundle.y_train.to_numpy()
    seasons = bundle.groups_train.to_numpy()
    # Optional row subsample for the SEARCH only (the final refit uses full data).
    meta = bundle.meta_train
    if subsample_rows and subsample_rows < len(X):
        rng = np.random.default_rng(S.RANDOM_STATE)
        idx = np.sort(rng.choice(len(X), size=subsample_rows, replace=False))
        X, y, seasons = X.iloc[idx].reset_index(drop=True), y[idx], seasons[idx]
        meta = meta.iloc[idx].reset_index(drop=True)
    maximize = spec.kind == "classification"
    folds_idx = list(T._season_folds(seasons, bundle.training_seasons, folds))
    # Censoring flags for the survival target, subsampled in step with X/y above.
    cens = (meta[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
            if spec.kind == "survival" else None)

    def objective(trial: optuna.Trial) -> float:
        params = _suggest(trial, spec)
        scale = params.get("aft_loss_distribution_scale", S.AFT_SCALE_DEFAULT)
        scores = []
        for step, (tr, val) in enumerate(folds_idx):
            model = T._make_model(spec, params)
            if spec.kind == "survival":
                model.fit(X.iloc[tr], y[tr],
                          sample_weight=T._sample_weight(spec, y[tr]),
                          is_censored=cens[tr])
                _, value = T._headline(spec, y[val], model.predict(X.iloc[val]),
                                       meta.iloc[val], scale)
            else:
                # NOTE: meta is deliberately NOT passed here. _sample_weight would then
                # apply the quantile models' IPW survival weights, which train.py:_fit
                # does apply -- so the search and the refit disagree for p10/p50/p90.
                # That mismatch is a real defect (ml_execution_plan.md, Phase 2 finding
                # 1) and fixing it re-opens the quantile params, so it is left alone
                # here rather than changed as a side effect of the survival work.
                model.fit(X.iloc[tr], y[tr], sample_weight=T._sample_weight(spec, y[tr]))
                _, value = T._headline(spec, y[val], model.predict(X.iloc[val]))
            scores.append(value)
            trial.report(float(np.mean(scores)), step=step)
            if trial.should_prune():
                raise optuna.TrialPruned()
        return float(np.mean(scores))

    STUDIES_DIR.mkdir(parents=True, exist_ok=True)
    study_name = S.optuna_study_name(target, version)
    study = optuna.create_study(
        direction="maximize" if maximize else "minimize",
        sampler=optuna.samplers.TPESampler(seed=S.RANDOM_STATE),
        pruner=optuna.pruners.MedianPruner(n_warmup_steps=1),
        study_name=study_name,
        storage=f"sqlite:///{STUDIES_DIR / f'{study_name}.db'}",
        load_if_exists=True,
    )
    study.optimize(objective, n_trials=trials, show_progress_bar=False)

    best_path = MODELS_DIR / f"{target}_best_params.json"
    best_path.write_text(json.dumps(study.best_params, indent=2, sort_keys=True))
    print(f"[{target}] best {('macro_f1' if maximize else 'pinball/rmse')}={study.best_value:.4f} "
          f"({len(study.trials)} trials) -> {best_path.name}")

    # Chain the production refit on the FULL training set (train.py runs its own 5-fold CV log).
    T.train_one(target, version=version, params=study.best_params, smoke=False)
    return study.best_params


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="all")
    ap.add_argument("--trials", type=int, default=50)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--version", default=S.MODEL_VERSION_DEFAULT,
                    help="model version to tune + refit; keys the Optuna study namespace (default: production version)")
    ap.add_argument("--subsample-rows", type=int, default=0,
                    help="row subsample for the SEARCH only (0=full); final refit always uses full data")
    args = ap.parse_args()
    targets = [t.name for t in S.PRODUCTION_TARGETS] if args.target == "all" else [args.target]
    for t in targets:
        tune_one(t, trials=args.trials, folds=args.folds, version=args.version, subsample_rows=args.subsample_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
