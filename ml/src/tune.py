"""Optuna hyperparameter search → best_params.json → chains the production refit.

CLI:
  python -m ml.src.tune --target all --trials 50              # canonical (refits MODEL_VERSION_DEFAULT)
  python -m ml.src.tune --target cliff_classifier --trials 20 --folds 3
  python -m ml.src.tune --target all --version v2 --trials 50 # tune a specific version
  python -m ml.src.tune --target stint_life_regressor --honest-split \
      --censoring-variant standard --objective green_pit_brier --no-refit   # 10e

TPESampler + MedianPruner (seeded by RANDOM_STATE). The objective is the mean
season-grouped CV headline metric (pinball ↓ for quantiles, macro-F1 ↑ for the
classifier, RMSE ↓ for stint-life). The study DB and best_params.json are persisted;
the closing operation refits on the full training set via train.train_one(version=...).
The study namespace is keyed off the version (schema.optuna_study_name) so a fresh
tuning run per version gets its own study instead of overwriting v1.

**Three things this search gets wrong by default for the stint-life target**, all found by
work item 10d and all now expressible as choices rather than as silence:

1. **The label was never chosen.** `load_features`' `censoring_variant` defaults to
   `standard`, and this module never passed one -- so the shipped params were selected
   against whichever construction the default happened to be, not against the one the app's
   gauge shows. `--censoring-variant` makes it a decision that appears in the run's record.
2. **The metric is the mixture.** `train._headline` on a survival target is the AFT NLL,
   which 10c ruled out as a headline for stint life because it scores tyre-limit endings
   and exogenous interruptions in one likelihood. `--objective` offers the two green-pit
   metrics 10d used instead.
3. **The eval season votes on its own hyperparameters.** Folds run over
   `bundle.training_seasons`, which is EVERY ingested season -- 2018-2024 today -- while
   `evaluate.py` reports on 2024. `--honest-split` confines them to the training side of
   `evaluate._evaluation_split`. Without it, a survival search now prints a warning saying
   so; the default is left alone because flipping it is a landing decision, not this
   module's to make.
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
# `max_depth`'s LOW bound moved 3 -> 2 by item 10e (2026-09-10), for the same reason the
# highs moved: a search cannot find an optimum its space does not contain. 10d measured the
# stint-life inner-fold calibration slope rising monotonically as depth falls -- 0.622 at the
# shipped depth 8, 0.708 at 3, 0.794 at 2 -- so its best arm sat one step OUTSIDE the space
# that produced the shipped params. A bound that excludes the value the previous item found
# best is a search stopped on its edge before it starts. Widening it does not endorse depth 2;
# it makes "the search did not want depth 2" a measurement rather than a restatement of the
# bound.
#
# `n_estimators`' LOW bound moved 200 -> 50 (step 100 -> 50) by the same item, for the same
# reason and on a measurement rather than a hunch: 10e's two declared searches BOTH stopped
# on `n_estimators = 200 (low)` while also sitting at `learning_rate` 0.0205 against a bound
# of 0.02. Those two axes multiply -- the total shrinkage a boosted fit applies is roughly
# `n_estimators * learning_rate` -- so a search pinned on both is asking for a weaker fit
# than the space can express, and the old floor of 200 was answering "no" on its behalf. The
# new grid is a strict superset of the old one (every former value is a multiple of 50).
SEARCH_SPACE: dict[str, dict] = {
    "n_estimators":     {"type": "int",   "low": 50,   "high": 1200, "step": 50},    # was 700; low was 200/step 100
    "max_depth":        {"type": "int",   "low": 2,    "high": 12},                  # was 8; low was 3
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


# ─── Selection objectives ───────────────────────────────────────────────────────
# `headline` is what every search before 10e used: `train._headline`, which for the
# survival target is the AFT NLL. 10c ruled that metric out as a headline for stint life
# because it scores a MIXTURE -- green-pit tyre-limit endings and exogenous SC/VSC/red
# interruptions in one likelihood -- and 10d then found the shipped params had been
# selected on it, under the other label construction, with the eval season inside the
# validation folds. The two alternatives below are the metrics 10d actually used, scored
# on the green-pit stratum of each validation fold, and both are lower-is-better:
#
#   green_pit_brier        -- IPCW-Brier. A proper scoring rule: it prices the LEVEL of the
#                             predictions as well as their spread, which |slope - 1| does not.
#   green_pit_calibration  -- |calibration slope - 1|. The dispersion of the risk score, and
#                             the thing 10d's winning arm moved. On its own it is blind to
#                             the level bias 10d found survives every fix, which is exactly
#                             why 10e declares both and reports the difference.
#
# Green-pit rows are uncensored under BOTH label constructions (a stint that ended in a
# green-flag tyre change is by definition not censored), so these read the predictions only
# -- the label variant enters through what the model was FITTED on, never through the score.
OBJECTIVE_CHOICES = ("headline", "green_pit_brier", "green_pit_calibration")


def _green_pit_objective(objective: str, y, pred, cens, scale, green) -> float:
    """One validation fold's green-pit score. Lower is better for both variants."""
    from ml.src import survival as SV

    m = np.asarray(green, dtype=bool)
    if m.sum() < 20:                      # too thin to score; don't let it vote
        return float("nan")
    y_g = np.asarray(y, dtype=np.float64)[m]
    p_g = np.asarray(pred, dtype=np.float64)[m]
    c_g = np.asarray(cens, dtype=bool)[m]
    if objective == "green_pit_brier":
        return float(SV.ipcw_brier(y_g, p_g, c_g, scale)[0])
    slope = SV.d_calibration(y_g, p_g, c_g, scale)["calibration_slope"]
    return float(abs(slope - 1.0))


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


