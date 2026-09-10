"""Evaluation: honest metrics, strong baselines, cohorts, calibration, and elevations.

CLI:
  python -m ml.src.evaluate --all                 # evaluate every production target
  python -m ml.src.evaluate --target cliff_classifier
  python -m ml.src.evaluate --all --version smoke  # CI-fast (smoke params)

The headline contract (the gate): **every model must beat its per-cohort baseline on the
headline metric** (pinball ↓ for quantiles, macro-F1 ↑ for the classifier, RMSE ↓ for stint-life).
`tests/test_evaluate.py::test_model_beats_baseline_overall` reads the JSON this writes.

Phase 6 added the two things that gate never carried, and both are written per model:

  * an **attainable ceiling** (`ml/src/ceiling.py`) -- skill as a fraction of what is
    reachable rather than of 1.0. A pinball of 0.199 and a macro-F1 of 0.404 are
    uninterpretable on their own; against the ceiling one of them is a strong result and
    the other is a model that is not bounded by the ceiling at all.
  * an **interval** on the margin (`ml/src/intervals.py`) -- paired t over the season
    folds, plus a bootstrap resampling whole stints. The effective sample is ~7,100
    stints, not ~137,000 laps. `card.py` refuses to write a card whose
    `beats_baseline: true` carries neither.

Holdout policy: the designated holdout is 2025, *not yet ingested* → there is no live
holdout today. The evaluation set is therefore the **final TimeSeriesSplit fold**-train on
2018–2023, evaluate on 2024 (the most-recent, holdout-shaped unseen season). The moment 2025 ingests
this switches to a true-holdout evaluation with **zero code changes** (`_evaluation_split` detects a
populated holdout and uses it instead). Eval models are refit on the honest split and are distinct
from the shipped `_v3.bst` (which use all seasons-correct for production scoring).

Each elevation (conformal coverage, SHAP+permutation, ablation+learning curve, behaviour audit,
adversarial leakage probe, biggest-misses) is wrapped so a failure degrades to a logged note and
never blocks the core headline/baseline/cohort gate. Artefacts (PNGs, parquets) land in ml/artefacts/
(gitignored, regen-able); the metrics JSON is the single feed for card.py.
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

from ml.src import attribution as AT  # noqa: E402
from ml.src import ceiling as CE  # noqa: E402
from ml.src import crps as CR  # noqa: E402
from ml.src import features as F  # noqa: E402
from ml.src import intervals as IV  # noqa: E402
from ml.src import schema as S  # noqa: E402
from ml.src import survival as SV  # noqa: E402
from ml.src import train as T  # noqa: E402

warnings.filterwarnings("ignore")

ARTEFACTS_DIR = Path("ml/artefacts")
MODELS_DIR = Path("ml/models")
EVAL_METRICS_PATH = ARTEFACTS_DIR / "evaluation_metrics.json"

MIN_COHORT_N = 30          # cells below this fold into "_other" (R5)
AGE_BUCKET_WIDTH = 5       # laps per age_in_stint bucket for the baseline key
CONFORMAL_TARGET = 0.80    # quantile interval [p10, p90] nominal coverage
SHAP_SAMPLE = 1000
PERM_SAMPLE = 3000
PERM_REPEATS = 5
CV_SPLITS = 5              # season-grouped folds; the paired interval's n (Phase 6)
ORACLE_MIN_SPAN = 0.005    # an oracle < 0.5% better than the floor is not a denominator

# Heavy elevations (ablation / learning-curve / SHAP / PDP) run on the headline model of each
# family; the quantile siblings share p50's feature structure, so we don't triple the cost.
ELEVATION_TARGETS = frozenset(
    {"degradation_regressor_p50", "cliff_classifier", "stint_life_regressor"})

# The within-stint attribution (open item 15) is drop-AND-flatten over ~30 units, i.e.
# ~46 refits at ~10 s each. That is minutes per target, so it is opt-in via
# `--attribution` rather than part of the default gate, and scoped to the two families
# whose within-stint behaviour is actually in question: the degradation headline (which
# scores 2.84x the stint-level ceiling) and the classifier (which scores 1.14x it).
# Stint life is excluded on purpose -- its target is a deterministic ramp inside its own
# stint, so "within-stint variation" is not a meaningful question there.
ATTRIBUTION_TARGETS = frozenset({"degradation_regressor_p50", "cliff_classifier"})
ATTRIBUTION_NOISE_SEEDS = 5   # seed-only refits establishing the floor every delta clears
RUN_ATTRIBUTION = False    # set by the CLI flag; never on by default

# Raw cohort/baseline dimensions, keyed by lap_id (read-only, once per run).
COHORT_DIMS = (
    "compound", "is_rain_lap", "age_in_stint", "lap_in_stint",
    S.DEGRADATION_TARGET, "laps_until_cliff_class",
    "circuit_key", "race_year", "constructor_id", "stint_id",
)


# ─── Metric direction helpers ──────────────────────────────────────────────────
def _higher_is_better(spec: S.TargetSpec) -> bool:
    return spec.kind == "classification"  # macro-F1 ↑; pinball / rmse ↓


def _is_better(model_val: float, base_val: float, higher_is_better: bool) -> bool:
    return model_val > base_val if higher_is_better else model_val < base_val


def _headline_metric_name(spec: S.TargetSpec) -> str:
    return {"quantile": "pinball", "classification": "macro_f1",
            "survival": "aft_nloglik"}.get(spec.kind, "rmse")


def _score(spec: S.TargetSpec, y_true: np.ndarray, pred: np.ndarray,
           cens: np.ndarray | None = None, scale: float | None = None) -> float:
    """Model/baseline headline on a row set. pred is class-index for the classifier,
    and the median remaining life for the survival model -- which also needs `cens`,
    because scoring a censored row as an observed death is the exact mistake the AFT
    framing exists to avoid. Passing cens=None for a survival spec is a programming
    error, not a default: it is raised rather than silently scored."""
    if spec.kind == "survival":
        if cens is None:
            raise ValueError(
                "_score on a survival target needs the censoring flags; without them "
                "the likelihood is computed over the wrong population")
        meta = pd.DataFrame({S.STINT_LIFE_CENSOR_COLUMN: np.asarray(cens, dtype=bool)})
        _, value = T._headline(spec, y_true, pred, meta, scale)
        return value
    _, value = T._headline(spec, y_true, pred)
    return value


# ─── Eval split: true holdout if populated, else the final CV fold (today) ──────
class EvalSplit:
    def __init__(self, mode: str, eval_season: int | None,
                 X_tr, y_tr, seasons_tr, lap_ids_tr,
                 X_ev, y_ev, lap_ids_ev, cens_tr=None, cens_ev=None, w_tr=None):
        self.mode = mode                  # "holdout" | "cv_final_fold"
        self.eval_season = eval_season
        self.X_tr, self.y_tr = X_tr, y_tr
        self.seasons_tr = seasons_tr
        self.lap_ids_tr = np.asarray(lap_ids_tr)
        self.X_ev, self.y_ev = X_ev, y_ev
        self.lap_ids_ev = np.asarray(lap_ids_ev)
        # Right-censoring flags, aligned row-for-row with y_tr / y_ev. None for every
        # target except stint life -- the survival model cannot be fitted or scored
        # without them, and everything else ignores them.
        self.cens_tr = None if cens_tr is None else np.asarray(cens_tr, dtype=bool)
        self.cens_ev = None if cens_ev is None else np.asarray(cens_ev, dtype=bool)
        # Training-side row weights (IPW), aligned row-for-row with y_tr. None for
        # every target except the quantile trio. Carried here for the same reason the
        # censoring flags are: the fit is wrong without them and nothing else says so.
        self.w_tr = None if w_tr is None else np.asarray(w_tr, dtype=np.float32)


def _evaluation_split(bundle: F.FeatureBundle) -> EvalSplit:
    """Live holdout when 2025 has ingested; until then the final TimeSeriesSplit fold (2024)."""
    is_survival = S.TARGET_BY_NAME[bundle.target_name].kind == "survival" \
        if bundle.target_name else False
    cc = S.STINT_LIFE_CENSOR_COLUMN
    cens_all_tr = (bundle.meta_train[cc].to_numpy(dtype=bool) if is_survival else None)
    spec = S.TARGET_BY_NAME[bundle.target_name] if bundle.target_name else None
    w_all_tr = _row_weights(spec, bundle.meta_train) if spec is not None else None

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
            bundle.meta_holdout[keep]["lap_id"].to_numpy(),
            cens_tr=cens_all_tr, w_tr=w_all_tr,
            cens_ev=(bundle.meta_holdout[keep][cc].to_numpy(dtype=bool)
                     if is_survival else None))

    seasons = bundle.groups_train.to_numpy()
    folds = list(T._season_folds(seasons, bundle.training_seasons, n_splits=5))
    tr, ev = folds[-1]  # final fold: train ⊂ early seasons, validate on the latest (2024)
    y = bundle.y_train.to_numpy()
    lap_ids = bundle.meta_train["lap_id"].to_numpy()
    return EvalSplit(
        "cv_final_fold", int(seasons[ev][0]),
        bundle.X_train.iloc[tr].reset_index(drop=True), y[tr],
        seasons[tr], lap_ids[tr],
        bundle.X_train.iloc[ev].reset_index(drop=True), y[ev], lap_ids[ev],
        cens_tr=(cens_all_tr[tr] if cens_all_tr is not None else None),
        cens_ev=(cens_all_tr[ev] if cens_all_tr is not None else None),
        w_tr=(w_all_tr[tr] if w_all_tr is not None else None))


# ─── Cohort dimension table (raw, keyed by lap_id) ──────────────────────────────
def load_cohort_dims(duckdb_path: str = S.DUCKDB_PATH) -> pd.DataFrame:
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        df = con.execute(
            f"SELECT {', '.join(COHORT_DIMS)} , lap_id FROM {S.MART}").df()
        # stint_length_laps lives in fct_stint_features (the cliff mart only carries stint_id);
        # the stint-life baseline derives remaining life from it join exactly as load_features.
        stint_len = con.execute(
            f"SELECT stint_id, stint_length_laps FROM {S.STINT_FEATURES}").df()
    finally:
        con.close()
    df = df.merge(stint_len, on="stint_id", how="left")
    df["age_bucket"] = np.where(
        df["age_in_stint"].notna(),
        (df["age_in_stint"].fillna(0) // AGE_BUCKET_WIDTH).astype("Int64"), -1)
    return df.set_index("lap_id")


# ─── Baselines (one strong anchor per family) ───────────────────────────────────
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
    cell group-mean remaining life (stint-life). Every baseline is a NON-LEAKAGE anchor:
    it never reads the per-row answer, so 'beats baseline' is a valid quality gate."""
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
    # stint-life: FAIR cell group-mean of actual remaining life (compound × circuit × age-bucket),
    # compound→global fallback. NOT the old (stint_length − lap_in_stint)/2 anchor that is half
    # the target, a leakage near-oracle the masked model cannot fairly be required to beat.
    for d in (train_dims, eval_dims):
        d["remaining_stint_life_laps"] = d["stint_length_laps"] - d["lap_in_stint"]
    base = _apply_cell_baseline(train_dims, eval_dims, "remaining_stint_life_laps", agg="mean")
    return np.clip(base, 0, None)


