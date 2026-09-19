"""10d -- fix the stint-life calibration defect: the four declared arms, re-run on v12.

WHY THIS IS A RE-RUN. `10d` was measured on 2026-09-10 and found that the defect it was
created to fix did not exist as described: the 1.232 slope it inherited from `10c` was an
IN-SAMPLE number, and out of sample the slope was 0.666, on the other side of 1.0. That
finding stands. What does not stand is the substrate under it -- `08m` repaired the
compound wear curve and `08n` shipped v12 on 2026-09-16, so the `cv_final_fold` eval fold
is 19,973 laps / 9,149 green-pit today against the 20,272 / 9,270 every figure in that
verdict was measured on. And the label moved: `D5` settled on the realised stint ending
and `10b`'s 2026-09-18 ruling rejected its own label, so the incumbent this run compares
against is `standard`, not `10b`.

THE ARMS, as pre-registered 2026-09-10 and re-declared with their addendum 2026-09-18.

    A0   nothing -- the incumbent, refit honestly, `standard` labels, shipped v12 params
    A1   aft_loss_distribution_scale in [0.30, 1.40]
    A2   aft_loss_distribution in {normal, logistic, extreme}, each at its own A1 scale
    A3   label construction in {standard, 10b}
    A4   capacity: max_depth in {3,4,5,6,8} x n_estimators in {200,400}
    A4x  capacity: max_depth 2 -- PROMOTED from post-hoc extension to declared arm

Every arm is selected on the TRAINING SIDE ONLY -- expanding season folds inside
2018-2023, pooled out-of-fold predictions. Nothing is selected on the 2024 rows. That is
the constraint the method section sets, and it is what keeps this a fit change rather
than a post-hoc recalibration against the green-pit evaluation sample.

METHOD (gates.md).

    gate 5   the cause label must not be inside FEATURE_COLUMNS
    gate 2*  substituted: every arm shares one split; A1/A2/A4/A4x share the labels too
    gate 1a  E._fit/_score reproduces today's published v12 headline
    gate 1b  the 8 figures of 10b section 4's A0 row, to every stored digit
    gate 1c  substrate drift against what the 2026-09-10 verdict scored
    gate 1d  the optimism gap -- the original gate-1 finding, re-measured on v12
    gate 6   selection on the training side only, pooled OOF, declared before the run
    gate 3   5-reseed floors, XGBoost's `seed` genuinely varied, each arm its own
    gate 4   inapplicable -- no arm adds a column; the reseed null is the substitute
    gate 7   Construction A exactly as declared, AND Construction B beside it
    boot     paired race-level cluster bootstrap, 200 draws, races the unit

Reads the warehouse read-only. Writes nothing to `ml/models/`, nothing to the warehouse,
nothing to `ml/artefacts/evaluation_metrics.json`: `evaluate.run()` is never called. The
only outputs are the JSON and log named below.

Usage:  PYTHONPATH=. python3 scripts/arms_10d_calibration_arms.py
        PYTHONPATH=. python3 scripts/arms_10d_calibration_arms.py --boot-draws 20
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import linregress, norm

from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S
from ml.src import survival as SV
from ml.src import train as T

TARGET = "stint_life_regressor"

# ─── Pre-registered constants (leaf doc; A1-A4 2026-09-10, A4x 2026-09-18) ──────────
SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(5))   # 20260528-32
BOOT_DRAWS = 200
BOOT_SEED = 20260910          # the seed the 2026-09-10 run used, races the unit
E_VALUE_C = 1.5               # Construction A: s = c*sqrt(2)*sd, lambda = 2/c
E_VALUE_G = 1.0               # Construction B: safe-t, a one-sd effect
A1_SCALES = tuple(round(0.30 + 0.10 * i, 2) for i in range(12))       # 0.30 .. 1.40
A2_DISTRIBUTIONS = ("normal", "logistic", "extreme")
A4_DEPTHS = (3, 4, 5, 6, 8)
A4X_DEPTHS = (2,)
A4_N_ESTIMATORS = (200, 400)
N_INNER_SPLITS = 5

# The declared e-value family: five arms. A0 is the baseline, not a member.
DECLARED_ARMS = ("A1", "A2", "A3", "A4", "A4x")

# What the 2026-09-10 verdict scored, for the drift table. NOT a reproduction target --
# the point of the table is that it cannot be one.
PUBLISHED_0910 = {
    "n_eval_laps": 20272, "n_green_pit": 9270, "n_eval_races": 24,
    "A0_was_label": "10b",
    "A0_slope": 0.6664, "A0_auc": 0.6914, "A0_brier": 0.2059,
    "A3_standard_slope": 0.7000, "A3_standard_auc": 0.6935, "A3_standard_brier": 0.1903,
    "A4_depth3_slope": 0.8791, "A4x_depth2_slope": 1.0735,
    "slope_sd": 0.006208, "slope_floor": 0.017559,
}
# 10b section 4's A0 row, republished 2026-09-18 on this substrate. Gate 1b's anchor.
ANCHOR_10B_A0 = {
    "green_pit_nll": 3.4376675618143007,
    "green_pit_ipcw_brier": 0.1903917717687864,
    "green_pit_auc": 0.6895774514309989,
    "calibration_slope": 0.6735936337052354,
    "calibration_intercept": 0.23187910000373496,
    "mean_log_bias": -0.27413700814322794,
    "margin_sd": 0.5818239268804684,
}

OUT_DIR = Path("_improvements/eval/10d")
OUT = OUT_DIR / "arms_10d_calibration_arms.json"
LOG = OUT_DIR / "arms_10d_calibration_arms.log"


# ─── Fit helpers, through evaluate.py / train.py's own paths ────────────────────────
def fit_seeded(spec, params: dict, X, y, cens, w, seed: int):
    """E._fit with the seed overridden, and nothing else changed.

    `AFTBooster` takes `seed` inside its own params dict, where `**p` merges AFTER the
    default, so injecting it there is the supported route. Varying it is the point:
    `subsample` and `colsample_bytree` redraw, so the refits genuinely differ.
    """
    model = T._make_model(spec, {**params, "seed": int(seed)})
    weights = np.asarray(w, dtype=np.float32) if w is not None else T._sample_weight(spec, y)
    model.fit(X, y, sample_weight=weights, is_censored=np.asarray(cens, dtype=bool))
    return model


def median_laps(margin: np.ndarray, scale: float, distribution: str) -> np.ndarray:
    """Margin -> median remaining life, correct for the distribution actually fitted.

    `SV.laps_from_margin` hard-codes the log-normal, whose standardised median is 0 so
    the median is exp(margin). `logistic` is also symmetric about 0, so it shares that.
    `extreme` (smallest extreme value / Gumbel) is NOT: its standardised median is
    log(log 2) = -0.3665, so exp(margin) is its 63rd percentile, not its 50th. This is
    the plumbing the 2026-09-10 run said `extreme` would need if A2 had selected it, and
    it exists here so that the arm can be scored honestly rather than screened and
    dropped.
    """
    m = np.asarray(margin, dtype=np.float64)
    if distribution == "extreme":
        m = m + scale * np.log(np.log(2.0))
    return np.clip(np.exp(m) - S.AFT_LABEL_SHIFT, 0.0, None)


def xgb_aft_nloglik(model, X, y, cens) -> float:
    """XGBoost's OWN aft-nloglik on a row set, at the model's own distribution.

    A2 compares distributions, and `SV.aft_nloglik` assumes the log-normal -- scoring
    `extreme` with it would compare three fits through one distribution's likelihood,
    which is not a comparison. The booster's own eval metric reads the distribution and
    scale out of the params it was trained with, so it is the only scorer that is
    correct for all three.
    """
    d = xgb.DMatrix(X, feature_names=list(X.columns), missing=np.nan)
    lower, upper = SV.aft_bounds(y, np.asarray(cens, dtype=bool))
    d.set_float_info("label_lower_bound", lower)
    d.set_float_info("label_upper_bound", upper)
    raw = model.booster.eval(d)          # "[0]\teval-aft-nloglik:1.836400"
    return float(raw.rsplit(":", 1)[1])


# ─── The headline instrument: the green-pit stratum ─────────────────────────────────
def green_pit_metrics(y, pred, cens, scale: float, n_bins: int = 5) -> dict:
    """Every declared metric and diagnostic on one row set, in 10d's own conventions."""
    y = np.asarray(y, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    cens = np.asarray(cens, dtype=bool)
    out: dict = {"n": int(len(y)), "n_censored": int(cens.sum())}

    out["green_pit_nll"] = float(SV.aft_nloglik(y, pred, cens, scale))
    brier, _ = SV.ipcw_brier(y, pred, cens, scale)
    out["green_pit_ipcw_brier"] = float(brier)
    auc, _ = SV.time_dependent_auc(y, pred, cens, scale)
    out["green_pit_auc"] = None if np.isnan(auc) else float(auc)

    cal = SV.d_calibration(y, pred, cens, scale, n_bins=n_bins)
    slope = cal.get("calibration_slope")
    out["calibration_slope"] = None if slope is None or np.isnan(slope) else float(slope)
    exp_r = np.asarray(cal["exp_event_rates"], dtype=np.float64)
    obs_r = np.asarray(cal["obs_event_rates"], dtype=np.float64)
    if len(exp_r) > 2:
        out["calibration_intercept"] = float(linregress(exp_r, obs_r).intercept)
    else:
        out["calibration_intercept"] = None
    out["calibration_bins"] = {"predicted": exp_r.tolist(), "observed": obs_r.tolist()}

    # 10d's sign convention: NEGATIVE mean log bias = the model over-predicts remaining
    # life (pred > y), which is the direction that is dangerous for the gauge.
    sh = S.AFT_LABEL_SHIFT
    out["mean_log_bias"] = float(np.mean(np.log(y + sh)
                                         - np.log(np.maximum(pred + sh, 1e-12))))
    out["margin_sd"] = float(np.std(np.log(np.maximum(pred + sh, 1e-12)), ddof=1))
    return out


def abs_slope_minus_one(m: dict) -> float:
    s = m.get("calibration_slope")
    return float("inf") if s is None else abs(s - 1.0)


# ─── E-values ───────────────────────────────────────────────────────────────────────
def construction_a(delta: float, sd: float, c: float = E_VALUE_C) -> dict:
    """E = exp((2/c^2) * (z - 1)), z = delta / (sqrt(2)*sd). Exactly as declared.

    Validity is CONDITIONAL on the true sigma being <= s = c*sqrt(2)*sd, and `sd` here is
    a five-seed plug-in of REFIT noise. The 2026-09-10 verdict established that the
    estimand's uncertainty is SAMPLING noise, 16-30x larger, so this is reported because
    it was declared -- not because it should be believed. See Construction B beside it.
    """
    z = delta / (np.sqrt(2.0) * sd) if sd > 0 else (0.0 if delta == 0 else np.inf)
    return {"delta": float(delta), "sd": float(sd), "c": c, "lambda": 2.0 / c,
            "z": float(z), "E": float(np.exp((2.0 / c ** 2) * (z - 1.0)))}


def construction_b(d: np.ndarray, g: float = E_VALUE_G) -> dict:
    """Paired safe-t: E = (1+ng)^(-1/2) * [(1+t^2/(n-1))/(1+t^2/((1+ng)(n-1)))]^(n/2).

    Grunwald / de Heide / Koolen's one-sample Bayes factor under a right-Haar prior on
    sigma. Exact for any unknown sigma, which is what removes the plug-in-scale hole
    Construction A falls into here.
    """
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    d_bar, s_d = float(d.mean()), float(d.std(ddof=1))
    cap = (1.0 + n * g) ** ((n - 1) / 2.0)
    if s_d == 0.0:
        t = 0.0 if d_bar == 0.0 else float(np.copysign(np.inf, d_bar))
    else:
        t = float(np.sqrt(n) * d_bar / s_d)
    if np.isfinite(t):
        num = 1.0 + t * t / (n - 1)
        den = 1.0 + t * t / ((1.0 + n * g) * (n - 1))
        e = (1.0 + n * g) ** -0.5 * (num / den) ** (n / 2.0)
    else:
        e = cap
    return {"n": n, "g": g, "d_bar": d_bar, "s_d": s_d, "t": t, "E": float(e),
            "direction_is_improvement": bool(d_bar > 0),
            "max_attainable_E": float(cap)}


def construction_b_validity(n_draws: int = 100_000, seed: int = S.RANDOM_STATE) -> dict:
    """Null mean of E must be 1, and the reference's worked example must return 17.0."""
    rng = np.random.default_rng(seed)
    out: dict = {}
    n, g = len(SEEDS), E_VALUE_G
    for sigma in (0.0001, 0.01, 1.0):
        d = rng.normal(0.0, sigma, size=(n_draws, n))
        t = np.sqrt(n) * d.mean(axis=1) / d.std(axis=1, ddof=1)
        num = 1.0 + t ** 2 / (n - 1)
        den = 1.0 + t ** 2 / ((1.0 + n * g) * (n - 1))
        e = (1.0 + n * g) ** -0.5 * (num / den) ** (n / 2.0)
        out[f"sigma={sigma}"] = {"mean_E": float(e.mean()),
                                 "mc_se": float(e.std(ddof=1) / np.sqrt(n_draws))}
    w = construction_b(np.array([0.0121, 0.0088, 0.0154, 0.0067, 0.0110]))
    out["reference_worked_example"] = {"t": w["t"], "E": w["E"], "published": 17.0}
    return out


def ebh(evals: dict[str, float], alpha: float = 0.05) -> dict:
    """e-BH: sort descending, k* = max{k : E_[k] >= n/(alpha*k)}, reject the k* largest."""
    order = sorted(evals.items(), key=lambda kv: kv[1], reverse=True)
    n = len(order)
    ladder, k_star = [], 0
    for k, (arm, e) in enumerate(order, start=1):
        thr = n / (alpha * k)
        q = bool(e >= thr)
        ladder.append({"rank": k, "arm": arm, "E": float(e), "threshold": thr,
                       "qualifies": q})
        if q:
            k_star = k
    return {"n_declared_arms": n, "alpha": alpha, "k_star": k_star,
            "rejected": [r["arm"] for r in ladder[:k_star]], "ladder": ladder,
            "threshold_for_a_lone_rejection": n / alpha}


# ─── Cause labels and race ids ──────────────────────────────────────────────────────
def cause_and_race(lap_ids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    con = duckdb.connect(S.DUCKDB_PATH, read_only=True)
    try:
        df = con.execute(
            f"""SELECT DISTINCT m.lap_id, sf.stint_end_cause, m.race_id
                FROM {S.MART} m
                JOIN {S.STINT_FEATURES} sf ON m.stint_id = sf.stint_id""").df()
    finally:
        con.close()
    cause = dict(zip(df["lap_id"], df["stint_end_cause"]))
    race = dict(zip(df["lap_id"], df["race_id"]))
    return (np.array([cause.get(l) for l in lap_ids], dtype=object),
            np.array([race.get(l) for l in lap_ids], dtype=object))


# ─── Train-side inner CV: pooled out-of-fold selection ──────────────────────────────
class InnerFolds:
    """Expanding season folds INSIDE the training side of cv_final_fold (2018-2023).

    Nothing in here has ever seen a 2024 row. The pooled out-of-fold predictions are the
    selection signal for every arm: each row is scored by a model that did not fit it,
    and within one configuration every fold shares a scale, so pooling is legitimate.
    """

    def __init__(self, split, gp_tr: np.ndarray):
        seasons = np.asarray(split.seasons_tr)
        train_seasons = sorted({int(x) for x in seasons.tolist()})
        self.train_seasons = train_seasons
        self.folds = list(T._season_folds(seasons, train_seasons,
                                          n_splits=N_INNER_SPLITS))
        self.split = split
        self.gp = gp_tr

    def evaluate(self, params: dict, variant_split=None, distribution: str = "normal"):
        """Fit every fold, pool OOF green-pit predictions, return the selection signal.

        `variant_split` lets A3 swap the LABELS (censoring flags) while keeping the same
        rows -- it is the only arm that touches them.
        """
        sp = variant_split if variant_split is not None else self.split
        spec = S.TARGET_BY_NAME[TARGET]
        scale = float(params.get("aft_loss_distribution_scale", S.AFT_SCALE_DEFAULT))
        oof_idx, oof_pred = [], []
        per_fold, xgb_nll = [], []
        for tr, ev in self.folds:
            w = None if sp.w_tr is None else sp.w_tr[tr]
            m = T._make_model(spec, dict(params))
            weights = (np.asarray(w, dtype=np.float32) if w is not None
                       else T._sample_weight(spec, sp.y_tr[tr]))
            m.fit(sp.X_tr.iloc[tr], sp.y_tr[tr], sample_weight=weights,
                  is_censored=sp.cens_tr[tr])
            Xv = sp.X_tr.iloc[ev]
            pred = median_laps(m.predict_margin(Xv), scale, distribution)
            xgb_nll.append(xgb_aft_nloglik(m, Xv, sp.y_tr[ev], sp.cens_tr[ev]))
            g = self.gp[ev]
            if g.sum() > 50:
                per_fold.append(green_pit_metrics(sp.y_tr[ev][g], pred[g],
                                                  sp.cens_tr[ev][g], scale))
            oof_idx.append(ev)
            oof_pred.append(pred)
        idx = np.concatenate(oof_idx)
        pred = np.concatenate(oof_pred)
        g = self.gp[idx]
        pooled = green_pit_metrics(sp.y_tr[idx][g], pred[g], sp.cens_tr[idx][g], scale)
        return {
            "pooled_oof": pooled,
            "pooled_abs_slope_minus_1": abs_slope_minus_one(pooled),
            "xgb_aft_nloglik_mean": float(np.mean(xgb_nll)),
            "xgb_aft_nloglik_by_fold": [float(v) for v in xgb_nll],
            "per_fold_slope": [m.get("calibration_slope") for m in per_fold],
            "n_folds": len(self.folds),
            "n_pooled_green_pit": int(g.sum()),
        }


# ─── Main ───────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot-draws", type=int, default=BOOT_DRAWS)
    ap.add_argument("--skip-boot", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    t_start = time.time()

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        lines.append(msg)

    spec = S.TARGET_BY_NAME[TARGET]
    base_params = E._params_for(TARGET, S.MODEL_VERSION_DEFAULT)
    report: dict = {
        "item": "10d", "generated_at": pd.Timestamp.utcnow().isoformat(),
        "substrate": {"model_version": S.MODEL_VERSION_DEFAULT,
                      "n_feature_columns": len(S.FEATURE_COLUMNS),
                      "params": base_params,
                      "params_source": f"ml/models/{TARGET}_best_params.json"},
        "seeds": list(SEEDS), "declared_arms": list(DECLARED_ARMS),
        "a1_scales": list(A1_SCALES), "a2_distributions": list(A2_DISTRIBUTIONS),
        "a4_grid": {"max_depth": list(A4_DEPTHS), "n_estimators": list(A4_N_ESTIMATORS)},
        "a4x_grid": {"max_depth": list(A4X_DEPTHS),
                     "n_estimators": list(A4_N_ESTIMATORS)},
    }

    log("=" * 78)
    log("10d -- fix the stint-life calibration defect: A1-A4 + A4x, re-run on v12")
    log(f"substrate {S.MODEL_VERSION_DEFAULT}, {len(S.FEATURE_COLUMNS)} feature columns")
    log("=" * 78)

    # ── gate 5 ──────────────────────────────────────────────────────────────────────
    log("\n[gate 5] label-adjacency: the cause label must not be a feature")
    leak = [c for c in ("stint_end_cause", S.STINT_LIFE_CENSOR_COLUMN,
                        "end_regime", "end_cause_confidence")
            if c in set(S.FEATURE_COLUMNS)]
    report["gate_5"] = {"label_columns_in_feature_contract": leak, "pass": not leak}
    log(f"  columns leaking into FEATURE_COLUMNS: {leak or 'none'}  "
        f"-> {'PASS' if not leak else 'FAIL'}")
    if leak:
        raise SystemExit("gate 5 failed: the cause label is inside the feature contract")

    # ── setup: both label constructions ─────────────────────────────────────────────
    log("\n[setup] loading both label constructions")
    bundles, splits = {}, {}
    for variant in ("standard", "10b"):
        bundles[variant] = F.load_features(target=TARGET, censoring_variant=variant)
        splits[variant] = E._evaluation_split(bundles[variant])
        s = splits[variant]
        log(f"  {variant}: n_tr={len(s.y_tr)} n_ev={len(s.y_ev)} "
            f"cens_tr={s.cens_tr.mean():.4f} cens_ev={s.cens_ev.mean():.4f}")
    sp, sp10b = splits["standard"], splits["10b"]

    # ── gate 2 substitute ───────────────────────────────────────────────────────────
    log("\n[gate 2*] one split for every arm; only A3 touches the labels")
    ident = {
        "X_tr_identical": bool(sp.X_tr.equals(sp10b.X_tr)),
        "X_ev_identical": bool(sp.X_ev.equals(sp10b.X_ev)),
        "y_tr_identical": bool(np.array_equal(sp.y_tr, sp10b.y_tr)),
        "y_ev_identical": bool(np.array_equal(sp.y_ev, sp10b.y_ev)),
        "lap_ids_ev_identical": bool(np.array_equal(sp.lap_ids_ev, sp10b.lap_ids_ev)),
        "split_mode": sp.mode, "eval_season": int(sp.eval_season),
        "train_seasons": sorted({int(x) for x in sp.seasons_tr.tolist()}),
        "cens_tr_rows_differing": int((sp.cens_tr != sp10b.cens_tr).sum()),
        "cens_ev_rows_differing": int((sp.cens_ev != sp10b.cens_ev).sum()),
    }
    ident["pass"] = all(v for k, v in ident.items() if k.endswith("_identical"))
    report["gate_2_substitute"] = ident
    for k in [k for k in ident if k.endswith("_identical")]:
        log(f"  {k}: {ident[k]}")
    log(f"  censoring flags differing: train {ident['cens_tr_rows_differing']}, "
        f"eval {ident['cens_ev_rows_differing']}  <- the entire content of A3")
    if not ident["pass"]:
        raise SystemExit("gate 2 substitute failed: the arms do not share a split")

    # ── the green-pit stratum ───────────────────────────────────────────────────────
    cause_ev, race_ev = cause_and_race(sp.lap_ids_ev)
    cause_tr, _ = cause_and_race(sp.lap_ids_tr)
    gp = cause_ev == "green_pit"
    gp_tr = cause_tr == "green_pit"
    n_races = len({r for r in race_ev.tolist()})
    report["green_pit_stratum"] = {
        "n_eval_laps": int(len(sp.y_ev)), "n_green_pit": int(gp.sum()),
        "n_eval_races": int(n_races),
        "n_green_pit_races": int(len({r for r in race_ev[gp].tolist()})),
        "censored_within_stratum_standard": float(sp.cens_ev[gp].mean()),
        "n_green_pit_train": int(gp_tr.sum()),
        "eval_cause_counts": {str(k): int(v) for k, v in
                              pd.Series(cause_ev.astype(str)).value_counts().items()},
    }
    log(f"\n[setup] green-pit stratum: {gp.sum()} eval laps over {n_races} races, "
        f"censoring {sp.cens_ev[gp].mean():.4f}; {gp_tr.sum()} train-side laps")

    # ── gate 1a / 1b: the instrument ────────────────────────────────────────────────
    log("\n[gate 1a] reproduce today's published v12 headline through E._fit/_score")
    pub = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())
    pub_headline = float(pub["models"][TARGET]["headline"])
    m_a0 = E._fit(spec, base_params, sp.X_tr, sp.y_tr, sp.cens_tr, sp.w_tr)
    repro = E._score(spec, sp.y_ev, E._predict_index(spec, m_a0, sp.X_ev),
                     sp.cens_ev, m_a0.scale)
    ok_a = repro == pub_headline
    report["gate_1a"] = {"published_headline": pub_headline,
                         "published_version": pub.get("version"),
                         "published_censoring_variant": pub.get("censoring_variant"),
                         "reproduced_headline": repro, "exact": bool(ok_a)}
    log(f"  published  ({pub.get('version')}, {pub.get('censoring_variant')}): "
        f"{pub_headline!r}")
    log(f"  reproduced (E._fit/_score, A0/standard):        {repro!r}")
    log(f"  exact: {ok_a}  -> {'PASS' if ok_a else 'FAIL'}")
    if not ok_a:
        raise SystemExit("gate 1a failed: the harness does not reproduce the v12 headline")

    log("\n[gate 1b] reproduce 10b section 4's A0 row -- all 8 figures, every digit")
    a0_pred = m_a0.predict(sp.X_ev)
    a0 = green_pit_metrics(sp.y_ev[gp], a0_pred[gp], sp.cens_ev[gp], m_a0.scale)
    anchor = {k: {"published": v, "reproduced": a0[k], "exact": bool(a0[k] == v)}
              for k, v in ANCHOR_10B_A0.items()}
    anchor_ok = all(v["exact"] for v in anchor.values())
    report["gate_1b"] = {"anchors": anchor, "all_exact": anchor_ok}
    for k, v in anchor.items():
        log(f"  {k:24s} {v['reproduced']!r}  {'EXACT' if v['exact'] else 'DIFFERS'}")
    log(f"  -> {'PASS' if anchor_ok else 'FAIL'}")
    if not anchor_ok:
        raise SystemExit("gate 1b failed: 10b section 4's A0 row does not reproduce")

    # ── gate 1c: substrate drift ────────────────────────────────────────────────────
    drift = {
        "published_2026_09_10": PUBLISHED_0910,
        "today_n_eval_laps": int(len(sp.y_ev)), "today_n_green_pit": int(gp.sum()),
        "today_n_eval_races": int(n_races),
        "reproduction_of_the_2026_09_10_figures_possible": False,
        "why": ("08m rebuilt the warehouse and 08n shipped v12 on 2026-09-16, after the "
                "2026-09-10 run. The eval rows are not the same rows, so no figure that "
                "run published can be reproduced; gate 1 is anchored on today's "
                "published v12 headline and on 10b section 4's A0 row instead."),
    }
    report["gate_1c_substrate_drift"] = drift
    log("\n[gate 1c] substrate drift since the 2026-09-10 run")
    log(f"  eval laps  {PUBLISHED_0910['n_eval_laps']} -> {len(sp.y_ev)}")
    log(f"  green-pit  {PUBLISHED_0910['n_green_pit']} -> {int(gp.sum())}")
    log(f"  eval races {PUBLISHED_0910['n_eval_races']} -> {n_races}")
    log(f"  A0's label {PUBLISHED_0910['A0_was_label']} -> standard (D5; 10b rejected)")

    # ── gate 1d: the optimism gap, re-measured on v12 ───────────────────────────────
    log("\n[gate 1d] the optimism gap -- the original gate-1 finding, re-measured on v12")
    b = bundles["standard"]
    cens_all = b.meta_train[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
    m_in = E._fit(spec, base_params, b.X_train, b.y_train.to_numpy(), cens_all, None)
    in_pred = m_in.predict(sp.X_ev)
    a0_in = green_pit_metrics(sp.y_ev[gp], in_pred[gp], sp.cens_ev[gp], m_in.scale)
    optimism = {k: {"honest": a0[k], "in_sample": a0_in[k],
                    "optimism": float(a0_in[k] - a0[k])}
                for k in ("green_pit_nll", "green_pit_ipcw_brier", "green_pit_auc",
                          "calibration_slope", "mean_log_bias")}
    report["gate_1d_optimism"] = {
        "honest_n_fit_rows": int(len(sp.y_tr)),
        "in_sample_n_fit_rows": int(len(b.X_train)), "metrics": optimism,
        "note": ("in_sample refits on EVERY training season, 2018-2024, exactly as "
                 "train.py does, then scores the 2024 eval rows -- which are inside that "
                 "fit. That is the mode every 10c figure was measured in.")}
    for k, v in optimism.items():
        log(f"  {k:22s} honest {v['honest']:+.6f}  in-sample {v['in_sample']:+.6f}  "
            f"optimism {v['optimism']:+.6f}")

    inner = InnerFolds(sp, gp_tr)
    inner10b = InnerFolds(sp10b, gp_tr)
    log(f"\n[gate 6] train-side inner CV: {len(inner.folds)} expanding season folds over "
        f"{inner.train_seasons}; nothing below ever sees a 2024 row")
    report["inner_cv"] = {"n_folds": len(inner.folds),
                          "train_seasons": inner.train_seasons,
                          "selection": "pooled out-of-fold green-pit |slope - 1|"}

    selections: dict[str, dict] = {}

    # ── A1: the AFT scale ───────────────────────────────────────────────────────────
    log("\n[A1] aft_loss_distribution_scale sweep, selected on inner-fold |slope - 1|")
    a1_rows = []
    for s_ in A1_SCALES:
        t0 = time.time()
        r = inner.evaluate({**base_params, "aft_loss_distribution_scale": s_})
        a1_rows.append({"scale": s_,
                        "inner_slope": r["pooled_oof"]["calibration_slope"],
                        "abs_slope_minus_1": r["pooled_abs_slope_minus_1"],
                        "inner_xgb_nll": r["xgb_aft_nloglik_mean"],
                        "inner_brier": r["pooled_oof"]["green_pit_ipcw_brier"]})
        log(f"  scale {s_:.2f}: inner slope {a1_rows[-1]['inner_slope']:.4f}  "
            f"|slope-1| {a1_rows[-1]['abs_slope_minus_1']:.4f}  "
            f"xgb-NLL {a1_rows[-1]['inner_xgb_nll']:.4f}  ({time.time()-t0:.0f}s)")
    a1_best = min(a1_rows, key=lambda r: (r["abs_slope_minus_1"], r["inner_xgb_nll"]))
    a1_nll_best = min(a1_rows, key=lambda r: r["inner_xgb_nll"])
    selections["A1"] = {
        "sweep": a1_rows, "selected": a1_best,
        "params": {**base_params,
                   "aft_loss_distribution_scale": a1_best["scale"]},
        "variant": "standard", "distribution": "normal",
        "inner_nll_optimum_scale": a1_nll_best["scale"],
        "inner_slope_range": [min(r["inner_slope"] for r in a1_rows),
                              max(r["inner_slope"] for r in a1_rows)]}
    log(f"  -> A1 selects scale {a1_best['scale']} (inner |slope-1| "
        f"{a1_best['abs_slope_minus_1']:.4f}); inner-NLL optimum is "
        f"{a1_nll_best['scale']}, shipped is "
        f"{base_params['aft_loss_distribution_scale']}")

    # ── A2: the distributional assumption ───────────────────────────────────────────
    log("\n[A2] aft_loss_distribution, each at its OWN swept scale, on xgb's own NLL")
    a2_rows = []
    for dist in A2_DISTRIBUTIONS:
        best = None
        for s_ in A1_SCALES:
            r = inner.evaluate({**base_params, "aft_loss_distribution": dist,
                                "aft_loss_distribution_scale": s_},
                               distribution=dist)
            row = {"distribution": dist, "scale": s_,
                   "inner_xgb_nll": r["xgb_aft_nloglik_mean"],
                   "inner_slope": r["pooled_oof"]["calibration_slope"]}
            if best is None or row["inner_xgb_nll"] < best["inner_xgb_nll"]:
                best = row
        a2_rows.append(best)
        log(f"  {dist:9s}: best inner xgb-NLL {best['inner_xgb_nll']:.4f} "
            f"at scale {best['scale']:.2f}  (inner slope {best['inner_slope']:.4f})")
    a2_best = min(a2_rows, key=lambda r: r["inner_xgb_nll"])
    selections["A2"] = {
        "sweep": a2_rows, "selected": a2_best,
        "params": {**base_params, "aft_loss_distribution": a2_best["distribution"],
                   "aft_loss_distribution_scale": a2_best["scale"]},
        "variant": "standard", "distribution": a2_best["distribution"],
        "selects_the_incumbent_distribution":
            bool(a2_best["distribution"] == S.AFT_DISTRIBUTION)}
    log(f"  -> A2 selects {a2_best['distribution']} at scale {a2_best['scale']} "
        f"(incumbent distribution is {S.AFT_DISTRIBUTION})")

    # ── A3: the label construction ──────────────────────────────────────────────────
    log("\n[A3] label construction {standard, 10b}, on inner-fold |slope - 1|")
    a3_rows = []
    for variant, folds in (("standard", inner), ("10b", inner10b)):
        r = folds.evaluate(base_params)
        a3_rows.append({"variant": variant,
                        "inner_slope": r["pooled_oof"]["calibration_slope"],
                        "abs_slope_minus_1": r["pooled_abs_slope_minus_1"],
                        "inner_brier": r["pooled_oof"]["green_pit_ipcw_brier"],
                        "inner_xgb_nll": r["xgb_aft_nloglik_mean"]})
        log(f"  {variant:9s}: inner slope {a3_rows[-1]['inner_slope']:.4f}  "
            f"|slope-1| {a3_rows[-1]['abs_slope_minus_1']:.4f}  "
            f"inner green-pit Brier {a3_rows[-1]['inner_brier']:.4f}")
    a3_best = min(a3_rows, key=lambda r: r["abs_slope_minus_1"])
    selections["A3"] = {
        "sweep": a3_rows, "selected": a3_best, "params": dict(base_params),
        "variant": a3_best["variant"], "distribution": "normal",
        "selects_the_incumbent_label": bool(a3_best["variant"] == "standard")}
    log(f"  -> A3 selects the {a3_best['variant']} label "
        f"(incumbent is standard, per D5)")

    # ── A4 / A4x: capacity ──────────────────────────────────────────────────────────
    for name, depths in (("A4", A4_DEPTHS), ("A4x", A4X_DEPTHS)):
        log(f"\n[{name}] capacity grid, on inner-fold |slope - 1|")
        rows = []
        for d_ in depths:
            for n_ in A4_N_ESTIMATORS:
                r = inner.evaluate({**base_params, "max_depth": d_, "n_estimators": n_})
                rows.append({"max_depth": d_, "n_estimators": n_,
                             "inner_slope": r["pooled_oof"]["calibration_slope"],
                             "abs_slope_minus_1": r["pooled_abs_slope_minus_1"],
                             "inner_xgb_nll": r["xgb_aft_nloglik_mean"],
                             "inner_brier": r["pooled_oof"]["green_pit_ipcw_brier"]})
                log(f"  depth {d_} x {n_}: inner slope {rows[-1]['inner_slope']:.4f}  "
                    f"|slope-1| {rows[-1]['abs_slope_minus_1']:.4f}  "
                    f"xgb-NLL {rows[-1]['inner_xgb_nll']:.4f}")
        best = min(rows, key=lambda r: (r["abs_slope_minus_1"], r["inner_xgb_nll"]))
        selections[name] = {
            "sweep": rows, "selected": best,
            "params": {**base_params, "max_depth": best["max_depth"],
                       "n_estimators": best["n_estimators"]},
            "variant": "standard", "distribution": "normal"}
        log(f"  -> {name} selects depth {best['max_depth']} x "
            f"{best['n_estimators']}")

    report["selections"] = selections

    # ── score every arm on 2024, at every seed ──────────────────────────────────────
    log("\n[gate 3] every arm on the 2024 eval fold, 5 seeds, XGBoost's seed varied")
    arms = {"A0": {"params": dict(base_params), "variant": "standard",
                   "distribution": "normal"},
            **{k: {"params": v["params"], "variant": v["variant"],
                   "distribution": v["distribution"]} for k, v in selections.items()}}
    by_seed: dict[str, dict[str, list]] = {}
    canonical: dict[str, dict] = {}
    canonical_pred: dict[str, tuple[np.ndarray, float]] = {}
    METRICS = ("green_pit_nll", "green_pit_ipcw_brier", "green_pit_auc",
               "calibration_slope", "mean_log_bias", "calibration_intercept",
               "margin_sd")
    for arm, cfg in arms.items():
        s_ = splits[cfg["variant"]]
        scale = float(cfg["params"].get("aft_loss_distribution_scale",
                                        S.AFT_SCALE_DEFAULT))
        by_seed[arm] = {m: [] for m in METRICS}
        for i, seed in enumerate(SEEDS):
            t0 = time.time()
            m = fit_seeded(spec, cfg["params"], s_.X_tr, s_.y_tr, s_.cens_tr,
                           s_.w_tr, seed)
            pred = median_laps(m.predict_margin(sp.X_ev), scale, cfg["distribution"])
            gpm = green_pit_metrics(sp.y_ev[gp], pred[gp], sp.cens_ev[gp], scale)
            for k in METRICS:
                by_seed[arm][k].append(gpm[k])
            if i == 0:        # seed 20260528 == E._fit's default, the canonical fit
                canonical[arm] = gpm
                canonical_pred[arm] = (pred, scale)
            log(f"  {arm:4s} seed {seed}: slope {gpm['calibration_slope']:.6f}  "
                f"AUC {gpm['green_pit_auc']:.6f}  "
                f"Brier {gpm['green_pit_ipcw_brier']:.6f}  "
                f"mlb {gpm['mean_log_bias']:+.6f}  ({time.time()-t0:.0f}s)")

    # gate 1b again: the canonical A0 must still be 10b section 4's row
    assert canonical["A0"]["calibration_slope"] == a0["calibration_slope"], \
        "the canonical A0 refit drifted from the gate-1b anchor"

    floors: dict[str, dict] = {}
    for arm in arms:
        floors[arm] = {}
        for k in METRICS:
            a = np.asarray([v for v in by_seed[arm][k] if v is not None],
                           dtype=np.float64)
            sd = float(a.std(ddof=1))
            floors[arm][k] = {"by_seed": a.tolist(), "mean": float(a.mean()), "sd": sd,
                              "delta_noise_2sd": float(2.0 * np.sqrt(2.0) * sd)}
    report["gate_3_reseed_floors"] = floors
    log("\n[gate 3] floors (2*sqrt(2)*sd), each arm its own")
    for arm in arms:
        log(f"  {arm:4s} slope sd {floors[arm]['calibration_slope']['sd']:.6f} "
            f"floor {floors[arm]['calibration_slope']['delta_noise_2sd']:.6f}   "
            f"AUC sd {floors[arm]['green_pit_auc']['sd']:.6f} "
            f"floor {floors[arm]['green_pit_auc']['delta_noise_2sd']:.6f}")

    # ── paired reseed deltas ────────────────────────────────────────────────────────
    paired: dict[str, dict] = {}
    for arm in DECLARED_ARMS:
        a0v = np.asarray(by_seed["A0"]["calibration_slope"], dtype=np.float64)
        arv = np.asarray(by_seed[arm]["calibration_slope"], dtype=np.float64)
        d_slope = np.abs(a0v - 1.0) - np.abs(arv - 1.0)
        d_auc = (np.asarray(by_seed[arm]["green_pit_auc"], dtype=np.float64)
                 - np.asarray(by_seed["A0"]["green_pit_auc"], dtype=np.float64))
        d_brier = (np.asarray(by_seed["A0"]["green_pit_ipcw_brier"], dtype=np.float64)
                   - np.asarray(by_seed[arm]["green_pit_ipcw_brier"], dtype=np.float64))
        d_bias = (np.abs(np.asarray(by_seed["A0"]["mean_log_bias"], dtype=np.float64))
                  - np.abs(np.asarray(by_seed[arm]["mean_log_bias"], dtype=np.float64)))
        f_slope = floors[arm]["calibration_slope"]["delta_noise_2sd"]
        f_auc = floors[arm]["green_pit_auc"]["delta_noise_2sd"]
        paired[arm] = {
            "slope_deltas_by_seed": d_slope.tolist(),
            "slope_delta": float(d_slope.mean()),
            "slope_x_own_floor": (None if f_slope == 0
                                  else float(d_slope.mean() / f_slope)),
            "auc_delta": float(d_auc.mean()),
            "auc_x_own_floor": None if f_auc == 0 else float(d_auc.mean() / f_auc),
            "brier_delta": float(d_brier.mean()),
            "abs_mean_log_bias_delta": float(d_bias.mean()),
            "auc_deltas_by_seed": d_auc.tolist(),
        }
    report["gate_3_paired_reseed_deltas"] = paired

    # ── gate 4 ──────────────────────────────────────────────────────────────────────
    report["gate_4"] = {
        "applicable": False,
        "why": ("the permutation null row-shuffles NEW columns. No arm adds one: A1, A2, "
                "A4 and A4x change how the same 32-feature matrix is fitted and A3 moves "
                "only the censoring flags. Capacity is identical between each arm and A0 "
                "by construction for A1/A2/A3, and IS the arm for A4/A4x -- which is the "
                "correction 10e made to how the 2026-09-10 run phrased this."),
        "substitute": "the 5-seed reseed null; its floors are gate_3_reseed_floors",
    }

    # ── gate 7 ──────────────────────────────────────────────────────────────────────
    log("\n[gate 7] Construction A exactly as declared, and Construction B beside it")
    validity = construction_b_validity()
    report["gate_7_construction_b_validity"] = validity
    log(f"  B validity: worked example t="
        f"{validity['reference_worked_example']['t']:.2f} "
        f"E={validity['reference_worked_example']['E']:.2f} (published 17.0)")
    for k, v in validity.items():
        if k.startswith("sigma="):
            log(f"  B null mean E at {k}: {v['mean_E']:.4f} (+/- {v['mc_se']:.4f})")

    sd_a0_slope = floors["A0"]["calibration_slope"]["sd"]
    e_a, e_b = {}, {}
    for arm in DECLARED_ARMS:
        e_a[arm] = construction_a(paired[arm]["slope_delta"], sd_a0_slope)
        e_b[arm] = construction_b(np.asarray(paired[arm]["slope_deltas_by_seed"]))
    report["gate_7_construction_a"] = {
        "declared": "E = exp(0.8889*(z-1)), z = delta/(sqrt(2)*sd), c=1.5, lambda=4/3",
        "sd_source": "A0's 5-seed reseed sd of the green-pit calibration slope",
        "sd": sd_a0_slope, "arms": e_a,
        "caveat": ("the declared scale is REFIT noise. The estimand's uncertainty is "
                   "SAMPLING noise, which the paired race-cluster bootstrap below puts "
                   "far larger. Reported because it was declared; read through the "
                   "bootstrap.")}
    report["gate_7_construction_b"] = {"g": E_VALUE_G, "arms": e_b}
    log(f"  Construction A sd (A0 slope reseed) = {sd_a0_slope:.6f}")
    for arm in DECLARED_ARMS:
        log(f"  {arm:4s} delta {paired[arm]['slope_delta']:+.4f}  "
            f"A: z {e_a[arm]['z']:.2f} E {e_a[arm]['E']:.4g}   "
            f"B: t {e_b[arm]['t']:+.2f} E {e_b[arm]['E']:.4g}")
    report["gate_7_ebh_construction_a"] = ebh({a: e_a[a]["E"] for a in DECLARED_ARMS})
    report["gate_7_ebh_construction_b"] = ebh({a: e_b[a]["E"] for a in DECLARED_ARMS})
    for tag, key in (("A", "gate_7_ebh_construction_a"),
                     ("B", "gate_7_ebh_construction_b")):
        eb = report[key]
        log(f"  item-level e-BH ({tag}) at alpha=0.05 over {eb['n_declared_arms']} "
            f"arms: k*={eb['k_star']}, rejects {eb['rejected']}")

    # ── the paired race-level cluster bootstrap ─────────────────────────────────────
    if not args.skip_boot:
        log(f"\n[boot] paired race-cluster bootstrap, {args.boot_draws} draws, "
            f"seed {BOOT_SEED}, races the unit")
        gp_idx = np.flatnonzero(gp)
        races = np.array([str(r) for r in race_ev[gp]], dtype=object)
        uniq = np.array(sorted(set(races.tolist())), dtype=object)
        rows_by_race = {r: gp_idx[races == r] for r in uniq}
        rng = np.random.default_rng(BOOT_SEED)
        marg: dict[str, dict[str, list[float]]] = {
            a: {"calibration_slope": [], "green_pit_auc": [],
                "green_pit_ipcw_brier": []} for a in arms}
        pair: dict[str, dict[str, list[float]]] = {
            a: {"slope": [], "auc": [], "brier": [], "abs_mean_log_bias": []}
            for a in DECLARED_ARMS}
        t0 = time.time()
        for i in range(args.boot_draws):
            pick = rng.choice(len(uniq), size=len(uniq), replace=True)
            idx = np.concatenate([rows_by_race[uniq[j]] for j in pick])
            y_b, c_b = sp.y_ev[idx], sp.cens_ev[idx]
            mm = {}
            for a in arms:
                pr, sc_ = canonical_pred[a]
                mm[a] = green_pit_metrics(y_b, pr[idx], c_b, sc_)
                for k in marg[a]:
                    if mm[a][k] is not None:
                        marg[a][k].append(float(mm[a][k]))
            for a in DECLARED_ARMS:
                if mm[a]["calibration_slope"] is not None \
                        and mm["A0"]["calibration_slope"] is not None:
                    pair[a]["slope"].append(
                        abs(mm["A0"]["calibration_slope"] - 1.0)
                        - abs(mm[a]["calibration_slope"] - 1.0))
                if mm[a]["green_pit_auc"] is not None \
                        and mm["A0"]["green_pit_auc"] is not None:
                    pair[a]["auc"].append(
                        mm[a]["green_pit_auc"] - mm["A0"]["green_pit_auc"])
                pair[a]["brier"].append(mm["A0"]["green_pit_ipcw_brier"]
                                        - mm[a]["green_pit_ipcw_brier"])
                pair[a]["abs_mean_log_bias"].append(
                    abs(mm["A0"]["mean_log_bias"]) - abs(mm[a]["mean_log_bias"]))
            if (i + 1) % 50 == 0:
                log(f"  {i+1}/{args.boot_draws} draws ({time.time()-t0:.0f}s)")

        def summarise(a: list[float]) -> dict:
            x = np.asarray(a, dtype=np.float64)
            if len(x) == 0:
                return {"n_draws": 0}
            return {"n_draws": int(len(x)), "mean": float(x.mean()),
                    "ci95_low": float(np.percentile(x, 2.5)),
                    "ci95_high": float(np.percentile(x, 97.5)),
                    "p_improves": float((x > 0).mean()),
                    "p_below_one": float((x < 1.0).mean())}

        report["bootstrap_marginal"] = {
            a: {k: summarise(v) for k, v in marg[a].items()} for a in arms}
        report["bootstrap_paired"] = {
            a: {k: summarise(v) for k, v in pair[a].items()} for a in DECLARED_ARMS}
        report["bootstrap_meta"] = {
            "draws": args.boot_draws, "seed": BOOT_SEED, "n_races": int(len(uniq)),
            "unit": "race_id",
            "note": ("marginal intervals are each arm on its own; paired intervals score "
                     "both arms on the SAME resampled races, so the shared race-draw "
                     "noise cancels. The 2026-09-10 verdict section 4 ruled the paired "
                     "bootstrap authoritative where the floor, the e-value and the "
                     "bootstrap disagree, and this run does not re-litigate that.")}
        log("\n[boot] marginal slope intervals")
        for a in arms:
            m_ = report["bootstrap_marginal"][a]["calibration_slope"]
            log(f"  {a:4s} slope {canonical[a]['calibration_slope']:.4f}  "
                f"95% [{m_['ci95_low']:.4f}, {m_['ci95_high']:.4f}]  "
                f"P(<1) {m_['p_below_one']:.3f}")
        log("\n[boot] paired deltas vs A0 (positive = the arm improves)")
        for a in DECLARED_ARMS:
            p_ = report["bootstrap_paired"][a]
            log(f"  {a:4s} slope {p_['slope']['mean']:+.4f} "
                f"[{p_['slope']['ci95_low']:+.4f}, {p_['slope']['ci95_high']:+.4f}] "
                f"P {p_['slope']['p_improves']:.3f}   "
                f"Brier {p_['brier']['mean']:+.4f} "
                f"P {p_['brier']['p_improves']:.3f}   "
                f"AUC {p_['auc']['mean']:+.4f}")

    report["canonical_arms"] = canonical

    # ── the verdict, against the declared three-leg criterion ───────────────────────
    verdict = {"declared_criterion": (
        "(i) |slope-1| decreases vs A0; (ii) paired race-cluster bootstrap "
        "P(improves) >= 0.95; (iii) the AUC cost is no larger than the arm's own AUC "
        "reseed floor. Declared 2026-09-18 with leg (ii) flagged as the bar this run "
        "expects to miss."), "arms": {}}
    for a in DECLARED_ARMS:
        p_ = report.get("bootstrap_paired", {}).get(a, {})
        pi = p_.get("slope", {}).get("p_improves")
        auc_cost = -paired[a]["auc_delta"]
        auc_floor = floors[a]["green_pit_auc"]["delta_noise_2sd"]
        legs = {
            "i_slope_improves": bool(paired[a]["slope_delta"] > 0),
            "ii_bootstrap_p95": (None if pi is None else bool(pi >= 0.95)),
            "iii_auc_cost_within_floor": bool(auc_cost <= auc_floor),
        }
        verdict["arms"][a] = {
            "slope": canonical[a]["calibration_slope"],
            "slope_delta": paired[a]["slope_delta"],
            "bootstrap_p_improves": pi, "auc_cost": float(auc_cost),
            "auc_floor": auc_floor, "legs": legs,
            "passes": bool(all(v for v in legs.values() if v is not None)
                           and legs["ii_bootstrap_p95"] is True)}
    verdict["any_arm_passes"] = any(v["passes"] for v in verdict["arms"].values())
    report["verdict"] = verdict

    log("\n" + "=" * 78)
    log("VERDICT against the pre-registered three-leg criterion")
    for a in DECLARED_ARMS:
        v = verdict["arms"][a]
        log(f"  {a:4s} slope {v['slope']:.4f} (delta {v['slope_delta']:+.4f})  "
            f"legs i/ii/iii = {v['legs']['i_slope_improves']}/"
            f"{v['legs']['ii_bootstrap_p95']}/"
            f"{v['legs']['iii_auc_cost_within_floor']}  passes {v['passes']}")
    log(f"  ANY ARM PASSES: {verdict['any_arm_passes']}")
    log("=" * 78)

    report["runtime_s"] = round(time.time() - t_start, 1)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    LOG.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}\nwrote {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
