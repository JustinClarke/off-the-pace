"""The within-stint attribution, proven on data whose answer is planted in advance.

Open item 15 asks what the within-stint signal *is*. The whole answer rests on one
operation — replacing a feature with its per-stint summary — being exactly what it claims:
between-stint information preserved, within-stint variation removed, nothing else touched.
If flattening also perturbs the between-stint part, every `flatten_delta` downstream is a
sum of two effects again and the module has reproduced the defect it exists to fix.

So the operation is proven first (variance identities on data with a known ICC), and only
then the decomposition it feeds (a planted signal that is *known* to be within-stint, and
a second one known to be between-stint, recovered separately from the same fit).

Everything here runs on synthetic data. No warehouse, no artefacts, no skips.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.src import attribution as A
from ml.src import ceiling as CE
from ml.src import schema as S

RNG_SEED = S.RANDOM_STATE
N_GROUPS, PER_GROUP = 600, 19


def _stints(n_groups: int = N_GROUPS, per_group: int = PER_GROUP):
    return np.repeat(np.arange(n_groups), per_group)


def _feature(icc: float, stints: np.ndarray, seed: int = RNG_SEED) -> np.ndarray:
    """A column with an exactly-specified between-stint share."""
    rng = np.random.default_rng(seed)
    k = len(np.unique(stints))
    per = len(stints) // k
    return (np.repeat(rng.normal(0.0, np.sqrt(icc), k), per)
            + rng.normal(0.0, np.sqrt(1.0 - icc), len(stints)))


# ─── The flatten operation itself ───────────────────────────────────────────────
def test_flatten_makes_a_column_stint_constant():
    """After flattening, the between-stint share is 1.0 by construction."""
    g = _stints()
    X = pd.DataFrame({"f": _feature(0.10, g)})
    Xf = A.stint_flatten(X, g, ["f"])
    assert CE.variance_components(Xf["f"].to_numpy(), g).share == pytest.approx(1.0, abs=1e-6)
    assert Xf.groupby(g)["f"].nunique().max() == 1


def test_flatten_preserves_the_between_stint_part_exactly():
    """The identity the whole module rests on: per-stint means are untouched.

    This is the test that makes `flatten_delta` a *within-stint* quantity. If the
    per-stint means moved, the refit would be seeing a different stint-level problem too
    and the delta would mix the two components — exactly the conflation that `drop`
    suffers from and that this module was written to separate.
    """
    g = _stints()
    X = pd.DataFrame({"f": _feature(0.10, g), "other": _feature(0.30, g, seed=7)})
    Xf = A.stint_flatten(X, g, ["f"])
    before = X.groupby(g)["f"].mean().to_numpy()
    after = Xf.groupby(g)["f"].mean().to_numpy()
    np.testing.assert_allclose(before, after, rtol=0, atol=1e-12)
    # And the column that was not named is bit-for-bit untouched.
    pd.testing.assert_series_equal(X["other"], Xf["other"])


def test_flatten_removes_exactly_the_within_stint_variance():
    """sigma_w^2 goes to zero, and sigma_b^2 inflates by a *known, exact* amount.

    The flattened column is built from per-stint **means**, and a mean of `n` laps is a
    noisy estimate of the stint effect: it carries `sigma_w^2 / n0` of within-stint
    scatter with it. So the ANOVA reads the flattened column as having
    `sigma_b^2 + sigma_w^2 / n0` of between-stint variance, not `sigma_b^2`. That is the
    *same* inflation Phase 6 corrected in Corrections §12 — the naive estimator's bias,
    reappearing here because a stint mean is exactly what the naive estimator averages.

    It is asserted as an identity rather than smoothed under a tolerance, because the
    two consequences pull in opposite directions and both need to be on the record:

    * It does **not** leak within-stint information into the flattened arm. The column is
      stint-constant by construction (ICC 1.0, the test above), so `flatten_delta` stays
      a clean within-stint quantity — which is all the decomposition needs.
    * It does mean the flattened arm sees a slightly *noisier* stint-level signal than a
      true stint effect would be, which can make `flatten_delta` marginally optimistic
      for a feature whose stint-level part is itself weak. At ~19 laps the inflation is
      `sigma_w^2 / 19`.
    """
    g = _stints(n_groups=3000)
    X = pd.DataFrame({"f": _feature(0.25, g)})
    vc0 = CE.variance_components(X["f"].to_numpy(), g)
    vc1 = CE.variance_components(A.stint_flatten(X, g, ["f"])["f"].to_numpy(), g)
    assert vc1.sigma_w2 == pytest.approx(0.0, abs=1e-9)
    assert vc1.sigma_b2 == pytest.approx(vc0.sigma_b2 + vc0.sigma_w2 / vc0.n0, rel=1e-9)


def test_flatten_is_a_noop_on_an_already_stint_constant_column():
    """The cost control and the interpretation guard, in one property.

    A constant-within-stint feature has no within-stint variation to remove, so a zero
    `flatten_delta` for it is arithmetic rather than evidence about the model. `noop`
    records which zeros are which.
    """
    g = _stints()
    rng = np.random.default_rng(RNG_SEED)
    const = np.repeat(rng.normal(size=N_GROUPS), PER_GROUP)
    X = pd.DataFrame({"f": const})
    Xf = A.stint_flatten(X, g, ["f"])
    pd.testing.assert_frame_equal(X, Xf)
    assert A.flatten_is_noop(X, Xf, ["f"])


def test_categoricals_are_moded_not_averaged():
    """Averaging ordinal codes for SOFT and HARD invents MEDIUM. The mode cannot."""
    g = np.array([0, 0, 0, 1, 1, 1])
    # `compound` is in S.CATEGORICAL_COLUMNS, so it must take the mode path.
    X = pd.DataFrame({"compound": [0.0, 0.0, 2.0, 1.0, 1.0, 1.0]})
    Xf = A.stint_flatten(X, g, ["compound"])
    assert set(np.unique(Xf["compound"])) <= set(np.unique(X["compound"])), \
        "flattening invented a compound code that does not exist in the column"
    assert list(Xf["compound"]) == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]


def test_booleans_stay_boolean_valued():
    g = np.array([0, 0, 0, 0])
    X = pd.DataFrame({"cliff_onset_passed": [1.0, 1.0, 0.0, 1.0]})
    Xf = A.stint_flatten(X, g, ["cliff_onset_passed"])
    assert set(np.unique(Xf["cliff_onset_passed"])) <= {0.0, 1.0}
    assert list(Xf["cliff_onset_passed"]) == [1.0] * 4


def test_all_nan_stint_stays_nan():
    """XGBoost's native-missing path must look the same on both arms of the ablation."""
    g = np.array([0, 0, 1, 1])
    X = pd.DataFrame({"f": [np.nan, np.nan, 1.0, 3.0]})
    Xf = A.stint_flatten(X, g, ["f"])
    assert np.isnan(Xf["f"].to_numpy()[:2]).all()
    assert Xf["f"].to_numpy()[2:].tolist() == [2.0, 2.0]