def _training_side(bundle: F.FeatureBundle):
    """The rows on the training side of the evaluation split, as a boolean mask.

    `evaluate._evaluation_split` is the authority on what the eval set is: a real holdout
    once 2025 ingests, and until then `cv_final_fold` -- train 2018-2023, evaluate 2024.
    Masking to `lap_ids_tr` therefore means "everything the eval fold is not", in both
    modes and with no literal year anywhere. It is imported lazily because evaluate.py
    pulls in matplotlib and the whole elevation stack, which a default `--target all` run
    has no use for.
    """
    from ml.src import evaluate as EV

    split = EV._evaluation_split(bundle)
    keep = np.isin(bundle.meta_train["lap_id"].to_numpy(), split.lap_ids_tr)
    return keep, split


def tune_one(target: str, *, trials: int, folds: int, version: str, subsample_rows: int = 0,
             censoring_variant: str = "standard", objective: str = "headline",
             honest_split: bool = False, studies_dir: Path = STUDIES_DIR,
             best_params_path: Path | None = None, refit: bool = True) -> dict:
    spec = S.TARGET_BY_NAME[target]
    bundle = F.load_features(target=target, censoring_variant=censoring_variant)
    X, y = bundle.X_train, bundle.y_train.to_numpy()
    seasons = bundle.groups_train.to_numpy()
    meta = bundle.meta_train
    green = None

    # 10e: confine the folds to the training side of the evaluation split, so the season
    # every downstream number is reported on cannot also be a validation fold here. Without
    # it, `bundle.training_seasons` is EVERY ingested season -- 2018-2024 today -- and the
    # eval season votes on its own hyperparameters. That is defect (c) of the three 10d
    # found in this function; the other two are `censoring_variant` (defaulted, never
    # chosen) and `objective` (the mixture NLL).
    fold_seasons = bundle.training_seasons
    if honest_split:
        keep, split = _training_side(bundle)
        X, y = X[keep].reset_index(drop=True), y[keep]
        seasons, meta = seasons[keep], meta[keep].reset_index(drop=True)
        fold_seasons = sorted(set(int(s) for s in seasons))
        print(f"[{target}] honest split: folds confined to {fold_seasons} "
              f"({len(y)} rows); {split.mode} eval season {split.eval_season} held out")
    elif spec.kind == "survival":
        print(f"[{target}] WARNING folds run over {bundle.training_seasons}, which includes "
              f"the season `evaluate.py` reports on. Hyperparameters selected here have seen "
              f"the eval fold -- pass --honest-split (see work/10-competing-risks.md, 10d/10e).")

    # Optional row subsample for the SEARCH only (the final refit uses full data).
    if subsample_rows and subsample_rows < len(X):
        rng = np.random.default_rng(S.RANDOM_STATE)
        idx = np.sort(rng.choice(len(X), size=subsample_rows, replace=False))
        X, y, seasons = X.iloc[idx].reset_index(drop=True), y[idx], seasons[idx]
        meta = meta.iloc[idx].reset_index(drop=True)

    if objective != "headline":
        if spec.kind != "survival":
            raise ValueError(f"objective {objective!r} is green-pit stratified and only "
                             f"defined for the survival target, not {target!r}")
        from ml.src import evaluate_10c as E10
        green = E10.get_cause_labels(meta["lap_id"].to_numpy(), meta) == "green_pit"
        print(f"[{target}] selecting on {objective} over {int(green.sum())} green-pit rows "
              f"of {len(green)} ({green.mean():.1%}); censoring_variant={censoring_variant}")

    maximize = spec.kind == "classification"
    folds_idx = list(T._season_folds(seasons, fold_seasons, folds))

    def objective_fn(trial: optuna.Trial) -> float:
        params = _suggest(trial, spec)
        scale = params.get("aft_loss_distribution_scale", S.AFT_SCALE_DEFAULT)
        scores, diagnostics = [], []
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
            pred = model.predict(X.iloc[val])
            name, headline = T._headline(spec, y[val], pred, meta.iloc[val], scale)
            if objective == "headline":
                value = headline
            else:
                value = _green_pit_objective(objective, y[val], pred,
                                             meta.iloc[val][S.STINT_LIFE_CENSOR_COLUMN]
                                             .to_numpy(dtype=bool), scale, green[val])
                diagnostics.append(headline)
            if not np.isfinite(value):    # an unscoreable fold must not read as a good one
                raise optuna.TrialPruned()
            scores.append(value)
            trial.report(float(np.mean(scores)), step=step)
            if trial.should_prune():
                raise optuna.TrialPruned()
        # The metric the search is NOT selecting on, carried per trial. It is what lets a
        # later reader ask whether the objective change moved the choice, or only the label.
        if diagnostics:
            trial.set_user_attr(f"mean_{name}", float(np.mean(diagnostics)))
        return float(np.mean(scores))

    studies_dir = Path(studies_dir)
    studies_dir.mkdir(parents=True, exist_ok=True)
    study_name = S.optuna_study_name(target, version)
    study = optuna.create_study(
        direction="maximize" if maximize else "minimize",
        sampler=optuna.samplers.TPESampler(seed=S.RANDOM_STATE),
        pruner=optuna.pruners.MedianPruner(n_warmup_steps=1),
        study_name=study_name,
        storage=f"sqlite:///{studies_dir / f'{study_name}.db'}",
        load_if_exists=True,
    )
    study.optimize(objective_fn, n_trials=trials, show_progress_bar=False)

    best_path = Path(best_params_path) if best_params_path is not None \
        else MODELS_DIR / f"{target}_best_params.json"
    best_path.parent.mkdir(parents=True, exist_ok=True)
    best_path.write_text(json.dumps(study.best_params, indent=2, sort_keys=True))
    metric_name = objective if objective != "headline" else (
        "macro_f1" if maximize else "pinball/rmse")
    print(f"[{target}] best {metric_name}={study.best_value:.4f} "
          f"({len(study.trials)} trials) -> {best_path}")

    # A search that ends on its own edge prints a best value like any other. Say so.
    pinned = boundary_params(study.best_params, spec)
    if pinned:
        named = ", ".join(f"{k}={study.best_params[k]} ({side})" for k, side in sorted(pinned.items()))
        print(f"[{target}] stopped on a search-space boundary: {named}. The optimum of "
              f"these {len(study.trials)} trials is where the space ran out, which is not "
              f"the same as convergence -- probe past the bound before reading it either way.")

    # Chain the production refit on the FULL training set (train.py runs its own 5-fold CV log).
    # `--no-refit` exists so a search can be RUN and READ without republishing an artefact:
    # a re-search is a measurement until someone rules on it, and the rule in this repo is
    # that landing is a separate, human decision.
    if refit:
        T.train_one(target, version=version, params=study.best_params, smoke=False,
                    censoring_variant=censoring_variant)
    else:
        print(f"[{target}] --no-refit: {best_path} written, no artefact republished")
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
    ap.add_argument("--censoring-variant", default="standard", choices=["standard", "10b"],
                    help="stint-life label construction to SEARCH against (default: standard, "
                         "the realised stint ending -- see D5)")
    ap.add_argument("--objective", default="headline", choices=list(OBJECTIVE_CHOICES),
                    help="selection metric (default: headline = train._headline, i.e. the "
                         "mixture AFT NLL for stint life, which 10c ruled out as a headline)")
    ap.add_argument("--honest-split", action="store_true",
                    help="confine the folds to the training side of evaluate.py's own split, "
                         "so the eval season cannot vote on its own hyperparameters")
    ap.add_argument("--studies-dir", default=str(STUDIES_DIR),
                    help="where the Optuna study DB lives")
    ap.add_argument("--best-params-out", default=None,
                    help="write best params here instead of ml/models/<target>_best_params.json")
    ap.add_argument("--no-refit", action="store_true",
                    help="do not chain train.train_one; leaves every shipped artefact alone")
    args = ap.parse_args()
    targets = [t.name for t in S.PRODUCTION_TARGETS] if args.target == "all" else [args.target]
    for t in targets:
        tune_one(t, trials=args.trials, folds=args.folds, version=args.version,
                 subsample_rows=args.subsample_rows,
                 censoring_variant=args.censoring_variant, objective=args.objective,
                 honest_split=args.honest_split, studies_dir=Path(args.studies_dir),
                 best_params_path=args.best_params_out, refit=not args.no_refit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
