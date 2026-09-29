"""Supplementary (NOT pre-registered) check for the W9 re-run of 08o.

08o's arm A is w = ones. XGBoost's reg:quantileerror fits a different model for
sample_weight=ones than for sample_weight=None (weighted vs unweighted leaf quantile), and
production (v13+) fits the trio with None. So this fits the TRUE production path (no weights)
over 08o's own 10 seeds, then pairs each seed with 08o's arm-B fit at the same seed
(08o JSON: refit_noise_floor_B.headline_by_seed) to answer "does the shipped unweighted fit
beat corrected IPW?" with the same floor rule (larger of the two arms' 2*sqrt(2)*sd) and the
same Construction-B e-value (n=10, g=1). Construction B depends on t^2 only, so E is the same
either way round: read the direction from the sign of mean_delta_B_vs_production (positive =
IPW has the lower pinball).

Inputs: the 08f-1 AFTER snapshot (same gate_after.duckdb, same _evaluation_split as 08o) and
08o's finished JSON. Output: supp_production_vs_ipw.json next to the 08o JSON.

Usage (as run 2026-09-29; SNAP_ROOT holds snap/after.pkl from gate_08f1 --stage export-after):
    PYTHONPATH=. python3 supp_prod_vs_ipw.py SNAP_ROOT OUT08O/08o_gate_arms.json fit
    PYTHONPATH=. python3 supp_prod_vs_ipw.py SNAP_ROOT OUT08O/08o_gate_arms.json pair
Check: seed 0 reproduces 08o's gate1_headline_production on all three heads (it does).
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from ml.src import evaluate as E
from ml.src import schema as S
from ml.src import train as T

SP = Path(sys.argv[1])
OUT_08O = Path(sys.argv[2])
SEEDS = tuple(S.RANDOM_STATE + i for i in range(10))
G = 1.0
TARGETS = ("degradation_regressor_p10", "degradation_regressor_p50", "degradation_regressor_p90")


def safe_t(d):
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    d_bar, s_d = float(d.mean()), float(d.std(ddof=1))
    t = float(np.sqrt(n) * d_bar / s_d) if s_d else (0.0 if d_bar == 0 else float(np.copysign(np.inf, d_bar)))
    cap = (1.0 + n * G) ** ((n - 1) / 2.0)
    if np.isfinite(t):
        e = (1.0 + n * G) ** -0.5 * ((1 + t * t / (n - 1)) / (1 + t * t / ((1 + n * G) * (n - 1)))) ** (n / 2.0)
    else:
        e = cap
    return {"n": n, "d_bar": d_bar, "s_d": s_d, "t": t, "E": float(e), "max_attainable_E": float(cap)}


def fit_production():
    """Phase 1: production-path (no sample_weight) headline for each of 08o's 10 seeds."""
    snap = pickle.load(open(SP / "snap" / "after.pkl", "rb"))["targets"]
    prod_all = {}
    for t in TARGETS:
        spec = S.TARGET_BY_NAME[t]
        params = E._params_for(t, S.MODEL_VERSION_DEFAULT)
        a = snap[t]
        X_tr, y_tr, X_ev, y_ev = a["X_tr"], a["y_tr"], a["X_ev"], a["y_ev"]
        t0 = time.time()
        prod = []
        for s in SEEDS:
            m = T._make_model(spec, {**params, "seed": int(s)})
            m.set_params(random_state=int(s))
            m.fit(X_tr, y_tr)  # no sample_weight: the production path
            prod.append(float(E._score(spec, y_ev, E._predict_index(spec, m, X_ev), cens=None, scale=None)))
        prod_all[t] = prod
        print(f"[{t}] production by seed: {[round(v, 8) for v in prod]} ({time.time()-t0:.0f}s)", flush=True)
        (SP / "supp_production_by_seed.json").write_text(json.dumps(prod_all, indent=2))
    return prod_all


def pair():
    """Phase 2: pair with 08o's per-seed arm-B (and arm-A) headlines."""
    prod_all = json.loads((SP / "supp_production_by_seed.json").read_text())
    o = json.loads(OUT_08O.read_text())
    out = {"note": __doc__, "seeds": list(SEEDS), "targets": {}}
    for t in TARGETS:
        r8 = o["targets"][t]
        b_seed = r8["refit_noise_floor_B"]["headline_by_seed"]
        a_seed = r8["refit_noise_floor_A"]["headline_by_seed"]
        prod = np.asarray(prod_all[t])
        floor_p = 2 * np.sqrt(2) * float(prod.std(ddof=1))
        floor_b = r8["refit_noise_floor_B"]["delta_noise_2sd"]
        F = max(floor_p, floor_b)
        d = prod - np.asarray(b_seed)  # lower pinball is better: positive = IPW (B) beats production
        canon = float(r8["gate1_headline_production"]) - float(r8["arm_B_ipw"]["headline"])
        res = {
            "production_by_seed": prod.tolist(), "ipw_B_by_seed": b_seed, "ones_A_by_seed": a_seed,
            "production_mean": float(prod.mean()), "ipw_B_mean": float(np.mean(b_seed)),
            "ones_A_mean": float(np.mean(a_seed)),
            "floor_production_2sqrt2sd": floor_p, "floor_B_2sqrt2sd": floor_b, "floor_quoted": F,
            "canonical_seed_delta_B_vs_production": canon,
            "canonical_seed_floor_ratio": canon / F,
            "paired_B_vs_production_deltas": d.tolist(),
            "mean_delta_B_vs_production": float(d.mean()),
            "mean_delta_floor_ratio": float(d.mean() / F),
            "clears_floor": bool(abs(d.mean()) > F),
            "seeds_B_better": int((d > 0).sum()),
            "e_value_B_beats_production": safe_t(d),
            "e_value_production_beats_B": safe_t(-d),
            "mean_gap_ones_minus_none": float(np.mean(a_seed) - prod.mean()),
        }
        out["targets"][t] = res
        print(f"[{t}] prod mean={prod.mean():.8f} B mean={np.mean(b_seed):.8f} A(ones) mean={np.mean(a_seed):.8f} | "
              f"canonical B-vs-prod={canon:+.6f} ({canon/F:+.2f}x) | paired mean={d.mean():+.6f} floor={F:.6f} "
              f"({d.mean()/F:+.2f}x) B better {int((d>0).sum())}/10 | E(B>prod)={res['e_value_B_beats_production']['E']:.4g} "
              f"E(prod>B)={res['e_value_production_beats_B']['E']:.4g}", flush=True)
    (OUT_08O.parent / "supp_production_vs_ipw.json").write_text(json.dumps(out, indent=2))
    print("wrote", OUT_08O.parent / "supp_production_vs_ipw.json")


if __name__ == "__main__":
    fit_production() if sys.argv[3] == "fit" else pair()