# ─── Survival report: the two populations, never pooled ─────────────────────────
def survival_report(y_true, model_pred, base_pred, cens, scale: float) -> dict:
    """Stint-life quality, censored and uncensored reported apart.

    They are kept apart because pooling them is how this model was previously
    flattered. ml_headroom_ii.md #3 measured a "+12.4% improvement" from training
    on uncensored stints only; that gain is the selection effect scoring itself,
    since the stints that end in a tyre change are exactly the ones the pit wall
    chose to end. An uncensored-only number is therefore reported as one of two
    populations and never as the headline.

    C-index is computed over all rows -- it is defined on censored data, and
    ranking is the property the gauge's colour band actually depends on.
    """
    c = np.asarray(cens, dtype=bool)
    y = np.asarray(y_true, dtype=np.float64)
    mp = np.asarray(model_pred, dtype=np.float64)
    bp = np.asarray(base_pred, dtype=np.float64)

    def pop(mask: np.ndarray) -> dict:
        if not mask.any():
            return {"n": 0, "aft_nloglik": None, "baseline_aft_nloglik": None,
                    "median_abs_error_laps": None}
        d = {"n": int(mask.sum()),
             "aft_nloglik": SV.aft_nloglik(y[mask], mp[mask], c[mask], scale),
             "baseline_aft_nloglik": SV.aft_nloglik(y[mask], bp[mask], c[mask], scale)}
        # A median absolute error is meaningful only where the life was observed;
        # on a censored row the "error" is against a lower bound, so it is omitted
        # rather than reported as if it meant the same thing.
        d["median_abs_error_laps"] = (
            float(np.median(np.abs(mp[mask] - y[mask]))) if not c[mask].any() else None)
        return d

    return {
        "scale": float(scale),
        "label_shift": S.AFT_LABEL_SHIFT,
        "distribution": S.AFT_DISTRIBUTION,
        "censored_share": float(c.mean()),
        "c_index": SV.c_index(y, mp, c),
        "baseline_c_index": SV.c_index(y, bp, c),
        "uncensored": pop(~c),
        "censored": pop(c),
    }


# ─── Cohort metric breakdown ────────────────────────────────────────────────────
def _cohort_table(spec: S.TargetSpec, dim_name: str, dims: pd.DataFrame,
                  y_true: np.ndarray, model_pred: np.ndarray,
                  base_pred: np.ndarray, cens: np.ndarray | None = None,
                  scale: float | None = None) -> tuple[dict, list]:
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
        cm = None if cens is None else cens[m]
        mv = _score(spec, y_true[m], model_pred[m], cm, scale)
        bv = _score(spec, y_true[m], base_pred[m], cm, scale)
        beats = _is_better(mv, bv, hib)
        table[str(key)] = {"n": int(m.sum()), "model": mv, "baseline": bv, "beats_baseline": beats}
        if not beats:
            under.append({"dimension": dim_name, "cohort": str(key),
                          "n": int(m.sum()), "model": mv, "baseline": bv})
    return table, under


# ─── Calibration / split-conformal coverage ─────────────────────────────────────
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


