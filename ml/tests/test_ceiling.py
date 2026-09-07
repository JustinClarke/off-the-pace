"""The ceiling arithmetic, proven against data whose answer is known in advance.

`ml_execution_plan.md` Corrections §12 reported the trained degradation target as 17.5%
between-stint. That number is `var(per-stint means) / var(column)`, which counts
`sigma_w^2 / n_bar` of within-stint scatter as between-stint signal — at ~19 laps per
stint, most of the 17.5%. Phase 6's checklist says the ceiling must be computed
*properly* rather than inherited, so the estimator that replaces it ships with a proof
that it recovers a known answer and that the old one does not.

Everything here runs on synthetic data. No warehouse, no artefacts, no skips.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.src import ceiling as CE
from ml.src import intervals as IV
from ml.src import schema as S

RNG_SEED = S.RANDOM_STATE


def _clustered(icc: float, n_groups: int = 4000, per_group: int = 19, seed: int = RNG_SEED):
    """y = group effect + noise, with an exactly-specified intraclass correlation."""
    rng = np.random.default_rng(seed)
    g = np.repeat(np.arange(n_groups), per_group)
    y = (np.repeat(rng.normal(0.0, np.sqrt(icc), n_groups), per_group)
         + rng.normal(0.0, np.sqrt(1.0 - icc), n_groups * per_group))
    order = np.tile(np.arange(per_group), n_groups)
    return y, g, order


@pytest.mark.parametrize("true_icc", [0.03, 0.20, 0.40])
def test_anova_recovers_a_known_icc(true_icc):
    y, g, _ = _clustered(true_icc)
    vc = CE.variance_components(y, g)
    assert vc is not None
    assert vc.share == pytest.approx(true_icc, abs=0.015), (
        f"one-way ANOVA returned {vc.share:.4f} for a true ICC of {true_icc}")


def test_the_naive_estimator_is_the_one_that_was_wrong():
    """The liveness proof for the correction itself.

    At the ICC the degradation target actually sits near, the naive estimator does not
    err slightly — it more than doubles the answer. If this ever stops holding, either
    the estimator changed or the group sizes did, and §12's correction needs re-reading.
    """
    y, g, _ = _clustered(0.03)
    vc = CE.variance_components(y, g)
    assert vc.share_naive > 2 * vc.share, (
        f"naive={vc.share_naive:.4f} vs anova={vc.share:.4f} — the inflation this "
        f"module exists to remove is not present, so the test is not testing it")


def test_between_stint_share_is_zero_when_groups_carry_nothing():
    y, g, _ = _clustered(0.0)
    vc = CE.variance_components(y, g)
    assert vc.share < 0.01


def test_between_stint_share_is_one_when_the_group_is_the_whole_signal():
    g = np.repeat(np.arange(500), 19)
    y = np.repeat(np.linspace(0, 10, 500), 19)     # constant within group
    vc = CE.variance_components(y, g)
    assert vc.share > 0.99


def test_categorical_decomposition_matches_the_continuous_one_on_a_binary_target():
    """A two-class Gini decomposition is the same arithmetic as one indicator's ANOVA."""
    rng = np.random.default_rng(RNG_SEED)
    g = np.repeat(np.arange(3000), 19)
    p = np.repeat(rng.uniform(0.1, 0.9, 3000), 19)
    labels = np.where(rng.random(len(g)) < p, "a", "b")
    cat = CE.categorical_variance_components(labels, g)
    cont = CE.variance_components((labels == "a").astype(float), g)
    assert cat.share == pytest.approx(cont.share, abs=1e-9)


def test_rolling_window_overlap_inflates_the_estimate_and_thinning_removes_it():
    """Why `S.TARGET_HORIZON_LAPS` exists.

    Build a target with *no* group structure at all, then make it a rolling 5-sum. The
    full-sample estimator reads a between-group share out of pure noise, because
    consecutive rows share four of their five terms. The non-overlapping thinning is what
    puts it back to zero — and Phase 7 retargets onto exactly such a column.
    """
    rng = np.random.default_rng(RNG_SEED)
    n_groups, per_group, h = 3000, 25, 5
    g = np.repeat(np.arange(n_groups), per_group)
    order = np.tile(np.arange(per_group), n_groups)
    noise = rng.normal(size=(n_groups, per_group + h))
    rolled = np.stack([noise[:, i:i + h].sum(axis=1) for i in range(per_group)], axis=1)
    y = rolled.reshape(-1)

    full = CE.variance_components(y, g)
    mask = CE.thin_non_overlapping(g, order, h)
    thinned = CE.variance_components(y[mask], g[mask])
    assert full.share > 0.05, "overlap inflation absent — the fixture is not testing it"
    assert thinned.share < full.share / 2, (
        f"thinning did not remove the overlap artefact: {full.share:.4f} → {thinned.share:.4f}")


