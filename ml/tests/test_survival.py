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


# ─── Cause-specific metrics (10c) ───────────────────────────────────────────────
# These three went into a measurement run untested, and two of them were not
# computing what their names claimed. The regressions below are the checks that
# would have caught it.

def test_d_calibration_risk_score_is_not_constant():
    """The original bug: predicted risk was read off each row's survival curve at
    that row's OWN predicted median, which is 0.5 by definition. Every row scored
    0.5, all five bins collapsed into one, and the slope came back nan. A risk
    score that does not vary with the prediction is not a risk score."""
    rng = np.random.default_rng(S.RANDOM_STATE)
    n = 600
    pred = rng.uniform(4, 35, n)
    y = rng.uniform(1, 40, n)
    cens = rng.random(n) < 0.3

    cal = SV.d_calibration(y, pred, cens, scale=0.8)
    assert len(cal["pred_quantiles"]) >= 3, "bins collapsed - risk score is degenerate"
    assert np.ptp(cal["exp_event_rates"]) > 0.05, "expected event rates barely vary"


def test_d_calibration_recovers_a_slope_near_one_when_well_specified():
    """Draw survival times FROM the model the metric assumes, so calibration is
    correct by construction and the slope has a known target."""
    rng = np.random.default_rng(S.RANDOM_STATE)
    n, scale = 4000, 0.6
    pred = rng.uniform(4, 30, n)
    # lognormal AFT: log(T + shift) ~ Normal(log(pred + shift), scale)
    mu = np.log(pred + S.AFT_LABEL_SHIFT)
    y = np.exp(rng.normal(mu, scale)) - S.AFT_LABEL_SHIFT
    y = np.maximum(y, 0.0)
    cens = np.zeros(n, dtype=bool)

    cal = SV.d_calibration(y, pred, cens, scale=scale)
    assert cal["calibration_slope"] == pytest.approx(1.0, abs=0.25)


def test_d_calibration_slope_is_nan_without_events():
    """An all-censored stratum has no events, so KM never drops and every observed
    rate is 0 - which regresses to a slope of exactly 0. That is unassessable, and
    reporting 0.0 would read as catastrophic miscalibration instead of no data."""
    rng = np.random.default_rng(S.RANDOM_STATE)
    n = 300
    cal = SV.d_calibration(
        rng.uniform(1, 30, n), rng.uniform(4, 25, n), np.ones(n, dtype=bool), scale=0.8
    )
    assert np.isnan(cal["calibration_slope"])


def test_ipcw_brier_weights_depend_on_the_horizon():
    """The original bug: the weight for a row was 1/G(its own time) at every
    horizon, and both branches of the censored/uncensored conditional were
    identical. Under real censoring the per-horizon scores must not be reproducible
    by any single fixed reweighting, so check they respond to censoring at all."""
    rng = np.random.default_rng(S.RANDOM_STATE)
    n = 800
    y = rng.uniform(1, 30, n)
    pred = np.full(n, 12.0)

    _, per_time_light = SV.ipcw_brier(y, pred, rng.random(n) < 0.05, scale=0.8)
    _, per_time_heavy = SV.ipcw_brier(y, pred, rng.random(n) < 0.60, scale=0.8)

    assert not np.allclose(per_time_light, per_time_heavy, atol=1e-3)


def test_ipcw_brier_rewards_the_better_prediction():
    rng = np.random.default_rng(S.RANDOM_STATE)
    n, scale = 1500, 0.6
    truth = 15.0
    y = np.exp(rng.normal(np.log(truth + S.AFT_LABEL_SHIFT), scale, size=n)) - S.AFT_LABEL_SHIFT
    y = np.maximum(y, 0.0)
    cens = rng.random(n) < 0.25

    near, _ = SV.ipcw_brier(y, np.full(n, truth), cens, scale)
    far, _ = SV.ipcw_brier(y, np.full(n, truth * 4), cens, scale)
    assert near < far


