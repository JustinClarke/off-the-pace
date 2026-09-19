"""10b — the cause-specific arm: non-green endings treated as censored.

WHY THIS EXISTS, AND WHY IT IS A RE-RUN. `10b` has been measured twice and ruled on
neither time. The first measurement returned +0.179 NLL and was withdrawn: 92.6% of it
was a scoring artefact from comparing a model scored under `standard` labels against one
scored under `10b` labels. The rerun matched the scoring and returned -0.028 -- but it
fitted the booster on every training season, 2018-2024, and scored the 2024 eval rows,
so the eval set sat inside its own training data. That is the identical gate-1 defect
`10d` later found in `10c`, and it is why -0.028 was never ruled on either.

AND THE SUBSTRATE MOVED UNDER ALL OF IT. `08m` rebuilt the warehouse and `08n` shipped
v12 on 2026-09-16. The `cv_final_fold` eval fold is 19,973 laps today against the 20,272
that `10b`, `10c`, `10d` and `10e` all scored. Gate 1's literal requirement -- reproduce
the published headline to six decimals -- CANNOT be met against any figure those four
items published, because the rows are not the same rows. What is anchored instead is
today's published v12 headline, and the drift is reported rather than papered over.

THE DESIGN.

    A0 = `standard` labels -- the realised stint ending. Production's shipped v12
         variant, and what D5 ruled the gauge should mean.
    A1 = `10b` labels     -- every non-green ending recoded to censored.

Same 32-column matrix, same v12 tuned params, same split, same rows. The ONLY thing
that differs is the censoring flag on 9,135 training rows (sc_pit 5,710 + vsc_pit 2,575
+ red 850) and 1,185 eval rows. Capacity is therefore identical BY CONSTRUCTION -- not
by assumption, and unlike `10e`'s hyperparameter re-search, where capacity *was* the arm.

THE SCORING PROBLEM, WHICH IS THE WHOLE METHODOLOGICAL CONTENT. AFT NLL is computed
*against* the censoring flags, so "which labels to score under" is not a detail -- it is
how +0.179 happened. Both arms are scored on the GREEN-PIT STRATUM ONLY, where the two
label constructions are identical row for row: `green_pit` is uncensored under both, `y`
matches exactly, and the metrics' horizon grid (deciles of uncensored `y`) is therefore
the same grid for both arms. Step 1d verifies that array-for-array before anything is
fitted. That stratum is also the tyre-limit set the reframing exists to isolate, and it
carries no censoring at all, so it is the least IPCW-exposed thing `10c` measured.

METHOD (gates.md steps 1-3 are the acceptance set; 4, 5 and 7 are stated too).

    step 1a  E._fit/_score reproduces today's published v12 headline to six decimals
    step 1b  substrate drift against what 10b/10c/10d/10e scored, stated as a table
    step 1c  gate 5: stint_end_cause / is_censored_stint absent from FEATURE_COLUMNS
    step 1d  gate 2 substitute: X, y, lap_ids identical between the two bundles
    step 1e  the optimism gap, both variants, plus the 2x2 scoring table that makes
             the original +0.179 artefact visible in one place
    step 2   both arms at the canonical seed, through evaluate.py's own _fit/_score
    step 3   each arm's OWN 5-reseed floor, XGBoost's `seed` genuinely varied
    step 7   Construction B (paired safe-t), n=5, g=1.0, declared in the leaf doc
             before this ran; verified against 100k null draws and the reference's
             own worked example; reported for both hypotheses including E < 1
    boot     paired race-level cluster bootstrap, 200 draws, races the unit -- the
             instrument 10d section 4 ruled authoritative where the three disagree

Reads the warehouse read-only. Writes nothing to `ml/models/`, nothing to the warehouse,
nothing to `ml/artefacts/evaluation_metrics.json`: `evaluate.run()` is never called. The
only outputs are the JSON and log named below.

Usage:  PYTHONPATH=. python3 scripts/arms_10b_cause_specific_censoring.py
        PYTHONPATH=. python3 scripts/arms_10b_cause_specific_censoring.py --boot-draws 20
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import linregress

from ml.src import attribution as AT
from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S
from ml.src import survival as SV

TARGET = "stint_life_regressor"

# ─── The arms ───────────────────────────────────────────────────────────────────────
ARMS: dict[str, str] = {"A0": "standard", "A1": "10b"}
ARM_OF_RECORD = "A1"          # the challenger; its own floor is the delta's denominator

# ─── Pre-registered constants (leaf doc, 2026-09-18, before any arm was fitted) ─────
SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(5))   # 20260528-32
E_VALUE_G = 1.0               # a one-sd effect, as in 02c / 08h / 08i
BOOT_DRAWS = 200
BOOT_SEED = 20260910          # the seed 10d and 10e both used, races the unit
HYPOTHESES = ("green_pit_nll", "green_pit_ipcw_brier")   # H1, H2 -- the DECLARED two
# Floored and bootstrapped as well, but NOT declared hypotheses and NOT counted in the
# e-value family: quoting a gain with no floor under it is the gap this closes, and
# promoting a diagnostic to a hypothesis after seeing it is the thing gate 6 forbids.
DIAGNOSTICS = ("green_pit_auc", "calibration_slope")
METRICS = HYPOTHESES + DIAGNOSTICS
# Positive delta = 10b improves, per metric. NLL and Brier are lower-is-better, AUC is
# higher-is-better, and the slope is scored on |slope - 1| exactly as 10d and 10e did.
HIGHER_IS_BETTER = {"green_pit_auc": True}
TOWARD_ONE = ("calibration_slope",)

# What 10b/10c/10d/10e all scored, for the drift table. Not a target to reproduce --
# the point of the table is that it CANNOT be reproduced on this substrate.
PUBLISHED = {
    "n_eval_laps": 20272,
    "n_green_pit": 9270,
    "n_eval_races": 24,
    "honest_10b": {"ipcw_brier": 0.205929, "auc": 0.691432, "slope": 0.666397},
    "honest_standard": {"ipcw_brier": 0.190290, "auc": 0.693548, "slope": 0.700013},
    "recorded_10b_delta_nll": -0.0281,
}

OUT_DIR = Path("_improvements/eval/10b")
OUT = OUT_DIR / "arms_10b_cause_specific_censoring.json"
LOG = OUT_DIR / "arms_10b_cause_specific_censoring.log"


# ─── Fit / score, through evaluate.py's own paths (08h/08i's helpers, unchanged) ─────
def fit_seeded(spec: S.TargetSpec, params: dict, X, y, cens, w, seed: int):
    """E._fit with the seed overridden, and nothing else changed.

    `AFTBooster` has no `set_params` -- it takes `seed` inside its own params dict,
    where `**p` merges AFTER the default, so injecting it there is the supported route.
    Varying it is the point: `subsample` and `colsample_bytree` redraw, so the refits
    genuinely differ. 10b's original zero-variance reseed table -- and the "infinity x
    floor" it produced -- came from not varying it.
    """
    from ml.src import train as T
    model = T._make_model(spec, {**params, "seed": int(seed)})
    weights = np.asarray(w, dtype=np.float32) if w is not None else T._sample_weight(spec, y)
    model.fit(X, y, sample_weight=weights, is_censored=np.asarray(cens, dtype=bool))
    return model


def full_fold_nll(spec, model, X_ev, y_ev, cens_ev) -> float:
    """The production headline, through evaluate.py's own scorer.

    The AFT scale is a term in the likelihood, so it must be the scale of the model
    being scored -- `evaluate.run()` takes it off the fitted model and so does this.
    """
    return E._score(spec, y_ev, E._predict_index(spec, model, X_ev), cens_ev, model.scale)


# ─── The headline instrument: the green-pit stratum, matched under both labels ───────
def green_pit_metrics(y, pred, cens, scale: float, n_bins: int = 5) -> dict:
    """Every declared metric and diagnostic on one row set.

    `cens` is passed through rather than assumed all-False: the stratum carries no
    censoring under either label construction (step 1d asserts it), and passing the
    real flags means this function does not silently depend on that being true.
    """
    y = np.asarray(y, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    cens = np.asarray(cens, dtype=bool)
    out: dict = {"n": int(len(y)), "n_censored": int(cens.sum())}

    out["green_pit_nll"] = float(SV.aft_nloglik(y, pred, cens, scale))          # H1
    brier, _ = SV.ipcw_brier(y, pred, cens, scale)
    out["green_pit_ipcw_brier"] = float(brier)                                  # H2
    auc, _ = SV.time_dependent_auc(y, pred, cens, scale)
    out["green_pit_auc"] = None if np.isnan(auc) else float(auc)

    cal = SV.d_calibration(y, pred, cens, scale, n_bins=n_bins)
    slope = cal.get("calibration_slope")
    out["calibration_slope"] = None if slope is None or np.isnan(slope) else float(slope)
    exp_r = np.asarray(cal["exp_event_rates"], dtype=np.float64)
    obs_r = np.asarray(cal["obs_event_rates"], dtype=np.float64)
    # The intercept is not returned by d_calibration; it comes from the SAME linregress
    # on the SAME five binned points, which is the convention 10d and 10e reported.
    if len(exp_r) > 2:
        lr = linregress(exp_r, obs_r)
        out["calibration_intercept"] = float(lr.intercept)
    else:
        out["calibration_intercept"] = None
    out["calibration_bins"] = {"predicted": exp_r.tolist(), "observed": obs_r.tolist()}

    # Mean log-scale bias, 10d's sign convention: NEGATIVE = the model over-predicts
    # remaining life (pred > y), which is the direction that is dangerous for the gauge.
    sh = S.AFT_LABEL_SHIFT
    out["mean_log_bias"] = float(np.mean(np.log(y + sh) - np.log(np.maximum(pred + sh, 1e-12))))
    out["margin_sd"] = float(np.std(np.log(np.maximum(pred + sh, 1e-12)), ddof=1))
    return out


def delta_pair(a0: dict, a1: dict) -> dict:
    """Declared orientation: positive = 10b (A1) improves. Both hypotheses are
    lower-is-better scores, so the delta is A0 minus A1."""
    out = {}
    for k in HYPOTHESES:
        out[k] = float(a0[k] - a1[k])
    # Diagnostics, each in its own natural direction.
    if a0.get("green_pit_auc") is not None and a1.get("green_pit_auc") is not None:
        out["green_pit_auc"] = float(a1["green_pit_auc"] - a0["green_pit_auc"])
    for k in ("calibration_slope",):
        if a0.get(k) is not None and a1.get(k) is not None:
            out[f"abs_{k}_minus_1"] = float(abs(a0[k] - 1.0) - abs(a1[k] - 1.0))
    return out


# ─── E-value, Construction B (paired safe-t) ────────────────────────────────────────
def safe_t_e_value(d: np.ndarray, g: float = E_VALUE_G) -> dict:
    """E = (1+ng)^(-1/2) * [(1+t^2/(n-1)) / (1+t^2/((1+ng)(n-1)))]^(n/2).

    Grunwald / de Heide / Koolen's safe t-test: the one-sample Bayes factor under a
    right-Haar prior on sigma and N(0,g) on the effect size. Exact for any unknown
    sigma, which is what removes the plug-in-scale hole 10d's Construction A fell into.
    """
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    d_bar = float(d.mean())
    s_d = float(d.std(ddof=1))
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
    # The formula is symmetric in t, so a consistently NEGATIVE delta also returns a
    # large E -- evidence against exchangeability in the WRONG direction. Direction is
    # carried beside the number rather than folded into it: applying a one-sided
    # transform after seeing the data is the one thing that voids an e-value.
    return {"n": n, "g": g, "d_bar": d_bar, "s_d": s_d, "t": t, "E": float(e),
            "direction_is_improvement": bool(d_bar > 0),
            "max_attainable_E": float(cap)}


def ebh(evals: dict[str, dict], alpha: float = 0.05) -> dict:
    """e-BH over this item's declared hypotheses: sort descending and take
    `k* = max{k : E_[k] >= n/(alpha*k)}`, rejecting the k* largest.

    The `k*` rule is the whole point and an earlier draft of this script got it wrong
    by testing only the lone-rejection bar `n/alpha`. Several arms clearing TOGETHER is
    much cheaper than one clearing alone -- `e_value_construction.md` section 6 says so
    explicitly, and it is the correct incentive.

    Direction is NOT folded in. The safe-t statistic is symmetric in `t`, so a
    rejection here means "not exchangeable", which is a different claim from "the arm
    improves the model"; `direction_is_improvement` is carried beside each row.
    """
    order = sorted(evals.items(), key=lambda kv: kv[1]["E"], reverse=True)
    n = len(order)
    ladder, k_star = [], 0
    for k, (h, e) in enumerate(order, start=1):
        thr = n / (alpha * k)
        qualifies = bool(e["E"] >= thr)
        ladder.append({"rank": k, "hypothesis": h, "E": e["E"], "threshold": thr,
                       "qualifies": qualifies,
                       "direction_is_improvement": e["direction_is_improvement"]})
        if qualifies:
            k_star = k
    return {
        "n_declared_hypotheses": n, "alpha": alpha, "k_star": k_star,
        "rejected": [r["hypothesis"] for r in ladder[:k_star]],
        "ladder": ladder,
        "threshold_for_a_lone_rejection": n / (alpha * 1),
        "max_attainable_E": max(e["max_attainable_E"] for e in evals.values()),
        "note": ("item-level e-BH over this item's own declared hypotheses. The campaign "
                 "family is larger, so this is a CEILING on what this item could claim, "
                 "never a floor. A rejection is a statement about exchangeability, not "
                 "about the direction of the effect -- see direction_is_improvement."),
    }


def e_value_validity_check(n_draws: int = 100_000, seed: int = S.RANDOM_STATE) -> dict:
    """Push i.i.d. N(0, sigma) deltas through the implementation; mean(E) must be 1,
    and the reference's worked example must return 17.0. Required by section 4 of
    `e_value_construction.md`: a construction whose null mean is not 1 is not an
    e-value, and the check costs a minute."""
    rng = np.random.default_rng(seed)
    out: dict = {}
    n, g = len(SEEDS), E_VALUE_G
    for sigma in (0.0001, 0.001, 0.01, 0.1, 1.0):
        d = rng.normal(0.0, sigma, size=(n_draws, n))
        t = np.sqrt(n) * d.mean(axis=1) / d.std(axis=1, ddof=1)
        num = 1.0 + t ** 2 / (n - 1)
        den = 1.0 + t ** 2 / ((1.0 + n * g) * (n - 1))
        e = (1.0 + n * g) ** -0.5 * (num / den) ** (n / 2.0)
        out[f"sigma={sigma}"] = {"mean_E": float(e.mean()),
                                 "mc_se": float(e.std(ddof=1) / np.sqrt(n_draws))}
    worked = safe_t_e_value(np.array([0.0121, 0.0088, 0.0154, 0.0067, 0.0110]))
    out["reference_worked_example"] = {"t": worked["t"], "E": worked["E"],
                                       "published": 17.0}
    return out


# ─── Cause labels and race ids on the eval rows ─────────────────────────────────────
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
    params = E._params_for(TARGET, S.MODEL_VERSION_DEFAULT)
    report: dict = {
        "item": "10b", "generated_at": pd.Timestamp.utcnow().isoformat(),
        "substrate": {"model_version": S.MODEL_VERSION_DEFAULT,
                      "n_feature_columns": len(S.FEATURE_COLUMNS),
                      "params": params, "params_source":
                      f"ml/models/{TARGET}_best_params.json"},
        "arms": ARMS, "seeds": list(SEEDS), "e_value_g": E_VALUE_G,
        "hypotheses": list(HYPOTHESES),
    }

    log("=" * 78)
    log("10b -- the cause-specific arm: non-green endings treated as censored")
    log(f"substrate {S.MODEL_VERSION_DEFAULT}, {len(S.FEATURE_COLUMNS)} feature columns")
    log("=" * 78)

    # ── step 1c: gate 5, the label is label-adjacent ────────────────────────────────
    log("\n[step 1c] gate 5 -- label-adjacency: the cause label must not be a feature")
    leak = [c for c in ("stint_end_cause", S.STINT_LIFE_CENSOR_COLUMN,
                        "end_regime", "end_cause_confidence")
            if c in set(S.FEATURE_COLUMNS)]
    report["gate_5"] = {"label_columns_in_feature_contract": leak, "pass": not leak}
    log(f"  columns leaking into FEATURE_COLUMNS: {leak or 'none'}  "
        f"-> {'PASS' if not leak else 'FAIL'}")
    if leak:
        raise SystemExit("gate 5 failed: the cause label is inside the feature contract")

    # ── bundles and splits ─────────────────────────────────────────────────────────
    log("\n[setup] loading both label constructions")
    bundles, splits = {}, {}
    for arm, variant in ARMS.items():
        bundles[arm] = F.load_features(target=TARGET, censoring_variant=variant)
        splits[arm] = E._evaluation_split(bundles[arm])
        log(f"  {arm} ({variant}): n_tr={len(splits[arm].y_tr)} "
            f"n_ev={len(splits[arm].y_ev)} cens_tr={splits[arm].cens_tr.mean():.4f} "
            f"cens_ev={splits[arm].cens_ev.mean():.4f}")

    s0, s1 = splits["A0"], splits["A1"]

    # ── step 1d: gate 2 substitute, the split is identical ─────────────────────────
    log("\n[step 1d] gate 2 substitute -- the two arms differ in the LABEL and nothing else")
    ident = {
        "X_tr_identical": bool(s0.X_tr.equals(s1.X_tr)),
        "X_ev_identical": bool(s0.X_ev.equals(s1.X_ev)),
        "y_tr_identical": bool(np.array_equal(s0.y_tr, s1.y_tr)),
        "y_ev_identical": bool(np.array_equal(s0.y_ev, s1.y_ev)),
        "lap_ids_tr_identical": bool(np.array_equal(s0.lap_ids_tr, s1.lap_ids_tr)),
        "lap_ids_ev_identical": bool(np.array_equal(s0.lap_ids_ev, s1.lap_ids_ev)),
        "split_mode": s0.mode, "eval_season": int(s0.eval_season),
        "train_seasons": sorted({int(x) for x in s0.seasons_tr.tolist()}),
        "cens_tr_rows_differing": int((s0.cens_tr != s1.cens_tr).sum()),
        "cens_ev_rows_differing": int((s0.cens_ev != s1.cens_ev).sum()),
    }
    ident["pass"] = all(ident[k] for k in ident if k.endswith("_identical"))
    report["gate_2_substitute"] = ident
    for k in ("X_tr_identical", "X_ev_identical", "y_tr_identical", "y_ev_identical",
              "lap_ids_tr_identical", "lap_ids_ev_identical"):
        log(f"  {k}: {ident[k]}")
    log(f"  censoring flags differing: train {ident['cens_tr_rows_differing']}, "
        f"eval {ident['cens_ev_rows_differing']}  <- the entire content of the arm")
    if not ident["pass"]:
        raise SystemExit("gate 2 substitute failed: the two arms do not share a split")

    # ── the green-pit stratum ──────────────────────────────────────────────────────
    cause_ev, race_ev = cause_and_race(s0.lap_ids_ev)
    gp = cause_ev == "green_pit"
    cause_tr, _ = cause_and_race(s0.lap_ids_tr)
    strata = {str(k): int(v) for k, v in
              pd.Series(cause_ev.astype(str)).value_counts().items()}
    gp_matched = {
        "n_green_pit": int(gp.sum()),
        "n_eval_races": int(len({r for r in race_ev.tolist()})),
        "n_green_pit_races": int(len({r for r in race_ev[gp].tolist()})),
        "censored_under_standard": float(s0.cens_ev[gp].mean()),
        "censored_under_10b": float(s1.cens_ev[gp].mean()),
        "y_identical_on_stratum": bool(np.array_equal(s0.y_ev[gp], s1.y_ev[gp])),
        "eval_cause_counts": strata,
        "train_cause_counts": {str(k): int(v) for k, v in
                               pd.Series(cause_tr.astype(str)).value_counts().items()},
    }
    report["green_pit_stratum"] = gp_matched
    log("\n[setup] the headline instrument -- the green-pit stratum")
    log(f"  n={gp_matched['n_green_pit']} laps over "
        f"{gp_matched['n_green_pit_races']} races; censoring "
        f"{gp_matched['censored_under_standard']:.3f} (standard) / "
        f"{gp_matched['censored_under_10b']:.3f} (10b); "
        f"y identical: {gp_matched['y_identical_on_stratum']}")
    if not gp_matched["y_identical_on_stratum"]:
        raise SystemExit("the green-pit stratum is not matched; the headline is invalid")

    # ── step 1b: substrate drift ───────────────────────────────────────────────────
    drift = {
        "published_n_eval_laps": PUBLISHED["n_eval_laps"],
        "today_n_eval_laps": int(len(s0.y_ev)),
        "published_n_green_pit": PUBLISHED["n_green_pit"],
        "today_n_green_pit": int(gp.sum()),
        "published_n_eval_races": PUBLISHED["n_eval_races"],
        "today_n_eval_races": gp_matched["n_eval_races"],
        "six_decimal_reproduction_of_published_figures_possible": False,
        "why": ("08m rebuilt the warehouse and 08n shipped v12 on 2026-09-16, after "
                "10b/10c/10d/10e ran. The eval rows are not the same rows, so no "
                "figure those items published can be reproduced to six decimals; "
                "gate 1 is anchored on today's published v12 headline instead."),
    }
    report["step_1b_substrate_drift"] = drift
    log("\n[step 1b] substrate drift since 10b/10c/10d/10e ran")
    log(f"  eval laps    {drift['published_n_eval_laps']} published -> "
        f"{drift['today_n_eval_laps']} today")
    log(f"  green-pit    {drift['published_n_green_pit']} published -> "
        f"{drift['today_n_green_pit']} today")
    log(f"  eval races   {drift['published_n_eval_races']} published -> "
        f"{drift['today_n_eval_races']} today")

    # ── step 1a: gate 1, reproduce today's published v12 headline ──────────────────
    log("\n[step 1a] gate 1 -- reproduce the published v12 headline through E._fit/_score")
    pub = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())
    pub_headline = float(pub["models"][TARGET]["headline"])
    pub_variant = pub.get("censoring_variant")
    m_a0 = E._fit(spec, params, s0.X_tr, s0.y_tr, s0.cens_tr, s0.w_tr)
    repro = full_fold_nll(spec, m_a0, s0.X_ev, s0.y_ev, s0.cens_ev)
    ok6 = round(repro, 6) == round(pub_headline, 6)
    report["step_1a_instrument"] = {
        "published_headline": pub_headline,
        "published_censoring_variant": pub_variant,
        "published_version": pub.get("version"),
        "reproduced_headline": repro,
        "abs_difference": abs(repro - pub_headline),
        "matches_to_six_decimals": bool(ok6),
    }
    log(f"  published  ({pub.get('version')}, variant={pub_variant}): {pub_headline!r}")
    log(f"  reproduced (E._fit/_score, A0/standard):                 {repro!r}")
    log(f"  matches to six decimals: {ok6}  -> {'PASS' if ok6 else 'FAIL'}")
    if not ok6:
        raise SystemExit("gate 1 failed: the harness does not reproduce the v12 headline")

    # ── step 1e: the optimism gap, and the 2x2 scoring table ───────────────────────
    log("\n[step 1e] gate 1 -- the optimism gap, and the 2x2 scoring table")
    honest_models, in_sample_models = {}, {}
    for arm in ARMS:
        sp = splits[arm]
        honest_models[arm] = (m_a0 if arm == "A0"
                              else E._fit(spec, params, sp.X_tr, sp.y_tr, sp.cens_tr, sp.w_tr))
        # in_sample: fit on EVERY training season (2018-2024) exactly as train.py does,
        # then score the 2024 eval rows -- which are inside that fit. This is the mode
        # the recorded -0.028 was measured in.
        b = bundles[arm]
        cens_all = b.meta_train[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
        in_sample_models[arm] = E._fit(spec, params, b.X_train, b.y_train.to_numpy(),
                                       cens_all, None)

    modes = {}
    for mode, models in (("honest", honest_models), ("in_sample", in_sample_models)):
        block = {}
        for arm in ARMS:
            pred = models[arm].predict(s0.X_ev)
            scale = models[arm].scale
            gpm = green_pit_metrics(s0.y_ev[gp], pred[gp], s0.cens_ev[gp], scale)
            # The 2x2: one model, scored under BOTH label constructions on the full fold.
            gpm["full_fold_nll_scored_under_standard"] = float(
                SV.aft_nloglik(s0.y_ev, pred, s0.cens_ev, scale))
            gpm["full_fold_nll_scored_under_10b"] = float(
                SV.aft_nloglik(s1.y_ev, pred, s1.cens_ev, scale))
            gpm["scale"] = float(scale)
            gpm["n_fit_rows"] = (int(len(splits[arm].y_tr)) if mode == "honest"
                                 else int(len(bundles[arm].X_train)))
            block[arm] = gpm
        block["delta_A0_minus_A1"] = delta_pair(block["A0"], block["A1"])
        block["delta_full_fold_nll_scored_under_10b"] = float(
            block["A0"]["full_fold_nll_scored_under_10b"]
            - block["A1"]["full_fold_nll_scored_under_10b"])
        block["delta_full_fold_nll_scored_under_standard"] = float(
            block["A0"]["full_fold_nll_scored_under_standard"]
            - block["A1"]["full_fold_nll_scored_under_standard"])
        # The artefact: A1 scored under its OWN labels against A0 scored under A0's.
        block["mismatched_scoring_delta"] = float(
            block["A0"]["full_fold_nll_scored_under_standard"]
            - block["A1"]["full_fold_nll_scored_under_10b"])
        modes[mode] = block

    report["step_1e_modes"] = modes
    for mode in ("honest", "in_sample"):
        b = modes[mode]
        log(f"  -- {mode} --")
        for arm in ARMS:
            log(f"     {arm} ({ARMS[arm]}): green-pit NLL {b[arm]['green_pit_nll']:.6f}  "
                f"Brier {b[arm]['green_pit_ipcw_brier']:.6f}  "
                f"AUC {b[arm]['green_pit_auc']:.6f}  "
                f"slope {b[arm]['calibration_slope']:.6f}")
        log(f"     full-fold NLL under 10b labels:      A0 "
            f"{b['A0']['full_fold_nll_scored_under_10b']:.6f}  A1 "
            f"{b['A1']['full_fold_nll_scored_under_10b']:.6f}  "
            f"delta {b['delta_full_fold_nll_scored_under_10b']:+.6f}")
        log(f"     full-fold NLL under standard labels: A0 "
            f"{b['A0']['full_fold_nll_scored_under_standard']:.6f}  A1 "
            f"{b['A1']['full_fold_nll_scored_under_standard']:.6f}  "
            f"delta {b['delta_full_fold_nll_scored_under_standard']:+.6f}")
        log(f"     MISMATCHED (A0 under standard vs A1 under 10b): "
            f"{b['mismatched_scoring_delta']:+.6f}  <- the original artefact's shape")
    optimism = {
        k: {"honest": modes["honest"]["A1"][k], "in_sample": modes["in_sample"]["A1"][k],
            "optimism": modes["in_sample"]["A1"][k] - modes["honest"]["A1"][k]}
        for k in ("green_pit_nll", "green_pit_ipcw_brier", "green_pit_auc",
                  "calibration_slope")}
    report["step_1e_optimism_A1"] = optimism

    # ── step 1f: why the full-fold NLL reverses the stratum's ruling ───────────────
    # The full fold is ~48-54% censored, and a censored row scores through
    # log S(t) = log P(T > t), which is monotonically IMPROVED by predicting a longer
    # life. An arm trained to treat every short non-green ending as censored predicts
    # longer lives, so it collects that reward on half the rows without having to be
    # right about any of them. This decomposes the full-fold NLL into the two
    # populations so the claim is a measurement rather than an argument.
    log("\n[step 1f] why the full-fold NLL reverses the stratum's ruling")
    decomp = {}
    for arm in ARMS:
        pred = honest_models[arm].predict(s0.X_ev)
        scale = honest_models[arm].scale
        row = {"mean_pred_median_laps": float(np.mean(pred)),
               "median_pred_median_laps": float(np.median(pred))}
        for lab, sp in (("standard", s0), ("10b", s1)):
            c = sp.cens_ev
            row[f"scored_under_{lab}"] = {
                "censored_share": float(c.mean()),
                "nll_all": float(SV.aft_nloglik(sp.y_ev, pred, c, scale)),
                "nll_uncensored_rows": float(
                    SV.aft_nloglik(sp.y_ev[~c], pred[~c], c[~c], scale)),
                "nll_censored_rows": float(
                    SV.aft_nloglik(sp.y_ev[c], pred[c], c[c], scale)),
            }
        decomp[arm] = row
    for lab in ("standard", "10b"):
        d_unc = (decomp["A0"][f"scored_under_{lab}"]["nll_uncensored_rows"]
                 - decomp["A1"][f"scored_under_{lab}"]["nll_uncensored_rows"])
        d_cen = (decomp["A0"][f"scored_under_{lab}"]["nll_censored_rows"]
                 - decomp["A1"][f"scored_under_{lab}"]["nll_censored_rows"])
        decomp[f"delta_under_{lab}"] = {
            "uncensored_rows": float(d_unc), "censored_rows": float(d_cen)}
        log(f"  scored under {lab} labels "
            f"({decomp['A0'][f'scored_under_{lab}']['censored_share']:.3f} censored): "
            f"delta on uncensored rows {d_unc:+.6f}, on censored rows {d_cen:+.6f}")
    log(f"  mean predicted median life: A0 "
        f"{decomp['A0']['mean_pred_median_laps']:.3f} laps, A1 "
        f"{decomp['A1']['mean_pred_median_laps']:.3f} laps")
    report["step_1f_full_fold_decomposition"] = decomp

    # ── step 2 / step 3: the arms at the canonical seed, and each arm's own floor ───
    log("\n[step 2 + 3] the arms, and each arm's OWN 5-reseed floor")
    canonical = {arm: modes["honest"][arm] for arm in ARMS}
    report["step_2_arms_canonical_seed"] = {
        "note": ("the canonical fit is E._fit, whose AFTBooster default seed is "
                 "S.RANDOM_STATE = 20260528 -- i.e. the first reseed. Values therefore "
                 "coincide with seed 20260528 below, by construction and not by luck."),
        "arms": canonical,
        "delta_A0_minus_A1": modes["honest"]["delta_A0_minus_A1"],
    }

    floors: dict[str, dict] = {}
    by_seed: dict[str, dict[str, list[float]]] = {a: {m: [] for m in METRICS}
                                                  for a in ARMS}
    for arm in ARMS:
        sp = splits[arm]
        for seed in SEEDS:
            t0 = time.time()
            m = fit_seeded(spec, params, sp.X_tr, sp.y_tr, sp.cens_tr, sp.w_tr, seed)
            pred = m.predict(s0.X_ev)
            gpm = green_pit_metrics(s0.y_ev[gp], pred[gp], s0.cens_ev[gp], m.scale)
            for k in METRICS:
                by_seed[arm][k].append(float(gpm[k]))
            log(f"  {arm} seed {seed}: NLL {gpm['green_pit_nll']:.6f}  "
                f"Brier {gpm['green_pit_ipcw_brier']:.6f}  "
                f"AUC {gpm['green_pit_auc']:.6f}  "
                f"slope {gpm['calibration_slope']:.6f}  ({time.time()-t0:.1f}s)")
        floors[arm] = {}
        for h in METRICS:
            a = np.asarray(by_seed[arm][h], dtype=np.float64)
            sd = float(a.std(ddof=1))
            floors[arm][h] = {"n_seeds": len(a), "by_seed": a.tolist(),
                              "mean": float(a.mean()), "sd": sd,
                              "delta_noise_1sd": float(np.sqrt(2.0) * sd),
                              "delta_noise_2sd": float(2.0 * np.sqrt(2.0) * sd)}

    # A cross-check that the floor helper and this arithmetic agree, on A1's own family.
    sp1 = splits["A1"]
    nf_check = AT.refit_noise_floor(
        lambda s: fit_seeded(spec, params, sp1.X_tr, sp1.y_tr, sp1.cens_tr, sp1.w_tr, s),
        lambda y_ev, model, X_ev: SV.aft_nloglik(
            y_ev[gp], model.predict(X_ev)[gp], s0.cens_ev[gp], model.scale),
        s0.X_ev, s0.y_ev, SEEDS)
    floors["A1"]["green_pit_nll"]["attribution_py_cross_check"] = {
        "delta_noise_2sd": nf_check["delta_noise_2sd"],
        "agrees": bool(abs(nf_check["delta_noise_2sd"]
                           - floors["A1"]["green_pit_nll"]["delta_noise_2sd"]) < 1e-12)}
    report["step_3_reseed_floors"] = floors

    log("\n[step 3] floors (2*sqrt(2)*sd), each arm its own -- never borrowed")
    for arm in ARMS:
        for h in METRICS:
            f = floors[arm][h]
            log(f"  {arm} {h}: sd {f['sd']:.6f}  floor {f['delta_noise_2sd']:.6f}")

    # Paired reseed deltas: both arms at the SAME seed, so shared seed noise cancels.
    paired = {}
    for h in METRICS:
        a0_v = np.asarray(by_seed["A0"][h], dtype=np.float64)
        a1_v = np.asarray(by_seed["A1"][h], dtype=np.float64)
        if h in TOWARD_ONE:
            d = np.abs(a0_v - 1.0) - np.abs(a1_v - 1.0)
        elif HIGHER_IS_BETTER.get(h):
            d = a1_v - a0_v
        else:
            d = a0_v - a1_v
        arm_floor = floors[ARM_OF_RECORD][h]["delta_noise_2sd"]
        other_floor = floors["A0"][h]["delta_noise_2sd"]
        paired[h] = {
            "deltas_by_seed": d.tolist(), "mean": float(d.mean()),
            "sd": float(d.std(ddof=1)),
            "floor_of_record_A1": arm_floor, "floor_A0": other_floor,
            "x_floor_of_record": (None if arm_floor == 0 else float(d.mean() / arm_floor)),
            "x_floor_A0": (None if other_floor == 0 else float(d.mean() / other_floor)),
            "clears_own_floor": (None if arm_floor == 0
                                 else bool(d.mean() > arm_floor)),
        }
    report["step_3_paired_reseed_deltas"] = paired
    report["step_3_note"] = (
        "The two DECLARED hypotheses are green_pit_nll and green_pit_ipcw_brier. "
        "green_pit_auc and calibration_slope are floored and bootstrapped here as "
        "diagnostics so that any gain on them is quoted with a floor under it, but "
        "they are NOT counted in the e-value family: promoting a diagnostic to a "
        "hypothesis after seeing its value is what gate 6 exists to prevent.")
    log("\n[step 3] the delta, with its floor ratio (positive = 10b improves)")
    for h in METRICS:
        p = paired[h]
        tag = "DECLARED  " if h in HYPOTHESES else "diagnostic"
        log(f"  [{tag}] {h}: delta {p['mean']:+.6f}  "
            f"x A1 floor {p['x_floor_of_record']:+.2f}  "
            f"x A0 floor {p['x_floor_A0']:+.2f}  clears: {p['clears_own_floor']}")

    # ── step 7: the e-values ───────────────────────────────────────────────────────
    log("\n[step 7] gate 7 -- Construction B on the paired reseed deltas")
    validity = e_value_validity_check()
    report["step_7_validity_check"] = validity
    log(f"  validity: worked example t={validity['reference_worked_example']['t']:.2f} "
        f"E={validity['reference_worked_example']['E']:.2f} (published 17.0)")
    for k, v in validity.items():
        if k.startswith("sigma="):
            log(f"  null mean E at {k}: {v['mean_E']:.4f} (+/- {v['mc_se']:.4f})")
    evals = {h: safe_t_e_value(np.asarray(paired[h]["deltas_by_seed"])) for h in HYPOTHESES}
    report["step_7_e_values"] = evals
    for h in HYPOTHESES:
        e = evals[h]
        log(f"  {h}: t {e['t']:+.3f}  E {e['E']:.4g}  "
            f"direction_is_improvement {e['direction_is_improvement']}")
    report["step_7_ebh"] = ebh(evals, alpha=0.05)
    eb = report["step_7_ebh"]
    log(f"  item-level e-BH at alpha=0.05 over {eb['n_declared_hypotheses']} declared "
        f"hypotheses: k* = {eb['k_star']}, rejects {eb['rejected']}")
    for row in eb["ladder"]:
        log(f"    rank {row['rank']}: {row['hypothesis']}  E {row['E']:.4g}  "
            f"needs {row['threshold']:.1f} -> {'qualifies' if row['qualifies'] else 'no'}")
    log(f"  max attainable E at n={len(SEEDS)}, g={E_VALUE_G} is "
        f"{eb['max_attainable_E']:.1f}; a LONE rejection needed "
        f"{eb['threshold_for_a_lone_rejection']:.1f}")
    if eb["k_star"]:
        log("  NOTE: the rejections' DIRECTION is carried separately -- "
            f"improvement={[evals[h]['direction_is_improvement'] for h in HYPOTHESES]}")

    # ── the paired race-level cluster bootstrap ────────────────────────────────────
    if not args.skip_boot:
        log(f"\n[boot] paired race-level cluster bootstrap, {args.boot_draws} draws, "
            f"seed {BOOT_SEED}, races the unit")
        gp_idx = np.flatnonzero(gp)
        races = np.array([str(r) for r in race_ev[gp]], dtype=object)
        uniq = np.array(sorted(set(races.tolist())), dtype=object)
        rows_by_race = {r: gp_idx[races == r] for r in uniq}
        pred_a0 = honest_models["A0"].predict(s0.X_ev)
        pred_a1 = honest_models["A1"].predict(s0.X_ev)
        sc_a0, sc_a1 = honest_models["A0"].scale, honest_models["A1"].scale
        rng = np.random.default_rng(BOOT_SEED)
        keys = ("green_pit_nll", "green_pit_ipcw_brier", "green_pit_auc",
                "calibration_slope")
        draws: dict[str, list[float]] = {k: [] for k in keys}
        t0 = time.time()
        for i in range(args.boot_draws):
            pick = rng.choice(len(uniq), size=len(uniq), replace=True)
            idx = np.concatenate([rows_by_race[uniq[j]] for j in pick])
            y_b, c_b = s0.y_ev[idx], s0.cens_ev[idx]
            m0 = green_pit_metrics(y_b, pred_a0[idx], c_b, sc_a0)
            m1 = green_pit_metrics(y_b, pred_a1[idx], c_b, sc_a1)
            for k in keys:
                if m0.get(k) is None or m1.get(k) is None:
                    continue
                if k == "green_pit_auc":
                    draws[k].append(float(m1[k] - m0[k]))          # higher is better
                elif k == "calibration_slope":
                    draws[k].append(float(abs(m0[k] - 1.0) - abs(m1[k] - 1.0)))
                else:
                    draws[k].append(float(m0[k] - m1[k]))          # lower is better
            if (i + 1) % 25 == 0:
                log(f"  {i+1}/{args.boot_draws} draws ({time.time()-t0:.0f}s)")
        boot = {}
        for k in keys:
            a = np.asarray(draws[k], dtype=np.float64)
            if len(a) == 0:
                boot[k] = {"n_draws": 0}
                continue
            boot[k] = {"n_draws": int(len(a)), "mean": float(a.mean()),
                       "ci95_low": float(np.percentile(a, 2.5)),
                       "ci95_high": float(np.percentile(a, 97.5)),
                       "p_improves": float((a > 0).mean())}
        report["bootstrap_paired_race_cluster"] = {
            "draws": args.boot_draws, "seed": BOOT_SEED,
            "n_races": int(len(uniq)), "unit": "race_id",
            "note": ("both arms scored on the SAME resampled races, so the shared "
                     "race-draw noise cancels. 10d section 4 ruled this the instrument "
                     "to believe where the floor, the e-value and the bootstrap "
                     "disagree, and this item does not re-litigate that."),
            "deltas": boot,
        }
        log("\n[boot] paired deltas (positive = 10b improves)")
        for k in keys:
            b = boot[k]
            if b.get("n_draws"):
                log(f"  {k}: {b['mean']:+.6f}  95% [{b['ci95_low']:+.6f}, "
                    f"{b['ci95_high']:+.6f}]  P(improves) {b['p_improves']:.3f}")

    # ── the verdict, assembled from the declared pass criterion ───────────────────
    h1 = paired["green_pit_nll"]
    h2 = paired["green_pit_ipcw_brier"]
    bp = report.get("bootstrap_paired_race_cluster", {}).get("deltas", {})
    p_h1 = bp.get("green_pit_nll", {}).get("p_improves")
    verdict = {
        "declared_criterion": ("positive green-pit NLL delta, above A1's own reseed "
                               "floor, with paired-bootstrap P(improves) >= 0.95 and "
                               "H2 not contradicting it"),
        "h1_delta": h1["mean"], "h1_x_own_floor": h1["x_floor_of_record"],
        "h1_positive": bool(h1["mean"] > 0),
        "h1_clears_own_floor": h1["clears_own_floor"],
        "h1_bootstrap_p_improves": p_h1,
        "h2_delta": h2["mean"], "h2_x_own_floor": h2["x_floor_of_record"],
        "h2_positive": bool(h2["mean"] > 0),
        "hypotheses_agree_in_sign": bool((h1["mean"] > 0) == (h2["mean"] > 0)),
    }
    verdict["passes"] = bool(
        verdict["h1_positive"] and verdict["h1_clears_own_floor"]
        and (p_h1 is not None and p_h1 >= 0.95) and verdict["h2_positive"])
    report["verdict"] = verdict
    log("\n" + "=" * 78)
    log("VERDICT against the pre-registered criterion")
    log(f"  H1 green-pit NLL   delta {h1['mean']:+.6f}  "
        f"({h1['x_floor_of_record']:+.2f}x own floor)  positive {verdict['h1_positive']}  "
        f"clears floor {verdict['h1_clears_own_floor']}  boot P {p_h1}")
    log(f"  H2 green-pit Brier delta {h2['mean']:+.6f}  "
        f"({h2['x_floor_of_record']:+.2f}x own floor)  positive {verdict['h2_positive']}")
    log(f"  hypotheses agree in sign: {verdict['hypotheses_agree_in_sign']}")
    log(f"  PASSES: {verdict['passes']}")
    log("=" * 78)

    report["runtime_s"] = round(time.time() - t_start, 1)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    LOG.write_text("\n".join(lines) + "\n")
    log(f"\nwrote {OUT}")
    log(f"wrote {LOG}")
    LOG.write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
