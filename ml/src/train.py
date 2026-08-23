"""Shared training engine for all five degradation models (smoke + production).

CLI:
  python -m ml.src.train --target degradation_regressor_p50 --smoke
  python -m ml.src.train --all --smoke
  python -m ml.src.train --target cliff_classifier --version v1 --params <best_params.json>
  python -m ml.src.train --all --tuned          # production retrain (see --tuned below)

Note on --params: without it (and without --smoke) this trains at SMOKE_DEFAULTS, which
is *not* a production model. There is no implicit fallback to the tuned parameters, so
`--all` on its own writes five untuned boosters. `--tuned` is the production path: it
resolves each target's own ml/models/<target>_best_params.json and defaults the version
to S.MODEL_VERSION_DEFAULT, retraining at the params tune.py already found without
paying for a fresh 50-trial search.

Builds a season-grouped expanding-window CV (TimeSeriesSplit over whole seasons -
never row-level), reports the per-target headline metric, then refits on the full
training set and writes <target>_<version>.bst + a training-log JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sklearn
import xgboost as xgb
from sklearn.metrics import f1_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.utils.class_weight import compute_class_weight

from ml.src import features as F
from ml.src import schema as S
from ml.src import survival as SV

MODELS_DIR = Path("ml/models")
LOGS_DIR = MODELS_DIR / "training_logs"
SMOKE_DEFAULTS = dict(n_estimators=120, max_depth=4, learning_rate=0.1)


# ─── Metrics ─────────────────────────────────────────────────────────────────────
def pinball_loss(y, pred, alpha: float) -> float:
    d = y-pred
    return float(np.mean(np.maximum(alpha * d, (alpha-1) * d)))


def rmse(y, pred) -> float:
    return float(np.sqrt(np.mean((y-pred) ** 2)))


def _headline(spec: S.TargetSpec, y, pred, meta=None, scale: float | None = None) -> tuple[str, float]:
    if spec.kind == "quantile":
        return "pinball", pinball_loss(y, pred, spec.quantile_alpha)
    if spec.kind == "classification":
        return "macro_f1", float(f1_score(y, pred, average="macro"))
    if spec.kind == "survival":
        cens = meta[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
        return "aft_nloglik", SV.aft_nloglik(y, pred, cens, scale or S.AFT_SCALE_DEFAULT)
    return "rmse", rmse(y, pred)


# ─── Model construction ──────────────────────────────────────────────────────────
class AFTBooster:
    """xgb.train wrapper exposing the slice of the sklearn surface train.py uses.

    survival:aft reads its labels from the DMatrix (label_lower_bound /
    label_upper_bound), and the sklearn API has no way to set them --
    XGBRegressor(objective="survival:aft").fit(X, y) raises
    `Check failed: info.labels_lower_bound_.Size() == ndata (0 vs N)` the moment
    it runs. So this owns a Booster directly and speaks fit / predict /
    save_model, and train_one does not have to care which API it got.

    predict() returns the MEDIAN remaining life in laps: for a log-normal the
    median is exp(margin), and the AFT_LABEL_SHIFT is subtracted back off here so
    callers see laps. predict_quantile() gives any other percentile from the same
    fit -- the scale is the only extra number needed.
    """

    def __init__(self, spec: S.TargetSpec, params: dict):
        p = dict(params)
        # n_estimators is a sklearn-ism; xgb.train takes it as num_boost_round.
        self.num_boost_round = int(p.pop("n_estimators", 100))
        self.scale = float(p.pop("aft_loss_distribution_scale", S.AFT_SCALE_DEFAULT))
        self.params = {
            "objective": spec.objective,
            "eval_metric": "aft-nloglik",
            "aft_loss_distribution": S.AFT_DISTRIBUTION,
            "aft_loss_distribution_scale": self.scale,
            "tree_method": "hist",
            "seed": S.RANDOM_STATE,
            "nthread": os.cpu_count(),
            **p,
        }
        self.booster: xgb.Booster | None = None
        self.feature_names: list[str] | None = None

    def _dmatrix(self, X, y=None, is_censored=None, sample_weight=None) -> xgb.DMatrix:
        d = xgb.DMatrix(X, feature_names=list(X.columns), missing=np.nan)
        if y is not None:
            lower, upper = SV.aft_bounds(y, is_censored)
            d.set_float_info("label_lower_bound", lower)
            d.set_float_info("label_upper_bound", upper)
        if sample_weight is not None:
            d.set_weight(sample_weight)
        return d

    def fit(self, X, y, sample_weight=None, is_censored=None):
        if is_censored is None:
            raise ValueError(
                "AFTBooster.fit needs is_censored: without it every row would be "
                "treated as an observed death and the survival framing is inert.")
        self.feature_names = list(X.columns)
        d = self._dmatrix(X, y, is_censored, sample_weight)
        self.booster = xgb.train(self.params, d, num_boost_round=self.num_boost_round)
        return self

    def predict_margin(self, X) -> np.ndarray:
        return self.booster.predict(self._dmatrix(X), output_margin=True).astype(np.float64)

    def predict(self, X) -> np.ndarray:
        """Median remaining stint life, in laps, clipped at 0."""
        return SV.laps_from_margin(self.predict_margin(X), self.scale)

    def predict_quantile(self, X, q: float) -> np.ndarray:
        """q-th percentile of the fitted log-normal, in laps, clipped at 0."""
        return SV.laps_from_margin(self.predict_margin(X), self.scale, q)

    def save_model(self, path: str) -> None:
        self.booster.save_model(path)


def _make_model(spec: S.TargetSpec, params: dict):
    common = dict(tree_method="hist", random_state=S.RANDOM_STATE,
                  n_jobs=os.cpu_count(), **params)
    if spec.kind == "quantile":
        return xgb.XGBRegressor(objective="reg:quantileerror",
                                quantile_alpha=spec.quantile_alpha, **common)
    if spec.kind == "classification":
        return xgb.XGBClassifier(objective="multi:softprob", **common)
    if spec.kind == "survival":
        return AFTBooster(spec, params)
    return xgb.XGBRegressor(objective="reg:squarederror", **common)


def _fit(model, spec: S.TargetSpec, X, y, meta):
    """One fit call whichever API `model` came from. The survival path needs the
    censoring flag, which lives in meta and has no sklearn equivalent."""
    w = _sample_weight(spec, y, meta)
    if spec.kind == "survival":
        return model.fit(X, y, sample_weight=w,
                         is_censored=meta[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool))
    return model.fit(X, y, sample_weight=w)


def _sample_weight(spec: S.TargetSpec, y, meta=None) -> np.ndarray | None:
    """Return per-row training weights.

    Classifier: balanced class weights for minority cliff-window recall.
    Quantile regressors (C2): IPW survival weights from meta["survival_weight"]
    so early-pitted (degraded) stints are not under-counted at high lap_in_stint.

    Survival (stint life): deliberately None. The censoring that the IPW weights
    approximate for the quantile models is now represented exactly, as an interval
    label -- weighting on top of that would count it twice.
    """
    if spec.kind == "classification":
        classes = np.unique(y)
        w = compute_class_weight("balanced", classes=classes, y=y)
        lut = dict(zip(classes, w))
        return np.asarray([lut[v] for v in y], dtype=np.float32)
    if spec.kind == "quantile" and meta is not None and "survival_weight" in meta.columns:
        return meta["survival_weight"].to_numpy(dtype=np.float32)
    return None


def _season_folds(seasons: np.ndarray, training_seasons: list[int], n_splits: int):
    """Yield (train_idx, val_idx) where whole seasons move together (expanding window)."""
    uniq = np.asarray(sorted(training_seasons))
    # An expanding window over whole seasons needs one season to validate each fold, so
    # n_splits folds need n_splits+1 seasons. Fold down to what the data actually carries
    # rather than dying: a fixture-built warehouse (CI: 3 seasons) can't feed the
    # production default of 5. No-op on the real warehouse (7 training seasons).
    usable = min(n_splits, len(uniq)-1)
    if usable < 1:
        raise ValueError(
            f"season-grouped CV needs >= 2 training seasons, got {len(uniq)}: {list(uniq)}"
        )
    if usable < n_splits:
        print(f"[cv] {len(uniq)} training seasons supports {usable} folds, not {n_splits}")
    for tr_seasons_idx, val_seasons_idx in TimeSeriesSplit(n_splits=usable).split(uniq):
        tr = np.isin(seasons, uniq[tr_seasons_idx])
        val = np.isin(seasons, uniq[val_seasons_idx])
        yield np.where(tr)[0], np.where(val)[0]


# ─── Train one target ──────────────────────────────────────────────────────────
def train_one(target: str, *, version: str, params: dict | None,
              smoke: bool, n_splits: int = 5) -> dict:
    spec = S.TARGET_BY_NAME[target]
    bundle = F.load_features(target=target, persist_encoders=True)
    X, y = bundle.X_train, bundle.y_train.to_numpy()
    seasons = bundle.groups_train.to_numpy()

    fit_params = dict(SMOKE_DEFAULTS) if (smoke or not params) else dict(params)
    t0 = time.time()

    scale = float(fit_params.get("aft_loss_distribution_scale", S.AFT_SCALE_DEFAULT))

    fold_metrics = []
    for k, (tr, val) in enumerate(_season_folds(seasons, bundle.training_seasons, n_splits)):
        model = _make_model(spec, fit_params)
        _fit(model, spec, X.iloc[tr], y[tr], bundle.meta_train.iloc[tr])
        pred = model.predict(X.iloc[val])
        meta_val = bundle.meta_train.iloc[val]
        name, value = _headline(spec, y[val], pred, meta_val, scale)
        fold = {"fold": k, "val_season": int(seasons[val][0]), name: value}
        if spec.kind == "survival":
            # The headline is a likelihood, which says nothing about ranking. C is
            # reported beside it every fold so a fit that improves the NLL while
            # scrambling the order cannot pass unnoticed.
            cens = meta_val[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
            fold["c_index"] = SV.c_index(y[val], pred, cens)
            fold["censored_share"] = float(cens.mean())
        fold_metrics.append(fold)

    headline_name = fold_metrics[0].keys()-{"fold", "val_season", "c_index", "censored_share"}
    headline_name = next(iter(headline_name))
    headline = float(np.mean([m[headline_name] for m in fold_metrics]))

    # Refit on the full training set → the shipped booster.
    final = _make_model(spec, fit_params)
    _fit(final, spec, X, y, bundle.meta_train)
    fit_seconds = round(time.time()-t0, 2)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    bst_path = MODELS_DIR / f"{S.artefact_name(spec, version)}.bst"
    final.save_model(str(bst_path))

    log = {
        "target": target, "version": version, "smoke": smoke,
        "objective": spec.objective, "quantile_alpha": spec.quantile_alpha,
        **({"aft": {"distribution": S.AFT_DISTRIBUTION, "scale": scale,
                    "label_shift": S.AFT_LABEL_SHIFT,
                    "c_index_cv": float(np.mean([m["c_index"] for m in fold_metrics])),
                    "censored_share": float(
                        bundle.meta_train[S.STINT_LIFE_CENSOR_COLUMN].mean())}}
           if spec.kind == "survival" else {}),
        "headline_metric": headline_name, "headline_cv": headline,
        "fold_metrics": fold_metrics, "params": fit_params,
        "n_train_rows": int(len(X)), "n_features": len(bundle.feature_columns),
        "training_seasons": bundle.training_seasons,
        "fingerprint": bundle.fingerprint, "random_state": S.RANDOM_STATE,
        "fit_seconds": fit_seconds,
        "versions": {"xgboost": xgb.__version__, "sklearn": sklearn.__version__},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "bst_path": str(bst_path),
    }
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    (LOGS_DIR / f"{target}_{version}_{ts}.json").write_text(json.dumps(log, indent=2))
    print(f"[{target}] {headline_name}_cv={headline:.4f}  rows={len(X)}  "
          f"{fit_seconds}s  -> {bst_path.name}")
    return log


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=[t.name for t in S.PRODUCTION_TARGETS])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--version", default=None,
                    help="artefact version (default: v1, or MODEL_VERSION_DEFAULT with --tuned)")
    ap.add_argument("--params", help="best_params.json from tune.py")
    ap.add_argument("--tuned", action="store_true",
                    help="retrain each target at its own ml/models/<target>_best_params.json, "
                         "at MODEL_VERSION_DEFAULT. The production retrain path.")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--n-estimators", type=int)
    ap.add_argument("--max-depth", type=int)
    args = ap.parse_args()

    if args.tuned and (args.smoke or args.params):
        ap.error("--tuned resolves params per target; do not combine it with --smoke or --params")

    params = json.loads(Path(args.params).read_text()) if args.params else None
    if args.n_estimators or args.max_depth:  # CI tiny-smoke overrides
        params = dict(params or SMOKE_DEFAULTS)
        if args.n_estimators:
            params["n_estimators"] = args.n_estimators
        if args.max_depth:
            params["max_depth"] = args.max_depth

    if args.smoke:
        version = "smoke"
    elif args.version:
        version = args.version
    else:
        version = S.MODEL_VERSION_DEFAULT if args.tuned else "v1"

    targets = [t.name for t in S.PRODUCTION_TARGETS] if args.all else [args.target]
    if not targets or targets == [None]:
        ap.error("pass --target <name> or --all")

    if args.tuned:  # resolve every path up front: a missing file must not half-train the set
        tuned_paths = {t: MODELS_DIR / f"{t}_best_params.json" for t in targets}
        missing = sorted(str(p) for p in tuned_paths.values() if not p.exists())
        if missing:
            ap.error("--tuned needs tuned params for every target; missing: " + ", ".join(missing))

    for t in targets:
        target_params = json.loads(tuned_paths[t].read_text()) if args.tuned else params
        train_one(t, version=version, params=target_params, smoke=args.smoke)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
