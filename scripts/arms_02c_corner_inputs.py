"""02c — Tier 2 corner-level driver inputs: the pre-registered arms.

Runs exactly the arms declared in _improvements/work/02-feature-expansion.md §3 `02c`
before any of them was run, on the families that are not barred:

    degradation_regressor p10 / p50 / p90   (pinball, lower better)
    cliff_classifier                        (macro-F1, higher better)

`stint_life_regressor` is BARRED here until 10e resolves (10d showed the shipped
booster was tuned under the wrong label); the pre-registration says so explicitly and
this script refuses to run it rather than leaving the bar to a reader's memory.

Protocol, in the order gates.md numbers it:

  1. instrument check  -- the 32-column refit must reproduce the published v11 headline
                          to six decimals, per family, before anything else is trusted.
  2. add-ablation      -- cv_final_fold, train 2018-2023, eval 2024, evaluate.py's own
                          _fit/_score.
  3. floor             -- attribution.refit_noise_floor over seeds RANDOM_STATE+0..4,
                          delta measured against 2*sqrt(2)*sd of THAT family.
  4. permutation null  -- the arm's own columns row-shuffled in train AND eval, so
                          capacity is preserved and signal destroyed. Capacity and
                          information reported separately.
  7. e-value           -- Construction B (paired safe-t) over the same five seeds, as
                          pre-registered, with the Monte Carlo validity check the
                          reference requires.

Deltas are oriented so POSITIVE ALWAYS MEANS IMPROVEMENT, on every metric.

Usage:  python -m scripts.arms_02c_corner_inputs
        (or  PYTHONPATH=. ./.venv/bin/python scripts/arms_02c_corner_inputs.py)

Writes ml/artefacts/02c_corner_inputs_arms.json -- every fit's headline, per seed, so a
reader can recompute any delta, floor ratio or e-value in the leaf doc without refitting.
The run that produced the committed artefact took ~35 minutes on 8 cores; its console
output is ml/artefacts/02c_corner_inputs_arms.log.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ml.src import attribution as AT
from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S
from ml.src import train as T

# ─── The ten columns, in the order the mart emits them ──────────────────────────
COVERAGE_COL = ("corner_input_coverage",)
RESIDUAL_COLS = (
    "corner_braking_loss_mean_s", "corner_braking_loss_sd_s", "corner_braking_loss_max_s",
    "corner_mid_residual_mean_s", "corner_mid_residual_sd_s", "corner_mid_residual_max_s",
    "corner_exit_residual_mean_s", "corner_exit_residual_sd_s", "corner_exit_residual_max_s",
)
ARMS: dict[str, tuple[str, ...]] = {
    "A_full": COVERAGE_COL + RESIDUAL_COLS,   # 10 -- the group as designed
    "B_residuals": RESIDUAL_COLS,             # 9  -- the driver-input channel alone
    "C_coverage": COVERAGE_COL,               # 1  -- the confound control
}

SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(5))
E_VALUE_G = 1.0          # pre-registered: a one-sd effect
FAMILIES = ("degradation_regressor_p10", "degradation_regressor_p50",
            "degradation_regressor_p90", "cliff_classifier")
OUT = Path("ml/artefacts/02c_corner_inputs_arms.json")


# ─── Column plumbing ────────────────────────────────────────────────────────────
def corner_frame(duckdb_path: str = S.DUCKDB_PATH) -> pd.DataFrame:
    """The ten mart columns, indexed by lap_id, float32, NaN preserved.

    Read straight off `fct_cliff_prediction_features` rather than through
    features.py: the columns are deliberately NOT in FEATURE_COLUMNS yet (the
    contract moves only if these arms say it should), so the loader does not carry
    them. Encoding matches `_encode_frame`'s continuous branch exactly -- to_numeric
    then float32, native NaN left as NaN.
    """
    cols = ", ".join(COVERAGE_COL + RESIDUAL_COLS)
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        df = con.execute(f"SELECT lap_id, {cols} FROM {S.MART}").df()
    finally:
        con.close()
    df = df.set_index("lap_id")
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")
    return df


def attach(X: pd.DataFrame, lap_ids: np.ndarray, extra: pd.DataFrame,
           cols: tuple[str, ...]) -> pd.DataFrame:
    """X with `cols` appended, aligned row-for-row on lap_id."""
    block = extra.reindex(pd.Index(lap_ids))[list(cols)]
    if block.isna().all(axis=1).all():
        raise RuntimeError("no corner rows matched the split's lap_ids")
    out = X.copy()
    for c in cols:
        out[c] = block[c].to_numpy(dtype=np.float32)
    return out


def shuffled(X: pd.DataFrame, cols: tuple[str, ...], rng: np.random.Generator) -> pd.DataFrame:
    """Row-shuffle the block of new columns JOINTLY.

    Jointly, not column-by-column: the arm's internal correlation structure is part of
    its capacity, and the null this scores is "these columns carry no information about
    the label", not "these columns are unrelated to each other". Capacity is preserved
    exactly -- same matrix shape, same marginal distributions, same NaN count. NaNs move
    with their values, which is why the leaf doc says this arm cannot by itself rule out
    a missingness-driven win, and why arm C exists.
    """
    out = X.copy()
    perm = rng.permutation(len(X))
    block = out[list(cols)].to_numpy()[perm]
    for i, c in enumerate(cols):
        out[c] = block[:, i]
    return out


# ─── Fit / score ────────────────────────────────────────────────────────────────
def fit_seeded(spec: S.TargetSpec, params: dict, X, y, w, seed: int):
    """evaluate.py's fit with the seed overridden -- the same override
    `within_stint_attribution.fit_seeded` uses, for the same reason: random_state is
    fixed inside T._make_model and cannot be passed through `params`."""
    m = T._make_model(spec, params)
    weights = w if w is not None else T._sample_weight(spec, y)
    m.set_params(random_state=seed)
    return m.fit(X, y, sample_weight=weights)


def score(spec: S.TargetSpec, model, X_ev, y_ev) -> float:
    return E._score(spec, y_ev, E._predict_index(spec, model, X_ev))


def delta(arm_value: float, base_value: float, higher_is_better: bool) -> float:
    """Positive = improvement, on every metric."""
    return (arm_value - base_value) if higher_is_better else (base_value - arm_value)


# ─── E-value, Construction B (paired safe-t) ────────────────────────────────────
def safe_t_e_value(d: np.ndarray, g: float = E_VALUE_G) -> dict:
    """E = (1+ng)^(-1/2) * [(1+t^2/(n-1)) / (1+t^2/((1+ng)(n-1)))]^(n/2).

    The one-sample Bayes factor under a right-Haar prior on sigma and N(0,g) on the
    effect size -- Grunwald, de Heide & Koolen's safe t-test. Exact for any unknown
    sigma, which is why the pre-registration chose it over Construction A: no prior
    separate reseed study of this substrate exists at the 32-column contract, so A's
    scale would be a plug-in from the same five seeds it scores.
    """
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    d_bar = float(d.mean())
    s_d = float(d.std(ddof=1))
    cap = (1.0 + n * g) ** ((n - 1) / 2.0)   # the t -> inf limit; 36 at n=5, g=1
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
    # The DECLARED formula is reported exactly as pre-registered, and it is symmetric
    # in t. A consistently negative delta therefore also returns a large E -- evidence
    # against "these columns are exchangeable with their own shuffle", in the wrong
    # direction. Reading that as support for the arm would be a misreading, so the
    # direction is carried beside the number rather than folded into it: applying a
    # one-sided transform now would be changing the construction after seeing the data,
    # which is the one thing that voids an e-value.
    return {"n": n, "g": g, "d_bar": d_bar, "s_d": s_d, "t": t, "E": float(e),
            "direction_is_improvement": bool(d_bar > 0),
            "max_attainable_E": float(cap)}


def e_value_validity_check(n_draws: int = 100_000, seed: int = S.RANDOM_STATE) -> dict:
    """Push i.i.d. N(0, sigma) deltas through the implementation and confirm mean(E)=1.

    Required by e_value_construction.md §4: "A construction whose null mean is not 1 is
    not an e-value." Run at several sigma because the whole point of Construction B is
    that validity does not depend on sigma.
    """
    rng = np.random.default_rng(seed)
    out = {}
    for sigma in (0.001, 0.01, 0.1, 1.0):
        d = rng.normal(0.0, sigma, size=(n_draws, len(SEEDS)))
        d_bar = d.mean(axis=1)
        s_d = d.std(axis=1, ddof=1)
        t = np.sqrt(len(SEEDS)) * d_bar / s_d
        n, g = len(SEEDS), E_VALUE_G
        num = 1.0 + t ** 2 / (n - 1)
        den = 1.0 + t ** 2 / ((1.0 + n * g) * (n - 1))
        e = (1.0 + n * g) ** -0.5 * (num / den) ** (n / 2.0)
        out[f"sigma={sigma}"] = {
            "mean_E": float(e.mean()),
            "mc_se": float(e.std(ddof=1) / np.sqrt(n_draws)),
            "p_E_gt_20": float((e > 20).mean()),
        }
    return out


# ─── One family ─────────────────────────────────────────────────────────────────
def run_family(target: str, split, extra: pd.DataFrame, published: float,
               log) -> dict:
    spec = S.TARGET_BY_NAME[target]
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    hib = E._higher_is_better(spec)
    w_tr = split.w_tr
    X_tr, X_ev = split.X_tr, split.X_ev
    y_tr, y_ev = split.y_tr, split.y_ev

    res: dict = {
        "target": target,
        "metric": E._headline_metric_name(spec),
        "higher_is_better": hib,
        "n_train": int(len(X_tr)), "n_eval": int(len(X_ev)),
        "n_baseline_features": int(X_tr.shape[1]),
        "seeds": list(SEEDS),
    }

    # ── Step 1: instrument check ────────────────────────────────────────────────
    t0 = time.time()
    base_model = E._fit(spec, params, X_tr, y_tr, w=w_tr)
    baseline = score(spec, base_model, X_ev, y_ev)
    res["baseline_headline"] = baseline
    res["published_headline"] = published
    res["instrument_check_6dp"] = bool(abs(baseline - published) < 5e-7)
    log(f"  [{target}] baseline={baseline:.10f} published={published:.10f} "
        f"instrument_check={res['instrument_check_6dp']} ({time.time()-t0:.0f}s)")
    if not res["instrument_check_6dp"]:
        res["aborted"] = ("instrument check failed: the 32-column refit does not "
                          "reproduce the published headline, so no delta below it "
                          "would mean anything")
        return res

    # ── Step 3: this family's own reseed floor ──────────────────────────────────
    t0 = time.time()
    floor = AT.refit_noise_floor(
        lambda s: fit_seeded(spec, params, X_tr, y_tr, w_tr, s),
        lambda yt, m, X: score(spec, m, X, yt),
        X_ev, y_ev, SEEDS)
    res["refit_noise"] = floor
    F2 = floor["delta_noise_2sd"]
    log(f"  [{target}] floor 2*sqrt(2)*sd = {F2:.8f}  (sd={floor['headline_sd']:.8f}, "
        f"{time.time()-t0:.0f}s)")

    # ── Steps 2 + 4 + 7, per arm ────────────────────────────────────────────────
    arm_rows: dict[str, dict] = {}
    for arm, cols in ARMS.items():
        t0 = time.time()
        Xa_tr = attach(X_tr, split.lap_ids_tr, extra, cols)
        Xa_ev = attach(X_ev, split.lap_ids_ev, extra, cols)

        # Canonical-seed add-ablation (the delta the floor judges).
        real_c = score(spec, E._fit(spec, params, Xa_tr, y_tr, w=w_tr), Xa_ev, y_ev)
        d_real = delta(real_c, baseline, hib)

        # Permutation null at the canonical seed: capacity and information, separately.
        rng_tr = np.random.default_rng([S.RANDOM_STATE, 0])
        rng_ev = np.random.default_rng([S.RANDOM_STATE, 1])
        Xs_tr = shuffled(Xa_tr, cols, rng_tr)
        Xs_ev = shuffled(Xa_ev, cols, rng_ev)
        shuf_c = score(spec, E._fit(spec, params, Xs_tr, y_tr, w=w_tr), Xs_ev, y_ev)
        capacity = delta(shuf_c, baseline, hib)
        information = delta(real_c, shuf_c, hib)

        # Paired five-seed arms for the e-value. The shuffle is redrawn per seed from a
        # stream keyed on that seed, so the five deltas are i.i.d. under H0 rather than
        # sharing one permutation draw.
        reals, shufs = [], []
        for s in SEEDS:
            reals.append(score(spec, fit_seeded(spec, params, Xa_tr, y_tr, w_tr, s),
                               Xa_ev, y_ev))
            r_tr = np.random.default_rng([int(s), 0])
            r_ev = np.random.default_rng([int(s), 1])
            shufs.append(score(spec, fit_seeded(spec, params,
                                                shuffled(Xa_tr, cols, r_tr), y_tr, w_tr, s),
                               shuffled(Xa_ev, cols, r_ev), y_ev))
        reals, shufs = np.asarray(reals), np.asarray(shufs)
        d_paired = np.asarray([delta(r, sh, hib) for r, sh in zip(reals, shufs)])
        ev = safe_t_e_value(d_paired)

        arm_rows[arm] = {
            "columns": list(cols), "n_columns": len(cols),
            "headline_real": real_c, "headline_shuffled": shuf_c,
            "delta_vs_baseline": d_real,
            "floor_ratio": (d_real / F2) if F2 else None,
            "clears_floor": bool(d_real > F2) if F2 else None,
            "capacity_delta": capacity,
            "capacity_floor_ratio": (capacity / F2) if F2 else None,
            "information_delta": information,
            "information_floor_ratio": (information / F2) if F2 else None,
            "information_clears_floor": bool(information > F2) if F2 else None,
            "paired_real_by_seed": reals.tolist(),
            "paired_shuffled_by_seed": shufs.tolist(),
            "paired_information_deltas": d_paired.tolist(),
            "e_value": ev,
            "seconds": round(time.time() - t0, 1),
        }
        log(f"  [{target}] {arm:<12} delta={d_real:+.8f} ({d_real/F2:+.2f}x floor) "
            f"cap={capacity:+.8f} info={information:+.8f} ({information/F2:+.2f}x) "
            f"E={ev['E']:.3g}  [{arm_rows[arm]['seconds']:.0f}s]")

    # ── Negative control: shuffle vs shuffle, on arm A's columns ────────────────
    # P's own null. Under H0 the real arm is exchangeable with a shuffle; under the
    # control BOTH sides are shuffles, so the delta is mean-zero by construction and
    # its E is an empirical check that the whole pipeline returns ~1 when nothing is
    # there. Cheap insurance against a plumbing bug reading as evidence.
    t0 = time.time()
    colsA = ARMS["A_full"]
    XA_tr = attach(X_tr, split.lap_ids_tr, extra, colsA)
    XA_ev = attach(X_ev, split.lap_ids_ev, extra, colsA)
    d_ctrl = []
    for s in SEEDS:
        a = score(spec, fit_seeded(spec, params,
                                   shuffled(XA_tr, colsA, np.random.default_rng([int(s), 0])),
                                   y_tr, w_tr, s),
                  shuffled(XA_ev, colsA, np.random.default_rng([int(s), 1])), y_ev)
        b = score(spec, fit_seeded(spec, params,
                                   shuffled(XA_tr, colsA, np.random.default_rng([int(s), 2])),
                                   y_tr, w_tr, s),
                  shuffled(XA_ev, colsA, np.random.default_rng([int(s), 3])), y_ev)
        d_ctrl.append(delta(a, b, hib))
    res["negative_control_shuffle_vs_shuffle"] = {
        "paired_deltas": d_ctrl,
        "e_value": safe_t_e_value(np.asarray(d_ctrl)),
        "note": ("both arms are shuffles of the same ten columns, so H0 is true by "
                 "construction. A large E here would mean the harness, not the data."),
        "seconds": round(time.time() - t0, 1),
    }
    log(f"  [{target}] control(shuffle vs shuffle) "
        f"E={res['negative_control_shuffle_vs_shuffle']['e_value']['E']:.3g}")

    res["arms"] = arm_rows
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", nargs="*", default=list(FAMILIES))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    if "stint_life_regressor" in args.families:
        raise SystemExit(
            "stint_life_regressor is BARRED until 10e resolves (10d: the shipped "
            "booster was tuned under the wrong label, on the mixture NLL, with 2024 in "
            "the validation folds). Measuring its floor now measures a model that is "
            "about to change. See 02b's note and the 02c pre-registration.")

    lines: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    published = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())
    extra = corner_frame()
    log(f"corner columns loaded: {extra.shape[0]} lap_ids x {extra.shape[1]} columns")

    out: dict = {
        "item": "02c",
        "ran_at": pd.Timestamp.utcnow().isoformat(),
        "contract_version": S.MODEL_VERSION_DEFAULT,
        "n_contract_features": len(S.FEATURE_COLUMNS),
        "seeds": list(SEEDS),
        "e_value_construction": {"name": "B (paired safe-t)", "n": len(SEEDS), "g": E_VALUE_G},
        "e_value_validity_check": e_value_validity_check(),
        "barred": {"stint_life_regressor": "until 10e resolves (10d's finding)"},
        "families": {},
    }
    log("e-value validity check (mean E under H0 must be 1.00):")
    for k, v in out["e_value_validity_check"].items():
        log(f"  {k:<14} mean_E={v['mean_E']:.4f} +/- {2*v['mc_se']:.4f}  "
            f"P(E>20)={v['p_E_gt_20']:.4f}")
    cap = (1.0 + len(SEEDS) * E_VALUE_G) ** ((len(SEEDS) - 1) / 2.0)
    out["e_value_construction"]["max_attainable_E"] = cap
    log(f"  max attainable E at n={len(SEEDS)}, g={E_VALUE_G}: {cap:.1f} "
        f"(t -> inf limit; a lone e-BH rejection at alpha=0.05 needs E >= 20*family_size)")

    # One bundle serves the whole degradation trio -- same rows, same target column,
    # same per-family mask; only the quantile alpha and the tuned params differ.
    bundles: dict[str, object] = {}
    for target in args.families:
        fam = S.TARGET_BY_NAME[target].family
        if fam not in bundles:
            bundles[fam] = E._evaluation_split(F.load_features(target=target))
        split = bundles[fam]
        log(f"\n=== {target} ({fam}) ===")
        out["families"][target] = run_family(
            target, split, extra, published["models"][target]["headline"], log)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, default=float))
    log(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