# ─── Dual importance: SHAP + permutation ─────────────────────────────────────────
def dual_importance(model, spec: S.TargetSpec, X_explain: pd.DataFrame,
                    X_perm: pd.DataFrame, y_perm: np.ndarray,
                    cens_perm=None, scale=None) -> dict:
    import shap
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import make_scorer, mean_pinball_loss

    feats = list(X_explain.columns)
    # AFTBooster is not a sklearn estimator; SHAP reads the raw Booster fine.
    expl = shap.TreeExplainer(model.booster if spec.kind == "survival" else model)
    sv = expl.shap_values(X_explain)
    sv = np.asarray(sv)
    # multiclass → (n, f, c) or list; collapse classes + rows to mean|.|
    shap_imp = np.abs(sv).mean(axis=tuple(i for i in range(sv.ndim) if i != sv.ndim-1)) \
        if sv.ndim == 3 else np.abs(sv).mean(axis=0)
    shap_rank = sorted(zip(feats, [float(v) for v in np.ravel(shap_imp)]),
                       key=lambda t: t[1], reverse=True)

    if spec.kind == "survival":
        # sklearn's permutation_importance wants an estimator it can score, and the
        # AFT wrapper is not one. Doing the shuffle directly against the censored
        # NLL is both simpler and the metric we actually care about -- going through
        # a sklearn scorer here would have meant scoring the survival model on
        # something that ignores censoring, which is the whole defect being fixed.
        rng = np.random.default_rng(S.RANDOM_STATE)
        c = np.asarray(cens_perm, dtype=bool)
        ref = SV.aft_nloglik(y_perm, model.predict(X_perm), c, scale)
        imp = []
        for f in feats:
            deltas = []
            for _ in range(PERM_REPEATS):
                Xp = X_perm.copy()
                Xp[f] = rng.permutation(Xp[f].to_numpy())
                # NLL is lower-is-better, so a feature that matters makes it rise;
                # sign it so "larger = more important", matching the other families.
                deltas.append(SV.aft_nloglik(y_perm, model.predict(Xp), c, scale) - ref)
            imp.append(float(np.mean(deltas)))
        perm_rank = sorted(zip(feats, imp), key=lambda t: t[1], reverse=True)
    else:
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


# ─── Ablation + learning curve ────────────────────────────────────────────────────
def ablation(spec: S.TargetSpec, params: dict, X_tr, y_tr, X_ev, y_ev,
             target: str, cens_tr=None, cens_ev=None, scale=None, w_tr=None) -> list[dict]:
    full = _fit(spec, params, X_tr, y_tr, cens_tr, w_tr)
    base = _score(spec, y_ev, _predict_index(spec, full, X_ev), cens_ev, scale)
    rows = [{"group": "<none>", "headline": base, "delta_vs_full": 0.0}]
    for grp, cols in S.FEATURE_GROUPS.items():
        keep = [c for c in X_tr.columns if c not in cols]
        if not keep:
            continue
        m = _fit(spec, params, X_tr[keep], y_tr, cens_tr, w_tr)
        val = _score(spec, y_ev, _predict_index(spec, m, X_ev[keep]), cens_ev, scale)
        rows.append({"group": grp, "headline": val, "delta_vs_full": val-base})
    pd.DataFrame(rows).to_parquet(ARTEFACTS_DIR / f"ablation_{target}.parquet", index=False)
    return rows


def learning_curve(spec: S.TargetSpec, params: dict, X_tr, y_tr, seasons_tr,
                   X_ev, y_ev, target: str, cens_tr=None, cens_ev=None,
                   scale=None, w_tr=None) -> list[dict]:
    seasons = sorted(set(int(s) for s in seasons_tr))
    rows = []
    for i in range(len(seasons)):
        used = seasons[: i + 1]
        m = np.isin(seasons_tr, used)
        if m.sum() < 100:
            continue
        model = _fit(spec, params, X_tr[m], y_tr[m],
                     None if cens_tr is None else np.asarray(cens_tr)[m],
                     None if w_tr is None else np.asarray(w_tr)[m])
        val = _score(spec, y_ev, _predict_index(spec, model, X_ev), cens_ev, scale)
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


# ─── Behaviour audit: PDP top-3 + monotonicity sanity ───────────────────────────
def behaviour_audit(model, spec: S.TargetSpec, X_ev: pd.DataFrame,
                    top_features: list[str], target: str) -> dict:
    from sklearn.inspection import PartialDependenceDisplay
    result: dict = {}
    top3 = [f for f in top_features if f in X_ev.columns][:3]
    # multi-class PDP requires a target class; explain the imminent-cliff class (0_to_2).
    pdp_kwargs = {"target": 0} if spec.kind == "classification" else {}
    try:
        if spec.kind == "survival":
            # AFTBooster is not a sklearn estimator, and PartialDependenceDisplay
            # only takes one. Stated as a skip rather than left to raise into
            # pdp_error, so "no PDP for stint life" reads as a decision instead of
            # looking like a transient failure nobody has looked at.
            raise NotImplementedError(
                "PDP skipped: survival model is a raw Booster, not a sklearn estimator; "
                "the monotonicity probe below covers the same question")
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
    # holding others at the median, more laps past the cliff should make the pace
    # penalty WORSE. The sign of "worse" is target-dependent -- degradation predicts a
    # time-loss magnitude (worse = higher, non-decreasing) but stint_life_regressor
    # predicts REMAINING LIFE (worse = lower, non-increasing), and applying the
    # degradation direction to both meant this probe reported stint_life_regressor's
    # correctly-decreasing predictions as "violations" while a model that wrongly held
    # remaining life flat or rising past the cliff would have passed clean. Fixed as
    # part of `05b` (see work/05-model-family.md) when the monotone_constraints arm
    # needed this probe's verdict to be trustworthy per family.
    expect_non_decreasing = spec.family != "stint_life_regressor"
    if spec.kind != "classification" and "laps_past_cliff" in X_ev.columns:
        base = X_ev.median(numeric_only=True)
        grid = np.linspace(float(X_ev["laps_past_cliff"].quantile(0.05)),
                           float(X_ev["laps_past_cliff"].quantile(0.95)), 20)
        probe = pd.DataFrame([base.to_dict()] * len(grid))[list(X_ev.columns)]
        probe["laps_past_cliff"] = grid
        preds = _predict_index(spec, model, probe).astype(float)
        diffs = np.diff(preds)
        violations = (diffs < -1e-6) if expect_non_decreasing else (diffs > 1e-6)
        result["monotonicity_laps_past_cliff"] = {
            "expected_direction": "non_decreasing" if expect_non_decreasing else "non_increasing",
            "violations": int(violations.sum()),
            "n_steps": int(len(diffs)),
            "monotone_as_expected": bool(not violations.any()),
        }
    return result


# ─── Adversarial leakage probe: predict race_year from X ─────────────────────────
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


# ─── Biggest misses: most-confident classifier disagreements ─────────────────────
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
def _fit(spec: S.TargetSpec, params: dict, X, y, cens=None, w=None):
    """Fit an eval model the way production fits it.

    The split is honest and the booster is refit rather than loaded -- that part is
    deliberate. What must NOT differ from production is the fit itself, and until this
    carried `w` it did: `T._sample_weight` returns the quantile trio's IPW survival
    weights only when handed `meta`, and this had none, so every degradation number in
    the report described an UNWEIGHTED model while `train.py:_fit` ships a weighted one.
    That is Phase 2 finding 1 in the place where it reaches the model card.

    `w` carries only the row-wise weights (IPW). Balanced class weights stay computed
    from the rows being fitted, exactly as train.py computes them, because they are a
    property of the label mix in those rows rather than of the rows themselves.
    """
    model = T._make_model(spec, params)
    if spec.kind == "quantile" and w is None:
        raise ValueError(
            "_fit on a quantile target needs the IPW survival weights production fits "
            "with; pass w=<row weights> (see _row_weights)")
    weights = np.asarray(w, dtype=np.float32) if w is not None else T._sample_weight(spec, y)
    if spec.kind == "survival":
        if cens is None:
            raise ValueError("_fit on a survival target needs the censoring flags")
        model.fit(X, y, sample_weight=weights, is_censored=np.asarray(cens, dtype=bool))
        return model
    model.fit(X, y, sample_weight=weights)
    return model