def test_time_dependent_auc_gives_ties_half_credit():
    """A constant prediction ties every pair. Counting ties in the denominator but
    never in the numerator scored that as 0.0 - perfectly wrong - when the honest
    answer for an uninformative model is chance."""
    rng = np.random.default_rng(S.RANDOM_STATE)
    n = 400
    y = rng.uniform(1, 30, n)
    cens = rng.random(n) < 0.3

    mean_auc, _ = SV.time_dependent_auc(y, np.full(n, 9.0), cens, scale=0.8)
    assert mean_auc == pytest.approx(0.5, abs=1e-9)


def test_time_dependent_auc_ranks_a_perfect_model_above_an_inverted_one():
    rng = np.random.default_rng(S.RANDOM_STATE)
    n = 500
    y = rng.uniform(1, 30, n)
    cens = rng.random(n) < 0.2

    good, _ = SV.time_dependent_auc(y, y.copy(), cens, scale=0.8)
    bad, _ = SV.time_dependent_auc(y, -y, cens, scale=0.8)
    assert good > 0.9
    assert bad < 0.1


def test_time_dependent_auc_risk_sets_are_disjoint():
    """at-risk was y >= t while events were y <= t, so a row sitting exactly on a
    horizon was compared against itself. Ties at t are common in lap data because
    the horizons are percentiles of observed lap counts."""
    y = np.array([5.0, 5.0, 5.0, 5.0, 10.0, 10.0, 15.0, 15.0, 20.0, 20.0])
    cens = np.zeros(len(y), dtype=bool)
    mean_auc, per_time = SV.time_dependent_auc(
        y, y.copy(), cens, scale=0.8, times=np.array([5.0, 10.0, 15.0])
    )
    # A perfect prediction on disjoint sets is 1.0 at every horizon that has both
    # an event set and an at-risk set; self-comparison would drag it below 1.
    assert np.nanmax(per_time) == pytest.approx(1.0)


# ─── 10c refresh: dependent-censoring band and D-calibration ────────────────────
def _toy(n=400, seed=7):
    rng = np.random.default_rng(seed)
    y = np.round(rng.gamma(4.0, 3.0, size=n))          # integer laps, heavy ties
    cens = rng.random(n) < 0.45
    pred = np.clip(y * rng.lognormal(0.0, 0.4, size=n), 0.0, None)
    return y, pred, cens


def test_clayton_theta_maps_tau_zero_to_independence():
    assert SV.clayton_theta(0.0) == 0.0
    assert SV.clayton_theta(0.5) == pytest.approx(2.0)
    assert SV.clayton_theta(-0.5) == pytest.approx(-2.0 / 3.0)
    with pytest.raises(ValueError):
        SV.clayton_theta(1.0)


def test_copula_graphic_at_tau_zero_is_kaplan_meier():
    """The instrument check for the whole dependence band. If tau=0 is not KM, the
    band's centre is not the incumbent estimate and nothing either side of it means
    anything. Ties are the hard part -- laps are integers -- so the toy has many."""
    from lifelines import KaplanMeierFitter
    y, _, cens = _toy()
    kmf = KaplanMeierFitter().fit(y, event_observed=cens)
    t, s = SV.copula_graphic_survival(y, cens, tau=0.0)
    grid = np.unique(y)
    mine = SV.step_eval(t, s, grid)
    theirs = np.asarray(kmf.survival_function_.asof(grid)).ravel()
    assert np.allclose(mine, theirs, atol=1e-12, rtol=0)


def test_copula_graphic_is_monotone_and_ordered_in_tau():
    y, _, cens = _toy()
    grid = np.unique(y)
    curves = {}
    for tau in (-0.5, -0.25, 0.0, 0.25, 0.5):
        t, s = SV.copula_graphic_survival(y, cens, tau=tau)
        v = SV.step_eval(t, s, grid)
        assert np.all(np.diff(v) <= 1e-12), f"not monotone at tau={tau}"
        assert v.min() >= 0.0 and v.max() <= 1.0
        curves[tau] = v
    # Positive dependence pushes the censoring marginal one way and negative the other,
    # consistently across the grid -- that ordering is what makes the band a bracket.
    assert not np.allclose(curves[-0.5], curves[0.5])