def test_misaligned_stint_ids_raise():
    X = pd.DataFrame({"f": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="must align"):
        A.stint_flatten(X, np.array([0, 1]), ["f"])


# ─── The decomposition the operation feeds ──────────────────────────────────────
def _linear_harness():
    """A least-squares fit/score pair. The module takes callables, so the decomposition
    can be proven without XGBoost in the loop — the property under test is the
    between/within separation, not the learner."""
    def fit(X, y):
        A_ = np.nan_to_num(X.to_numpy(dtype=np.float64))
        return np.linalg.lstsq(np.c_[A_, np.ones(len(A_))], y, rcond=None)[0]

    def score(y, model, X):
        A_ = np.nan_to_num(X.to_numpy(dtype=np.float64))
        return float(np.sqrt(np.mean((y - np.c_[A_, np.ones(len(A_))] @ model) ** 2)))
    return fit, score


def test_ablation_separates_a_within_stint_driver_from_a_between_stint_one():
    """The load-bearing test for item 15's method.

    Two planted features, both carrying real signal, differing only in *where* their
    variance lives. `within` is per-lap (ICC 0.02); `between` is stint-level (ICC 0.98).
    A drop removes each one's contribution and cannot tell them apart. Flattening must:
    cost almost the whole contribution for `within`, and almost none of it for `between`.
    """
    g = _stints(n_groups=1500)
    within = _feature(0.02, g, seed=1)
    between = _feature(0.98, g, seed=2)
    rng = np.random.default_rng(RNG_SEED)
    y = 3.0 * within + 3.0 * between + rng.normal(0, 0.25, len(g))
    X = pd.DataFrame({"within": within, "between": between})
    fit, score = _linear_harness()

    rows = A.within_stint_ablation(
        fit, score, X, y, g, X, y, g, higher_is_better=False,
        units={"within": ("within",), "between": ("between",)})
    by = {r["unit"]: r for r in rows}

    # Both features matter, and a drop says only that.
    assert by["within"]["drop_delta"] > 0.1 and by["between"]["drop_delta"] > 0.1

    # Flattening is the discriminator.
    assert by["within"]["flatten_share"] > 0.9, (
        "flattening a per-lap driver should cost nearly its whole contribution; "
        f"share={by['within']['flatten_share']}")
    assert by["between"]["flatten_share"] < 0.1, (
        "flattening a stint-level driver should cost almost nothing; "
        f"share={by['between']['flatten_share']}")
    assert by["between"]["flatten_is_noop"] is False  # ICC 0.98, not 1.0 — it does vary


def test_a_pure_noise_feature_shows_no_within_stint_contribution():
    g = _stints(n_groups=1200)
    real = _feature(0.5, g, seed=3)
    noise = _feature(0.05, g, seed=4)
    rng = np.random.default_rng(RNG_SEED)
    y = 2.0 * real + rng.normal(0, 0.3, len(g))
    X = pd.DataFrame({"real": real, "noise": noise})
    fit, score = _linear_harness()
    rows = A.within_stint_ablation(fit, score, X, y, g, X, y, g,
                                   higher_is_better=False,
                                   units={"noise": ("noise",)})
    assert abs([r for r in rows if r["unit"] == "noise"][0]["flatten_delta"]) < 0.01


def test_higher_is_better_orientation_is_positive_for_a_real_contribution():
    """macro-F1 is the one headline that goes up. Deltas must stay oriented so that
    positive means 'the model got worse without it' on both directions of metric."""
    g = _stints(n_groups=800)
    within = _feature(0.02, g, seed=5)
    rng = np.random.default_rng(RNG_SEED)
    y = 3.0 * within + rng.normal(0, 0.2, len(g))
    X = pd.DataFrame({"within": within})
    fit, rmse = _linear_harness()

    def neg_rmse(y_, m, X_):     # a higher-is-better metric over the same fit
        return -rmse(y_, m, X_)

    lo = A.within_stint_ablation(fit, rmse, X, y, g, X, y, g, False,
                                 {"within": ("within",)})
    hi = A.within_stint_ablation(fit, neg_rmse, X, y, g, X, y, g, True,
                                 {"within": ("within",)})
    a = [r for r in lo if r["unit"] == "within"][0]["flatten_delta"]
    b = [r for r in hi if r["unit"] == "within"][0]["flatten_delta"]
    assert a > 0 and b > 0
    assert a == pytest.approx(b, rel=1e-9)


# ─── Causality of the flatten (Corrections §22) ─────────────────────────────────
def _laps(n_groups: int = N_GROUPS, per_group: int = PER_GROUP):
    return np.tile(np.arange(1, per_group + 1), n_groups).astype(float)


def test_causal_mean_is_the_prefix_mean():
    g, lap = _stints(3, 5), _laps(3, 5)
    v = np.arange(15, dtype=float)
    X = pd.DataFrame({"f": v})
    got = A.causal_stint_mean(X, g, lap, ["f"])["f"].to_numpy()
    want = np.concatenate([np.cumsum(v[a:a + 5]) / np.arange(1, 6) for a in (0, 5, 10)])
    assert got == pytest.approx(want)


def test_causal_mean_meets_the_flatten_at_the_last_lap_and_the_raw_value_at_the_first():
    """The two operations agree exactly where the future is empty.

    The last lap of a stint has no later lap, so its prefix *is* the whole stint; the
    first has no earlier lap, so its prefix is itself. Everything between them is where
    `stint_flatten` is using laps the row could not have seen, and that gap is the whole
    subject of §22.
    """
    g, lap = _stints(200, 7), _laps(200, 7)
    X = pd.DataFrame({"f": _feature(0.3, g)})
    c = A.causal_stint_mean(X, g, lap, ["f"])["f"].to_numpy()
    f = A.stint_flatten(X, g, ["f"])["f"].to_numpy()
    last, first = lap == 7, lap == 1
    assert c[last] == pytest.approx(f[last], abs=1e-9)
    assert c[first] == pytest.approx(X["f"].to_numpy()[first], abs=1e-12)
    assert not np.allclose(c, f)          # and they differ everywhere else


def test_causal_mean_cannot_see_a_later_lap():
    """The liveness proof for causality: move the last lap, and only the last lap moves.

    A summary that changed an earlier row when a later lap changed would be look-ahead
    wearing a causal name, and every conclusion drawn from the causal arm would be void.
    """
    g, lap = _stints(50, 6), _laps(50, 6)
    X = pd.DataFrame({"f": _feature(0.2, g)})
    before = A.causal_stint_mean(X, g, lap, ["f"])["f"].to_numpy()
    X2 = X.copy()
    X2.loc[lap == 6, "f"] = X2.loc[lap == 6, "f"] + 100.0
    after = A.causal_stint_mean(X2, g, lap, ["f"])["f"].to_numpy()
    assert after[lap < 6] == pytest.approx(before[lap < 6], abs=1e-12)
    assert not np.allclose(after[lap == 6], before[lap == 6])
    # the same perturbation moves every row of the full-stint flatten
    fb = A.stint_flatten(X, g, ["f"])["f"].to_numpy()
    fa = A.stint_flatten(X2, g, ["f"])["f"].to_numpy()
    assert not np.allclose(fa[lap == 1], fb[lap == 1])


def test_future_mean_is_the_suffix_mean():
    g, lap = _stints(3, 5), _laps(3, 5)
    v = np.arange(15, dtype=float)
    X = pd.DataFrame({"f": v})
    got = A.future_stint_mean(X, g, lap, ["f"])["f"].to_numpy()
    want = np.concatenate([[v[a + k:a + 5].mean() for k in range(5)] for a in (0, 5, 10)])
    assert got == pytest.approx(want)
    # meets the full-stint mean at lap 1, where the suffix is the whole stint
    f = A.stint_flatten(X, g, ["f"])["f"].to_numpy()
    assert got[lap == 1] == pytest.approx(f[lap == 1], abs=1e-9)


def test_causal_mode_is_a_running_mode_on_discrete_columns():
    """Booleans and ordinal categoricals get a running mode, not a running mean, for the
    same reason `stint_flatten` modes them: the mean of two codes is a third code."""
    g, lap = np.zeros(5, dtype=int), np.arange(1, 6, dtype=float)
    X = pd.DataFrame({"cliff_onset_passed": np.array([1.0, 1.0, 0.0, 0.0, 0.0])})
    got = A.causal_stint_mean(X, g, lap, ["cliff_onset_passed"])["cliff_onset_passed"].to_numpy()
    # counts after each lap: 1 / 1,1 / 1,1+0 / tie 2-2 -> lowest value / 0 leads
    assert got.tolist() == [1.0, 1.0, 1.0, 0.0, 0.0]
    assert set(np.unique(got)) <= {0.0, 1.0}      # stays inside the column's value set


def test_causal_summary_is_invariant_to_row_order():
    """Rows arrive in warehouse order, not stint order. The summary is defined by
    (stint, lap) and must not depend on how the frame happens to be sorted."""
    g, lap = _stints(40, 5), _laps(40, 5)
    X = pd.DataFrame({"f": _feature(0.25, g)})
    straight = A.causal_stint_mean(X, g, lap, ["f"])["f"].to_numpy()
    rng = np.random.default_rng(RNG_SEED)
    perm = rng.permutation(len(g))
    shuffled = A.causal_stint_mean(X.iloc[perm].reset_index(drop=True),
                                   g[perm], lap[perm], ["f"])["f"].to_numpy()
    back = np.empty_like(straight)
    back[perm] = shuffled
    assert back == pytest.approx(straight, abs=1e-12)


def test_causal_summary_rejects_misaligned_inputs():
    X = pd.DataFrame({"f": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="must align"):
        A.causal_stint_mean(X, np.array([0, 0]), np.array([1.0, 2.0]), ["f"])


def _causality_case(target_kind: str, n_groups: int = 800, per_group: int = 9):
    """Plant a target that is reachable only from the future, or only from the past."""
    g, lap = _stints(n_groups, per_group), _laps(n_groups, per_group)
    f = _feature(0.05, g, seed=11)
    X = pd.DataFrame({"f": f})
    fut = A.future_stint_mean(X, g, lap, ["f"])["f"].to_numpy()
    past = A.causal_stint_mean(X, g, lap, ["f"])["f"].to_numpy()
    rng = np.random.default_rng(RNG_SEED)
    driver = fut if target_kind == "future" else past
    y = 3.0 * driver + rng.normal(0, 0.15, len(g))
    return X, y, g, lap


def test_flatten_causality_names_a_look_ahead_result_as_unreachable():
    """§22's finding, planted and recovered.

    The target here depends on the *rest of the stint* — the shape a forward-looking
    label has. Flattening therefore helps a great deal, and it would be read as "within-
    stint variation is hurting the model, flatten it and ship". The causal arm is what
    refuses that reading: the same summary over laps 1..t recovers almost none of it,
    because the information was never in the past.
    """
    X, y, g, lap = _causality_case("future")
    fit, score = _linear_harness()
    base = score(y, fit(X, y), X)
    Xf = A.stint_flatten(X, g, ["f"])
    flat = score(y, fit(Xf, y), Xf) - base

    r = A.flatten_causality(fit, score, X, y, g, lap, X, y, g, lap,
                            False, ("f",), base, flat, noise=0.01)
    assert flat < -0.05, "the planted flatten win must be large before it can be refused"
    assert r["causally_reachable"] is False
    assert r["lookahead_share"] > 0.8
    assert r["future_delta"] < flat, (
        "an arm built only from laps at or after the row should beat the full-stint "
        "mean here — that is what identifies the ingredient as the future")


def test_flatten_causality_confirms_a_result_the_past_can_supply():
    """The converse, and the reason the check is a discriminator rather than a veto: a
    flatten whose value is in the laps already run comes back reachable."""
    X, y, g, lap = _causality_case("past")
    fit, score = _linear_harness()
    base = score(y, fit(X, y), X)
    Xf = A.stint_flatten(X, g, ["f"])
    flat = score(y, fit(Xf, y), Xf) - base

    r = A.flatten_causality(fit, score, X, y, g, lap, X, y, g, lap,
                            False, ("f",), base, flat, noise=0.01)
    assert r["causally_reachable"] is True
    assert r["causal_delta"] < flat, "the causal summary is the better one here"


def test_rank_preservation_flags_a_counter_and_clears_a_per_lap_column():
    """The causal arm's own null check.

    `mean(1..t) = (t+1)/2` is a monotone relabelling of `t`, and a tree splits on global
    thresholds, so for a counter the causal summary is the same feature under another
    name. Its `causal_delta` is then ~0 no matter what the column carries, and reading a
    verdict off that number states the artefact as a finding.
    """
    g, lap = _stints(300, 8), _laps(300, 8)
    counter = pd.DataFrame({"age_in_stint": lap})
    noisy = pd.DataFrame({"f": _feature(0.05, g, seed=21)})
    for X, expect in ((counter, True), (noisy, False)):
        Xc = A.causal_stint_mean(X, g, lap, list(X.columns))
        r = A.rank_preservation(X, Xc, list(X.columns))
        assert r["degenerate"] is expect, (X.columns[0], r["median"])
    assert A.rank_preservation(counter, A.causal_stint_mean(counter, g, lap, ["age_in_stint"]),
                               ["age_in_stint"])["median"] == pytest.approx(1.0, abs=1e-9)


def test_rank_preservation_ignores_columns_the_transform_left_alone():
    """A stint-constant column is a no-op, not a relabelling. Counting it would drag the
    median to 1.0 and flag every unit that happens to contain one."""
    g, lap = _stints(200, 6), _laps(200, 6)
    const = np.repeat(np.arange(200, dtype=float), 6)
    X = pd.DataFrame({"stint_constant": const, "f": _feature(0.05, g, seed=22)})
    Xc = A.causal_stint_mean(X, g, lap, ["stint_constant", "f"])
    r = A.rank_preservation(X, Xc, ["stint_constant", "f"])
    assert r["n_changed_columns"] == 1 and "stint_constant" not in r["per_column"]
    assert r["degenerate"] is False


def test_flatten_causality_withholds_a_verdict_on_a_degenerate_arm():
    """No verdict is better than a verdict read off an arithmetic zero."""
    g, lap = _stints(400, 8), _laps(400, 8)
    X = pd.DataFrame({"age_in_stint": lap, "f": _feature(0.4, g, seed=23)})
    rng = np.random.default_rng(RNG_SEED)
    y = 2.0 * lap + rng.normal(0, 0.3, len(g))
    fit, score = _linear_harness()
    base = score(y, fit(X, y), X)
    r = A.flatten_causality(fit, score, X, y, g, lap, X, y, g, lap,
                            False, ("age_in_stint",), base, 0.5, noise=0.01)
    assert r["causal_rank_preservation"]["degenerate"] is True
    assert r["causally_reachable"] is None, (
        "a near-monotone relabelling cannot support a reachability verdict")
    assert r["causal_delta"] is not None      # the number is still reported


def test_flatten_causality_skips_the_future_arm_on_discrete_columns():
    """A running mode over future laps is not defined and is not needed: the future arm
    exists to identify the ingredient, so it runs on the continuous members and reports
    how many it used rather than raising."""
    g, lap = _stints(200, 6), _laps(200, 6)
    X = pd.DataFrame({"f": _feature(0.1, g, seed=12),
                      "cliff_onset_passed": (_feature(0.1, g, seed=13) > 0).astype(float)})
    rng = np.random.default_rng(RNG_SEED)
    y = 2.0 * X["f"].to_numpy() + rng.normal(0, 0.2, len(g))
    fit, score = _linear_harness()
    base = score(y, fit(X, y), X)
    r = A.flatten_causality(fit, score, X, y, g, lap, X, y, g, lap,
                            False, ("f", "cliff_onset_passed"), base, -0.2, noise=0.01)
    assert r["n_future_only_features"] == 1
    assert r["future_delta"] is not None


# ─── Selection, prediction split, roll-up ───────────────────────────────────────
def test_per_lap_features_selects_on_the_corrected_icc():
    g = _stints(n_groups=1500)
    X = pd.DataFrame({"perlap": _feature(0.05, g, seed=6),
                      "stintlevel": _feature(0.95, g, seed=7)})
    sel = A.per_lap_features(X, g)
    assert "perlap" in sel and "stintlevel" not in sel
    assert sel["perlap"] == pytest.approx(0.05, abs=0.02)


def test_prediction_variance_split_reads_a_stint_constant_predictor_as_one():
    g = _stints()
    y = _feature(0.03, g, seed=8)
    stint_constant = pd.Series(y).groupby(g).transform("mean").to_numpy()
    out = A.prediction_variance_split(stint_constant, y, g)
    assert out["prediction_between_stint_share"] == pytest.approx(1.0, abs=1e-6)
    assert out["target_between_stint_share"] == pytest.approx(0.03, abs=0.02)


def test_every_contract_feature_has_a_channel():
    """A 43rd feature must not land unclassified — the roll-up would silently lose it."""
    assert A.unmapped_features() == (), (
        f"features with no channel in attribution.CHANNELS: {A.unmapped_features()}")
    assert sum(len(v) for v in A.CHANNELS.values()) == len(S.FEATURE_COLUMNS)


def test_channels_are_disjoint():
    seen: dict[str, str] = {}
    for ch, cols in A.CHANNELS.items():
        for c in cols:
            assert c not in seen, f"{c} is in both {seen.get(c)} and {ch}"
            seen[c] = ch


def test_channel_rollup_shares_sum_to_one():
    rows = [{"unit": "push_residual", "kind": "feature", "flatten_delta": 0.010,
             "flatten_is_noop": False},
            {"unit": "dirty_air_share_lap", "kind": "feature", "flatten_delta": 0.005,
             "flatten_is_noop": False},
            {"unit": "lap_in_stint", "kind": "feature", "flatten_delta": 0.005,
             "flatten_is_noop": False},
            {"unit": "<none>", "kind": "reference", "flatten_delta": 0.0,
             "flatten_is_noop": False}]
    roll = A.channel_rollup(rows)
    assert sum(r["share_of_within_stint"] for r in roll) == pytest.approx(1.0)
    assert roll[0]["channel"] == "driver_push"   # 0.010 is the largest


# ─── The noise floor under every delta ──────────────────────────────────────────
def test_refit_noise_floor_is_zero_for_a_deterministic_learner():
    """A learner that ignores the seed has no refit jitter, so nothing is excused by it."""
    g = _stints(n_groups=200)
    X = pd.DataFrame({"f": _feature(0.2, g)})
    y = 2.0 * X["f"].to_numpy()
    fit, score = _linear_harness()
    out = A.refit_noise_floor(lambda seed: fit(X, y), score, X, y, seeds=(1, 2, 3))
    assert out["headline_sd"] == pytest.approx(0.0, abs=1e-12)
    assert out["delta_noise_2sd"] == pytest.approx(0.0, abs=1e-12)
    assert out["n_seeds"] == 3


def test_refit_noise_floor_scales_a_difference_by_root_two():
    """A `flatten_delta` is a difference of two independently-seeded fits, so the band it
    must clear is `sqrt(2)` wider than the headline's own spread — not equal to it."""
    calls = iter([1.0, 2.0, 3.0])
    out = A.refit_noise_floor(lambda s: None, lambda y, m, X: next(calls),
                              pd.DataFrame({"f": [0.0]}), np.array([0.0]),
                              seeds=(1, 2, 3))
    sd = float(np.std([1.0, 2.0, 3.0], ddof=1))
    assert out["headline_sd"] == pytest.approx(sd)
    assert out["delta_noise_1sd"] == pytest.approx(np.sqrt(2) * sd)
    assert out["delta_noise_2sd"] == pytest.approx(2 * np.sqrt(2) * sd)


def test_annotate_noise_marks_only_deltas_inside_the_band():
    rows = [{"drop_delta": 0.10, "flatten_delta": 0.001},
            {"drop_delta": None, "flatten_delta": 0.20}]
    A.annotate_noise(rows, delta_noise_2sd=0.01)
    assert rows[0]["drop_inside_noise"] is False
    assert rows[0]["flatten_inside_noise"] is True
    assert rows[1]["drop_inside_noise"] is None      # nothing measured, not "clean"
    assert rows[1]["flatten_inside_noise"] is False


def test_annotate_noise_is_null_when_the_floor_could_not_be_measured():
    """An absent noise floor must not read as 'this delta is real'."""
    rows = [{"drop_delta": 0.10, "flatten_delta": 0.001}]
    A.annotate_noise(rows, delta_noise_2sd=None)
    assert rows[0]["drop_inside_noise"] is None
    assert rows[0]["flatten_inside_noise"] is None