def _row_weights(spec: S.TargetSpec, meta: pd.DataFrame) -> np.ndarray | None:
    """The per-ROW training weights, sliceable alongside y (unlike balanced class
    weights, which are a per-FIT statistic). Today that is the quantile trio's IPW."""
    if spec.kind == "quantile" and "survival_weight" in meta.columns:
        return meta["survival_weight"].to_numpy(dtype=np.float32)
    return None


def _predict_index(spec: S.TargetSpec, model, X) -> np.ndarray:
    """Class index for the classifier; raw prediction otherwise (matches _score)."""
    return model.predict(X)


def _params_for(target: str, version: str) -> dict:
    """Tuned best_params for any production version (v1/v2/v3 the shipped models are
    refit from these); SMOKE_DEFAULTS only for the 'smoke' CI version."""
    p = MODELS_DIR / f"{target}_best_params.json"
    if version != "smoke" and p.exists():
        return json.loads(p.read_text())
    return dict(T.SMOKE_DEFAULTS)


# ─── Attainable ceilings (Phase 6 -- Corrections §12/§15) ───────────────────────
def _target_series(spec: S.TargetSpec, dims: pd.DataFrame) -> pd.Series:
    """The target column as it exists in the warehouse, for the ceiling arithmetic.

    Stint life is synthesised (`stint_length_laps - lap_in_stint`) exactly as
    features.py synthesises it, rather than read from a column that does not exist.
    """
    if spec.kind == "survival":
        return (dims["stint_length_laps"] - dims["lap_in_stint"]).clip(lower=0)
    return dims[spec.source_column]


def variance_ceiling(spec: S.TargetSpec, dims: pd.DataFrame) -> dict:
    """Between-stint share of the target's variance -- the ceiling on any predictor that
    is constant within a stint. Reported at mart scope, so it is a property of the
    column and directly comparable with Corrections §12.

    Three things it is NOT, all of which §12 was read as saying and none of which it
    supports: it is not a ceiling on the model (14 of 34 numeric features vary within a
    stint and can reach past it); it is not exact (see the estimator note in
    ml/src/ceiling.py); and it is not a noise estimate for a target whose within-stint
    variation is deterministic -- which stint life's is, being a ramp of -1 per lap.
    """
    horizon = S.TARGET_HORIZON_LAPS.get(spec.source_column, 1)
    col = _target_series(spec, dims)
    keep = col.notna() & dims["stint_id"].notna() & dims["lap_in_stint"].notna()
    y = col[keep]
    g = dims["stint_id"][keep].to_numpy()
    o = dims["lap_in_stint"][keep].to_numpy()

    categorical = spec.kind == "classification"
    vc = (CE.categorical_variance_components(y.to_numpy(), g) if categorical
          else CE.variance_components(y.to_numpy(dtype=np.float64), g))
    if vc is None:
        return {"error": "variance components not estimable"}

    out = {
        "target_column": spec.source_column,
        "scope": "mart",
        "horizon_laps": horizon,
        "estimator": ("gini_anova_icc_oneway" if categorical else "anova_icc_oneway"),
        "n_rows": vc.n, "n_stints": vc.n_groups,
        "mean_rows_per_stint": round(vc.mean_rows_per_group, 3),
        "sd": vc.sd,
        "between_stint_share": vc.share,
        "between_stint_share_naive": vc.share_naive,
        "naive_inflation_x": (vc.share_naive / vc.share) if vc.share > 0 else None,
    }
    if not categorical:
        lag1 = CE.within_group_lag1(y.to_numpy(dtype=np.float64), g, o)
        out["within_stint_lag1_autocorr"] = lag1
        # A rolling sum autocorrelates at (h-1)/h under white-noise increments. Quoting
        # the raw lag-1 for such a column as evidence of a *process* is the same
        # unanchored-number mistake this phase exists to fix, one level down.
        out["lag1_expected_from_window_overlap"] = (horizon - 1) / horizon
        out["lag1_excess_over_overlap"] = (
            None if lag1 is None else lag1 - (horizon - 1) / horizon)

    if horizon > 1:
        mask = CE.thin_non_overlapping(g, o, horizon)
        vc_thin = (CE.categorical_variance_components(y.to_numpy()[mask], g[mask]) if categorical
                   else CE.variance_components(y.to_numpy(dtype=np.float64)[mask], g[mask]))
        if vc_thin is not None:
            out["non_overlapping"] = {
                "n_rows": vc_thin.n, "n_stints": vc_thin.n_groups,
                "mean_rows_per_stint": round(vc_thin.mean_rows_per_group, 3),
                "between_stint_share": vc_thin.share,
                "between_stint_share_naive": vc_thin.share_naive,
            }
            out["between_stint_share_overlapping"] = out["between_stint_share"]
            out["between_stint_share"] = vc_thin.share
            out["estimator"] += "_non_overlapping"
    if spec.kind == "survival":
        out["within_stint_is_deterministic"] = True
        out["note"] = (
            "remaining life is stint_length - lap_in_stint, so its within-stint variation "
            "is a known ramp rather than noise: this share bounds stint-constant "
            "predictors, and bounds nothing about the model. Read the metric-native "
            "ceiling and the censored/uncensored split instead.")
    return out


