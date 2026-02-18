"""Evaluation: honest metrics, strong baselines, cohorts, calibration, and the §7 elevations.

CLI:
  python -m ml.src.evaluate --all                 # evaluate every production target
  python -m ml.src.evaluate --target cliff_classifier
  python -m ml.src.evaluate --all --version smoke  # CI-fast (smoke params)

The headline contract (the gate): **every model must beat its per-cohort baseline on the
headline metric** (pinball ↓ for quantiles, macro-F1 ↑ for the classifier, RMSE ↓ for stint-life).
`tests/test_evaluate.py::test_model_beats_baseline_overall` reads the JSON this writes.

Holdout policy (§2 / §16.6): the designated holdout is 2025, *not yet ingested* → there is no live
holdout today. The evaluation set is therefore the **final TimeSeriesSplit fold**-train on
2018–2023, evaluate on 2024 (the most-recent, holdout-shaped unseen season). The moment 2025 ingests
this switches to a true-holdout evaluation with **zero code changes** (`_evaluation_split` detects a
populated holdout and uses it instead). Eval models are refit on the honest split and are distinct
from the shipped `_v1.bst` (which use all seasons-correct for production scoring).

Each §7 elevation (conformal coverage, SHAP+permutation, ablation+learning curve, behaviour audit,
adversarial leakage probe, biggest-misses) is wrapped so a failure degrades to a logged note and
never blocks the core headline/baseline/cohort gate. Artefacts (PNGs, parquets) land in ml/artefacts/
(gitignored, regen-able); the metrics JSON is the single feed for card.py (M6).
"""
from __future__ import annotations

import argparse
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # headless: no display, deterministic file output
import matplotlib.pyplot as plt  # noqa: E402

from ml.src import features as F  # noqa: E402
from ml.src import schema as S  # noqa: E402
from ml.src import train as T  # noqa: E402

warnings.filterwarnings("ignore")

ARTEFACTS_DIR = Path("ml/artefacts")
MODELS_DIR = Path("ml/models")
EVAL_METRICS_PATH = ARTEFACTS_DIR / "evaluation_metrics.json"

MIN_COHORT_N = 30          # cells below this fold into "_other" (R5)
AGE_BUCKET_WIDTH = 5       # laps per age_in_stint bucket for the baseline key
CONFORMAL_TARGET = 0.80    # quantile interval [p10, p90] nominal coverage (§7.1)
SHAP_SAMPLE = 1000
PERM_SAMPLE = 3000
PERM_REPEATS = 5

# Heavy elevations (ablation / learning-curve / SHAP / PDP) run on the headline model of each
# family; the quantile siblings share p50's feature structure, so we don't triple the cost.
ELEVATION_TARGETS = frozenset(
    {"degradation_regressor_p50", "cliff_classifier", "stint_life_regressor"})

# Raw cohort/baseline dimensions, keyed by lap_id (read-only, once per run).
COHORT_DIMS = (
    "compound", "is_rain_lap", "age_in_stint", "lap_in_stint",
    "next_lap_degradation_jump_s", "laps_until_cliff_class",
    "circuit_key", "race_year", "constructor_id",
)


# ─── Metric direction helpers ──────────────────────────────────────────────────
def _higher_is_better(spec: S.TargetSpec) -> bool:
    return spec.kind == "classification"  # macro-F1 ↑; pinball / rmse ↓


def _is_better(model_val: float, base_val: float, higher_is_better: bool) -> bool:
    return model_val > base_val if higher_is_better else model_val < base_val


def _headline_metric_name(spec: S.TargetSpec) -> str:
    return {"quantile": "pinball", "classification": "macro_f1"}.get(spec.kind, "rmse")


def _score(spec: S.TargetSpec, y_true: np.ndarray, pred: np.ndarray) -> float:
    """Model/baseline headline on a row set. pred is class-index for the classifier."""
    _, value = T._headline(spec, y_true, pred)
    return value