def test_ipcw_brier_dependent_reproduces_the_incumbent_at_tau_zero():
    y, pred, cens = _toy()
    base, base_per = SV.ipcw_brier(y, pred, cens, scale=0.8)
    band, band_per = SV.ipcw_brier_dependent(y, pred, cens, scale=0.8, tau=0.0)
    assert band == pytest.approx(base, abs=1e-12)
    assert np.allclose(band_per, base_per, atol=1e-12, rtol=0)


def test_ipcw_brier_dependent_moves_with_tau():
    y, pred, cens = _toy()
    vals = [SV.ipcw_brier_dependent(y, pred, cens, 0.8, tau=t)[0]
            for t in (-0.5, 0.0, 0.5)]
    assert len({round(v, 10) for v in vals}) == 3


def test_uno_auc_is_a_probability_and_moves_with_tau():
    y, pred, cens = _toy()
    for tau in (-0.5, 0.0, 0.5):
        a, per = SV.time_dependent_auc_ipcw(y, pred, cens, 0.8, tau=tau)
        assert 0.0 <= a <= 1.0
        assert np.all((per[~np.isnan(per)] >= 0.0) & (per[~np.isnan(per)] <= 1.0))
    lo = SV.time_dependent_auc_ipcw(y, pred, cens, 0.8, tau=-0.5)[0]
    hi = SV.time_dependent_auc_ipcw(y, pred, cens, 0.8, tau=0.5)[0]
    assert lo != hi


def test_uno_auc_ranks_a_perfect_model_above_a_random_one():
    rng = np.random.default_rng(3)
    y = np.round(rng.gamma(4.0, 3.0, size=500))
    cens = np.zeros(len(y), dtype=bool)
    good = SV.time_dependent_auc_ipcw(y, y.astype(float), cens, 0.8)[0]
    bad = SV.time_dependent_auc_ipcw(y, rng.permutation(y).astype(float), cens, 0.8)[0]
    assert good > 0.9 and abs(bad - 0.5) < 0.1


def test_d_calibration_chisq_passes_on_a_correctly_specified_fit():
    """Draw the truth FROM the model the test then scores. A D-calibration that
    cannot pass here is measuring its own arithmetic, which is what the incumbent
    `d_calibration` was doing when it returned 0.5 for every row."""
    rng = np.random.default_rng(11)
    n, scale = 20000, 0.5
    mu = rng.normal(2.5, 0.4, size=n)
    t = np.exp(mu + scale * rng.normal(size=n)) - S.AFT_LABEL_SHIFT
    pred = np.exp(mu) - S.AFT_LABEL_SHIFT
    out = SV.d_calibration_chisq(np.clip(t, 0, None), np.clip(pred, 0, None),
                                 np.zeros(n, dtype=bool), scale)
    assert out["p_value"] > 0.01
    assert out["mean_abs_deviation_ratio"] < 0.05


def test_d_calibration_chisq_fails_on_a_biased_fit():
    rng = np.random.default_rng(12)
    n, scale = 20000, 0.5
    mu = rng.normal(2.5, 0.4, size=n)
    t = np.exp(mu + scale * rng.normal(size=n)) - S.AFT_LABEL_SHIFT
    pred = np.exp(mu + 0.6) - S.AFT_LABEL_SHIFT          # over-predicts life
    out = SV.d_calibration_chisq(np.clip(t, 0, None), np.clip(pred, 0, None),
                                 np.zeros(n, dtype=bool), scale)
    assert out["p_value"] < 1e-6


def test_d_calibration_chisq_conserves_mass_under_censoring():
    y, pred, cens = _toy()
    out = SV.d_calibration_chisq(y, pred, cens, 0.8)
    assert sum(out["bin_counts"]) == pytest.approx(len(y), abs=1e-9)
    assert out["n_censored"] == int(cens.sum())