def metric_native_ceiling(spec: S.TargetSpec, y_tr: np.ndarray, y_ev: np.ndarray,
                          stint_ev: np.ndarray, order_ev: np.ndarray,
                          headline: float, hib: bool,
                          cens_ev: np.ndarray | None, scale: float | None,
                          between_stint_share: float | None) -> dict:
    """The ceiling in the headline metric's own units, so `fraction_of_attainable` is a
    division of like by like rather than a variance share pressed into a pinball number.

    `floor` is the unconditional (stint-blind) statistic, repeated. The ceiling is a
    predictor handed the stint id and nothing else -- the best any stint-constant feature
    set can do -- and it is estimated three ways because the obvious two are both bad:

    * **in-sample** -- each stint's own statistic over its own ~19 laps, scored on those
      same laps. Overstates the ceiling.
    * **cross-fitted** -- odd laps predict even and vice versa, so ~9 laps per estimate.
      Genuinely out-of-sample, and for a *tail quantile* it is almost pure noise: the
      empirical p10 of nine numbers barely beats a global constant, which drives the
      denominator to zero and the fraction to nonsense. Reported, and refused as a
      denominator when its advantage over the floor is below `ORACLE_MIN_SPAN`.
    * **analytic** (quantile targets only) -- the one that is not estimated at all.
      Under a Gaussian approximation the minimum expected pinball at the true quantile is
      `sigma * phi(z_alpha)`, so knowing the stint scales sigma from `sqrt(sigma_b^2 +
      sigma_w^2)` down to `sigma_w` and the attainable fractional loss reduction is
      exactly `1 - sqrt(1 - ICC)`. The scale cancels; only the shape assumption remains.
      This is the load-bearing denominator for the quantile trio.

    **A fraction above 1.0 is a result, not an error.** It says the model is reaching
    past everything stint identity can supply -- i.e. into within-stint variation, the
    82.5% Corrections §12 reads as noise. That is the assumption the plan's measurement
    block flagged as "the one to attack first", and this is the number that attacks it.
    """
    alpha = spec.quantile_alpha
    # The classifier scores class INDICES; a float array of integral values is a
    # "continuous target" to sklearn and f1_score refuses it. Cast at the boundary.
    cast = ((lambda a: np.rint(a).astype(np.int64)) if spec.kind == "classification"
            else (lambda a: a))
    floor_pred = cast(CE.unconditional_floor(y_tr, spec.kind, alpha, len(y_ev)))
    floor = _score(spec, y_ev, floor_pred, cens_ev, scale)
    achieved = IV.signed_delta(headline, floor, hib)

    def frac(oracle: float | None) -> float | None:
        if oracle is None:
            return None
        span = IV.signed_delta(oracle, floor, hib)
        if span <= abs(floor) * ORACLE_MIN_SPAN:
            return None
        return float(achieved / span)

    if spec.kind == "survival":
        perfect = _score(spec, y_ev, np.asarray(y_ev, dtype=np.float64), cens_ev, scale)
        return {"basis": "perfect_prediction",
                "floor_metric": floor, "oracle_metric": perfect,
                "achieved_reduction": achieved,
                "fraction_of_attainable": frac(perfect),
                "note": ("floor = global mean remaining life; oracle = the censored AFT "
                         "likelihood at a perfect prediction, which is non-zero because "
                         "the log-normal scale is a fitted term. A hard bound, not an "
                         "estimate -- nothing can score past it, so this fraction cannot "
                         "exceed 1.")}

    in_sample = _score(spec, y_ev, cast(CE.stint_oracle(
        y_ev, stint_ev, order_ev, spec.kind, alpha, cross_fitted=False)), cens_ev, scale)
    crossfit = _score(spec, y_ev, cast(CE.stint_oracle(
        y_ev, stint_ev, order_ev, spec.kind, alpha, cross_fitted=True)), cens_ev, scale)

    out = {"basis": "stint_identity_oracle",
           "floor_metric": floor,
           "achieved_reduction": achieved,
           "achieved_reduction_pct_of_floor": float(achieved / abs(floor)) if floor else None,
           "oracle_metric_in_sample": in_sample,
           "oracle_metric_cross_fitted": crossfit,
           "in_sample_oracle_is_exact_optimum": spec.kind == "quantile",
           "fraction_of_attainable_in_sample": frac(in_sample),
           "fraction_of_attainable_cross_fitted": frac(crossfit)}

    if spec.kind == "quantile" and between_stint_share is not None:
        # No per-stint estimation, so no small-sample collapse -- which is the whole
        # reason this and not an empirical oracle is the primary denominator.
        ceiling_frac = CE.attainable_pinball_fraction(between_stint_share)
        out["basis"] = "analytic_from_icc"
        out["attainable_fraction_of_floor"] = ceiling_frac
        out["oracle_metric_analytic"] = float(floor * (1.0 - ceiling_frac))
        out["fraction_of_attainable"] = (
            float((achieved / abs(floor)) / ceiling_frac) if floor and ceiling_frac > 0 else None)
        out["note"] = (
            "primary denominator is analytic: under a Gaussian shape, knowing the stint "
            "scales sigma from sqrt(sigma_b^2 + sigma_w^2) to sigma_w, so a stint-constant "
            "predictor can remove at most 1 - sqrt(1 - ICC) of the expected pinball. It is "
            "the population ceiling and it is not estimated per stint, so it does not "
            "collapse at ~19 laps the way the empirical oracles do. "
            "fraction_of_attainable_in_sample carries a stronger property and no shape "
            "assumption: the per-stint empirical alpha-quantile is the EXACT minimiser of "
            "pinball over all stint-constant predictors on these very rows, so an "
            "out-of-sample model scoring below it has provably used within-stint "
            "information. Above 1 on either is a finding, not a defect.")
    else:
        out["note"] = (
            "floor = the unconditional statistic (stint-blind); oracle = the per-stint "
            "statistic. The in-sample oracle is scored on rows it saw and overstates the "
            "ceiling; the cross-fitted one estimates each stint from ~half its laps and "
            "understates it. Note the per-stint majority class maximises ACCURACY, not "
            "macro-F1, so unlike the quantile family this oracle is not an exact optimum "
            "and the fraction is indicative rather than a bound. A null fraction means "
            "that oracle's advantage over the floor was too small to divide by, not that "
            "the model failed.")
    return out