# ─── Eval split: true holdout if populated, else the final CV fold (today) ──────
class EvalSplit:
    def __init__(self, mode: str, eval_season: int | None,
                 X_tr, y_tr, seasons_tr, lap_ids_tr,
                 X_ev, y_ev, lap_ids_ev):
        self.mode = mode                  # "holdout" | "cv_final_fold"
        self.eval_season = eval_season
        self.X_tr, self.y_tr = X_tr, y_tr
        self.seasons_tr = seasons_tr
        self.lap_ids_tr = np.asarray(lap_ids_tr)
        self.X_ev, self.y_ev = X_ev, y_ev
        self.lap_ids_ev = np.asarray(lap_ids_ev)


def _evaluation_split(bundle: F.FeatureBundle) -> EvalSplit:
    """Live holdout when 2025 has ingested; until then the final TimeSeriesSplit fold (2024)."""
    holdout_live = (len(bundle.X_holdout) > 0 and bundle.y_holdout is not None
                    and bundle.y_holdout.notna().any())
    if holdout_live:
        keep = bundle.y_holdout.notna().to_numpy()
        return EvalSplit(
            "holdout", bundle.holdout_season,
            bundle.X_train, bundle.y_train.to_numpy(),
            bundle.groups_train.to_numpy(), bundle.meta_train["lap_id"].to_numpy(),
            bundle.X_holdout[keep].reset_index(drop=True),
            bundle.y_holdout[keep].to_numpy(),
            bundle.meta_holdout[keep]["lap_id"].to_numpy())

    seasons = bundle.groups_train.to_numpy()
    folds = list(T._season_folds(seasons, bundle.training_seasons, n_splits=5))
    tr, ev = folds[-1]  # final fold: train ⊂ early seasons, validate on the latest (2024)
    y = bundle.y_train.to_numpy()
    lap_ids = bundle.meta_train["lap_id"].to_numpy()
    return EvalSplit(
        "cv_final_fold", int(seasons[ev][0]),
        bundle.X_train.iloc[tr].reset_index(drop=True), y[tr],
        seasons[tr], lap_ids[tr],
        bundle.X_train.iloc[ev].reset_index(drop=True), y[ev], lap_ids[ev])