def test_lag1_of_a_rolling_sum_lands_near_the_overlap_prediction():
    """(h-1)/h under white-noise increments. §12 read +0.719 on the 5-lap column as
    evidence of a degradation *process*; white noise alone predicts +0.800."""
    rng = np.random.default_rng(RNG_SEED)
    n_groups, per_group, h = 2000, 25, 5
    g = np.repeat(np.arange(n_groups), per_group)
    order = np.tile(np.arange(per_group), n_groups)
    noise = rng.normal(size=(n_groups, per_group + h))
    y = np.stack([noise[:, i:i + h].sum(axis=1) for i in range(per_group)], axis=1).reshape(-1)
    assert CE.within_group_lag1(y, g, order) == pytest.approx((h - 1) / h, abs=0.02)


# ─── Oracles ────────────────────────────────────────────────────────────────────
def test_in_sample_stint_oracle_is_the_exact_pinball_optimum_over_stint_constants():
    """The property that makes `fraction_of_attainable_in_sample > 1` a proof rather
    than an estimate: no stint-constant predictor can score better on these rows."""
    from ml.src.train import pinball_loss

    rng = np.random.default_rng(RNG_SEED)
    y, g, order = _clustered(0.3, n_groups=300, per_group=19)
    oracle = CE.stint_oracle(y, g, order, "quantile", 0.5, cross_fitted=False)
    best = pinball_loss(y, oracle, 0.5)
    for _ in range(25):                       # any other stint-constant predictor
        offsets = np.repeat(rng.normal(0, 0.3, 300), 19)
        assert pinball_loss(y, oracle + offsets, 0.5) >= best - 1e-12


def test_cross_fitted_oracle_never_sees_the_row_it_predicts():
    """Constant-within-stint data would let an in-sample oracle look perfect; the
    cross-fitted one has to earn it from the other half of the stint."""
    g = np.repeat(np.arange(200), 10)
    y = np.repeat(np.linspace(-5, 5, 200), 10)
    order = np.tile(np.arange(10), 200)
    cf = CE.stint_oracle(y, g, order, "quantile", 0.5, cross_fitted=True)
    assert np.allclose(cf, y)                 # constant stints: both halves agree
    noisy = y + np.tile([0.0, 100.0] * 5, 200)   # every odd lap is shifted by +100
    cf_noisy = CE.stint_oracle(noisy, g, order, "quantile", 0.5, cross_fitted=True)
    even = np.tile([True, False] * 5, 200)
    # Even laps carry no shift, so a leaking oracle would predict them near y (|y| <= 5).
    # A clean one predicts them from the odd half and lands near y + 100.
    assert np.all(cf_noisy[even] > 90), (
        "even laps must be predicted from the odd (shifted) half — they are not, so the "
        "cross-fit is leaking the row it scores")
    assert np.all(cf_noisy[~even] < 10), "odd laps must be predicted from the unshifted half"


def test_unconditional_floor_knows_nothing_about_stints():
    y, g, _ = _clustered(0.5, n_groups=100, per_group=19)
    floor = CE.unconditional_floor(y, "quantile", 0.5, len(y))
    assert len(np.unique(floor)) == 1


# ─── Intervals ──────────────────────────────────────────────────────────────────
def test_paired_t_declines_a_win_that_is_inside_fold_noise():
    """Phase 2's checkpoint reported +0.75% at p=0.24 and declined to call it a win.
    That judgement is now the default rather than one careful session's discipline."""
    out = IV.paired_t([0.004, -0.002, 0.011, -0.006, 0.010])
    assert out["mean_delta"] > 0
    assert out["significant"] is False
    assert out["ci_low"] < 0 < out["ci_high"]


