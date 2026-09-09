"""CRPS for the degradation quantile trio, and its calibration/resolution/uncertainty
decomposition — work item `09a` (`_improvements/work/09-scoring-instruments.md`).

The degradation family reports pinball loss at alpha in {0.10, 0.50, 0.90}: three
headlines, each a strictly proper score for its OWN quantile, with no rule for combining
"p50 clears but p90 does not" into one number.

**CRPS is the strictly proper score for the whole predictive distribution**, in the
target's own units:

    CRPS(F, y) = 2 * integral_0^1  pinball_alpha(y, q_alpha(F))  dalpha

(Laio & Tamea 2007 eq. 6; Gneiting & Raftery 2007 eq. 20/Table 1). Averaged quantile loss
over a grid of alpha converges to this as the grid refines. With only the trio it is a
3-point trapezoidal approximation of that integral -- exact in the degenerate case where
the predictive distribution collapses to a point forecast (all three predictions equal),
which is how "CRPS reduces to MAE" is checked in
`ml/tests/test_crps.py::test_crps_reduces_to_mae_for_a_point_forecast`; not exact
elsewhere. There is no substitute for more quantile levels -- this is arithmetic over
predictions the programme already makes, at the cost `09a` was scoped at, not a claim
that 3 points is enough.

The grid does not reach alpha=0 or alpha=1 (the trio never predicts the tails), so it is
flat-extended: q_0 := q_0.10, q_1 := q_0.90. That is a real approximation at the extremes,
not a tail estimate.

**Decomposition.** Murphy's (1973) calibration-resolution-uncertainty split of a proper
score (score = MCB - DSC + UNC), evaluated at each quantile level via equal-frequency
bins of the raw forecast -- *not* the full isotonic/PAV recalibration of the modern CORP
literature (Dimitriadis, Gneiting & Jordan 2021; the CRPS-specific treatment in Arnold,
Henzi & Ziegel 2023), which is the more exact, more expensive version of the same idea
and was scoped out of `09a`'s "hours" budget; logged as a deviation in the leaf doc.
`UNC` is the pinball loss of the unconditional (whole-eval-fold) empirical alpha-quantile
-- the coarsest possible "forecast" -- so it is a second, independent read on the
target's irreducible spread, from a different construction than `01b`'s difference-based
floor. **The two are not interchangeable** (`foundations/epistemics.md`): report them
side by side, never as a difference.

The `reconstructed_crps == crps` identity (mcb - dsc + unc, summed over `score`'s own
definition) is pure arithmetic and holds unconditionally. Two sign properties do NOT
hold unconditionally, and only one of them is asserted anywhere in this module or its
tests: **`dsc >= 0` always**, because the K-bin per-bin-optimal fit is a strict
relaxation of the 1-bin global-constant fit `unc` uses (the K-bin search space contains
"all bins equal" as a special case, so its optimum cannot score worse). **`mcb` carries
no such guarantee** -- that requires recalibration flexible enough to reproduce the raw,
row-varying forecast exactly (i.e. full isotonic regression, whose fitted sequence is
free to vary point-to-point rather than being pinned to one constant per bin), which
this binned stand-in is not. A negative `mcb` here is not a bug: it says the raw
forecast carries real within-bin information no single bin constant can capture -- a
model doing well, read through a decomposition too coarse to credit it. Do not add an
`mcb >= 0` assertion against this implementation; it would be asserting something false.

Every quantity here is computed in-sample on the eval fold, the same posture as the
headline pinball, cohort tables and baseline already reported by `evaluate.py`.
"""
from __future__ import annotations

import numpy as np

from ml.src import train as T

MIN_BINS = 5
MAX_BINS = 40
ROWS_PER_BIN_TARGET = 500   # same folding-small-cells instinct as evaluate.py's MIN_COHORT_N


def _pinball_elementwise(y: np.ndarray, q: np.ndarray, alpha: float) -> np.ndarray:
    d = y - q
    return np.maximum(alpha * d, (alpha - 1.0) * d)