# ─── Cohort dimension table (raw, keyed by lap_id) ──────────────────────────────
def load_cohort_dims(duckdb_path: str = S.DUCKDB_PATH) -> pd.DataFrame:
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        df = con.execute(
            f"SELECT {', '.join(COHORT_DIMS)} , lap_id FROM {S.MART}").df()
    finally:
        con.close()
    df["age_bucket"] = np.where(
        df["age_in_stint"].notna(),
        (df["age_in_stint"].fillna(0) // AGE_BUCKET_WIDTH).astype("Int64"), -1)
    return df.set_index("lap_id")


# ─── Baselines (one strong anchor per family; §5.5) ─────────────────────────────
def _cell_lookup(train_dims: pd.DataFrame, value_col: str, agg) -> dict:
    """(compound, circuit_key, age_bucket) → agg(value); used with compound + global fallback."""
    g = train_dims.groupby(["compound", "circuit_key", "age_bucket"], observed=True)[value_col]
    return (g.quantile(agg) if isinstance(agg, float) else g.mean()).to_dict()


def _apply_cell_baseline(train_dims, eval_dims, value_col, agg) -> np.ndarray:
    """Cell agg → compound-level agg fallback → global agg fallback (never NaN)."""
    cell = _cell_lookup(train_dims, value_col, agg)
    by_comp = train_dims.groupby("compound", observed=True)[value_col]
    comp = (by_comp.quantile(agg) if isinstance(agg, float) else by_comp.mean()).to_dict()
    glob = (float(train_dims[value_col].quantile(agg)) if isinstance(agg, float)
            else float(train_dims[value_col].mean()))
    out = np.empty(len(eval_dims), dtype=np.float64)
    for i, (_, r) in enumerate(eval_dims.iterrows()):
        key = (r["compound"], r["circuit_key"], r["age_bucket"])
        out[i] = cell.get(key, comp.get(r["compound"], glob))
    return out


def baseline_predictions(spec: S.TargetSpec, train_dims: pd.DataFrame,
                         eval_dims: pd.DataFrame) -> np.ndarray:
    """Per family: cell group-mean (p50) / empirical pctile (p10/p90) / majority class /
    (stint_length − lap_in_stint)/2 (stint-life, knowingly leakage-shaped to be strong)."""
    if spec.name == "degradation_regressor_p50":
        return _apply_cell_baseline(train_dims, eval_dims, S.DEGRADATION_TARGET, agg="mean")
    if spec.name == "degradation_regressor_p10":
        return _apply_cell_baseline(train_dims, eval_dims, S.DEGRADATION_TARGET, agg=0.10)
    if spec.name == "degradation_regressor_p90":
        return _apply_cell_baseline(train_dims, eval_dims, S.DEGRADATION_TARGET, agg=0.90)
    if spec.kind == "classification":
        labels = list(S.CLIFF_CLASS_LABELS)
        maj = train_dims["laps_until_cliff_class"].mode().iloc[0]
        return np.full(len(eval_dims), labels.index(maj), dtype=np.int64)
    # stint-life: (stint_length_laps − lap_in_stint)/2, clipped ≥ 0
    half = (eval_dims["stint_length_laps"]-eval_dims["lap_in_stint"]) / 2.0
    return np.clip(half.to_numpy(dtype=np.float64), 0, None)


# ─── Cohort metric breakdown ────────────────────────────────────────────────────
def _cohort_table(spec: S.TargetSpec, dim_name: str, dims: pd.DataFrame,
                  y_true: np.ndarray, model_pred: np.ndarray,
                  base_pred: np.ndarray) -> tuple[dict, list]:
    """Per-cohort model-vs-baseline headline; cells with n<30 fold into '_other'. Returns
    (table, underperformers)."""
    hib = _higher_is_better(spec)
    series = dims[dim_name].astype("object").fillna("__null__").to_numpy()
    counts = pd.Series(series).value_counts()
    small = set(counts[counts < MIN_COHORT_N].index)
    keys = np.array(["_other" if v in small else v for v in series], dtype=object)

    table, under = {}, []
    for key in sorted(set(keys), key=str):
        m = keys == key
        if m.sum() == 0:
            continue
        mv = _score(spec, y_true[m], model_pred[m])
        bv = _score(spec, y_true[m], base_pred[m])
        beats = _is_better(mv, bv, hib)
        table[str(key)] = {"n": int(m.sum()), "model": mv, "baseline": bv, "beats_baseline": beats}
        if not beats:
            under.append({"dimension": dim_name, "cohort": str(key),
                          "n": int(m.sum()), "model": mv, "baseline": bv})
    return table, under


# ─── Calibration / split-conformal coverage (§7.1) ──────────────────────────────
def calibration_report(y: np.ndarray, p10: np.ndarray, p90: np.ndarray,
                       seed: int = S.RANDOM_STATE) -> dict:
    """Raw [p10,p90] coverage + a split-conformal (CQR) correction computed post-hoc on the
    eval predictions (calib/test halves)-a finite-sample 0.80 guarantee, no extra fits."""
    inside = (y >= p10) & (y <= p90)
    raw_cov = float(inside.mean())

    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    half = len(y) // 2
    cal, tst = idx[:half], idx[half:]
    scores = np.maximum(p10[cal]-y[cal], y[cal]-p90[cal])  # CQR conformity
    n = len(cal)
    q_level = min(1.0, np.ceil((n + 1) * CONFORMAL_TARGET) / n)
    q = float(np.quantile(scores, q_level, method="higher"))
    conf_inside = (y[tst] >= p10[tst]-q) & (y[tst] <= p90[tst] + q)
    return {
        "nominal": CONFORMAL_TARGET,
        "raw_empirical_coverage": raw_cov,
        "conformal_empirical_coverage": float(conf_inside.mean()),
        "conformal_q": q,
        "mean_interval_width": float(np.mean(p90-p10)),
        "n": int(len(y)),
    }


def _calibration_plot(y, p10, p90, path: Path) -> None:
    order = np.argsort(p10)
    fig, ax = plt.subplots(figsize=(6, 4))
    xs = np.arange(len(y))
    ax.fill_between(xs, np.sort(p10), p90[order], alpha=0.25, label="[p10, p90]")
    ax.scatter(xs, y[order], s=2, color="k", alpha=0.3, label="actual")
    ax.set_xlabel("eval laps (sorted by p10)")
    ax.set_ylabel("degradation jump (s)")
    ax.set_title("Quantile interval vs actual (degradation)")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ─── Dual importance: SHAP + permutation (§7.2) ─────────────────────────────────
def dual_importance(model, spec: S.TargetSpec, X_explain: pd.DataFrame,
                    X_perm: pd.DataFrame, y_perm: np.ndarray) -> dict:
    import shap
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import make_scorer, mean_pinball_loss

    feats = list(X_explain.columns)
    expl = shap.TreeExplainer(model)
    sv = expl.shap_values(X_explain)
    sv = np.asarray(sv)
    # multiclass → (n, f, c) or list; collapse classes + rows to mean|.|
    shap_imp = np.abs(sv).mean(axis=tuple(i for i in range(sv.ndim) if i != sv.ndim-1)) \
        if sv.ndim == 3 else np.abs(sv).mean(axis=0)
    shap_rank = sorted(zip(feats, [float(v) for v in np.ravel(shap_imp)]),
                       key=lambda t: t[1], reverse=True)

    if spec.kind == "classification":
        scoring = "f1_macro"
    elif spec.kind == "quantile":
        scoring = make_scorer(mean_pinball_loss, alpha=spec.quantile_alpha,
                              greater_is_better=False)
    else:
        scoring = "neg_root_mean_squared_error"
    perm = permutation_importance(model, X_perm, y_perm, n_repeats=PERM_REPEATS,
                                  random_state=S.RANDOM_STATE, scoring=scoring, n_jobs=-1)
    perm_rank = sorted(zip(feats, [float(v) for v in perm.importances_mean]),
                       key=lambda t: t[1], reverse=True)

    shap_top = [f for f, _ in shap_rank[:5]]
    perm_top = [f for f, _ in perm_rank[:5]]
    disagree = sorted(set(shap_top) ^ set(perm_top))
    note = ("SHAP and permutation top-5 agree" if not disagree
            else "top-5 differ on: " + ", ".join(disagree)
            + "-likely correlated features or leakage pressure")
    return {"shap_top5": shap_rank[:5], "permutation_top5": perm_rank[:5],
            "agreement_note": note}


# ─── Ablation + learning curve (§7.3) ────────────────────────────────────────────
def ablation(spec: S.TargetSpec, params: dict, X_tr, y_tr, X_ev, y_ev,
             target: str) -> list[dict]:
    full = _fit(spec, params, X_tr, y_tr)
    base = _score(spec, y_ev, _predict_index(spec, full, X_ev))
    rows = [{"group": "<none>", "headline": base, "delta_vs_full": 0.0}]
    for grp, cols in S.FEATURE_GROUPS.items():
        keep = [c for c in X_tr.columns if c not in cols]
        if not keep:
            continue
        m = _fit(spec, params, X_tr[keep], y_tr)
        val = _score(spec, y_ev, _predict_index(spec, m, X_ev[keep]))
        rows.append({"group": grp, "headline": val, "delta_vs_full": val-base})
    pd.DataFrame(rows).to_parquet(ARTEFACTS_DIR / f"ablation_{target}.parquet", index=False)
    return rows


def learning_curve(spec: S.TargetSpec, params: dict, X_tr, y_tr, seasons_tr,
                   X_ev, y_ev, target: str) -> list[dict]:
    seasons = sorted(set(int(s) for s in seasons_tr))
    rows = []
    for i in range(len(seasons)):
        used = seasons[: i + 1]
        m = np.isin(seasons_tr, used)
        if m.sum() < 100:
            continue
        model = _fit(spec, params, X_tr[m], y_tr[m])
        val = _score(spec, y_ev, _predict_index(spec, model, X_ev))
        rows.append({"train_seasons": used, "n_train": int(m.sum()), "headline": val})
    if rows:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot([r["n_train"] for r in rows], [r["headline"] for r in rows], "o-")
        ax.set_xlabel("training rows (expanding seasons)")
        ax.set_ylabel(_headline_metric_name(spec))
        ax.set_title(f"Learning curve-{target}")
        fig.tight_layout()
        fig.savefig(ARTEFACTS_DIR / f"learning_curve_{target}.png", dpi=110)
        plt.close(fig)
    return rows


# ─── Behaviour audit: PDP top-3 + monotonicity sanity (§7.4) ────────────────────
def behaviour_audit(model, spec: S.TargetSpec, X_ev: pd.DataFrame,
                    top_features: list[str], target: str) -> dict:
    from sklearn.inspection import PartialDependenceDisplay
    result: dict = {}
    top3 = [f for f in top_features if f in X_ev.columns][:3]
    # multi-class PDP requires a target class; explain the imminent-cliff class (0_to_2).
    pdp_kwargs = {"target": 0} if spec.kind == "classification" else {}
    try:
        fig, ax = plt.subplots(figsize=(9, 3))
        PartialDependenceDisplay.from_estimator(model, X_ev, top3, ax=ax, **pdp_kwargs)
        fig.suptitle(f"PDP top-3-{target}", fontsize=9)
        fig.tight_layout()
        fig.savefig(ARTEFACTS_DIR / f"pdp_{target}.png", dpi=110)
        plt.close(fig)
        result["pdp_features"] = top3
    except Exception as e:  # PDP is illustrative, never a gate
        result["pdp_error"] = str(e)

    # Monotonicity sanity (regressors only a class index has no ordered magnitude):
    # holding others at the median, predicted degradation should not DECREASE as
    # laps_past_cliff grows (more laps past the cliff ⇒ ≥ the pace penalty).
    if spec.kind != "classification" and "laps_past_cliff" in X_ev.columns:
        base = X_ev.median(numeric_only=True)
        grid = np.linspace(float(X_ev["laps_past_cliff"].quantile(0.05)),
                           float(X_ev["laps_past_cliff"].quantile(0.95)), 20)
        probe = pd.DataFrame([base.to_dict()] * len(grid))[list(X_ev.columns)]
        probe["laps_past_cliff"] = grid
        preds = _predict_index(spec, model, probe).astype(float)
        diffs = np.diff(preds)
        result["monotonicity_laps_past_cliff"] = {
            "violations": int((diffs < -1e-6).sum()),
            "n_steps": int(len(diffs)),
            "monotone_non_decreasing": bool((diffs >= -1e-6).all()),
        }
    return result


# ─── Adversarial leakage probe: predict race_year from X (§7.5) ──────────────────
def leakage_probe(X: pd.DataFrame, seasons: np.ndarray) -> dict:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split

    uniq = sorted(set(int(s) for s in seasons))
    y = np.array([uniq.index(int(s)) for s in seasons])
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.25, random_state=S.RANDOM_STATE, stratify=y)
    clf = xgb.XGBClassifier(objective="multi:softprob", num_class=len(uniq),
                            n_estimators=120, max_depth=4, tree_method="hist",
                            random_state=S.RANDOM_STATE, n_jobs=-1)
    clf.fit(Xtr, ytr)
    acc = float((clf.predict(Xte) == yte).mean())
    chance = float(pd.Series(ytr).value_counts(normalize=True).max())  # majority-class accuracy
    return {"accuracy": acc, "majority_class_accuracy": chance,
            "lift_over_chance": acc-chance, "n_seasons": len(uniq),
            "note": ("X carries strong residual temporal signal-race_year recoverable far "
                     "above chance; race_year is correctly excluded from features"
                     if acc-chance > 0.15 else
                     "X carries limited recoverable temporal signal")}


# ─── Biggest misses: most-confident classifier disagreements (§7.8) ─────────────
def biggest_misses(model, X_ev: pd.DataFrame, y_ev: np.ndarray,
                   lap_ids: np.ndarray, n: int = 100) -> int:
    y_ev = np.asarray(y_ev).astype(int)  # cliff label index (Series.map can yield float dtype)
    proba = model.predict_proba(X_ev)
    pred = proba.argmax(axis=1)
    conf = proba.max(axis=1)
    wrong = pred != y_ev
    if not wrong.any():
        return 0
    labels = np.asarray(S.CLIFF_CLASS_LABELS)
    df = pd.DataFrame({
        "lap_id": lap_ids[wrong],
        "true_class": labels[y_ev[wrong]],
        "predicted_class": labels[pred[wrong]],
        "predicted_confidence": conf[wrong],
    }).sort_values("predicted_confidence", ascending=False).head(n)
    df.to_parquet(ARTEFACTS_DIR / "holdout_biggest_misses.parquet", index=False)
    return int(len(df))


# ─── Eval-model fit/predict helpers (refit on the honest split; not the shipped v1) ─
def _fit(spec: S.TargetSpec, params: dict, X, y):
    model = T._make_model(spec, params)
    model.fit(X, y, sample_weight=T._sample_weight(spec, y))
    return model


def _predict_index(spec: S.TargetSpec, model, X) -> np.ndarray:
    """Class index for the classifier; raw prediction otherwise (matches _score)."""
    return model.predict(X)


def _params_for(target: str, version: str) -> dict:
    p = MODELS_DIR / f"{target}_best_params.json"
    if version == "v1" and p.exists():
        return json.loads(p.read_text())
    return dict(T.SMOKE_DEFAULTS)


# ─── Per-target orchestration ───────────────────────────────────────────────────
def evaluate_target(target: str, version: str, dims_all: pd.DataFrame,
                    shared: dict) -> dict:
    spec = S.TARGET_BY_NAME[target]
    bundle = F.load_features(target=target)
    split = _evaluation_split(bundle)
    params = _params_for(target, version)

    # Eval model: refit on the honest training side of the split.
    model = _fit(spec, params, split.X_tr, split.y_tr)
    model_pred = _predict_index(spec, model, split.X_ev)

    # Cohort/baseline dims aligned to the eval rows (and the training side, for the lookup).
    train_dims = dims_all.loc[split.lap_ids_tr].reset_index()
    eval_dims = dims_all.loc[split.lap_ids_ev].reset_index()
    eval_dims["stint_length_laps"] = bundle.meta_train.set_index("lap_id").reindex(
        split.lap_ids_ev)["stint_length_laps"].to_numpy()

    base_pred = baseline_predictions(spec, train_dims, eval_dims)

    hib = _higher_is_better(spec)
    headline = _score(spec, split.y_ev, model_pred)
    baseline = _score(spec, split.y_ev, base_pred)

    cohorts, under = {}, []
    for dim_name in ("compound", "circuit_key", "constructor_id", "is_rain_lap", "race_year"):
        tbl, u = _cohort_table(spec, dim_name, eval_dims, split.y_ev, model_pred, base_pred)
        cohorts[f"by_{dim_name}"] = tbl
        under.extend(u)

    out = {
        "family": spec.family, "kind": spec.kind,
        "headline_metric": _headline_metric_name(spec),
        "headline": headline, "baseline_headline": baseline,
        "beats_baseline": _is_better(headline, baseline, hib),
        "higher_is_better": hib,
        "n_eval_rows": int(len(split.y_ev)),
        "cohorts": cohorts, "underperforming_cohorts": under,
    }
    print(f"[{target}] {out['headline_metric']}: model={headline:.4f} "
          f"baseline={baseline:.4f}  beats={out['beats_baseline']}  "
          f"(mode={split.mode}, eval_season={split.eval_season}, n={len(split.y_ev)})")

    # Stash the degradation trio predictions for the family-level calibration report.
    if spec.family == "degradation_regressor":
        shared.setdefault("degradation", {})[spec.name] = {
            "y": split.y_ev, "pred": model_pred, "lap_ids": split.lap_ids_ev}

    # ── §7 elevations (headline model of each family; each wrapped, never a gate) ──
    if target in ELEVATION_TARGETS:
        try:
            sample_n = min(SHAP_SAMPLE, len(split.X_tr))
            Xs = split.X_tr.sample(sample_n, random_state=S.RANDOM_STATE)
            perm_n = min(PERM_SAMPLE, len(split.X_ev))
            idx = np.random.default_rng(S.RANDOM_STATE).choice(len(split.X_ev), perm_n, replace=False)
            out["importance"] = dual_importance(
                model, spec, Xs, split.X_ev.iloc[idx], split.y_ev[idx])
        except Exception as e:
            out["importance_error"] = str(e)
        try:
            out["ablation"] = ablation(spec, params, split.X_tr, split.y_tr,
                                       split.X_ev, split.y_ev, target)
        except Exception as e:
            out["ablation_error"] = str(e)
        try:
            out["learning_curve"] = learning_curve(spec, params, split.X_tr, split.y_tr,
                                                    split.seasons_tr, split.X_ev, split.y_ev, target)
        except Exception as e:
            out["learning_curve_error"] = str(e)
        try:
            top = [f for f, _ in out.get("importance", {}).get("shap_top5", [])] or \
                list(split.X_ev.columns[:3])
            out["behaviour_audit"] = behaviour_audit(model, spec, split.X_ev, top, target)
        except Exception as e:
            out["behaviour_audit_error"] = str(e)
        if spec.kind == "classification":
            try:
                out["biggest_misses_n"] = biggest_misses(
                    model, split.X_ev, split.y_ev, split.lap_ids_ev)
            except Exception as e:
                out["biggest_misses_error"] = str(e)
    return out


# ─── Top-level run ──────────────────────────────────────────────────────────────
def run(targets: list[str], version: str = S.MODEL_VERSION_DEFAULT) -> dict:
    ARTEFACTS_DIR.mkdir(parents=True, exist_ok=True)
    dims_all = load_cohort_dims()
    shared: dict = {}

    models: dict[str, dict] = {}
    for t in targets:
        models[t] = evaluate_target(t, version, dims_all, shared)

    report: dict = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "holdout_season": int(F.load_features().holdout_season),
        "evaluation_mode": next(iter(
            {m for m in [models[t].get("kind") for t in models]}), None) and "see_models",
        "models": models,
    }
    # Re-derive the split mode from any model run (uniform across targets today).
    sample_bundle = F.load_features(target=targets[0])
    sample_split = _evaluation_split(sample_bundle)
    report["evaluation_mode"] = sample_split.mode
    report["eval_season"] = sample_split.eval_season
    report["holdout_populated"] = sample_split.mode == "holdout"

    # Family-level calibration for the degradation quantile trio (§7.1).
    deg = shared.get("degradation", {})
    if {"degradation_regressor_p10", "degradation_regressor_p50",
            "degradation_regressor_p90"} <= set(deg):
        try:
            y = deg["degradation_regressor_p50"]["y"]
            p10 = deg["degradation_regressor_p10"]["pred"]
            p90 = deg["degradation_regressor_p90"]["pred"]
            lo, hi = np.minimum(p10, p90), np.maximum(p10, p90)  # guard any crossing
            report["calibration"] = calibration_report(y, lo, hi)
            _calibration_plot(y, lo, hi, ARTEFACTS_DIR / "calibration_degradation.png")
        except Exception as e:
            report["calibration_error"] = str(e)

    # Adversarial leakage probe (once, on the p50 training split) (§7.5).
    try:
        b = F.load_features(target="degradation_regressor_p50")
        report["leakage_probe"] = leakage_probe(b.X_train, b.groups_train.to_numpy())
    except Exception as e:
        report["leakage_probe_error"] = str(e)

    all_beat = all(m["beats_baseline"] for m in models.values())
    report["all_models_beat_baseline"] = all_beat
    report["underperforming_cohorts_total"] = sum(
        len(m["underperforming_cohorts"]) for m in models.values())

    EVAL_METRICS_PATH.write_text(json.dumps(report, indent=2, default=_json_default))
    print(f"\nwrote {EVAL_METRICS_PATH}  "
          f"(all_beat_baseline={all_beat}, mode={report['evaluation_mode']}, "
          f"eval_season={report['eval_season']})")
    return report


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"not JSON-serialisable: {type(o)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=[t.name for t in S.PRODUCTION_TARGETS])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--version", default=S.MODEL_VERSION_DEFAULT)
    args = ap.parse_args()
    targets = [t.name for t in S.PRODUCTION_TARGETS] if args.all else (
        [args.target] if args.target else None)
    if not targets:
        ap.error("pass --target <name> or --all")
    report = run(targets, args.version)
    return 0 if all(m["beats_baseline"] for m in report["models"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
