"""The stint-life AFT contract: label bounds, the margin->laps transform, and the
two metrics. These are the pieces the browser has a second implementation of, so
they are pinned here rather than only exercised through a training run."""
from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import norm

from ml.src import schema as S
from ml.src import survival as SV


# ─── Label bounds ───────────────────────────────────────────────────────────────
def test_uncensored_bounds_are_a_point():
    y = np.array([0.0, 3.0, 17.0])
    lo, hi = SV.aft_bounds(y, np.zeros(3, dtype=bool))
    assert np.allclose(lo, y + S.AFT_LABEL_SHIFT)
    assert np.allclose(lo, hi)


def test_censored_bounds_are_a_half_line():
    y = np.array([0.0, 3.0, 17.0])
    lo, hi = SV.aft_bounds(y, np.ones(3, dtype=bool))
    assert np.allclose(lo, y + S.AFT_LABEL_SHIFT)
    assert np.isinf(hi).all() and (hi > 0).all()


def test_shift_keeps_zero_life_off_log_zero():
    """The whole reason the shift exists. 2,264 training rows have zero remaining
    life; without the shift each contributes log(0) = -inf to the likelihood."""
    lo, _ = SV.aft_bounds(np.zeros(5), np.zeros(5, dtype=bool))
    assert (lo > 0).all()
    assert np.isfinite(np.log(lo)).all()


# ─── margin → laps ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("laps", [0.0, 1.0, 7.5, 40.0])
def test_margin_round_trips_to_laps(laps):
    m = np.log(laps + S.AFT_LABEL_SHIFT)
    assert SV.laps_from_margin(np.array([m]), 0.8)[0] == pytest.approx(laps)


def test_negative_life_is_clipped():
    assert SV.laps_from_margin(np.array([-5.0]), 0.8)[0] == 0.0


def test_median_is_scale_independent():
    m = np.array([np.log(13.0)])
    assert SV.laps_from_margin(m, 0.2)[0] == pytest.approx(SV.laps_from_margin(m, 1.1)[0])


def test_quantiles_bracket_the_median_and_widen_with_scale():
    m = np.array([np.log(13.0)])
    med = SV.laps_from_margin(m, 0.8)[0]
    narrow = SV.laps_from_margin(m, 0.3, 0.9)[0] - SV.laps_from_margin(m, 0.3, 0.1)[0]
    wide = SV.laps_from_margin(m, 1.0, 0.9)[0] - SV.laps_from_margin(m, 1.0, 0.1)[0]
    assert SV.laps_from_margin(m, 0.8, 0.1)[0] < med < SV.laps_from_margin(m, 0.8, 0.9)[0]
    assert wide > narrow


def test_quantile_matches_the_closed_form():
    m, scale, q = np.log(9.0), 0.8, 0.1
    expected = np.exp(m + scale * norm.ppf(q)) - S.AFT_LABEL_SHIFT
    assert SV.laps_from_margin(np.array([m]), scale, q)[0] == pytest.approx(expected)


# ─── Metrics ────────────────────────────────────────────────────────────────────
def test_nll_rewards_a_prediction_nearer_the_truth():
    y = np.array([10.0] * 200)
    cens = np.zeros(200, dtype=bool)
    good = SV.aft_nloglik(y, np.full(200, 10.0), cens, 0.8)
    bad = SV.aft_nloglik(y, np.full(200, 30.0), cens, 0.8)
    assert good < bad


def test_censoring_changes_the_score():
    """A censored row is scored on P(T > t), an uncensored one on the density at t.
    If the flag made no difference, the survival framing would be inert -- which is
    exactly the 'gate that cannot fail' shape this phase is about."""
    y = np.array([10.0] * 200)
    pred = np.full(200, 14.0)
    assert SV.aft_nloglik(y, pred, np.zeros(200, dtype=bool), 0.8) != pytest.approx(
        SV.aft_nloglik(y, pred, np.ones(200, dtype=bool), 0.8))


def test_over_prediction_is_cheap_on_censored_rows():
    """Predicting more life than observed is nearly free when the row is censored
    (the tyre really might have lasted) and costly when it is not."""
    y = np.array([5.0] * 200)
    over = np.full(200, 25.0)
    assert (SV.aft_nloglik(y, over, np.ones(200, dtype=bool), 0.8)
            < SV.aft_nloglik(y, over, np.zeros(200, dtype=bool), 0.8))


def test_nll_is_finite_on_zero_life_rows():
    y = np.zeros(50)
    for cens in (np.zeros(50, dtype=bool), np.ones(50, dtype=bool)):
        assert np.isfinite(SV.aft_nloglik(y, np.full(50, 2.0), cens, 0.8))


def test_c_index_ranks_perfectly_and_inversely():
    rng = np.random.default_rng(S.RANDOM_STATE)
    y = rng.uniform(1, 30, 400)
    cens = rng.random(400) < 0.4
    assert SV.c_index(y, y, cens) == pytest.approx(1.0)
    assert SV.c_index(y, -y, cens) == pytest.approx(0.0)


def test_c_index_of_a_constant_prediction_is_chance():
    rng = np.random.default_rng(S.RANDOM_STATE)
    y = rng.uniform(1, 30, 400)
    cens = rng.random(400) < 0.4
    assert SV.c_index(y, np.full(400, 7.0), cens) == pytest.approx(0.5, abs=0.02)


# ─── Artefact params ────────────────────────────────────────────────────────────
def test_aft_params_rejects_a_non_aft_booster(tmp_path):
    """aft_params reading a plain regressor must raise, not return a default. A
    silent default here would mean scoring an exp-scale margin as laps."""
    import xgboost as xgb

    X = np.random.default_rng(0).normal(size=(50, 3))
    b = xgb.train({"objective": "reg:squarederror", "tree_method": "hist"},
                  xgb.DMatrix(X, label=np.arange(50.0)), num_boost_round=2)
    with pytest.raises(ValueError, match="not an AFT booster"):
        SV.aft_params(b)
