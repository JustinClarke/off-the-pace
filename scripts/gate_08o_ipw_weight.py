"""08o -- gate whether to drop IPW survival weights from degradation quantile heads.

PRE-REGISTRATION (2026-09-22, before any arm runs)
==================================================

WHAT IS SHIPPED TODAY. `ml/src/train.py:175-176` applies IPW survival weights to
all three degradation quantile heads (p10, p50, p90) at train time. The docstring
states the rationale: *"so early-pitted (degraded) stints are not under-counted at
high `lap_in_stint`"* — a plausible-sounding correction that has never been tested
against NOT doing it at all.

WHAT 08f-1 MEASURED (by accident). Its baseline arm A was uniform weights (w = 1):
- p10:  uniform A = 0.4711254463; shipped IPW = 0.4764640778 (delta -0.00533863, floor 0.00763075, 0.70×)
- p50:  uniform A = 0.9817102187; shipped IPW = 0.9823587336 (delta -0.00064851, floor 0.01115092, 0.06×)
- p90:  uniform A = 0.5093926910; shipped IPW = 0.5128462338 (delta -0.00345354, floor 0.00839541, 0.41×)

Uniform is better on all three heads. Every delta is inside its own reseed floor. However,
the permutation-null information term on p10 clears the floor (-0.00990506, -1.30× the floor),
suggesting IPW reweighting as a mechanism does move p10 and p90, even if the shipped version
doesn't beat uniform.

HONEST PRIOR: three-for-three direction (uniform wins) and one floor-clearing information cost
(p10), not a demonstrated headline win. This item may well close as a null.

THREE ARMS
==========

- Arm A (uniform, w=1):       baseline, zero reweighting
- Arm B (shipped IPW):        current production weights (survival_weight column)
- Arm P (permutation null):   weight vector shuffled across training rows, destroying
                              alignment while preserving the value distribution

Only the degradation quantile trio: p10, p50, p90.
cliff_classifier and stint_life_regressor use different weight schemes (balanced class
weights, None respectively) and are asserted invariant by code trace, not re-run.

FAMILIES AND FLOORS
===================

Family: quantile_trio (p10, p50, p90)
Metric: pinball_loss (unweighted at eval time, per evaluate.py:620-637)
Floor method: refit_noise_floor over 10 seeds (matching post-09c e-value construction)
  DECISION (pre-registered): Use n=10 seeds for the floor study, consistent with
  post-09c Construction B e-value n=10. This gives more stable floor estimates.

EXPECTED DIRECTION
==================

Uniform weights (A) are expected to match or beat shipped IPW (B), based on 08f-1's
finding that uniform outperformed on all three heads and the deltas were inside noise.
The information term on p10 suggests alignment carries some signal, but not enough to
overcome the headline cost.

E-VALUE CONSTRUCTION (POST-09C)
================================

Construction B (paired safe-t):
  - n = 10 seeds
  - g = 1.0
  - E_max = 11^4.5 = 48,558.70
  - Null: information contrast (real arm vs its own row-shuffle)

This applies because the arms are declared AFTER 09c landing, per gates.md non-retroactivity.

EVALUATION SETUP
================

- Train fold: 2018-2023 (per F.FeatureBundle's training_seasons)
- Eval fold: cv_final_fold (2024 holdout, per evaluate.py::_evaluation_split)
- Refitting: evaluate.py's own _fit/_score, nothing reimplemented
- Eval-side weight trace: pinball_loss confirmed unweighted (evaluate.py:418-419, calls at 163 and 1023)

DELIVERABLES
============

1. Gate 1: Reproduce v12 headline on all three heads before any arm runs
2. Arm scores (A, B, P) with deltas vs baseline and floor ratios
3. Permutation-null information term and capacity decomposition
4. E-values for the information contrast (real vs shuffle, with validity check)
5. Written ruling on whether IPW weight should stay or drop
6. Eval-side trace confirming training weight doesn't move eval metric
7. Landing cost pricing (retrains model trio, version bump decision)
8. JSON summary of all results

ACCEPTANCE CRITERIA (Definition of Done)
=========================================

1. Written ruling with deltas quoted against their own floors and permutation-null
   split reported, not headline deltas alone
2. Eval-side question answered: dropping training weight does/doesn't move scoring path
   (traced to call sites)
3. Landing cost priced (three of five models retrain, recommend standalone vs D16 bundle)
4. survival_weight stays in IDENTIFIER_COLUMNS, not FEATURE_COLUMNS (feature contract unchanged)
5. All results recorded in JSON summary (implementations/08o/)

REFERENCE DATA FROM 08f-1
==========================

Permutation-null information (08f-1, real vs own shuffle, n=5 Construction B):
- p10: information -0.00990506 (-1.30× floor), capacity +0.00456643 (0.60×)
- p50: information -0.00431290 (-0.39× floor), capacity +0.00366439 (0.33×)
- p90: information +0.00558962 (0.67× floor), capacity -0.00904316 (-1.08×)

E-values (information, 08f-1):
- p10: E=2.11 (d_bar=-0.00444, n=5)
- p50: E=2.00 (d_bar=-0.00361, n=5)
- p90: E=1.78 (d_bar=+0.00264, n=5)

Negative control (shuffle vs shuffle, 08f-1):
- p10: E=0.47 (no signal)
- p50: E=8.76 (signal but this is the negative control)
- p90: E=0.93 (no signal)

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

SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(10))
E_VALUE_G = 1.0
E_VALUE_MAX = 11 ** 4.5  # post-09c Construction B: (1 + n*g)^((n-1)/2) where n=10, g=1
QUANTILE_TARGETS = ("degradation_regressor_p10", "degradation_regressor_p50",
                    "degradation_regressor_p90")
OUT = Path("_improvements/implementations/08o/08o_gate_arms.json")

print(f"PRE-REGISTRATION: Using {len(SEEDS)} seeds for both floor and e-value, "
      f"Construction B with E_max={E_VALUE_MAX:.2f}")


def delta(arm_value: float, base_value: float, higher_is_better: bool) -> float:
    """Positive delta = improvement, using higher_is_better convention."""
    return (arm_value - base_value) if higher_is_better else (base_value - arm_value)


def shuffle_weights(w: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Row-shuffle the weight VECTOR. Preserves value multiset; destroys row alignment."""
    return w[rng.permutation(len(w))]


