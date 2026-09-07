"""Intervals on the `beats_baseline` claim — Phase 6, Corrections §15.

`ml_execution_plan.md` §15: `fct_cliff_prediction_features` holds 137,447 rows over
**7,094 stints**. Laps inside one stint share a compound, a car, a circuit, a fuel load
and a driver, so they are not independent draws, and every interval in this series is
computed at lap grain. Standard errors are understated by roughly
`sqrt(137,447 / 7,094) ~ 4.4x`.

Phase 2's checkpoint got this right once -- it reported the tuned classifier beating the
floor by +0.75% at paired t=1.386, p=0.24, and declined to call it a win. Nothing else in
the series did. This module makes that the default: two intervals per claim, computed the
two ways that respect the clustering.

* **`paired_t_across_folds`** -- the season-grouped folds are the coarsest honest cluster
  (a whole season moves together), so the paired t over `n_splits` fold deltas needs no
  clustering correction at all. n=5 and 4 degrees of freedom make it a wide, conservative
  interval, which is the correct posture for a claim that has never carried one.

* **`cluster_bootstrap`** -- resample whole *stints* with replacement on the evaluation
  fold and re-score. Reported alongside a lap-grain bootstrap of the same quantity, so
  the width ratio §15 predicts is visible rather than asserted.

Every function here takes a scoring callable rather than a model, so the same interval
arithmetic serves pinball, macro-F1 and censored AFT NLL without knowing which it has.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from scipy import stats

BOOTSTRAP_RESAMPLES = 400   # 400 x (2 rescores) x 5 targets: seconds, not minutes
CI_LEVEL = 0.95


def signed_delta(model: float, baseline: float, higher_is_better: bool) -> float:
    """Model-minus-baseline, oriented so positive always means the model won."""
    return (model - baseline) if higher_is_better else (baseline - model)


def paired_t(deltas: list[float] | np.ndarray, ci_level: float = CI_LEVEL) -> dict:
    """Paired t on per-fold win margins against 0. Positive delta == model ahead.

    `significant` is the whole point of the module: a claim whose interval spans 0 is
    recorded, kept, and marked -- never deleted. Phase 6's checklist is explicit that a
    claim failing its own interval is the most useful line in the card.
    """
    d = np.asarray(deltas, dtype=np.float64)
    d = d[np.isfinite(d)]
    n = int(d.size)
    out: dict = {"n_folds": n, "fold_deltas": [float(x) for x in d],
                 "folds_won": int((d > 0).sum())}
    if n < 2:
        return {**out, "mean_delta": float(d[0]) if n else None,
                "t": None, "p_value": None, "ci_low": None, "ci_high": None,
                "significant": None,
                "note": "fewer than 2 folds - no interval is computable"}
    mean = float(d.mean())
    se = float(d.std(ddof=1) / np.sqrt(n))
    if se == 0:
        return {**out, "mean_delta": mean, "t": None, "p_value": None,
                "ci_low": mean, "ci_high": mean, "significant": bool(mean > 0),
                "note": "zero variance across folds - t is undefined"}
    t = mean / se
    p = float(2 * stats.t.sf(abs(t), df=n - 1))
    half = float(stats.t.ppf(0.5 + ci_level / 2, df=n - 1) * se)
    return {**out, "mean_delta": mean, "t": float(t), "p_value": p,
            "ci_low": mean - half, "ci_high": mean + half,
            "ci_level": ci_level,
            "significant": bool(mean - half > 0)}


def cluster_bootstrap(score: Callable[[np.ndarray], float],
                      clusters: np.ndarray,
                      n_rows: int,
                      *,
                      resamples: int = BOOTSTRAP_RESAMPLES,
                      ci_level: float = CI_LEVEL,
                      seed: int = 0) -> dict:
    """Percentile CI on `score(row_index)` under resampling of whole clusters.

    `clusters` is one label per row (stint_id for the clustered version, the row's own
    index for the lap-grain comparison). Clusters are drawn with replacement to the same
    cluster count; the row index they expand to is handed to `score`.
    """
    labels, inverse = np.unique(np.asarray(clusters), return_inverse=True)
    rows_by_cluster = [np.where(inverse == i)[0] for i in range(len(labels))]
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(resamples):
        pick = rng.integers(0, len(labels), size=len(labels))
        idx = np.concatenate([rows_by_cluster[i] for i in pick])
        try:
            draws.append(float(score(idx)))
        except Exception:
            continue
    if len(draws) < 2:
        return {"n_clusters": int(len(labels)), "n_rows": int(n_rows),
                "resamples": len(draws), "ci_low": None, "ci_high": None,
                "note": "scoring failed on the resamples - no interval"}
    a = np.asarray(draws, dtype=np.float64)
    lo, hi = np.percentile(a, [(1 - ci_level) / 2 * 100, (0.5 + ci_level / 2) * 100])
    return {"n_clusters": int(len(labels)), "n_rows": int(n_rows),
            "resamples": int(a.size), "mean": float(a.mean()),
            "ci_low": float(lo), "ci_high": float(hi), "ci_level": ci_level,
            "width": float(hi - lo), "significant": bool(lo > 0)}


def width_ratio(clustered: dict, lap_grain: dict) -> float | None:
    """How much wider the honest interval is. §15 predicts ~sqrt(rows / stints) ~ 4.4x.

    Reported rather than assumed: the prediction is exact only for a mean under equal
    cluster sizes and constant intra-cluster correlation, and the headline metrics are
    neither means nor equally clustered.
    """
    a, b = clustered.get("width"), lap_grain.get("width")
    if not a or not b:
        return None
    return float(a / b)