# ─── What the within-stint signal is (open item 15) ─────────────────────────────
def within_stint_attribution(spec: S.TargetSpec, params: dict,
                             X_tr: pd.DataFrame, y_tr: np.ndarray, stint_tr: np.ndarray,
                             X_ev: pd.DataFrame, y_ev: np.ndarray, stint_ev: np.ndarray,
                             model_pred: np.ndarray, hib: bool, target: str,
                             cens_tr=None, cens_ev=None, scale=None,
                             lap_tr: np.ndarray | None = None,
                             lap_ev: np.ndarray | None = None,
                             w_tr: np.ndarray | None = None) -> dict:
    """Split every feature group's contribution into its between- and within-stint parts.

    Phase 6 established *that* the degradation family reaches past the stint-level
    ceiling (2.84x for p50). Open item 15 asks what it is reaching with. The existing
    `ablation` cannot answer it: dropping `dirty_air` removes "this stint ran in traffic"
    and "this lap ran in traffic" in one move, and those are the two competing readings.

    Flattening a group to its per-stint summary removes only the second. So each unit is
    measured twice -- dropped and flattened -- and the ratio is the share of that unit's
    contribution that could only have come from within-stint variation.

    Three passes, coarse to fine:

    * **groups** -- the ablation's own 10 units, so the new numbers sit directly beside
      the ones already in the card and the artefacts.
    * **channels** -- `attribution.CHANNELS`, which cross the groups deliberately: the
      tyre/driver question lives *inside* the `thermal` group, so no grouping the ablation
      already uses can answer it.
    * **features** -- every feature whose own between-stint share is under 50%, flattened
      alone. Self-selecting, because flattening a stint-constant feature is provably a
      no-op.

    A fourth pass then asks of every channel that cleared the floor whether its result is
    reachable by a *feature*. The flatten is a per-stint mean over laps 1..N, so on a
    forward-looking target it knows laps that had not run when the row is scored. That is
    correct for an information measurement and inadmissible in a feature, and the two
    readings of a negative delta -- "within-stint variation hurts" and "knowing the rest
    of the stint helps" -- are indistinguishable without the causal arm. See
    `attribution.flatten_causality`, and Corrections §22 for the result that made this
    pass compulsory rather than optional.
    """
    def fit(X, y):
        # Column transforms only: the rows (and so w_tr) are the same set every time.
        return _fit(spec, params, X, y, cens_tr, w_tr)

    def score(y_true, model, X):
        return _score(spec, y_true, _predict_index(spec, model, X), cens_ev, scale)

    def fit_seeded(seed: int):
        # random_state is fixed inside T._make_model and cannot be passed through
        # `params` (duplicate keyword), so it is overridden on the built estimator.
        # AFTBooster has no set_params (unlike the two sklearn families), so its
        # seed is mutated directly on the params dict instead.
        m = T._make_model(spec, params)
        weights = w_tr if w_tr is not None else T._sample_weight(spec, y_tr)
        if spec.kind == "survival":
            m.params["seed"] = seed
            return m.fit(X_tr, y_tr, sample_weight=weights,
                         is_censored=np.asarray(cens_tr, dtype=bool))
        m.set_params(random_state=seed)
        return m.fit(X_tr, y_tr, sample_weight=weights)

    out: dict = {
        "prediction_variance": AT.prediction_variance_split(model_pred, y_ev, stint_ev),
        "per_lap_icc_max": AT.PER_LAP_ICC_MAX,
    }

    # The denominator for every delta below. Without it these are point estimates with
    # nothing under them -- the same defect Phase 6 spent itself removing one level up.
    try:
        out["refit_noise"] = AT.refit_noise_floor(
            fit_seeded, score, X_ev, y_ev,
            tuple(S.RANDOM_STATE + i for i in range(ATTRIBUTION_NOISE_SEEDS)))
        noise = out["refit_noise"]["delta_noise_2sd"]
    except Exception as e:  # noqa: BLE001
        out["refit_noise"] = {"error": f"{type(e).__name__}: {e}"}
        noise = None

    # Which features even *have* within-stint variation to remove. Measured on the eval
    # rows, so the ICCs are comparable with the target's own share from `variance_ceiling`.
    icc = AT.per_lap_features(X_ev, stint_ev)
    out["per_lap_features"] = dict(sorted(icc.items(), key=lambda kv: kv[1]))

    common = dict(higher_is_better=hib, feature_icc=icc)
    rows_groups = AT.within_stint_ablation(
        fit, score, X_tr, y_tr, stint_tr, X_ev, y_ev, stint_ev,
        units=dict(S.FEATURE_GROUPS), **common)
    rows_channels = AT.within_stint_ablation(
        fit, score, X_tr, y_tr, stint_tr, X_ev, y_ev, stint_ev,
        units=dict(AT.CHANNELS), **common)
    rows_features = AT.within_stint_ablation(
        fit, score, X_tr, y_tr, stint_tr, X_ev, y_ev, stint_ev,
        units={f: (f,) for f in icc}, drop=False, **common)

    for tag, rows in (("group", rows_groups), ("channel", rows_channels),
                      ("feature", rows_features)):
        AT.annotate_noise(rows, noise)
        for r in rows:
            r["pass"] = tag

    # Causality of every channel result that cleared the floor. Two extra fits each, and
    # only for the rows anyone would act on -- a delta inside the noise floor is not a
    # finding and does not need to be re-measured to be declined.
    if lap_tr is not None and lap_ev is not None and noise is not None:
        # The channel pass's own reference row, so the causal arm is measured against the
        # exact headline its flatten_delta was measured against rather than a refit of it.
        base_headline = rows_channels[0]["headline"]
        for r in rows_channels:
            if r["unit"] == "<none>" or abs(r["flatten_delta"]) <= noise:
                continue
            try:
                r["causality"] = AT.flatten_causality(
                    fit, score, X_tr, y_tr, stint_tr, lap_tr, X_ev, y_ev, stint_ev,
                    lap_ev, hib, AT.CHANNELS[r["unit"]], base_headline,
                    r["flatten_delta"], noise=noise)
            except Exception as e:  # noqa: BLE001
                r["causality_error"] = f"{type(e).__name__}: {e}"
    else:
        out["causality_skipped"] = (
            "no lap order or no noise floor; the causal arm needs both")
    all_rows = rows_groups + [r for r in rows_channels if r["unit"] != "<none>"] \
        + [r for r in rows_features if r["unit"] != "<none>"]
    # The causality block is nested in the JSON and flattened here: a parquet column that
    # is a struct on three rows and null on ninety is a column no reader wants.
    flat = []
    for r in all_rows:
        c = r.get("causality") or {}
        flat.append({**{k: v for k, v in r.items() if k != "causality"},
                     **{f"causality_{k}": c.get(k) for k in
                        ("causal_delta", "future_delta", "lookahead_share",
                         "causally_reachable")}})
    pd.DataFrame(flat).to_parquet(
        ARTEFACTS_DIR / f"attribution_{target}.parquet", index=False)

    out["groups"] = [r for r in rows_groups if r["unit"] != "<none>"]
    out["channels"] = [r for r in rows_channels if r["unit"] != "<none>"]
    out["features"] = [r for r in rows_features if r["unit"] != "<none>"]
    out["channel_rollup_from_features"] = AT.channel_rollup(
        [dict(r, kind="feature") for r in out["features"]])
    out["note"] = (
        "drop_delta = the unit's whole contribution; flatten_delta = the part that is "
        "within-stint (the unit keeps its between-stint information and loses only its "
        "per-lap variation); flatten_share = the second over the first. Positive deltas "
        "always mean the model got worse without it, on both directions of metric. "
        "`channels` is the measured roll-up (flattened as one unit); "
        "`channel_rollup_from_features` sums correlated single-feature deltas and is "
        "indicative only. A `flatten_is_noop` row had no within-stint variation to "
        "remove, so its zero is arithmetic, not evidence. `*_inside_noise` compares the "
        "delta against `refit_noise.delta_noise_2sd`, the spread of seed-only refits of "
        "the unmodified feature set -- a delta inside it is not a finding. `causality` "
        "on a channel row re-runs the flatten over laps 1..t: a flatten_delta without a "
        "causal_delta beside it says what the model uses, never what a feature could "
        "supply.")
    return out


# ─── Intervals on the beats_baseline claim (Phase 6 -- Corrections §15) ─────────
def _fold_dims(dims_all: pd.DataFrame, lap_ids: np.ndarray,
               stint_len: pd.Series) -> pd.DataFrame:
    d = dims_all.loc[lap_ids].reset_index()
    d["stint_length_laps"] = stint_len.reindex(lap_ids).to_numpy()
    return d


def fold_paired_interval(spec: S.TargetSpec, params: dict, bundle: F.FeatureBundle,
                         dims_all: pd.DataFrame, hib: bool) -> dict:
    """Refit per season fold, score model and baseline on each, paired-t the margins.

    The season fold is the coarsest honest cluster in this warehouse -- a whole season
    moves together, so no clustering correction is needed on top and the n is simply the
    fold count. It is the format Phase 2's checkpoint already used (paired t, n=5) and
    the reason that checkpoint was right to decline a +0.75% win at p=0.24.
    """
    X = bundle.X_train
    y = bundle.y_train.to_numpy()
    seasons = bundle.groups_train.to_numpy()
    lap_ids = bundle.meta_train["lap_id"].to_numpy()
    stint_len = bundle.meta_train.set_index("lap_id")["stint_length_laps"]
    cc = S.STINT_LIFE_CENSOR_COLUMN
    cens = (bundle.meta_train[cc].to_numpy(dtype=bool) if spec.kind == "survival" else None)
    w = _row_weights(spec, bundle.meta_train)

    deltas, folds = [], []
    for k, (tr, val) in enumerate(T._season_folds(seasons, bundle.training_seasons, CV_SPLITS)):
        m = _fit(spec, params, X.iloc[tr].reset_index(drop=True), y[tr],
                 None if cens is None else cens[tr],
                 None if w is None else w[tr])
        pred = _predict_index(spec, m, X.iloc[val].reset_index(drop=True))
        scale_k = getattr(m, "scale", None) if spec.kind == "survival" else None
        base = baseline_predictions(
            spec, _fold_dims(dims_all, lap_ids[tr], stint_len),
            _fold_dims(dims_all, lap_ids[val], stint_len))
        c_val = None if cens is None else cens[val]
        mv = _score(spec, y[val], pred, c_val, scale_k)
        bv = _score(spec, y[val], base, c_val, scale_k)
        deltas.append(IV.signed_delta(mv, bv, hib))
        folds.append({"fold": k, "val_season": int(seasons[val][0]), "n": int(val.size),
                      "model": mv, "baseline": bv})
    out = IV.paired_t(deltas)
    out["folds"] = folds
    out["method"] = "paired t over season-grouped CV folds (whole seasons move together)"
    return out