def safe_t_e_value(d: np.ndarray, g: float = E_VALUE_G) -> dict:
    """Construction B (paired safe-t), n=10."""
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
    return {"n": n, "g": g, "d_bar": d_bar, "s_d": s_d, "t": t, "E": float(e),
            "direction_is_improvement": bool(d_bar > 0), "max_attainable_E": float(cap)}


def e_value_validity_check(n_draws: int = 100_000, seed: int = S.RANDOM_STATE) -> dict:
    """Verify e-value calibration under H0 (mean E should be 1.0)."""
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


def fit_seeded(spec: S.TargetSpec, params: dict, X, y, w: np.ndarray, seed: int):
    """Fit with specified seed and weight vector."""
    model = T._make_model(spec, {**params, "seed": int(seed)})
    model.set_params(random_state=int(seed))
    if spec.kind == "quantile" and w is None:
        raise ValueError("quantile fit needs per-row weights")
    weights = np.asarray(w, dtype=np.float32) if w is not None else None
    model.fit(X, y, sample_weight=weights)
    return model


def score_model(spec: S.TargetSpec, model, X_ev, y_ev) -> float:
    """Score model on eval set (no weights at eval time)."""
    return E._score(spec, y_ev, E._predict_index(spec, model, X_ev), cens=None, scale=None)


