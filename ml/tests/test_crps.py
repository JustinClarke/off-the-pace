"""CRPS + decomposition arithmetic, proven on synthetic data — work item `09a`.

No warehouse, no artefacts, no skips (same posture as test_ceiling.py): every claim in
ml/src/crps.py's docstring is checked against a case where the right answer is known by
construction, rather than trusted because the formula looks right.
"""
from __future__ import annotations

import numpy as np
import pytest

from ml.src import crps as CR
from ml.src import train as T


def _rng():
    return np.random.default_rng(20260528)


def test_crps_reduces_to_mae_for_a_point_forecast():
    """A trio collapsed to one constant point forecast integrates EXACTLY to MAE: for
    fixed q the pinball loss is linear in alpha (no kink -- y>=q is alpha-independent),
    so the 3-point trapezoid is exact regardless of grid spacing, not just close."""
    rng = _rng()
    y = rng.normal(loc=5.0, scale=2.0, size=2000)
    q = np.full_like(y, 4.2)
    report = CR.crps_report(y, {0.10: q, 0.50: q, 0.90: q})
    mae = float(np.mean(np.abs(y - q)))
    assert report["crps"] == pytest.approx(mae, rel=1e-9)


def test_decomposition_reconstructs_crps():
    """mcb - dsc + unc must reproduce crps by construction, on non-degenerate,
    imperfectly-calibrated predictions (not just the point-forecast special case)."""
    rng = _rng()
    n = 6000
    x = rng.normal(size=n)
    y = 3.0 + 1.5 * x + rng.normal(scale=1.0, size=n)
    # Deliberately imperfect quantile predictions: right shape, wrong scale and a
    # constant bias, so mcb and dsc are both non-trivially non-zero.
    p10 = (3.0 + 1.5 * x) - 1.0 * 1.2816 + 0.3
    p50 = (3.0 + 1.5 * x) + 0.3
    p90 = (3.0 + 1.5 * x) + 1.0 * 1.2816 + 0.3
    report = CR.crps_report(y, {0.10: p10, 0.50: p50, 0.90: p90})
    d = report["decomposition"]
    assert d["reconstructed_crps"] == pytest.approx(report["crps"], rel=1e-9)
    # dsc >= 0 always holds for this binned recalibration (the K-bin per-bin-optimal fit
    # weakly dominates the 1-bin global-constant fit `unc` uses -- see crps.py's
    # docstring). mcb carries no such guarantee here and is deliberately not asserted.
    assert d["dsc"] >= -1e-9


def test_crps_is_nonnegative_and_beats_a_useless_forecast():
    """A well-formed trio should score better (lower CRPS) than a trio that ignores the
    covariate entirely -- the same beats_baseline instinct evaluate.py applies elsewhere."""
    rng = _rng()
    n = 4000
    x = rng.normal(size=n)
    y = 3.0 + 1.5 * x + rng.normal(scale=1.0, size=n)
    good = CR.crps_report(y, {
        0.10: (3.0 + 1.5 * x) - 1.2816, 0.50: 3.0 + 1.5 * x, 0.90: (3.0 + 1.5 * x) + 1.2816})
    z10, z90 = float(np.quantile(y, 0.10)), float(np.quantile(y, 0.90))
    useless = CR.crps_report(y, {
        0.10: np.full(n, z10), 0.50: np.full(n, float(np.median(y))), 0.90: np.full(n, z90)})
    assert good["crps"] >= 0
    assert useless["crps"] >= 0
    assert good["crps"] < useless["crps"]


def test_unc_matches_the_unconditional_pinball_loss_at_each_alpha():
    """`unc` at a given alpha is defined as the pinball loss of the single unconditional
    empirical alpha-quantile -- check it against ml.src.train.pinball_loss directly,
    rather than trusting crps.py's own internal formula for it."""
    rng = _rng()
    y = rng.gamma(shape=2.0, scale=1.5, size=3000)
    q = rng.normal(size=3000)  # arbitrary, uncorrelated forecast -- only unc is checked
    report = CR.crps_report(y, {0.10: q, 0.50: q, 0.90: q * 0})
    for alpha, row in report["per_alpha"].items():
        expected = T.pinball_loss(y, np.full_like(y, np.quantile(y, alpha)), alpha)
        assert row["unc"] == pytest.approx(expected, rel=1e-9)


def test_raises_on_a_single_quantile_level():
    with pytest.raises(ValueError):
        CR.crps_report(np.array([1.0, 2.0, 3.0]), {0.50: np.array([1.0, 1.0, 1.0])})