def _trapz(values: list[float], grid: list[float]) -> float:
    v = np.asarray(values, dtype=np.float64)
    g = np.asarray(grid, dtype=np.float64)
    return float(np.sum((g[1:] - g[:-1]) * (v[1:] + v[:-1]) / 2.0))


def _n_bins(n_rows: int) -> int:
    return int(np.clip(n_rows // ROWS_PER_BIN_TARGET, MIN_BINS, MAX_BINS))


def _reliability_at_alpha(y: np.ndarray, q: np.ndarray, alpha: float) -> dict:
    """Murphy split of the mean pinball loss at one quantile level: score = mcb - dsc + unc.

    `recal` bins rows into equal-frequency buckets of the raw forecast `q` and replaces
    each bucket's forecast with the empirical alpha-quantile of `y` inside it -- the
    binned stand-in for a full isotonic recalibration curve (see module docstring).
    """
    n = len(y)
    k = min(_n_bins(n), max(n, 1))
    order = np.argsort(q, kind="mergesort")
    y_sorted = y[order]
    bin_id = np.minimum((np.arange(n) * k) // max(n, 1), k - 1)

    unc_pred = float(np.quantile(y, alpha))
    unc = float(np.mean(_pinball_elementwise(y, np.full(n, unc_pred), alpha)))
    raw = T.pinball_loss(y, q, alpha)

    recal_sorted = np.empty(n, dtype=np.float64)
    for b in range(k):
        m = bin_id == b
        recal_sorted[m] = np.quantile(y_sorted[m], alpha)
    recal = np.empty(n, dtype=np.float64)
    recal[order] = recal_sorted
    recal_score = float(np.mean(_pinball_elementwise(y, recal, alpha)))

    return {"alpha": alpha, "n": n, "n_bins": k,
            "score": raw, "mcb": raw - recal_score,
            "dsc": unc - recal_score, "unc": unc}


def crps_report(y: np.ndarray, alpha_preds: dict[float, np.ndarray]) -> dict:
    """CRPS (trapezoidal over `alpha_preds`' keys, flat-extended to [0, 1]) plus its
    calibration/resolution/uncertainty decomposition, integrated the same way.

    `alpha_preds`: {quantile_alpha: predicted quantile array}, row-aligned with `y` --
    the trio is {0.10: p10 preds, 0.50: p50 preds, 0.90: p90 preds}. Needs >= 2 levels.
    """
    y = np.asarray(y, dtype=np.float64)
    alphas = sorted(alpha_preds)
    if len(alphas) < 2:
        raise ValueError("crps_report needs at least two quantile levels to integrate over")

    per_alpha = {a: _reliability_at_alpha(y, np.asarray(alpha_preds[a], dtype=np.float64), a)
                 for a in alphas}
    grid_a = [0.0, *alphas, 1.0]

    def integrate(key: str) -> float:
        vals = [per_alpha[alphas[0]][key], *(per_alpha[a][key] for a in alphas),
                per_alpha[alphas[-1]][key]]
        return 2.0 * _trapz(vals, grid_a)

    crps = integrate("score")
    mcb, dsc, unc = integrate("mcb"), integrate("dsc"), integrate("unc")
    return {
        "crps": crps,
        "grid_alphas": grid_a,
        "per_alpha": per_alpha,
        "decomposition": {
            "mcb": mcb, "dsc": dsc, "unc": unc,
            "reconstructed_crps": mcb - dsc + unc,
            "method": ("binned Murphy calibration-resolution-uncertainty split at each "
                       "available quantile level, trapezoidal-integrated over the same "
                       "alpha grid as `crps` -- mcb - dsc + unc reproduces `crps` by "
                       "construction (see reconstructed_crps); it is not a second, "
                       "weaker estimate of it."),
        },
        "note": ("flat-extended at alpha=0 and alpha=1 from the trio's own p10/p90, not "
                 "a tail estimate. `decomposition.unc` is an independent read on the "
                 "target's irreducible spread, in the SAME units as `crps` but from a "
                 "different construction than 01b's difference-based floor -- report "
                 "them side by side, never as a difference (foundations/epistemics.md)."),
    }
