"""08h — baseline_observations_n as a feature: the add-ablation 08e deferred

WHY THIS EXISTS. `08e` rebuilt `int_lap_thermal_proxy.stint_baseline_pace` and shipped
`baseline_observations_n` into the mart contract deliberately NOT in FEATURE_COLUMNS,
deferring the add-ablation gate. This script runs that gate.

THE DESIGN.

    baseline A  = the 32-column contract                 (32 columns)
    arm    A+B  = the full 32-column contract + baseline_observations_n (33 columns)

The column records how many valid prior laps informed each row's baseline (ranges 0–75,
mean 12.5 over 137,447 mart rows). The model currently cannot tell those apart, and the
difference is exactly the uncertainty the rebuild introduced. If the model wants this
uncertainty, it should be measurable as information gain net of the noise floor.

HAZARD: The NULLs are deterministic on count-of-valid-prior-laps, which is NOT a contract
axis — `02a`'s declarability argument does not carry over. Shipping the count so a consumer
can condition on the missingness is one thing; putting it in `X` makes the model's behaviour
depend on an axis nothing declares. That is the trade this item has to price, not assume.

METHOD.

    add-ablation through evaluate.py's own _fit/_score
    test against each family's own 5-reseed floor
    run the permutation-null arm (same three arms 08e/08f went through)
    also run it as a PAIR with push_residual to distinguish "the model wants the
      uncertainty" from "the model wants another counter"

ORDERING — this runs AFTER 08g, which has an instrument check on a 32-column contract.
A 33-column contract makes that arm a different arm and voids that check.

Reads the warehouse read-only. Writes nothing to `ml/models/`, nothing to
`ml/artefacts/evaluation_metrics.json`, nothing to the warehouse and nothing to git:
`evaluate.run()` is never called, so no artefact directory is touched. The only
output is the JSON named below.

Usage:  PYTHONPATH=. python3 scripts/arms_08h_baseline_observations_n.py
        PYTHONPATH=. python3 scripts/arms_08h_baseline_observations_n.py --families cliff_classifier
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ml.src import attribution as AT
from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S
from ml.src import train as T

# ─── The candidate column ───────────────────────────────────────────────────────────
CANDIDATE_COL = "baseline_observations_n"

SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(5))
E_VALUE_G = 1.0  # pre-registered: a one-sd effect, as in 02c
FAMILIES = ("degradation_regressor_p10", "degradation_regressor_p50",
            "degradation_regressor_p90", "cliff_classifier",
            "stint_life_regressor")
OUT = Path("ml/artefacts/08h_baseline_observations_n_arms.json")


# ─── Fit / score, through evaluate.py's own paths ───────────────────────────────────
def fit_seeded(spec: S.TargetSpec, params: dict, X, y, cens, w, seed: int):
    """E._fit with the seed overridden, and nothing else changed.

    The override differs by API and both are exercised here, which is why it is not
    02c's single `set_params` line. `T._make_model` passes `random_state` positionally
    into the sklearn constructors, so injecting it through `params` would collide
    ("multiple values for keyword argument"); it is set afterwards instead. `AFTBooster`
    has no `set_params` at all -- it takes `seed` inside its own params dict, where
    `**p` merges AFTER the default, so injecting it there is the supported route.
    """
    if spec.kind == "survival":
        model = T._make_model(spec, {**params, "seed": int(seed)})
    else:
        model = T._make_model(spec, params)
        model.set_params(random_state=int(seed))
    if spec.kind == "quantile" and w is None:
        raise ValueError("quantile fit needs the IPW row weights production fits with")
    weights = np.asarray(w, dtype=np.float32) if w is not None else T._sample_weight(spec, y)
    if spec.kind == "survival":
        model.fit(X, y, sample_weight=weights, is_censored=np.asarray(cens, dtype=bool))
    else:
        model.fit(X, y, sample_weight=weights)
    return model


def score_model(spec: S.TargetSpec, model, X_ev, y_ev, cens_ev) -> float:
    """The headline, through evaluate.py's own scorer.

    The AFT scale is a term in the likelihood, so it must be the scale of the model
    being scored -- `evaluate.run()` takes it off the fitted model and so does this.
    """
    scale = getattr(model, "scale", None) if spec.kind == "survival" else None
    return E._score(spec, y_ev, E._predict_index(spec, model, X_ev), cens_ev, scale)


def delta(arm_value: float, base_value: float, higher_is_better: bool) -> float:
    """Positive = improvement, on every metric."""
    return (arm_value - base_value) if higher_is_better else (base_value - arm_value)


def shuffled(X: pd.DataFrame, col: str, rng: np.random.Generator) -> pd.DataFrame:
    """Row-shuffle a single column.

    Preserves the shape, marginals, NaN count, NaNs move with their values.
    """
    out = X.copy()
    perm = rng.permutation(len(X))
    out[col] = out[col].to_numpy()[perm]
    return out


def rank_degeneracy(X: pd.DataFrame, col: str, top_k: int = 5) -> dict:
    """Spearman(col, every other column), against `attribution.RANK_DEGENERATE_RHO`.

    WHY. This is the leaf doc's "another counter" question asked directly, and it is the
    prior `attribution.py` names: above `RANK_DEGENERATE_RHO` a tree sees the same
    feature, because XGBoost splits on global thresholds and any globally-monotone
    relabelling induces the same partitions. A candidate that is a monotone relabelling
    of a column already in `X` cannot add information no matter what its delta looks
    like, so this runs BEFORE the deltas are interpreted, not after.
    """
    from scipy.stats import spearmanr

    base = pd.to_numeric(X[col], errors="coerce")
    rhos: dict[str, float] = {}
    for c in X.columns:
        if c == col:
            continue
        other = pd.to_numeric(X[c], errors="coerce")
        m = base.notna() & other.notna()
        if m.sum() < 100 or base[m].nunique() < 2 or other[m].nunique() < 2:
            continue
        r = spearmanr(base[m], other[m]).statistic
        if np.isfinite(r):
            rhos[c] = float(r)
    ranked = sorted(rhos.items(), key=lambda kv: -abs(kv[1]))[:top_k]
    top = ranked[0] if ranked else (None, 0.0)
    return {
        "threshold_RANK_DEGENERATE_RHO": float(AT.RANK_DEGENERATE_RHO),
        "max_abs_spearman_feature": top[0],
        "max_abs_spearman": float(top[1]),
        "is_rank_degenerate": bool(abs(top[1]) >= AT.RANK_DEGENERATE_RHO),
        "top_k": [{"feature": f, "spearman": r} for f, r in ranked],
    }


def shuffled_pair(X: pd.DataFrame, cols: tuple[str, ...],
                  rng: np.random.Generator) -> pd.DataFrame:
    """Row-shuffle a pair of columns JOINTLY.

    Jointly, not column-by-column: the internal correlation structure is part
    of its capacity, and the null being scored is "these two columns carry no
    information about the label", not "these two are unrelated to each other".
    """
    out = X.copy()
    perm = rng.permutation(len(X))
    block = out[list(cols)].to_numpy()[perm]
    for i, c in enumerate(cols):
        out[c] = block[:, i]
    return out


# ─── E-value, Construction B (paired safe-t) ────────────────────────────────────
def safe_t_e_value(d: np.ndarray, g: float = E_VALUE_G) -> dict:
    """E = (1+ng)^(-1/2) * [(1+t^2/(n-1)) / (1+t^2/((1+ng)(n-1)))]^(n/2).

    Grunwald / de Heide / Koolen's safe t-test: the one-sample Bayes factor under a
    right-Haar prior on sigma and N(0,g) on the effect size. Exact for any unknown
    sigma, which is why the construction does not need a prior reseed study of this
    substrate -- the substrate has just moved, so no such study exists.
    """
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    d_bar = float(d.mean())
    s_d = float(d.std(ddof=1))
    cap = (1.0 + n * g) ** ((n - 1) / 2.0)  # the t -> inf limit; 36 at n=5, g=1
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
    # The declared formula is symmetric in t, so a consistently NEGATIVE delta also
    # returns a large E -- evidence against exchangeability in the wrong direction.
    # Direction is carried beside the number rather than folded into it: applying a
    # one-sided transform after seeing the data is the one thing that voids an e-value.
    return {"n": n, "g": g, "d_bar": d_bar, "s_d": s_d, "t": t, "E": float(e),
            "direction_is_improvement": bool(d_bar > 0),
            "max_attainable_E": float(cap)}


def e_value_validity_check(n_draws: int = 100_000, seed: int = S.RANDOM_STATE) -> dict:
    """Push i.i.d. N(0, sigma) deltas through the implementation; mean(E) must be 1.

    Required by `e_value_construction.md` §4: a construction whose null mean is not 1
    is not an e-value. Run at several sigma because Construction B's whole claim is
    that validity does not depend on sigma.
    """
    rng = np.random.default_rng(seed)
    out = {}
    n, g = len(SEEDS), E_VALUE_G
    for sigma in (0.001, 0.01, 0.1, 1.0):
        d = rng.normal(0.0, sigma, size=(n_draws, n))
        t = np.sqrt(n) * d.mean(axis=1) / d.std(axis=1, ddof=1)
        num = 1.0 + t ** 2 / (n - 1)
        den = 1.0 + t ** 2 / ((1.0 + n * g) * (n - 1))
        e = (1.0 + n * g) ** -0.5 * (num / den) ** (n / 2.0)
        out[f"sigma={sigma}"] = {"mean_E": float(e.mean()),
                                 "mc_se": float(e.std(ddof=1) / np.sqrt(n_draws)),
                                 "p_E_gt_20": float((e > 20).mean())}
    return out


# ─── One family ─────────────────────────────────────────────────────────────────
def run_family(target: str, split, log) -> dict:
    spec = S.TARGET_BY_NAME[target]
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    hib = E._higher_is_better(spec)
    w_tr, c_tr, c_ev = split.w_tr, split.cens_tr, split.cens_ev
    y_tr, y_ev = split.y_tr, split.y_ev

    # Load the candidate column from warehouse, aligned by lap_id
    import duckdb
    con = duckdb.connect(S.DUCKDB_PATH, read_only=True)

    # Get the full dataset with the candidate column
    all_data = con.execute(
        f"SELECT lap_id, {CANDIDATE_COL} FROM {S.MART} WHERE is_training_eligible"
    ).df().set_index("lap_id")
    con.close()

    # Align with split's lap_ids
    baseline_observations_n_tr = pd.Series(
        all_data.loc[split.lap_ids_tr, CANDIDATE_COL].astype("float32").values,
        index=range(len(split.lap_ids_tr))
    )
    baseline_observations_n_ev = pd.Series(
        all_data.loc[split.lap_ids_ev, CANDIDATE_COL].astype("float32").values,
        index=range(len(split.lap_ids_ev))
    )

    Xf_tr, Xf_ev = split.X_tr, split.X_ev                       # baseline 32
    Xa_tr = split.X_tr.copy()                                    # add arm 33
    Xa_ev = split.X_ev.copy()
    Xa_tr[CANDIDATE_COL] = baseline_observations_n_tr.values
    Xa_ev[CANDIDATE_COL] = baseline_observations_n_ev.values

    res: dict = {
        "target": target,
        "metric": E._headline_metric_name(spec),
        "higher_is_better": hib,
        "n_train": int(len(Xf_tr)), "n_eval": int(len(Xf_ev)),
        "n_baseline_features": int(Xf_tr.shape[1]),
        "n_add_arm_features": int(Xa_tr.shape[1]),
        "candidate_column": CANDIDATE_COL,
        "split_mode": split.mode, "eval_season": split.eval_season,
        "seeds": list(SEEDS),
    }

    # ── Rank-degeneracy: is this just a relabelling of a column already in X? ───
    rd_tr = rank_degeneracy(Xa_tr, CANDIDATE_COL)
    rd_ev = rank_degeneracy(Xa_ev, CANDIDATE_COL)
    res["rank_degeneracy"] = {"train": rd_tr, "eval": rd_ev}
    log(f"  [{target}] rank-degeneracy (eval): max |rho| = {rd_ev['max_abs_spearman']:+.4f} "
        f"vs {rd_ev['max_abs_spearman_feature']} "
        f"(threshold {rd_ev['threshold_RANK_DEGENERATE_RHO']}, "
        f"degenerate={rd_ev['is_rank_degenerate']})")
    log(f"  [{target}] top ranks: " + ", ".join(
        f"{d['feature']}={d['spearman']:+.4f}" for d in rd_ev["top_k"]))

    # ── Step 2: the add-ablation, at the canonical seed ─────────────────────────
    t0 = time.time()
    base_model = E._fit(spec, params, Xf_tr, y_tr, cens=c_tr, w=w_tr)
    baseline = score_model(spec, base_model, Xf_ev, y_ev, c_ev)
    add_model = E._fit(spec, params, Xa_tr, y_tr, cens=c_tr, w=w_tr)
    add_ablation = score_model(spec, add_model, Xa_ev, y_ev, c_ev)
    res["baseline_headline"] = baseline
    res["add_ablation_headline"] = add_ablation
    d_real = delta(add_ablation, baseline, hib)
    log(f"  [{target}] baseline(32)={baseline:.10f}  "
        f"add_ablation(33)={add_ablation:.10f}  delta={d_real:+.8f} ({time.time()-t0:.0f}s)")

    # ── Step 3: each arm's own reseed floor; quote against the LARGER ───────────
    t0 = time.time()
    floor_base = AT.refit_noise_floor(
        lambda s: fit_seeded(spec, params, Xf_tr, y_tr, c_tr, w_tr, s),
        lambda yt, m, X: score_model(spec, m, X, yt, c_ev),
        Xf_ev, y_ev, SEEDS)
    floor_add = AT.refit_noise_floor(
        lambda s: fit_seeded(spec, params, Xa_tr, y_tr, c_tr, w_tr, s),
        lambda yt, m, X: score_model(spec, m, X, yt, c_ev),
        Xa_ev, y_ev, SEEDS)
    F2 = max(floor_base["delta_noise_2sd"], floor_add["delta_noise_2sd"])
    res["refit_noise_baseline"] = floor_base
    res["refit_noise_add_arm"] = floor_add
    res["floor_2sqrt2sd"] = F2
    res["floor_quoted_from"] = ("add_arm"
                                if floor_add["delta_noise_2sd"] >= floor_base["delta_noise_2sd"]
                                else "baseline")
    log(f"  [{target}] floor 2*sqrt(2)*sd = {F2:.8f} (from {res['floor_quoted_from']}; "
        f"baseline={floor_base['delta_noise_2sd']:.8f}, add={floor_add['delta_noise_2sd']:.8f}) "
        f"({time.time()-t0:.0f}s)")

    # ── Step 4: permutation null at the canonical seed ──────────────────────────
    t0 = time.time()
    Xs_tr = shuffled(Xa_tr, CANDIDATE_COL, np.random.default_rng([S.RANDOM_STATE, 0]))
    Xs_ev = shuffled(Xa_ev, CANDIDATE_COL, np.random.default_rng([S.RANDOM_STATE, 1]))
    shuf_headline = score_model(
        spec, E._fit(spec, params, Xs_tr, y_tr, cens=c_tr, w=w_tr), Xs_ev, y_ev, c_ev)
    capacity = delta(shuf_headline, baseline, hib)
    information = delta(add_ablation, shuf_headline, hib)
    log(f"  [{target}] shuffled={shuf_headline:.10f}  capacity={capacity:+.8f} "
        f"({capacity/F2:+.2f}x)  information={information:+.8f} ({information/F2:+.2f}x) "
        f"({time.time()-t0:.0f}s)")

    # ── Step 7: paired five-seed information contrast -> e-value ────────────────
    t0 = time.time()
    reals, shufs = [], []
    for s in SEEDS:
        reals.append(score_model(
            spec, fit_seeded(spec, params, Xa_tr, y_tr, c_tr, w_tr, s), Xa_ev, y_ev, c_ev))
        # The shuffle is redrawn per seed from a stream keyed on that seed, so the five
        # deltas are i.i.d. under H0 rather than all sharing one permutation draw.
        sh_tr = shuffled(Xa_tr, CANDIDATE_COL, np.random.default_rng([int(s), 0]))
        sh_ev = shuffled(Xa_ev, CANDIDATE_COL, np.random.default_rng([int(s), 1]))
        shufs.append(score_model(
            spec, fit_seeded(spec, params, sh_tr, y_tr, c_tr, w_tr, s), sh_ev, y_ev, c_ev))
    reals, shufs = np.asarray(reals), np.asarray(shufs)
    d_paired = np.asarray([delta(r, sh, hib) for r, sh in zip(reals, shufs)])
    ev = safe_t_e_value(d_paired)
    log(f"  [{target}] E(information) = {ev['E']:.4g}  "
        f"(d_bar={ev['d_bar']:+.8f}, improvement={ev['direction_is_improvement']}) "
        f"({time.time()-t0:.0f}s)")

    # ── Negative control: shuffle vs shuffle ────────────────────────────────────
    # Under H0 the real arm is exchangeable with a shuffle; here BOTH sides are
    # shuffles, so the delta is mean-zero by construction. A large E here would mean
    # the harness, not the data. Cheap insurance against a plumbing bug.
    t0 = time.time()
    d_ctrl = []
    for s in SEEDS:
        a = score_model(spec, fit_seeded(
            spec, params, shuffled(Xa_tr, CANDIDATE_COL, np.random.default_rng([int(s), 0])),
            y_tr, c_tr, w_tr, s),
            shuffled(Xa_ev, CANDIDATE_COL, np.random.default_rng([int(s), 1])), y_ev, c_ev)
        b = score_model(spec, fit_seeded(
            spec, params, shuffled(Xa_tr, CANDIDATE_COL, np.random.default_rng([int(s), 2])),
            y_tr, c_tr, w_tr, s),
            shuffled(Xa_ev, CANDIDATE_COL, np.random.default_rng([int(s), 3])), y_ev, c_ev)
        d_ctrl.append(delta(a, b, hib))
    ctrl_ev = safe_t_e_value(np.asarray(d_ctrl))
    log(f"  [{target}] control(shuffle vs shuffle) E={ctrl_ev['E']:.4g} "
        f"({time.time()-t0:.0f}s)")

    # ── Reference arm: push_residual shuffled ALONE ─────────────────────────────
    # WHY THIS EXISTS. The joint arm below destroys `push_residual` as well as the
    # candidate, and `push_residual` is an already-gated column carrying real signal
    # (08e family T). So a large E on the joint arm is mostly `push_residual`'s own
    # information and says nothing about the candidate on its own. The joint number is
    # only interpretable against this one: the question the leaf doc asks is whether the
    # two are SYNERGISTIC (the count qualifies the estimate) or merely ADDITIVE (the
    # count is a separate, counter-like channel). That needs all three of
    # info(candidate), info(push_residual) and info(pair), on common random numbers.
    t0 = time.time()
    pr_reals, pr_shufs = [], []
    for s in SEEDS:
        pr_reals.append(score_model(
            spec, fit_seeded(spec, params, Xa_tr, y_tr, c_tr, w_tr, s), Xa_ev, y_ev, c_ev))
        sh_tr = shuffled(Xa_tr, "push_residual", np.random.default_rng([int(s), 0]))
        sh_ev = shuffled(Xa_ev, "push_residual", np.random.default_rng([int(s), 1]))
        pr_shufs.append(score_model(
            spec, fit_seeded(spec, params, sh_tr, y_tr, c_tr, w_tr, s), sh_ev, y_ev, c_ev))
    pr_reals, pr_shufs = np.asarray(pr_reals), np.asarray(pr_shufs)
    d_pr_info = np.asarray([delta(r, sh, hib) for r, sh in zip(pr_reals, pr_shufs)])
    pr_ev = safe_t_e_value(d_pr_info)
    log(f"  [{target}] reference(push_residual alone) E={pr_ev['E']:.4g} "
        f"(d_bar={pr_ev['d_bar']:+.8f}, {pr_ev['d_bar']/F2:+.2f}x floor) "
        f"({time.time()-t0:.0f}s)")

    # ── Pair arm: baseline_observations_n paired with push_residual ──────────────
    # Same permutation streams as the two single-column arms above, so the synergy
    # estimate below is a common-random-numbers contrast rather than three independent
    # draws.
    t0 = time.time()
    pair_reals, pair_shufs = [], []
    for s in SEEDS:
        pair_reals.append(score_model(
            spec, fit_seeded(spec, params, Xa_tr, y_tr, c_tr, w_tr, s), Xa_ev, y_ev, c_ev))
        # Shuffle BOTH columns jointly
        sh_tr = shuffled_pair(Xa_tr, (CANDIDATE_COL, "push_residual"),
                              np.random.default_rng([int(s), 0]))
        sh_ev = shuffled_pair(Xa_ev, (CANDIDATE_COL, "push_residual"),
                              np.random.default_rng([int(s), 1]))
        pair_shufs.append(score_model(
            spec, fit_seeded(spec, params, sh_tr, y_tr, c_tr, w_tr, s), sh_ev, y_ev, c_ev))
    pair_reals, pair_shufs = np.asarray(pair_reals), np.asarray(pair_shufs)
    d_pair_info = np.asarray([delta(r, sh, hib) for r, sh in zip(pair_reals, pair_shufs)])
    pair_ev = safe_t_e_value(d_pair_info)
    pair_capacity = delta(pair_shufs.mean(), baseline, hib)
    # Synergy: how much the pair carries OVER the sum of the two singles. ~0 means the
    # count is a separate channel, not the uncertainty qualifying the estimate.
    synergy = float(d_pair_info.mean() - d_paired.mean() - d_pr_info.mean())
    log(f"  [{target}] pair(baseline_obs_n + push_residual) E={pair_ev['E']:.4g} "
        f"(d_bar={pair_ev['d_bar']:+.8f}) ({time.time()-t0:.0f}s)")
    log(f"  [{target}] additivity: info(pair)={d_pair_info.mean():+.8f} vs "
        f"info(cand)+info(push_residual)={d_paired.mean()+d_pr_info.mean():+.8f}  "
        f"synergy={synergy:+.8f} ({synergy/F2:+.2f}x floor)")

    res.update({
        "add_ablation": {
            "delta_vs_baseline": d_real,
            "floor_ratio": (d_real / F2) if F2 else None,
            "clears_floor": bool(d_real > F2) if F2 else None,
        },
        "permutation_null": {
            "headline_shuffled": shuf_headline,
            "capacity_delta": capacity,
            "capacity_floor_ratio": (capacity / F2) if F2 else None,
            "information_delta": information,
            "information_floor_ratio": (information / F2) if F2 else None,
            "information_clears_floor": bool(information > F2) if F2 else None,
        },
        "paired_seeds": {
            "real_by_seed": reals.tolist(),
            "shuffled_by_seed": shufs.tolist(),
            "information_deltas": d_paired.tolist(),
            "e_value": ev,
        },
        "negative_control_shuffle_vs_shuffle": {
            "paired_deltas": d_ctrl,
            "e_value": ctrl_ev,
            "note": ("both arms are shuffles of the same column, so H0 is true "
                     "by construction; a large E here would indict the harness."),
        },
        "reference_arm_push_residual_alone": {
            "note": ("push_residual shuffled on its own. The joint arm is only "
                     "interpretable against this: push_residual is already-gated and "
                     "carries real signal, so it dominates any arm that destroys it."),
            "information_delta": float(d_pr_info.mean()),
            "information_floor_ratio": (float(d_pr_info.mean()) / F2) if F2 else None,
            "e_value": pr_ev,
            "real_by_seed": pr_reals.tolist(),
            "shuffled_by_seed": pr_shufs.tolist(),
            "information_deltas": d_pr_info.tolist(),
        },
        "pair_arm_with_push_residual": {
            "note": ("distinguish 'model wants the uncertainty' (synergy with "
                     "push_residual) from 'model wants another counter' (additive, "
                     "separate channel). Read `synergy_vs_additive` -- NOT the raw E, "
                     "which is dominated by push_residual's own information."),
            "information_delta": d_pair_info.mean() if len(d_pair_info) > 0 else None,
            "information_floor_ratio": (d_pair_info.mean() / F2) if F2 and len(d_pair_info) > 0 else None,
            "e_value": pair_ev,
            "real_by_seed": pair_reals.tolist(),
            "shuffled_by_seed": pair_shufs.tolist(),
            "information_deltas": d_pair_info.tolist(),
            "synergy_vs_additive": {
                "info_pair": float(d_pair_info.mean()),
                "info_candidate_alone": float(d_paired.mean()),
                "info_push_residual_alone": float(d_pr_info.mean()),
                "sum_of_singles": float(d_paired.mean() + d_pr_info.mean()),
                "synergy": synergy,
                "synergy_floor_ratio": (synergy / F2) if F2 else None,
            },
        },
    })
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", nargs="*", default=list(FAMILIES))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    lines: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    published = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())
    pub_version = published.get("version")

    out: dict = {
        "item": "08h",
        "purpose": ("add-ablation testing whether baseline_observations_n should be a "
                    "feature, deferred from 08e"),
        "ran_at": pd.Timestamp.utcnow().isoformat(),
        "contract_version": S.MODEL_VERSION_DEFAULT,
        "published_artefact_version": pub_version,
        "n_baseline_features": len(S.FEATURE_COLUMNS),
        "candidate_column": CANDIDATE_COL,
        "seeds": list(SEEDS),
        "e_value_construction": {"name": "B (paired safe-t)", "n": len(SEEDS),
                                 "g": E_VALUE_G,
                                 "null": "information contrast: real vs its own shuffle"},
        "e_value_validity_check": e_value_validity_check(),
        "families": {},
    }

    log(f"contract {S.MODEL_VERSION_DEFAULT}, {len(S.FEATURE_COLUMNS)} features")
    log(f"candidate column = {CANDIDATE_COL}")
    log("e-value validity check (mean E under H0 must be 1.00):")
    for k, v in out["e_value_validity_check"].items():
        log(f"  {k:<14} mean_E={v['mean_E']:.4f} +/- {2*v['mc_se']:.4f}  "
            f"P(E>20)={v['p_E_gt_20']:.4f}")
    cap = (1.0 + len(SEEDS) * E_VALUE_G) ** ((len(SEEDS) - 1) / 2.0)
    out["e_value_construction"]["max_attainable_E"] = cap
    log(f"  max attainable E at n={len(SEEDS)}, g={E_VALUE_G}: {cap:.1f}")

    # One bundle serves the whole degradation trio: same rows, same target column,
    # same per-family mask; only the quantile alpha and the tuned params differ.
    bundles: dict[str, object] = {}
    for target in args.families:
        spec = S.TARGET_BY_NAME[target]
        fam = spec.family
        if fam not in bundles:
            bundles[fam] = E._evaluation_split(F.load_features(target=target))
        split = bundles[fam]
        log(f"\n=== {target} ({fam}) ===")
        out["families"][target] = run_family(target, split, log)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2, default=float))

    Path(args.out).with_suffix(".log").write_text("\n".join(lines) + "\n")
    log(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