def stint_cluster_interval(spec: S.TargetSpec, y_ev: np.ndarray, model_pred: np.ndarray,
                           base_pred: np.ndarray, stint_ev: np.ndarray, hib: bool,
                           cens_ev: np.ndarray | None, scale: float | None) -> dict:
    """Bootstrap the eval-fold win margin, resampling whole stints -- and, beside it, the
    same quantity resampling laps, so §15's ~4.4x understatement is shown rather than
    asserted."""
    def delta(idx: np.ndarray) -> float:
        c = None if cens_ev is None else cens_ev[idx]
        return IV.signed_delta(_score(spec, y_ev[idx], model_pred[idx], c, scale),
                               _score(spec, y_ev[idx], base_pred[idx], c, scale), hib)

    clustered = IV.cluster_bootstrap(delta, stint_ev, len(y_ev), seed=S.RANDOM_STATE)
    lap_grain = IV.cluster_bootstrap(delta, np.arange(len(y_ev)), len(y_ev),
                                     seed=S.RANDOM_STATE)
    ratio = IV.width_ratio(clustered, lap_grain)
    k = max(clustered.get("n_clusters") or 1, 1)
    n_bar = len(y_ev) / k
    # §15 predicts sqrt(rows / stints). That is the worst case -- it assumes the scored
    # quantity is perfectly correlated inside a stint. The scored quantity here is the
    # model-minus-baseline WIN MARGIN, not the target, and the two are not equally
    # clustered. Both numbers are published so the gap is visible; the implied
    # intra-cluster correlation of the margin is what actually sets the widening.
    return {"method": "percentile bootstrap over whole stints, on the evaluation fold",
            "stint_grain": clustered, "lap_grain": lap_grain,
            "width_ratio_stint_over_lap": ratio,
            "worst_case_ratio_sqrt_rows_over_stints": float(np.sqrt(n_bar)),
            "mean_laps_per_stint": float(n_bar),
            "implied_intra_stint_correlation_of_margin": (
                None if ratio is None or n_bar <= 1
                else float((ratio ** 2 - 1) / (n_bar - 1)))}


def stint_fold_purity(bundle: F.FeatureBundle) -> dict:
    """Phase 6 asks for stint-grain CV grouping. Measured before it is built: with
    season-grouped folds a stint cannot straddle a boundary, because a stint belongs to
    one race and a race to one season. Reported as a number so the property is asserted
    rather than believed -- `ml/tests/test_ceiling.py` fails if it ever stops holding."""
    seasons = bundle.groups_train.to_numpy()
    stints = bundle.meta_train["stint_id"].to_numpy()
    straddling = int(pd.DataFrame({"s": stints, "y": seasons})
                     .groupby("s")["y"].nunique().gt(1).sum())
    counts = pd.Series(stints).value_counts()
    return {"n_stints": int(counts.size), "n_rows": int(counts.sum()),
            "mean_laps_per_stint": float(counts.mean()),
            "stints_straddling_a_season_fold": straddling,
            "effective_sample_ratio": float(np.sqrt(counts.sum() / max(counts.size, 1))),
            "note": ("season-grouped folds are already stint-pure; the clustering damage "
                     "was never in the split, it was in every interval computed at lap "
                     "grain over it (Corrections §15).")}


