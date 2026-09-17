"""08e — the thermal family (T) re-read on the v12 / 08m substrate.

WHY THIS EXISTS. `08e` rebuilt `int_lap_thermal_proxy.stint_baseline_pace` as a
trailing expanding median and was taken to GATED on 2026-09-09. Then `08m`
(2026-09-16) repaired the compound wear curve and rebuilt the warehouse, which made
`next_5_lap_cumulative_jump_s` **a different quantity** (target mean -1.8793 ->
-0.3946 s; `is_training_eligible` 82,470 -> 81,619). Every pinball number, reseed
floor and floor-ratio in `08e`'s gate section is therefore on a superseded target and
carries a STALE banner. Open decision `D3` says those deltas "must be re-read first".
This script is that re-read: gate steps 1-4 and 7, re-run for family T alone, on the
current substrate, against the published **v12** headline.

WHAT IT DOES *NOT* DO. It does not re-run `08e`'s materiality probe (the BLOCK vs
TRAILING correlation contrast). That ruling rests on construction plus a
position-matched correlation contrast, neither of which the target change touches --
`08m` moved the label, not the leak. The leakage ruling stands; only the headline
numbers needed refreshing.

THE DESIGN, AND ONE DELIBERATE DIFFERENCE FROM THE 2026-09-09 RUN.

    baseline A  = the 32-column contract MINUS family T   (28 columns)
    arm    A+T  = the full 32-column contract

The 2026-09-09 run used a joint baseline that excluded family T *and* family C
(`cliff_candidate_flag`), so one common reference served both `08e` and `08f`. `08j`
has since pruned `cliff_candidate_flag` from the contract outright (ruled dead on both
substrates by `08g`), so "contract minus T" IS the direct analogue of that run's `A`
and no third arm is needed. The contract is 32 columns here, not 33, for that reason.

NO NUMBER HERE MAY BE DIFFED AGAINST THE 2026-09-09 TABLE. Both runs score a
different target. Per `foundations/epistemics.md`'s protocol-anchoring rule, the old
and new floor ratios are read side by side as two separate measurements, never
subtracted.

Family T, fixed by lineage rather than by taste -- the only contract columns fed by
`int_lap_thermal_proxy`:

    push_residual, cumulative_push_load_surface,
    cumulative_push_load_bulk, surface_bulk_ratio

Protocol, in the order `foundations/gates.md` numbers it:

  1. instrument check  -- the full 32-column refit must reproduce the published v12
                          headline to six decimals, per family, or the run aborts.
  2. add-ablation      -- cv_final_fold, train 2018-2023, eval 2024, through
                          evaluate.py's own _fit/_predict_index/_score. No
                          reimplementation of fit, score or CV.
  3. floor             -- attribution.refit_noise_floor over seeds RANDOM_STATE+0..4,
                          computed on BOTH arms; every ratio is quoted against the
                          LARGER of the two, which is the conservative call and the
                          one the 2026-09-09 run made.
  4. permutation null  -- family T row-shuffled JOINTLY in train AND eval, so capacity
                          and the block's own joint distribution are preserved exactly
                          and only its alignment with the label is destroyed. Capacity
                          (shuffled - baseline) and information (real - shuffled) are
                          reported separately, never summed into one claim.
  7. e-value           -- Construction B (paired safe-t) over the same five seeds on
                          the INFORMATION contrast (real vs its own shuffle), which is
                          the null gate step 4 isolates. Includes the Monte Carlo
                          validity check `e_value_construction.md` §4 requires, and a
                          shuffle-vs-shuffle negative control.

Deltas are oriented so POSITIVE ALWAYS MEANS IMPROVEMENT, on every metric.

Reads the warehouse read-only. Writes nothing to `ml/models/`, nothing to
`ml/artefacts/evaluation_metrics.json`, nothing to the warehouse and nothing to git:
`evaluate.run()` is never called, so no artefact directory is touched. The only
output is the JSON named below.

Usage:  PYTHONPATH=. python3 scripts/arms_08e_thermal_family.py
        PYTHONPATH=. python3 scripts/arms_08e_thermal_family.py --families cliff_classifier
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

# ─── Family T: the only contract columns fed by int_lap_thermal_proxy ───────────
T_COLS: tuple[str, ...] = (
    "push_residual",
    "cumulative_push_load_surface",
    "cumulative_push_load_bulk",
    "surface_bulk_ratio",
)

SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(5))
E_VALUE_G = 1.0  # pre-registered: a one-sd effect, as in 02c
FAMILIES = ("degradation_regressor_p10", "degradation_regressor_p50",
            "degradation_regressor_p90", "cliff_classifier",
            "stint_life_regressor")
OUT = Path("ml/artefacts/08e_thermal_family_arms.json")


# ─── Fit / score, through evaluate.py's own paths ───────────────────────────────
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


def shuffled(X: pd.DataFrame, cols: tuple[str, ...],
             rng: np.random.Generator) -> pd.DataFrame:
    """Row-shuffle the family block JOINTLY.

    Jointly, not column-by-column: the block's internal correlation structure is part
    of its capacity, and the null being scored is "these four columns carry no
    information about the label", not "these four are unrelated to each other".
    Capacity is preserved exactly -- same shape, same marginals, same NaN count, NaNs
    moving with their values.
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
def run_family(target: str, split, published: float, log) -> dict:
    spec = S.TARGET_BY_NAME[target]
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    hib = E._higher_is_better(spec)
    w_tr, c_tr, c_ev = split.w_tr, split.cens_tr, split.cens_ev
    y_tr, y_ev = split.y_tr, split.y_ev

    missing = [c for c in T_COLS if c not in split.X_tr.columns]
    if missing:
        raise RuntimeError(f"family T columns absent from the contract: {missing}")

    Xf_tr, Xf_ev = split.X_tr, split.X_ev                       # full 32
    Xa_tr = split.X_tr.drop(columns=list(T_COLS))               # baseline A, 28
    Xa_ev = split.X_ev.drop(columns=list(T_COLS))

    res: dict = {
        "target": target,
        "metric": E._headline_metric_name(spec),
        "higher_is_better": hib,
        "n_train": int(len(Xf_tr)), "n_eval": int(len(Xf_ev)),
        "n_contract_features": int(Xf_tr.shape[1]),
        "n_baseline_features": int(Xa_tr.shape[1]),
        "family_T_columns": list(T_COLS),
        "split_mode": split.mode, "eval_season": split.eval_season,
        "seeds": list(SEEDS),
    }

    # ── Step 1: instrument check, against the published v12 headline ────────────
    t0 = time.time()
    full_model = E._fit(spec, params, Xf_tr, y_tr, cens=c_tr, w=w_tr)
    full_headline = score_model(spec, full_model, Xf_ev, y_ev, c_ev)
    res["full_contract_headline"] = full_headline
    res["published_v12_headline"] = published
    res["instrument_check_6dp"] = bool(abs(full_headline - published) < 5e-7)
    log(f"  [{target}] full-contract={full_headline:.10f} published_v12={published:.10f} "
        f"instrument_check={res['instrument_check_6dp']} ({time.time()-t0:.0f}s)")
    if not res["instrument_check_6dp"]:
        res["aborted"] = ("instrument check failed: the 32-column refit does not "
                          "reproduce the published v12 headline, so every delta "
                          "measured against it would be meaningless")
        log(f"  [{target}] ABORTED -- {res['aborted']}")
        return res

    # ── Step 2: the add-ablation, at the canonical seed ─────────────────────────
    t0 = time.time()
    base_model = E._fit(spec, params, Xa_tr, y_tr, cens=c_tr, w=w_tr)
    baseline = score_model(spec, base_model, Xa_ev, y_ev, c_ev)
    res["baseline_A_headline"] = baseline
    d_real = delta(full_headline, baseline, hib)
    log(f"  [{target}] baseline_A(28 cols)={baseline:.10f}  "
        f"add-ablation delta={d_real:+.8f} ({time.time()-t0:.0f}s)")

    # ── Step 3: each arm's own reseed floor; quote against the LARGER ───────────
    t0 = time.time()
    floor_base = AT.refit_noise_floor(
        lambda s: fit_seeded(spec, params, Xa_tr, y_tr, c_tr, w_tr, s),
        lambda yt, m, X: score_model(spec, m, X, yt, c_ev),
        Xa_ev, y_ev, SEEDS)
    floor_full = AT.refit_noise_floor(
        lambda s: fit_seeded(spec, params, Xf_tr, y_tr, c_tr, w_tr, s),
        lambda yt, m, X: score_model(spec, m, X, yt, c_ev),
        Xf_ev, y_ev, SEEDS)
    F2 = max(floor_base["delta_noise_2sd"], floor_full["delta_noise_2sd"])
    res["refit_noise_baseline_A"] = floor_base
    res["refit_noise_full_contract"] = floor_full
    res["floor_2sqrt2sd"] = F2
    res["floor_quoted_from"] = ("full_contract"
                                if floor_full["delta_noise_2sd"] >= floor_base["delta_noise_2sd"]
                                else "baseline_A")
    log(f"  [{target}] floor 2*sqrt(2)*sd = {F2:.8f} (from {res['floor_quoted_from']}; "
        f"A={floor_base['delta_noise_2sd']:.8f}, full={floor_full['delta_noise_2sd']:.8f}) "
        f"({time.time()-t0:.0f}s)")

    # ── Step 4: permutation null at the canonical seed ──────────────────────────
    t0 = time.time()
    Xs_tr = shuffled(Xf_tr, T_COLS, np.random.default_rng([S.RANDOM_STATE, 0]))
    Xs_ev = shuffled(Xf_ev, T_COLS, np.random.default_rng([S.RANDOM_STATE, 1]))
    shuf_headline = score_model(
        spec, E._fit(spec, params, Xs_tr, y_tr, cens=c_tr, w=w_tr), Xs_ev, y_ev, c_ev)
    capacity = delta(shuf_headline, baseline, hib)
    information = delta(full_headline, shuf_headline, hib)
    log(f"  [{target}] shuffled={shuf_headline:.10f}  capacity={capacity:+.8f} "
        f"({capacity/F2:+.2f}x)  information={information:+.8f} ({information/F2:+.2f}x) "
        f"({time.time()-t0:.0f}s)")

    # ── Step 7: paired five-seed information contrast -> e-value ────────────────
    t0 = time.time()
    reals, shufs = [], []
    for s in SEEDS:
        reals.append(score_model(
            spec, fit_seeded(spec, params, Xf_tr, y_tr, c_tr, w_tr, s), Xf_ev, y_ev, c_ev))
        # The shuffle is redrawn per seed from a stream keyed on that seed, so the five
        # deltas are i.i.d. under H0 rather than all sharing one permutation draw.
        sh_tr = shuffled(Xf_tr, T_COLS, np.random.default_rng([int(s), 0]))
        sh_ev = shuffled(Xf_ev, T_COLS, np.random.default_rng([int(s), 1]))
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
            spec, params, shuffled(Xf_tr, T_COLS, np.random.default_rng([int(s), 0])),
            y_tr, c_tr, w_tr, s),
            shuffled(Xf_ev, T_COLS, np.random.default_rng([int(s), 1])), y_ev, c_ev)
        b = score_model(spec, fit_seeded(
            spec, params, shuffled(Xf_tr, T_COLS, np.random.default_rng([int(s), 2])),
            y_tr, c_tr, w_tr, s),
            shuffled(Xf_ev, T_COLS, np.random.default_rng([int(s), 3])), y_ev, c_ev)
        d_ctrl.append(delta(a, b, hib))
    ctrl_ev = safe_t_e_value(np.asarray(d_ctrl))
    log(f"  [{target}] control(shuffle vs shuffle) E={ctrl_ev['E']:.4g} "
        f"({time.time()-t0:.0f}s)")

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
            "note": ("both arms are shuffles of the same four columns, so H0 is true "
                     "by construction; a large E here would indict the harness."),
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
        "item": "08e",
        "purpose": ("re-read of family T's gate on the v12 / 08m substrate, because "
                    "08m made next_5_lap_cumulative_jump_s a different quantity and "
                    "every 08e number was measured on the old one (decision D3)"),
        "ran_at": pd.Timestamp.utcnow().isoformat(),
        "contract_version": S.MODEL_VERSION_DEFAULT,
        "published_artefact_version": pub_version,
        "n_contract_features": len(S.FEATURE_COLUMNS),
        "family_T_columns": list(T_COLS),
        "baseline_design": ("full contract minus family T. The 2026-09-09 run's "
                            "baseline also excluded cliff_candidate_flag; 08j has "
                            "since pruned that column from the contract, so minus-T "
                            "is the direct analogue and no third arm is needed."),
        "not_comparable_to": ("the 2026-09-09 08e gate table -- it scores a different "
                              "target. Read side by side, never subtracted."),
        "seeds": list(SEEDS),
        "e_value_construction": {"name": "B (paired safe-t)", "n": len(SEEDS),
                                 "g": E_VALUE_G,
                                 "null": "information contrast: real vs its own shuffle"},
        "e_value_validity_check": e_value_validity_check(),
        "families": {},
    }

    log(f"contract {S.MODEL_VERSION_DEFAULT}, {len(S.FEATURE_COLUMNS)} features; "
        f"published artefact version {pub_version}")
    log(f"family T = {', '.join(T_COLS)}")
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
        fam = S.TARGET_BY_NAME[target].family
        if fam not in bundles:
            bundles[fam] = E._evaluation_split(F.load_features(target=target))
        split = bundles[fam]
        log(f"\n=== {target} ({fam}) ===")
        out["families"][target] = run_family(
            target, split, published["models"][target]["headline"], log)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2, default=float))

    Path(args.out).with_suffix(".log").write_text("\n".join(lines) + "\n")
    log(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
