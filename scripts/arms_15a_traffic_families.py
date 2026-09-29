"""WI-15a -- the traffic families' gate (steps 1-4 and 7), on the settled v15 substrate.

The arms, columns, baselines, decision rule and e-value construction are pre-registered in
`_roadmap/_fixes/wi/WI-15-traffic-thermal-feature-semantics.md` ("Pre-registration: WI-15a's gate
arms", written before any arm ran). This script runs exactly that and nothing else.

    family P (F43)  the 9 `proximity` columns   (fed only by int_lap_proximity)
    family D (F48)  the 4 `dirty_air` columns   (fed only by int_lap_air_state)

    baseline A_X = full contract minus family X; arm = full contract.  10 hypotheses.

Shares its fit / score / shuffle / safe-t machinery with `arms_08e_thermal_family.py`, so the two
gates are the same instrument. Differences from 08e, all deliberate:
  * two column families, not one;
  * e-value at n = 10, g = 1 (09c, for arms declared after 2026-09-19); the ten seeds nest the
    floor's five;
  * refits are shared where the registration makes them identical: the ten full-contract fits are
    fitted once per target and serve both families and both the floor and the paired contrast; the
    canonical (seed RANDOM_STATE) baseline, floor-base fit and shuffle are the seed-0 members of
    their five-/ten-seed sets;
  * the shuffle-vs-shuffle negative control runs on the first five seeds only (a harness check, not
    a declared hypothesis).

Reads the warehouse read-only. Writes only ml/artefacts/15a_traffic_families_arms.{json,log}.

Usage:  PYTHONPATH=. ./.venv/bin/python scripts/arms_15a_traffic_families.py [--targets ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arms_08e_thermal_family as A  # noqa: E402  (shared instrument)

from ml.src import evaluate as E  # noqa: E402
from ml.src import features as F  # noqa: E402
from ml.src import schema as S  # noqa: E402

FAMILIES_COLS: dict[str, tuple[str, ...]] = {
    "P_proximity": tuple(S.FEATURE_GROUPS["proximity"]),
    "D_dirty_air": tuple(S.FEATURE_GROUPS["dirty_air"]),
}
assert len(FAMILIES_COLS["P_proximity"]) == 9 and len(FAMILIES_COLS["D_dirty_air"]) == 4

FLOOR_SEEDS = tuple(S.RANDOM_STATE + i for i in range(5))
E_SEEDS = tuple(S.RANDOM_STATE + i for i in range(10))
CTRL_SEEDS = FLOOR_SEEDS
assert E_SEEDS[:5] == FLOOR_SEEDS
G = 1.0
M_DECLARED = 145  # 135 (09c 103 + 02d 20 + 02h 12) + this item's 10; count-forward, not re-audited
TARGETS = ("degradation_regressor_p10", "degradation_regressor_p50", "degradation_regressor_p90",
           "cliff_classifier", "stint_life_regressor")
OUT = Path("ml/artefacts/15a_traffic_families_arms.json")


def safe_t(d) -> dict:
    return A.safe_t_e_value(np.asarray(d), g=G)


def validity_check(n_draws: int = 100_000) -> dict:
    rng = np.random.default_rng(S.RANDOM_STATE)
    n, out = len(E_SEEDS), {}
    for sigma in (0.001, 0.01, 0.1, 1.0):
        d = rng.normal(0.0, sigma, size=(n_draws, n))
        t = np.sqrt(n) * d.mean(axis=1) / d.std(axis=1, ddof=1)
        e = (1 + n * G) ** -0.5 * ((1 + t ** 2 / (n - 1)) / (1 + t ** 2 / ((1 + n * G) * (n - 1)))) ** (n / 2)
        se = float(e.std(ddof=1) / np.sqrt(n_draws))
        out[f"sigma={sigma}"] = {"mean_E": float(e.mean()), "mc_se": se,
                                 "ok_within_3se": bool(abs(e.mean() - 1.0) <= 3 * se),
                                 "p_E_gt_20": float((e > 20).mean())}
    return out


def run_target(target: str, split, published: float, log) -> dict:
    spec = S.TARGET_BY_NAME[target]
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    hib = E._higher_is_better(spec)
    Xtr, Xev = split.X_tr, split.X_ev
    ytr, yev, ctr, cev, wtr = split.y_tr, split.y_ev, split.cens_tr, split.cens_ev, split.w_tr

    def fit(X, seed):
        return A.fit_seeded(spec, params, X, ytr, ctr, wtr, seed)

    def score(m, X):
        return A.score_model(spec, m, X, yev, cev)

    res: dict = {"target": target, "metric": E._headline_metric_name(spec), "higher_is_better": hib,
                 "n_train": int(len(Xtr)), "n_eval": int(len(Xev)),
                 "n_contract_features": int(Xtr.shape[1]), "eval_season": split.eval_season,
                 "split_mode": split.mode, "floor_seeds": list(FLOOR_SEEDS), "e_seeds": list(E_SEEDS)}

    # Step 1 -- instrument check on the production-path fit (E._fit), exactly as 08e does.
    t0 = time.time()
    headline = A.score_model(spec, E._fit(spec, params, Xtr, ytr, cens=ctr, w=wtr), Xev, yev, cev)
    res["full_contract_headline"] = headline
    res["published_v15_headline"] = published
    res["instrument_check_6dp"] = bool(abs(headline - published) < 5e-7)
    log(f"  [{target}] full={headline:.10f} published_v15={published:.10f} "
        f"instrument_check={res['instrument_check_6dp']} ({time.time()-t0:.0f}s)")
    if not res["instrument_check_6dp"]:
        res["aborted"] = "instrument check failed; every delta would be meaningless"
        return res

    # The ten full-contract fits, once, serving both families (floor uses the first five).
    t0 = time.time()
    real = np.asarray([score(fit(Xtr, s), Xev) for s in E_SEEDS])
    log(f"  [{target}] 10 full-contract seeds sd(5)={real[:5].std(ddof=1):.8f} ({time.time()-t0:.0f}s)")
    res["real_by_seed"] = real.tolist()
    # Same definition as attribution.refit_noise_floor (2*sqrt(2)*sd over the five floor seeds),
    # computed from the shared fits instead of refitting them.
    full_floor = float(2 * np.sqrt(2) * real[:5].std(ddof=1))

    res["families"] = {}
    for fam, cols in FAMILIES_COLS.items():
        missing = [c for c in cols if c not in Xtr.columns]
        if missing:
            raise RuntimeError(f"{fam}: columns absent from the contract: {missing}")
        Xa_tr, Xa_ev = Xtr.drop(columns=list(cols)), Xev.drop(columns=list(cols))
        fr: dict = {"columns": list(cols), "n_baseline_features": int(Xa_tr.shape[1])}

        # Step 2 + 3 -- baseline at each floor seed; seed 0 is the canonical baseline.
        t0 = time.time()
        base = np.asarray([score(fit(Xa_tr, s), Xa_ev) for s in FLOOR_SEEDS])
        baseline = float(base[0])
        base_floor = float(2 * np.sqrt(2) * base.std(ddof=1))
        F2 = max(base_floor, full_floor)
        d_real = A.delta(float(real[0]), baseline, hib)
        fr.update({"baseline_headline": baseline, "baseline_by_floor_seed": base.tolist(),
                   "floor_baseline": base_floor, "floor_full": full_floor, "floor_2sqrt2sd": F2,
                   "floor_quoted_from": "full_contract" if full_floor >= base_floor else "baseline"})
        log(f"  [{target}/{fam}] baseline={baseline:.10f} add-ablation delta={d_real:+.8f} "
            f"floor={F2:.8f} ({d_real/F2 if F2 else float('nan'):+.2f}x) ({time.time()-t0:.0f}s)")

        # Step 4 -- paired shuffled fits at all ten seeds; seed 0 is the canonical permutation null.
        t0 = time.time()
        shuf = []
        for s in E_SEEDS:
            sh_tr = A.shuffled(Xtr, cols, np.random.default_rng([int(s), 0]))
            sh_ev = A.shuffled(Xev, cols, np.random.default_rng([int(s), 1]))
            shuf.append(score(fit(sh_tr, s), sh_ev))
        shuf = np.asarray(shuf)
        capacity = A.delta(float(shuf[0]), baseline, hib)
        information = A.delta(float(real[0]), float(shuf[0]), hib)
        d_pair = np.asarray([A.delta(r, sh, hib) for r, sh in zip(real, shuf)])
        ev = safe_t(d_pair)
        fr.update({
            "add_ablation": {"delta": d_real, "floor_ratio": d_real / F2 if F2 else None,
                             "clears_floor": bool(d_real > F2),
                             "non_harm_ok": bool(d_real >= -F2)},
            "permutation_null": {"headline_shuffled": float(shuf[0]), "capacity_delta": capacity,
                                 "capacity_floor_ratio": capacity / F2 if F2 else None,
                                 "information_delta": information,
                                 "information_floor_ratio": information / F2 if F2 else None,
                                 "information_clears_floor": bool(information > F2)},
            "paired_seeds": {"real_by_seed": real.tolist(), "shuffled_by_seed": shuf.tolist(),
                             "information_deltas": d_pair.tolist(), "e_value": ev},
        })
        log(f"  [{target}/{fam}] capacity={capacity:+.8f} ({capacity/F2:+.2f}x) "
            f"information={information:+.8f} ({information/F2:+.2f}x)  E(n=10)={ev['E']:.4g} "
            f"d_bar={ev['d_bar']:+.8f} improve={ev['direction_is_improvement']} ({time.time()-t0:.0f}s)")

        # Negative control -- shuffle vs shuffle, five nested seeds (harness check).
        t0 = time.time()
        d_ctrl = []
        for s in CTRL_SEEDS:
            a = score(fit(A.shuffled(Xtr, cols, np.random.default_rng([int(s), 0])), s),
                      A.shuffled(Xev, cols, np.random.default_rng([int(s), 1])))
            b = score(fit(A.shuffled(Xtr, cols, np.random.default_rng([int(s), 2])), s),
                      A.shuffled(Xev, cols, np.random.default_rng([int(s), 3])))
            d_ctrl.append(A.delta(a, b, hib))
        ctrl = A.safe_t_e_value(np.asarray(d_ctrl), g=G)
        fr["negative_control"] = {"paired_deltas": d_ctrl, "e_value": ctrl, "harness_ok": bool(ctrl["E"] < 20)}
        log(f"  [{target}/{fam}] control E(n=5)={ctrl['E']:.4g} ok={ctrl['E'] < 20} ({time.time()-t0:.0f}s)")
        res["families"][fam] = fr
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", nargs="*", default=list(TARGETS))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    lines: list[str] = []

    def log(m: str) -> None:
        print(m, flush=True)
        lines.append(m)

    published = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())
    out = {"item": "WI-15a", "pre_registration": "wi/WI-15-traffic-thermal-feature-semantics.md",
           "ran_at": pd.Timestamp.utcnow().isoformat(), "published_artefact_version": published.get("version"),
           "quantile_sample_weight": S.QUANTILE_SAMPLE_WEIGHT,
           "families": {k: list(v) for k, v in FAMILIES_COLS.items()},
           "e_value_construction": {"name": "B (paired safe-t)", "n": len(E_SEEDS), "g": G,
                                    "max_attainable_E": (1 + len(E_SEEDS) * G) ** ((len(E_SEEDS) - 1) / 2),
                                    "m_declared": M_DECLARED, "lone_rejection_bar": 20 * (M_DECLARED + 1)},
           "e_value_validity_check": validity_check(), "targets": {}}
    log(f"WI-15a gate; published artefact {published.get('version')}; weights={S.QUANTILE_SAMPLE_WEIGHT}")
    for k, v in out["e_value_validity_check"].items():
        log(f"  validity {k}: mean_E={v['mean_E']:.4f} +/- {2*v['mc_se']:.4f} ok_3se={v['ok_within_3se']}")
    bundles: dict = {}
    for t in args.targets:
        fam = S.TARGET_BY_NAME[t].family
        if fam not in bundles:
            bundles[fam] = E._evaluation_split(F.load_features(target=t))
        log(f"\n=== {t} ===")
        out["targets"][t] = run_target(t, bundles[fam], published["models"][t]["headline"], log)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2, default=float))
        Path(args.out).with_suffix(".log").write_text("\n".join(lines) + "\n")
    log(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