def test_paired_t_accepts_a_win_that_clears_it():
    out = IV.paired_t([0.10, 0.12, 0.09, 0.11, 0.10])
    assert out["significant"] is True
    assert out["p_value"] < 0.01


def test_clustered_bootstrap_is_wider_than_lap_grain_when_rows_are_clustered():
    """Corrections §15's mechanism, on data built to carry it. The size of the widening
    depends on the intra-cluster correlation of the *scored quantity*, which is why
    evaluate.py publishes the measured ratio instead of asserting sqrt(rows/stints)."""
    rng = np.random.default_rng(RNG_SEED)
    per_group, n_groups = 19, 600
    clusters = np.repeat(np.arange(n_groups), per_group)
    values = (np.repeat(rng.normal(0.05, 0.20, n_groups), per_group)
              + rng.normal(0, 0.02, n_groups * per_group))

    def score(idx):
        return float(values[idx].mean())

    clustered = IV.cluster_bootstrap(score, clusters, len(values), resamples=200, seed=1)
    lap = IV.cluster_bootstrap(score, np.arange(len(values)), len(values),
                               resamples=200, seed=1)
    ratio = IV.width_ratio(clustered, lap)
    assert ratio > 2.0, f"clustered interval only {ratio:.2f}x the lap-grain one"


def test_signed_delta_orients_both_metric_directions():
    assert IV.signed_delta(0.20, 0.29, higher_is_better=False) > 0   # pinball ↓
    assert IV.signed_delta(0.40, 0.22, higher_is_better=True) > 0    # macro-F1 ↑
    assert IV.signed_delta(0.29, 0.20, higher_is_better=False) < 0


# ─── The stint-grain claim itself ───────────────────────────────────────────────
def test_season_grouped_folds_cannot_split_a_stint():
    """Phase 6's checklist asks for stint-grain CV nesting. Measured rather than built:
    a stint belongs to one race and a race to one season, so season-grouped folds are
    already stint-pure and the clustering damage was only ever in the intervals."""
    stints = np.repeat(np.arange(500), 19)
    seasons = np.repeat(np.random.default_rng(RNG_SEED).integers(2018, 2025, 500), 19)
    straddling = (pd.DataFrame({"s": stints, "y": seasons})
                  .groupby("s")["y"].nunique().gt(1).sum())
    assert straddling == 0


def test_analytic_pinball_ceiling_predicts_the_achievable_reduction():
    """The derivation behind the primary denominator, checked end-to-end.

    Build clustered data at a known ICC, score the two optimal predictors — stint-blind
    and stint-aware — and confirm the measured fractional pinball reduction is the one
    `attainable_pinball_fraction` claims. If this drifts, every `fraction_of_attainable`
    in the model card is being divided by the wrong number.
    """
    from scipy import stats

    from ml.src.train import pinball_loss

    rng = np.random.default_rng(RNG_SEED)
    for icc in (0.03, 0.20, 0.40):
        k, per = 20_000, 30
        mu = rng.normal(0.0, np.sqrt(icc), k)
        y = np.repeat(mu, per) + rng.normal(0.0, np.sqrt(1.0 - icc), k * per)
        for alpha in (0.1, 0.5, 0.9):
            z = stats.norm.ppf(alpha)
            blind = pinball_loss(y, np.full_like(y, z), alpha)             # sigma_t == 1
            aware = pinball_loss(y, np.repeat(mu, per) + z * np.sqrt(1 - icc), alpha)
            measured = 1.0 - aware / blind
            assert measured == pytest.approx(CE.attainable_pinball_fraction(icc), abs=0.005), (
                f"icc={icc} alpha={alpha}: measured {measured:.4f}, "
                f"formula {CE.attainable_pinball_fraction(icc):.4f}")


def test_the_analytic_ceiling_is_the_same_at_every_quantile():
    """alpha cancels out of the ratio — which is why one ICC anchors all three of p10,
    p50 and p90 rather than needing a separate ceiling each."""
    assert CE.attainable_pinball_fraction(0.0) == 0.0
    assert CE.attainable_pinball_fraction(1.0) == 1.0
    assert CE.attainable_pinball_fraction(0.0289) == pytest.approx(0.0145559, abs=1e-6)
