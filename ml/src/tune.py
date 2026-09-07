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


# ─── The search space ───────────────────────────────────────────────────────────
# Declared as data so `boundary_params` reads the same numbers `_suggest` searches.
# Every search from Phase 2 to Phase 7 stopped with `max_depth` on its ceiling and
# none of them said so, because a search that ends on its own edge prints a best
# value like any other: the bound is invisible in the output, and "the learner is
# saturated" cannot be told apart from "the learner was never allowed to ask for
# more". `tune_one` now names the pinned parameters at the end of every search.
#
# The ranges below are the widened ones (open item 21); the bound each replaced is in
# the comment beside it. What the widening bought, measured: a 50-trial p50 search in
# this space lands on max_depth 9 / min_child_weight 42 / n_estimators 900 -- INTERIOR
# on all three axes, where the incumbent was pinned on two edges of the old space. So
# the old bounds really were truncating the optimum. They were truncating it by 0.33%
# (fold-paired +0.0038, p=0.198, 4/5), which is why the params did not move and the
# bounds did: a space that contains its own optimum is worth having even when what it
# contains is not worth shipping. Note the coordinate probe in the same checkpoint says
# the opposite, and is the weaker instrument -- stepping one axis past the bound cannot
# see a move that needs three axes at once.
SEARCH_SPACE: dict[str, dict] = {
    "n_estimators":     {"type": "int",   "low": 200,  "high": 1200, "step": 100},   # was 700
    "max_depth":        {"type": "int",   "low": 3,    "high": 12},                  # was 8
    "learning_rate":    {"type": "float", "low": 0.02, "high": 0.2, "log": True},
    "subsample":        {"type": "float", "low": 0.6,  "high": 1.0},
    "colsample_bytree": {"type": "float", "low": 0.6,  "high": 1.0},
    "min_child_weight": {"type": "int",   "low": 1,    "high": 60, "log": True},     # was 20, linear
    "reg_alpha":        {"type": "float", "low": 1e-3, "high": 5.0, "log": True},
    "reg_lambda":       {"type": "float", "low": 1e-3, "high": 5.0, "log": True},
    "gamma":            {"type": "float", "low": 1e-3, "high": 5.0, "log": True},
}

# The AFT scale is a fitted parameter of the likelihood, not a tree knob, and the
# headline moves a lot with it: at the current production params the CV NLL runs
# 3.06 at 0.30, 2.09 at 0.80 and back to 2.11 at 1.00. Leaving it fixed would search
# the trees against the wrong noise model.
SURVIVAL_SPACE: dict[str, dict] = {
    "aft_loss_distribution_scale": {"type": "float", "low": 0.3, "high": 1.2},
}


def _space_for(spec: S.TargetSpec | None) -> dict[str, dict]:
    survival = spec is not None and spec.kind == "survival"
    return {**SEARCH_SPACE, **(SURVIVAL_SPACE if survival else {})}


def _suggest(trial: optuna.Trial, spec: S.TargetSpec | None = None) -> dict:
    params = {}
    for name, d in _space_for(spec).items():
        if d["type"] == "int":
            params[name] = trial.suggest_int(name, d["low"], d["high"],
                                             step=d.get("step", 1), log=d.get("log", False))
        else:
            params[name] = trial.suggest_float(name, d["low"], d["high"], log=d.get("log", False))
    return params


def boundary_params(best: dict, spec: S.TargetSpec | None = None,
                    rel_tol: float = 1e-6) -> dict[str, str]:
    """Which of `best` sit on an edge of the space that produced them: name -> low|high.

    An int is on the edge when it equals the bound. A float is on the edge when it is
    within `rel_tol` of one -- a continuous suggestion practically never returns its
    bound exactly, and a value 1e-9 inside it is pinned in every sense that matters.

    A pin is a fact about the search, not a verdict on the model: it says the optimum
    of the trials run sits where the space ran out, which happens both when the
    learner wants more capacity and when the optimum genuinely lives at the edge.
    Phase 8 and open item 21 are one of each. Telling them apart takes a probe past
    the bound, so this reports rather than fails.
    """
    out: dict[str, str] = {}
    for name, d in _space_for(spec).items():
        if name not in best:
            continue
        value, low, high = float(best[name]), float(d["low"]), float(d["high"])
        if d["type"] == "int":
            hit_low, hit_high = value == low, value == high
        else:
            hit_low = abs(value - low) <= rel_tol * max(abs(low), 1.0)
            hit_high = abs(value - high) <= rel_tol * max(abs(high), 1.0)
        if hit_low or hit_high:
            out[name] = "low" if hit_low else "high"
    return out


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

    def objective(trial: optuna.Trial) -> float:
        params = _suggest(trial, spec)
        scale = params.get("aft_loss_distribution_scale", S.AFT_SCALE_DEFAULT)
        scores = []
        for step, (tr, val) in enumerate(folds_idx):
            model = T._make_model(spec, params)
            # The fold fit goes through train.py's own _fit, so the objective is
            # measured under exactly the weights the production refit applies:
            # IPW survival weights for the quantile trio, balanced class weights for
            # the classifier, none for AFT (which carries censoring in the label).
            # Until Phase 2 finding 1 was fixed this path called model.fit directly
            # without meta, so the quantile search silently dropped the IPW weights
            # that train.py:_fit applies -- p10/p50/p90 were selected against an
            # objective the refit does not use. Do not reintroduce a second fit call
            # here: one code path is what keeps search and refit in agreement.
            T._fit(model, spec, X.iloc[tr], y[tr], meta.iloc[tr])
            _, value = T._headline(spec, y[val], model.predict(X.iloc[val]),
                                   meta.iloc[val], scale)
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

    # A search that ends on its own edge prints a best value like any other. Say so.
    pinned = boundary_params(study.best_params, spec)
    if pinned:
        named = ", ".join(f"{k}={study.best_params[k]} ({side})" for k, side in sorted(pinned.items()))
        print(f"[{target}] stopped on a search-space boundary: {named}. The optimum of "
              f"these {len(study.trials)} trials is where the space ran out, which is not "
              f"the same as convergence -- probe past the bound before reading it either way.")

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
