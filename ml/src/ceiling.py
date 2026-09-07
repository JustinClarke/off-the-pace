"""Attainable ceilings — the denominator this series never wrote down.

Every headline in the repo is a ratio against a baseline; none is a ratio against
what is *reachable*. `ml_execution_plan.md` Corrections §12/§15 measured the gap and
Phase 6 is the repair. This module owns the ceiling arithmetic; `evaluate.py` calls it
and publishes the result beside each headline.

Two independent ceilings are computed, because they answer different questions and
they are biased in opposite directions:

**1. Distributional — the between-stint variance share (ICC).** Laps inside one stint
share a compound, a car, a circuit, a fuel load and a driver. Any predictor that is
constant within a stint can reach no further than the between-stint component of the
target's variance, by construction. That share is what §12 reported at 17.5% for the
trained degradation target.

  **§12's 17.5% is an artefact of the estimator, not a measurement.** It is
  `var(per-stint means) / var(column)`, which counts `sigma_w^2 / n_bar` of pure
  within-stint scatter as if it were between-stint signal. At ~19 laps per stint that
  inflation is ~5% of total variance — most of the 17.5%. The one-way random-effects
  (ANOVA) estimator below removes it: `sigma_b^2 = (MSB - MSW) / n0`. On simulated data
  with a known ICC of 0.03 the naive estimator returns 0.081 and this one returns 0.030
  (`ml/tests/test_ceiling.py::test_anova_recovers_a_known_icc`). Both are reported —
  `share` is load-bearing, `share_naive` is carried so the correction stays visible.

  For a rolling-window target (`next_5_lap_cumulative_jump_s` and friends) consecutive
  rows share `horizon - 1` of their `horizon` terms, so the within-stint residuals are
  *not* independent and the ANOVA estimator is biased upward again. Where `horizon > 1`
  a non-overlapping thinned estimate is computed and it, not the full-sample one, is
  load-bearing.

**2. Metric-native — a stint-identity oracle, in the headline metric itself.** The ICC
is a variance statement and the headlines are pinball / macro-F1 / AFT NLL, so the ICC
cannot be divided into them without a change of units. The oracle can: score a
predictor that is handed the stint id and nothing else, and read off how much of the
loss reduction it captures.

    fraction_of_attainable = (floor - model) / (floor - oracle)

  where `floor` is the unconditional statistic (stint-blind) and `oracle` is the
  per-stint statistic. Bracketed rather than pointed, because neither end is unbiased:
  the **in-sample** oracle sees the rows it is scored on and overstates the ceiling
  (fraction reads low); the **cross-fitted** oracle (odd laps predict even, even predict
  odd) estimates each stint's statistic from ~9 laps and understates it (fraction reads
  high). The truth is between, and reporting one end alone is the unanchored-number
  failure this module exists to fix.

Survival is the exception and takes a third form: a stint-identity oracle is meaningless
for a target that is a deterministic ramp inside its own stint (`stint_length -
lap_in_stint`), but the censored AFT NLL has a non-zero floor at a *perfect* prediction,
so that floor is a true irreducible bound and is used directly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


# ─── One-way random-effects variance components ─────────────────────────────────
@dataclass(frozen=True)
class VarianceComponents:
    n: int
    n_groups: int
    n0: float              # ANOVA's effective group size (harmonic-ish, unequal n_i)
    mean_rows_per_group: float
    sd: float
    sigma_b2: float        # between-group variance component
    sigma_w2: float        # within-group variance component
    share: float           # ICC = sigma_b2 / (sigma_b2 + sigma_w2)
    share_naive: float     # var(group means) / var(y)  -- the §12 estimator, biased up


def variance_components(y: np.ndarray, groups: np.ndarray) -> VarianceComponents | None:
    """ICC(1) by one-way ANOVA. None when the design cannot support it (<2 groups).

    sigma_b2 is a *difference of mean squares* and can come out negative when the true
    between-group component is at or near zero. It is clamped at 0 rather than reported
    as a negative variance -- but note that clamping makes the estimator very slightly
    optimistic at the low end, which is the end the degradation target lives at.
    """
    df = pd.DataFrame({"y": np.asarray(y, dtype=np.float64), "g": np.asarray(groups)}).dropna()
    if df.empty:
        return None
    grp = df.groupby("g", observed=True)["y"]
    n_i = grp.size().to_numpy(dtype=np.float64)
    m_i = grp.mean().to_numpy()
    n_total, k = float(n_i.sum()), int(len(n_i))
    if k < 2 or n_total - k < 1:
        return None

    grand = float(df["y"].mean())
    ssb = float((n_i * (m_i - grand) ** 2).sum())
    ssw = float(((df["y"].to_numpy() - df["g"].map(grp.mean()).to_numpy()) ** 2).sum())
    msb, msw = ssb / (k - 1), ssw / (n_total - k)
    n0 = (n_total - float((n_i ** 2).sum()) / n_total) / (k - 1)
    sigma_b2 = max((msb - msw) / n0, 0.0)
    total = sigma_b2 + msw
    var_y = float(np.var(df["y"].to_numpy()))
    return VarianceComponents(
        n=int(n_total), n_groups=k, n0=float(n0),
        mean_rows_per_group=n_total / k, sd=float(df["y"].std()),
        sigma_b2=sigma_b2, sigma_w2=float(msw),
        share=float(sigma_b2 / total) if total > 0 else 0.0,
        share_naive=float(np.var(m_i) / var_y) if var_y > 0 else 0.0)


def categorical_variance_components(labels: np.ndarray,
                                    groups: np.ndarray) -> VarianceComponents | None:
    """Gini decomposition: ANOVA each class indicator, then sum the components.

    A categorical target has no variance, but it has a Gini impurity
    `sum_c p_c (1 - p_c)`, which is exactly the summed variance of its one-hot
    indicators. Decomposing each indicator and summing the parts gives the same
    between/within split the continuous estimator gives, with the same bias correction.
    """
    s = pd.Series(labels).dropna()
    g = pd.Series(groups)[s.index]
    sigma_b2 = sigma_w2 = 0.0
    naive_num = naive_den = 0.0
    parts = 0
    for lab in sorted(s.unique()):
        vc = variance_components((s == lab).to_numpy(dtype=np.float64), g.to_numpy())
        if vc is None:
            continue
        parts += 1
        sigma_b2 += vc.sigma_b2
        sigma_w2 += vc.sigma_w2
        w = float(np.var((s == lab).to_numpy(dtype=np.float64)))
        naive_num += vc.share_naive * w
        naive_den += w
    if parts == 0:
        return None
    total = sigma_b2 + sigma_w2
    ref = variance_components((s == sorted(s.unique())[0]).to_numpy(dtype=np.float64), g.to_numpy())
    return VarianceComponents(
        n=ref.n, n_groups=ref.n_groups, n0=ref.n0,
        mean_rows_per_group=ref.mean_rows_per_group,
        sd=float(np.sqrt(total)), sigma_b2=sigma_b2, sigma_w2=sigma_w2,
        share=float(sigma_b2 / total) if total > 0 else 0.0,
        share_naive=float(naive_num / naive_den) if naive_den > 0 else 0.0)


def within_group_lag1(y: np.ndarray, groups: np.ndarray, order: np.ndarray) -> float | None:
    """corr(y_t, y_{t-1}) within group, ordered by `order`. §12's load-bearing statistic.

    Read it against what pure noise would give: for a rolling sum over `h` laps,
    consecutive rows share `h - 1` terms, so white-noise increments already produce
    `(h - 1) / h`. Only the excess over that is evidence of a process.
    """
    df = pd.DataFrame({"y": np.asarray(y, dtype=np.float64),
                       "g": np.asarray(groups), "o": np.asarray(order)}).dropna()
    if df.empty:
        return None
    df = df.sort_values(["g", "o"])
    lag = df.groupby("g", observed=True)["y"].shift(1)
    m = lag.notna()
    if m.sum() < 3:
        return None
    a, b = df["y"][m].to_numpy(), lag[m].to_numpy()
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def thin_non_overlapping(groups: np.ndarray, order: np.ndarray, horizon: int) -> np.ndarray:
    """Boolean mask keeping every `horizon`-th row within each group (rank order).

    Rolling-window targets overlap by construction; the ANOVA estimator assumes
    independent within-group residuals and is biased upward when they are not. Thinning
    to non-overlapping windows is the cheapest way to get an estimate that does not
    inherit that bias -- at the cost of ~horizon-fold fewer rows per group.
    """
    df = pd.DataFrame({"g": np.asarray(groups), "o": np.asarray(order)})
    rank = df.sort_values(["g", "o"]).groupby("g", observed=True).cumcount()
    return (rank.reindex(df.index) % max(horizon, 1) == 0).to_numpy()


# ─── The analytic pinball ceiling ───────────────────────────────────────────────
def attainable_pinball_fraction(icc: float) -> float:
    """Largest fraction of expected pinball loss that stint identity alone can remove.

    Model the target as `mu_i + eps`, `eps ~ N(0, sigma_w^2)`, `mu_i ~ N(m, sigma_b^2)`.
    For a Normal, the minimum expected pinball at the true alpha-quantile is
    `sigma * phi(z_alpha)` -- the alpha drops out of the *ratio*. A stint-blind predictor
    faces `sigma_t = sqrt(sigma_b^2 + sigma_w^2)`; one that knows the stint faces only
    `sigma_w`. So the best available fractional reduction is

        1 - sigma_w / sigma_t  =  1 - sqrt(1 - ICC)

    and it is the same number at every quantile. Two properties make this the primary
    denominator rather than an empirical oracle: it needs no per-stint estimate, so it
    does not collapse when a stint holds ~19 laps and the statistic is a tail quantile;
    and it is the *population* ceiling rather than an in-sample one.

    Its one assumption is shape -- that the within-stint conditional has the same
    distributional form as the marginal. Verified end-to-end against simulation in
    `ml/tests/test_ceiling.py::test_analytic_pinball_ceiling_predicts_the_achievable_reduction`.
    """
    return 1.0 - float(np.sqrt(max(1.0 - float(icc), 0.0)))


# ─── Metric-native oracles ──────────────────────────────────────────────────────
def _statistic(values: np.ndarray, kind: str, alpha: float | None) -> float:
    if kind == "classification":
        vals, counts = np.unique(values, return_counts=True)
        return float(vals[int(np.argmax(counts))])
    if kind == "quantile":
        return float(np.quantile(values, alpha if alpha is not None else 0.5))
    return float(np.mean(values))


def unconditional_floor(y_train: np.ndarray, kind: str, alpha: float | None,
                        n_eval: int) -> np.ndarray:
    """The stint-blind reference: one global statistic, repeated. Deliberately weaker
    than `evaluate.baseline_predictions` (which conditions on compound x circuit x age)
    -- this end of the bracket has to know *nothing*, or the ceiling it anchors is not a
    ceiling on stint-level information."""
    return np.full(n_eval, _statistic(np.asarray(y_train, dtype=np.float64), kind, alpha),
                   dtype=np.float64)


def stint_oracle(y: np.ndarray, stint_ids: np.ndarray, order: np.ndarray,
                 kind: str, alpha: float | None, *, cross_fitted: bool) -> np.ndarray:
    """A predictor handed the stint id and nothing else.

    `cross_fitted=False`: each row gets its own stint's statistic over all its laps --
    the row is inside the sample it is scored against, so this *overstates* the ceiling.

    `cross_fitted=True`: laps at even rank within the stint are predicted from the odd
    ones and vice versa. Genuinely out-of-sample, but each half holds ~9 laps, so the
    statistic is noisy and this *understates* the ceiling. Singleton halves fall back to
    the whole stint, and single-lap stints fall back to the global statistic.
    """
    y = np.asarray(y, dtype=np.float64)
    df = pd.DataFrame({"y": y, "g": np.asarray(stint_ids), "o": np.asarray(order)})
    df["rank"] = df.sort_values(["g", "o"]).groupby("g", observed=True).cumcount().reindex(df.index)
    out = np.full(len(df), _statistic(y, kind, alpha), dtype=np.float64)

    if not cross_fitted:
        for _, idx in df.groupby("g", observed=True).indices.items():
            out[idx] = _statistic(y[idx], kind, alpha)
        return out

    parity = (df["rank"].to_numpy() % 2).astype(int)
    for _, idx in df.groupby("g", observed=True).indices.items():
        for p in (0, 1):
            tgt = idx[parity[idx] == p]
            src = idx[parity[idx] != p]
            if len(tgt) == 0:
                continue
            out[tgt] = _statistic(y[src] if len(src) else y[idx], kind, alpha)
    return out