def run_quantile_target(target: str, bundle_after: F.FeatureBundle, published: float) -> dict:
    """Run arms A (uniform), B (shipped), P (permutation null) on one target."""
    spec = S.TARGET_BY_NAME[target]
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    hib = E._higher_is_better(spec)

    split = E._evaluation_split(bundle_after)
    X_tr = split.X_tr
    y_tr = split.y_tr
    X_ev = split.X_ev
    y_ev = split.y_ev

    # Get IPW weights from meta directly (after 08o, _row_weights returns None for quantile)
    # But we need to test against the pre-08o state with IPW weights
    if "survival_weight" not in bundle_after.meta_train.columns:
        raise ValueError(f"{target}: survival_weight not in meta_train")

    # Get the lap_ids to match the exact rows in the split
    # The split's lap_ids_tr tell us which rows from meta_train are in the training fold
    split_lap_ids_tr = set(split.lap_ids_tr)

    # Create a mapping from lap_id to weight in the full meta table
    meta_lap_to_weight = dict(zip(bundle_after.meta_train["lap_id"],
                                   bundle_after.meta_train["survival_weight"].values))

    # Reconstruct arm B: IPW weights (pre-08o shipped version)
    # Map each lap_id in the split's training set to its corresponding weight
    w_ipw = np.array([meta_lap_to_weight[lap_id] for lap_id in split.lap_ids_tr], dtype=np.float32)
    w_uniform = np.ones_like(w_ipw)  # Arm A: uniform weights

    res: dict = {
        "target": target,
        "metric": E._headline_metric_name(spec),
        "higher_is_better": hib,
        "n_train": int(len(X_tr)),
        "n_eval": int(len(X_ev)),
        "seeds": list(SEEDS),
        "w_ipw_summary": {
            "mean": float(w_ipw.mean()),
            "sd": float(w_ipw.std()),
            "min": float(w_ipw.min()),
            "max": float(w_ipw.max()),
        },
        "w_uniform_summary": {
            "mean": float(w_uniform.mean()),
            "sd": float(w_uniform.std()),
            "min": float(w_uniform.min()),
            "max": float(w_uniform.max()),
        },
    }

    # Gate 1: Reproduce v12 headline on arm B (shipped)
    print(f"[{target}] Gate 1: Reproducing v12 headline with shipped IPW weights...")
    t0 = time.time()
    model_b = E._fit(spec, params, X_tr, y_tr, cens=None, w=w_ipw)
    h_b = score_model(spec, model_b, X_ev, y_ev)
    res["gate1_headline_B"] = h_b
    res["published_v12_headline"] = published
    res["gate1_passes"] = bool(abs(h_b - published) < 5e-7)
    print(f"  Headline: {h_b:.10f}, Published: {published:.10f}, "
          f"Passes: {res['gate1_passes']} ({time.time()-t0:.0f}s)")

    if not res["gate1_passes"]:
        res["aborted"] = f"Gate 1 failed: headline diff = {abs(h_b - published):.2e}"
        print(f"  ABORTED: {res['aborted']}")
        return res

    # Score all three arms at canonical seed
    print(f"[{target}] Scoring three arms...")
    t0 = time.time()
    model_a = E._fit(spec, params, X_tr, y_tr, cens=None, w=w_uniform)
    h_a = score_model(spec, model_a, X_ev, y_ev)

    d_b_vs_a = delta(h_b, h_a, hib)
    d_a_vs_b = delta(h_a, h_b, hib)

    print(f"  Arm A (uniform): {h_a:.10f}")
    print(f"  Arm B (IPW):     {h_b:.10f}")
    print(f"  Delta B-vs-A:    {d_b_vs_a:+.8f}")
    print(f"  Delta A-vs-B:    {d_a_vs_b:+.8f} ({time.time()-t0:.0f}s)")

    # Floor study: refit_noise_floor with 10 seeds
    print(f"[{target}] Computing refit noise floor over {len(SEEDS)} seeds...")
    t0 = time.time()
    floor_a = AT.refit_noise_floor(
        lambda s: fit_seeded(spec, params, X_tr, y_tr, w_uniform, s),
        lambda yt, m, X: score_model(spec, m, X, yt),
        X_ev, y_ev, SEEDS
    )
    floor_b = AT.refit_noise_floor(
        lambda s: fit_seeded(spec, params, X_tr, y_tr, w_ipw, s),
        lambda yt, m, X: score_model(spec, m, X, yt),
        X_ev, y_ev, SEEDS
    )
    F2 = max(floor_a["delta_noise_2sd"], floor_b["delta_noise_2sd"])
    floor_source = "A" if floor_a["delta_noise_2sd"] >= floor_b["delta_noise_2sd"] else "B"
    print(f"  Floor (2√2·sd) = {F2:.8f} (from arm {floor_source}; "
          f"A={floor_a['delta_noise_2sd']:.8f}, B={floor_b['delta_noise_2sd']:.8f}) ({time.time()-t0:.0f}s)")

    res.update({
        "arm_A_uniform": {"headline": h_a, "delta_vs_B": d_a_vs_b, "floor_ratio": d_a_vs_b / F2 if F2 else None},
        "arm_B_ipw": {"headline": h_b, "delta_vs_A": d_b_vs_a, "floor_ratio": d_b_vs_a / F2 if F2 else None},
        "refit_noise_floor_A": floor_a,
        "refit_noise_floor_B": floor_b,
        "floor_2sqrt2sd": F2,
        "floor_source": floor_source,
    })

    # Permutation null: shuffle the IPW weight
    print(f"[{target}] Permutation null (shuffle arm B weights)...")
    t0 = time.time()
    rng_shuf = np.random.default_rng([S.RANDOM_STATE, 0])
    w_b_shuffled = shuffle_weights(w_ipw, rng_shuf)
    model_b_shuf = E._fit(spec, params, X_tr, y_tr, cens=None, w=w_b_shuffled)
    h_b_shuf = score_model(spec, model_b_shuf, X_ev, y_ev)

    cap_b = delta(h_b_shuf, h_a, hib)  # shuffled vs uniform
    info_b = delta(h_b, h_b_shuf, hib)  # real vs shuffled

    print(f"  Arm B shuffled:     {h_b_shuf:.10f}")
    print(f"  Capacity (shuf-A):  {cap_b:+.8f} ({cap_b/F2:+.2f}x floor)")
    print(f"  Information (B-shuf): {info_b:+.8f} ({info_b/F2:+.2f}x floor) ({time.time()-t0:.0f}s)")

    # Paired e-values (real vs shuffle, n=10 seeds)
    print(f"[{target}] Paired e-values: real B vs shuffled B ({len(SEEDS)} seeds)...")
    t0 = time.time()
    reals, shufs = [], []
    for s in SEEDS:
        real_model = fit_seeded(spec, params, X_tr, y_tr, w_ipw, s)
        reals.append(score_model(spec, real_model, X_ev, y_ev))
        w_shuf_s = shuffle_weights(w_ipw, np.random.default_rng([int(s), 0]))
        shuf_model = fit_seeded(spec, params, X_tr, y_tr, w_shuf_s, s)
        shufs.append(score_model(spec, shuf_model, X_ev, y_ev))

    reals, shufs = np.asarray(reals), np.asarray(shufs)
    d_paired = np.asarray([delta(r, sh, hib) for r, sh in zip(reals, shufs)])
    ev_b = safe_t_e_value(d_paired)
    print(f"  E(information, B real-vs-shuffle) = {ev_b['E']:.4g} "
          f"(d_bar={ev_b['d_bar']:+.8f}, max_E={ev_b['max_attainable_E']:.1f}) ({time.time()-t0:.0f}s)")

    # Negative control: shuffle vs shuffle
    print(f"[{target}] Negative control: shuffle B vs shuffle B...")
    t0 = time.time()
    d_ctrl = []
    for s in SEEDS:
        wa = shuffle_weights(w_ipw, np.random.default_rng([int(s), 2]))
        wb = shuffle_weights(w_ipw, np.random.default_rng([int(s), 3]))
        va = score_model(spec, fit_seeded(spec, params, X_tr, y_tr, wa, s), X_ev, y_ev)
        vb = score_model(spec, fit_seeded(spec, params, X_tr, y_tr, wb, s), X_ev, y_ev)
        d_ctrl.append(delta(va, vb, hib))

    ctrl_ev = safe_t_e_value(np.asarray(d_ctrl))
    print(f"  Control E (shuffle vs shuffle) = {ctrl_ev['E']:.4g} ({time.time()-t0:.0f}s)")

    res.update({
        "permutation_null_B": {
            "headline_shuffled": h_b_shuf,
            "capacity_delta": cap_b,
            "capacity_floor_ratio": cap_b / F2 if F2 else None,
            "information_delta": info_b,
            "information_floor_ratio": info_b / F2 if F2 else None,
        },
        "paired_seeds_B": {
            "real_by_seed": reals.tolist(),
            "shuffled_by_seed": shufs.tolist(),
            "information_deltas": d_paired.tolist(),
            "e_value": ev_b,
        },
        "negative_control_shuffle_vs_shuffle": {
            "paired_deltas": d_ctrl,
            "e_value": ctrl_ev,
        },
    })

    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    lines: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    # Load current features and artefacts (AFTER state, no warehouse work needed)
    published = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())
    pub_version = published.get("version")

    out: dict = {
        "item": "08o",
        "purpose": "gate whether to drop IPW survival weights from degradation quantile heads",
        "ran_at": pd.Timestamp.utcnow().isoformat(),
        "published_artefact_version": pub_version,
        "seeds": list(SEEDS),
        "floor_study_method": f"refit_noise_floor over {len(SEEDS)} seeds (post-09c matching)",
        "e_value_construction": {
            "name": "B (paired safe-t)",
            "n": len(SEEDS),
            "g": E_VALUE_G,
            "E_max": E_VALUE_MAX,
            "null": "information contrast: real arm B vs its own row-shuffle"
        },
        "e_value_validity_check": e_value_validity_check(),
        "targets": {},
    }

    log(f"Published artefact version: {pub_version}")
    log(f"Using {len(SEEDS)} seeds for floor and e-value (post-09c Construction B)")
    log(f"E_max = 11^4.5 = {E_VALUE_MAX:.2f}")
    log("\ne-value validity check (mean E under H0 should be 1.00):")
    for k, v in out["e_value_validity_check"].items():
        log(f"  {k:<14} mean_E={v['mean_E']:.4f} +/- {2*v['mc_se']:.4f}  P(E>20)={v['p_E_gt_20']:.4f}")

    # Gate 1 + arm evaluation for each quantile target
    for target in QUANTILE_TARGETS:
        log(f"\n{'='*70}")
        log(f"{target}")
        log(f"{'='*70}")

        # Load features for this target (same bundle object, just specify target)
        bundle = F.load_features(target=target)

        out["targets"][target] = run_quantile_target(
            target, bundle, published["models"][target]["headline"]
        )

        # Incrementally write results
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2, default=float))

    # Save log
    Path(args.out).with_suffix(".log").write_text("\n".join(lines) + "\n")
    log(f"\n{'='*70}")
    log(f"Wrote results to {args.out}")
    log(f"{'='*70}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