# ─── Per-target orchestration ───────────────────────────────────────────────────
def evaluate_target(target: str, version: str, dims_all: pd.DataFrame,
                    shared: dict, censoring_variant: str = "standard") -> dict:
    spec = S.TARGET_BY_NAME[target]
    bundle = F.load_features(target=target, censoring_variant=censoring_variant)
    split = _evaluation_split(bundle)
    params = _params_for(target, version)

    # Eval model: refit on the honest training side of the split.
    model = _fit(spec, params, split.X_tr, split.y_tr, split.cens_tr, split.w_tr)
    model_pred = _predict_index(spec, model, split.X_ev)
    # The AFT scale is a term in the likelihood, so it has to be the scale this
    # model was actually fitted at, not the module default.
    scale = getattr(model, "scale", None) if spec.kind == "survival" else None

    # Cohort/baseline dims aligned to the eval rows (and the training side, for the lookup).
    train_dims = dims_all.loc[split.lap_ids_tr].reset_index()
    eval_dims = dims_all.loc[split.lap_ids_ev].reset_index()
    stint_len = bundle.meta_train.set_index("lap_id")["stint_length_laps"]
    eval_dims["stint_length_laps"] = stint_len.reindex(split.lap_ids_ev).to_numpy()
    train_dims["stint_length_laps"] = stint_len.reindex(split.lap_ids_tr).to_numpy()

    base_pred = baseline_predictions(spec, train_dims, eval_dims)

    hib = _higher_is_better(spec)
    headline = _score(spec, split.y_ev, model_pred, split.cens_ev, scale)
    baseline = _score(spec, split.y_ev, base_pred, split.cens_ev, scale)

    cohorts, under = {}, []
    for dim_name in ("compound", "circuit_key", "constructor_id", "is_rain_lap", "race_year"):
        tbl, u = _cohort_table(spec, dim_name, eval_dims, split.y_ev, model_pred,
                               base_pred, split.cens_ev, scale)
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
    if spec.kind == "survival":
        out["survival"] = survival_report(split.y_ev, model_pred, base_pred,
                                          split.cens_ev, scale)

    # ── Phase 6: the denominator. A headline reported against 1.0 cannot say whether to
    # keep going or stop; a headline reported against what is reachable can. Failures
    # here are recorded, never swallowed -- an absent interval fails the card gate
    # (ml/tests/test_manifest_contract.py), which is the intended loud outcome.
    stint_ev = eval_dims["stint_id"].to_numpy()
    order_ev = eval_dims["lap_in_stint"].to_numpy()
    try:
        vc_cache = shared.setdefault("variance_ceiling", {})
        key = f"{spec.source_column}|{spec.kind}"
        if key not in vc_cache:
            vc_cache[key] = variance_ceiling(spec, dims_all.reset_index())
        out["attainable"] = {
            "variance": vc_cache[key],
            "metric_native": metric_native_ceiling(
                spec, split.y_tr, split.y_ev, stint_ev, order_ev,
                headline, hib, split.cens_ev, scale,
                vc_cache[key].get("between_stint_share")),
        }
    except Exception as e:  # noqa: BLE001 - recorded, and the card gate reads it
        out["attainable"] = {"error": f"{type(e).__name__}: {e}"}
    try:
        out["interval"] = {
            "fold_paired": fold_paired_interval(spec, params, bundle, dims_all, hib),
            "cluster_bootstrap": stint_cluster_interval(
                spec, split.y_ev, model_pred, base_pred, stint_ev, hib,
                split.cens_ev, scale),
        }
        sig = [out["interval"]["fold_paired"].get("significant"),
               out["interval"]["cluster_bootstrap"]["stint_grain"].get("significant")]
        # Both tests must clear zero. They ask different questions -- does the win hold
        # across seasons, and does it survive stint clustering within one -- and a claim
        # that only one of them supports is exactly the claim §15 says to stop making.
        out["beats_baseline_significant"] = (
            None if any(v is None for v in sig) else bool(all(sig)))
    except Exception as e:  # noqa: BLE001
        out["interval"] = {"error": f"{type(e).__name__}: {e}"}

    print(f"[{target}] {out['headline_metric']}: model={headline:.4f} "
          f"baseline={baseline:.4f}  beats={out['beats_baseline']}  "
          f"(mode={split.mode}, eval_season={split.eval_season}, n={len(split.y_ev)})")
    fp = out.get("interval", {}).get("fold_paired", {})
    att = out.get("attainable", {}).get("metric_native", {})
    if fp.get("p_value") is not None:
        frac = att.get("fraction_of_attainable")
        if frac is None:
            frac = att.get("fraction_of_attainable_in_sample")
        frac_txt = ("attainable: no usable denominator" if frac is None else
                    (f"{frac:.1f}x the stint-level ceiling (not binding)" if frac > 1.0
                     else f"{frac:.1%} of attainable ({att.get('basis')})"))
        print(f"[{target}] {frac_txt}; paired t={fp['t']:.3f} p={fp['p_value']:.4f} "
              f"({fp['folds_won']}/{fp['n_folds']} folds), "
              f"significant={out.get('beats_baseline_significant')}")
    if spec.kind == "survival":
        sr = out["survival"]
        print(f"[{target}] c_index={sr['c_index']:.4f}  "
              f"nll_uncensored={sr['uncensored']['aft_nloglik']:.4f} "
              f"(n={sr['uncensored']['n']})  "
              f"nll_censored={sr['censored']['aft_nloglik']:.4f} "
              f"(n={sr['censored']['n']})")

    # Stash the degradation trio predictions for the family-level calibration report.
    if spec.family == "degradation_regressor":
        shared.setdefault("degradation", {})[spec.name] = {
            "y": split.y_ev, "pred": model_pred, "lap_ids": split.lap_ids_ev}

    # ── Elevations: one per model family; each wrapped, never a gate ──────────────
    if target in ELEVATION_TARGETS:
        try:
            sample_n = min(SHAP_SAMPLE, len(split.X_tr))
            Xs = split.X_tr.sample(sample_n, random_state=S.RANDOM_STATE)
            perm_n = min(PERM_SAMPLE, len(split.X_ev))
            idx = np.random.default_rng(S.RANDOM_STATE).choice(len(split.X_ev), perm_n, replace=False)
            out["importance"] = dual_importance(
                model, spec, Xs, split.X_ev.iloc[idx], split.y_ev[idx],
                None if split.cens_ev is None else split.cens_ev[idx], scale)
        except Exception as e:
            out["importance_error"] = str(e)
        try:
            out["ablation"] = ablation(spec, params, split.X_tr, split.y_tr,
                                       split.X_ev, split.y_ev, target,
                                       split.cens_tr, split.cens_ev, scale, split.w_tr)
        except Exception as e:
            out["ablation_error"] = str(e)
        try:
            out["learning_curve"] = learning_curve(spec, params, split.X_tr, split.y_tr,
                                                    split.seasons_tr, split.X_ev, split.y_ev,
                                                    target, split.cens_tr, split.cens_ev, scale,
                                                    split.w_tr)
        except Exception as e:
            out["learning_curve_error"] = str(e)
        # Open item 15. Opt-in: ~46 refits, and it answers a question about the model
        # rather than gating a release, so it must not sit in the default path.
        if RUN_ATTRIBUTION and target in ATTRIBUTION_TARGETS:
            try:
                out["within_stint_attribution"] = within_stint_attribution(
                    spec, params, split.X_tr, split.y_tr,
                    train_dims["stint_id"].to_numpy(),
                    split.X_ev, split.y_ev, stint_ev, model_pred, hib, target,
                    split.cens_tr, split.cens_ev, scale,
                    lap_tr=train_dims["lap_in_stint"].to_numpy(), lap_ev=order_ev,
                    w_tr=split.w_tr)
            except Exception as e:
                out["within_stint_attribution_error"] = f"{type(e).__name__}: {e}"
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
def run(targets: list[str], version: str = S.MODEL_VERSION_DEFAULT,
        censoring_variant: str = "standard") -> dict:
    ARTEFACTS_DIR.mkdir(parents=True, exist_ok=True)
    dims_all = load_cohort_dims()
    shared: dict = {}

    models: dict[str, dict] = {}
    for t in targets:
        models[t] = evaluate_target(t, version, dims_all, shared, censoring_variant)

    report: dict = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "censoring_variant": censoring_variant,
        "holdout_season": int(F.load_features(censoring_variant=censoring_variant).holdout_season),
        "evaluation_mode": next(iter(
            {m for m in [models[t].get("kind") for t in models]}), None) and "see_models",
        "models": models,
    }
    # Re-derive the split mode from any model run (uniform across targets today).
    sample_bundle = F.load_features(target=targets[0], censoring_variant=censoring_variant)
    sample_split = _evaluation_split(sample_bundle)
    report["evaluation_mode"] = sample_split.mode
    report["eval_season"] = sample_split.eval_season
    report["holdout_populated"] = sample_split.mode == "holdout"

    # Family-level calibration for the degradation quantile trio.
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

        # 09a: CRPS alongside the trio, plus its calibration/resolution/uncertainty
        # decomposition (ml/src/crps.py). Same row set as the calibration block above.
        try:
            alpha_preds = {
                S.TARGET_BY_NAME[name].quantile_alpha: deg[name]["pred"]
                for name in ("degradation_regressor_p10", "degradation_regressor_p50",
                            "degradation_regressor_p90")}
            report["crps"] = CR.crps_report(y, alpha_preds)
            d = report["crps"]["decomposition"]
            print(f"[degradation trio] CRPS={report['crps']['crps']:.4f}  "
                  f"mcb={d['mcb']:.4f} dsc={d['dsc']:.4f} unc={d['unc']:.4f}")
        except Exception as e:
            report["crps_error"] = str(e)

    # Adversarial leakage probe (once, on the p50 training split).
    try:
        b = F.load_features(target="degradation_regressor_p50", censoring_variant=censoring_variant)
        report["leakage_probe"] = leakage_probe(b.X_train, b.groups_train.to_numpy())
    except Exception as e:
        report["leakage_probe_error"] = str(e)

    all_beat = all(m["beats_baseline"] for m in models.values())
    report["all_models_beat_baseline"] = all_beat
    report["underperforming_cohorts_total"] = sum(
        len(m["underperforming_cohorts"]) for m in models.values())

    # ── Phase 6: the clustering fact, and the claims that do not survive it ──────────
    try:
        report["stint_grain"] = stint_fold_purity(sample_bundle)
    except Exception as e:  # noqa: BLE001
        report["stint_grain_error"] = str(e)
    # Recorded, never deleted. A `beats_baseline: true` whose interval spans zero is the
    # most useful line in the card: it is the difference between a model that is better
    # and a model that has not been shown to be.
    report["claims_inside_noise"] = sorted(
        name for name, m in models.items()
        if m.get("beats_baseline") and m.get("beats_baseline_significant") is not True)
    report["all_claims_significant"] = not report["claims_inside_noise"]

    EVAL_METRICS_PATH.write_text(json.dumps(report, indent=2, default=_json_default))
    print(f"\nwrote {EVAL_METRICS_PATH}  "
          f"(all_beat_baseline={all_beat}, mode={report['evaluation_mode']}, "
          f"eval_season={report['eval_season']})")
    if report.get("claims_inside_noise"):
        print("claims inside noise (kept, not deleted): "
              + ", ".join(report["claims_inside_noise"]))
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
    ap.add_argument("--censoring-variant", default="standard",
                    choices=["standard", "10b"],
                    help="censoring scheme for stint-life target (default: standard)")
    ap.add_argument("--attribution", action="store_true",
                    help="also run the within-stint attribution (open item 15): "
                         "drop-vs-flatten over groups, channels and per-lap features. "
                         "~46 refits per target, minutes not seconds.")
    args = ap.parse_args()
    targets = [t.name for t in S.PRODUCTION_TARGETS] if args.all else (
        [args.target] if args.target else None)
    if not targets:
        ap.error("pass --target <name> or --all")
    global RUN_ATTRIBUTION
    RUN_ATTRIBUTION = bool(args.attribution)
    report = run(targets, args.version, args.censoring_variant)
    return 0 if all(m["beats_baseline"] for m in report["models"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
