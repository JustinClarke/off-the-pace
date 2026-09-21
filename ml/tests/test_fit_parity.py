"""Every fit path in the layer fits the way production fits (Phase 2 finding 1).

Three places build a booster: `train.py` (the shipped one), `tune.py` (the search) and
`evaluate.py` (the refit every published number is measured on). They must agree about
the fit, or the model that is searched, the model that is measured and the model that is
shipped are three different models wearing one name. Both disagreements this file locks
down were live in the tree until Phase 7.

**The search.** `tune.py`'s objective used to call `model.fit` directly, and deliberately did not pass
`meta`. `train._sample_weight` needed `meta` to produce the quantile trio's IPW survival
weights, so the search scored p10/p50/p90 **unweighted** while `train._fit` refitted them
**weighted** -- the params in `ml/models/degradation_regressor_p*_best_params.json` were
selected against an objective the refit did not use.

**08o dropped that weight from the training path**, so the trio is now fitted uniformly
everywhere. That changes the *value* these tests assert and not one word of the contract:
the search, the refit and the eval must still agree, and the way they are held to it is
still recording all three on identical rows rather than reading any of them. The tests
below were flipped, not deleted, because a weighting contract with no weights in it is
exactly the state in which the next weighting change slips through unnoticed.

The repair is that the fold fit goes through `train._fit`, the same function the refit
calls. These tests assert the resulting property rather than the call: for every
production target, the weights (and the AFT censoring flag) the search fits with are
exactly the ones the refit would apply to the same rows. `test_the_defect_was_real`
keeps the rest from being vacuous by showing the two paths genuinely disagreed.

**The identity of a fit.** A third disagreement is possible without any of the three
functions differing: the same artefact name, refitted against a different target column.
Phase 7 moved `DEGRADATION_TARGET`, so `make ml-retrain` would have overwritten the
shipped v6 boosters with five-lap models under the next-lap name. `train._guard_target_change`
refuses that, and the last tests here hold it.

**The evaluation.** `evaluate._fit` had the identical hole, one layer further on, and
it is the one that reaches print: the eval models behind every headline, ablation,
learning curve and `beats_baseline` interval were refit UNWEIGHTED against shipped
boosters that were weighted. Measured on the 1-lap target the gap is 0.15%/0.45%/-0.22%
pinball (p10/p50/p90) and on the 5-lap target it is +4.42% at p10 -- small, and small is
not the point: the number in the card described a model nobody trained.

The bundle here is synthetic on purpose: the contract under test is between these
functions, not between the layer and the warehouse, so it holds with no mart present.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from ml.src import evaluate as E
from ml.src import schema as S
from ml.src import train as T
from ml.src import tune as TU

SEASONS = (2019, 2020, 2021)
N_PER_SEASON = 80


def _y_for(spec: S.TargetSpec, n: int, rng: np.random.Generator) -> np.ndarray:
    if spec.kind == "classification":
        # Every class present in every fold, and deliberately imbalanced (1:1:1:5,
        # roughly the real label's shape) so balanced weights are not all 1.0.
        block = [0, 1, 2, 3, 3, 3, 3, 3]
        return np.tile(np.asarray(block), n // len(block) + 1)[:n]
    if spec.kind == "survival":
        return rng.integers(0, 25, size=n).astype("float64")
    return rng.normal(size=n)


def _bundle(spec: S.TargetSpec):
    """A FeatureBundle with the two columns the weighting contract turns on:
    `survival_weight` (IPW, quantile) and the censoring flag (AFT)."""
    rng = np.random.default_rng(S.RANDOM_STATE)
    n = N_PER_SEASON * len(SEASONS)
    X = pd.DataFrame(
        {c: rng.normal(size=n).astype("float32") for c in S.FEATURE_COLUMNS})
    y = pd.Series(_y_for(spec, n, rng))
    seasons = pd.Series(np.repeat(np.asarray(SEASONS), N_PER_SEASON))
    meta = pd.DataFrame({
        "lap_id": [f"l{i}" for i in range(n)],
        "stint_id": [f"s{i // 4}" for i in range(n)],
        "race_year": seasons,
        # Distinct per row so a mis-sliced weight vector cannot match by luck.
        "survival_weight": (1.0 + rng.random(n)).astype("float32"),
        S.STINT_LIFE_CENSOR_COLUMN: rng.random(n) < 0.45,
        S.STINT_LIFE_TARGET: y if spec.kind == "survival" else np.zeros(n),
        "stint_length_laps": np.full(n, 30.0),
    })
    from ml.src.features import FeatureBundle
    return FeatureBundle(
        target_name=spec.name, X_train=X, y_train=y, X_holdout=X.iloc[:0],
        y_holdout=y.iloc[:0], groups_train=seasons, meta_train=meta,
        meta_holdout=meta.iloc[:0], encoders={}, fingerprint="synthetic",
        feature_columns=list(S.FEATURE_COLUMNS), holdout_season=max(SEASONS) + 1,
        training_seasons=list(SEASONS),
    )


class _Recorder:
    """Stands in for the booster: records what it was fitted with, predicts a constant."""

    def __init__(self, log: list):
        self._log = log

    def fit(self, X, y, sample_weight=None, **kwargs):
        self._log.append({"rows": np.asarray(X.index), "sample_weight": sample_weight,
                          "kwargs": kwargs})
        return self

    def predict(self, X):
        return np.ones(len(X), dtype="float64")


@pytest.fixture
def search(monkeypatch, tmp_path):
    """Run one search trial for `target` and return (fit calls, bundle, folds)."""
    def _run(target: str, *, folds: int = 2):
        spec = S.TARGET_BY_NAME[target]
        bundle = _bundle(spec)
        calls: list[dict] = []
        monkeypatch.setattr(TU.F, "load_features", lambda **kw: bundle)
        monkeypatch.setattr(T, "_make_model", lambda spec, params: _Recorder(calls))
        # The closing production refit is a separate contract; this is the search.
        monkeypatch.setattr(T, "train_one", lambda *a, **kw: {})
        monkeypatch.setattr(TU, "STUDIES_DIR", tmp_path / "studies")
        monkeypatch.setattr(TU, "MODELS_DIR", tmp_path)
        TU.tune_one(target, trials=1, folds=folds, version="test")
        fold_idx = list(T._season_folds(bundle.groups_train.to_numpy(),
                                        bundle.training_seasons, folds))
        return calls, bundle, fold_idx
    return _run


@pytest.mark.parametrize("target", [t.name for t in S.PRODUCTION_TARGETS])
def test_search_fits_with_the_weights_the_refit_applies(search, target):
    """Phase 2 finding 1: per fold, the search's weights == the refit's weights.

    Asserted per fold rather than in aggregate, because the failure this replaced
    (weights computed from the full training frame, not the fold's rows) matches on
    length and not on values."""
    spec = S.TARGET_BY_NAME[target]
    calls, bundle, fold_idx = search(target)
    assert len(calls) == len(fold_idx), "one fit per fold"

    y = bundle.y_train.to_numpy()
    for call, (tr, _) in zip(calls, fold_idx):
        expected = T._sample_weight(spec, y[tr], bundle.meta_train.iloc[tr])
        got = call["sample_weight"]
        assert np.array_equal(call["rows"], tr), "the fold's own rows, in order"
        if expected is None:
            assert got is None
        else:
            assert got is not None, "the search dropped weights the refit applies"
            np.testing.assert_allclose(got, expected, rtol=0, atol=0)


@pytest.mark.parametrize("target", ["degradation_regressor_p10",
                                    "degradation_regressor_p50",
                                    "degradation_regressor_p90"])
def test_quantile_search_carries_no_row_weights(search, target):
    """The regression itself, post-08o: the trio searches UNWEIGHTED, per fold.

    08o measured IPW against uniform and dropped it, so the search must stop applying
    it too -- and this is the assertion that says so on the fold's own rows, rather
    than trusting that one shared code path implies one shared weighting.

    Pinned as `is None` and not merely "not the IPW vector": a constant weight vector
    would fit identically and still mean the search had grown a weighting scheme of its
    own that nothing downstream knows about."""
    calls, bundle, fold_idx = search(target)
    for call, (tr, _) in zip(calls, fold_idx):
        assert call["sample_weight"] is None, "08o dropped the trio's IPW weights"


def test_survival_search_passes_the_censoring_flag(search):
    """AFT carries censoring in the label, so its weight stays None and the flag
    must arrive instead -- sliced to the fold, like the weights."""
    calls, bundle, fold_idx = search("stint_life_regressor")
    cens = bundle.meta_train[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
    for call, (tr, _) in zip(calls, fold_idx):
        assert call["sample_weight"] is None, "weighting censoring counts it twice"
        assert np.array_equal(call["kwargs"]["is_censored"], cens[tr])


def test_classifier_search_carries_balanced_class_weights(search):
    """The classifier's weights never depended on meta, which is why the defect was
    quantile-only. Pinned so a future weighting change cannot pass silently."""
    calls, bundle, fold_idx = search("cliff_classifier")
    y = bundle.y_train.to_numpy()
    for call, (tr, _) in zip(calls, fold_idx):
        np.testing.assert_allclose(
            call["sample_weight"], T._sample_weight(S.TARGET_BY_NAME["cliff_classifier"], y[tr]),
            rtol=0, atol=0)
        assert len(np.unique(call["sample_weight"])) > 1, "balanced weights are not constant"


def test_the_drop_is_a_decision_not_a_missing_column(search):
    """Keeps the tests above from being vacuous, in the direction that now matters.

    Before 08o the anti-vacuity risk was that the two paths agreed by accident. After
    it, every weight assertion in this file is `is None`, and `is None` is also what you
    get if `survival_weight` quietly stopped reaching `meta` -- a mart change, a rename,
    a dropped IDENTIFIER_COLUMN. Those are different failures with identical test
    output, and only one of them is the ruling 08o took.

    So assert the column is still there, still varies row to row, still reaches
    `train._fit` as meta, and is still ignored. That is the difference between "we
    decided not to weight" and "we lost the weights"."""
    spec = S.TARGET_BY_NAME["degradation_regressor_p50"]
    _, bundle, fold_idx = search("degradation_regressor_p50")
    y = bundle.y_train.to_numpy()
    tr = fold_idx[0][0]
    meta_tr = bundle.meta_train.iloc[tr]

    assert "survival_weight" in meta_tr.columns, "the column still reaches train._fit"
    assert float(np.std(meta_tr["survival_weight"].to_numpy())) > 0, \
        "a constant column would make 'ignored' and 'absent' indistinguishable"
    assert T._sample_weight(spec, y[tr], meta_tr) is None, "handed the weights, declines them"
    assert T._sample_weight(spec, y[tr]) is None, "and does not depend on meta to decline"
    assert "survival_weight" in S.IDENTIFIER_COLUMNS, "08o DoD 4: the contract does not move"
    assert "survival_weight" not in S.FEATURE_COLUMNS, "never a predictor, under any outcome"


# ─── The evaluation path ────────────────────────────────────────────────────────
@pytest.mark.parametrize("target", [t.name for t in S.PRODUCTION_TARGETS])
def test_evaluate_refits_with_the_weights_production_ships(monkeypatch, target):
    """`evaluate._fit` and `train._fit` must put the same weights on the same rows.

    Asserted by recording both, on identical rows, rather than by reading either: this
    is the number the model card publishes, and "it looks like it passes meta" is what
    the old code looked like too."""
    spec = S.TARGET_BY_NAME[target]
    bundle = _bundle(spec)
    calls: list[dict] = []
    monkeypatch.setattr(T, "_make_model", lambda spec, params: _Recorder(calls))

    X, y, meta = bundle.X_train, bundle.y_train.to_numpy(), bundle.meta_train
    cens = meta[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
    E._fit(spec, {}, X, y, cens, E._row_weights(spec, meta))
    T._fit(_Recorder(calls), spec, X, y, meta)

    from_eval, from_train = calls[0]["sample_weight"], calls[1]["sample_weight"]
    if from_train is None:
        assert from_eval is None
    else:
        np.testing.assert_allclose(from_eval, from_train, rtol=0, atol=0)


@pytest.mark.parametrize("target", ["degradation_regressor_p10",
                                    "degradation_regressor_p50",
                                    "degradation_regressor_p90"])
def test_evaluate_fits_a_quantile_model_unweighted_like_production(monkeypatch, target):
    """The old guard here raised on `w is None` for a quantile target. 08o made that
    the production path, so the guard is gone and this asserts the replacement: a
    quantile eval fit with no weights passed fits with no weights, rather than raising
    or reaching for `meta['survival_weight']` on its own.

    The guard's purpose -- no silent fallback to a fit production does not use -- is
    now carried by `test_evaluate_refits_with_the_weights_production_ships`, which
    compares the two paths directly instead of hard-coding which of them is weighted."""
    spec = S.TARGET_BY_NAME[target]
    bundle = _bundle(spec)
    calls: list[dict] = []
    monkeypatch.setattr(T, "_make_model", lambda spec, params: _Recorder(calls))

    E._fit(spec, {}, bundle.X_train, bundle.y_train.to_numpy())
    assert len(calls) == 1 and calls[0]["sample_weight"] is None


@pytest.mark.parametrize("target", ["degradation_regressor_p10",
                                    "degradation_regressor_p50",
                                    "degradation_regressor_p90"])
def test_the_trio_really_trains_with_no_weights(target):
    """A real booster, not a recorder: 08o removed an argument that XGBoost was being
    handed, and `sample_weight=None` has to reach a live `fit` without a shape or dtype
    complaint before any of the parity assertions above mean anything."""
    spec = S.TARGET_BY_NAME[target]
    bundle = _bundle(spec)
    model = T._fit(T._make_model(spec, {"n_estimators": 4, "max_depth": 2}), spec,
                   bundle.X_train, bundle.y_train.to_numpy(), bundle.meta_train)
    pred = model.predict(bundle.X_train)
    assert pred.shape == (len(bundle.X_train),)
    assert np.isfinite(pred).all()


def test_the_eval_split_still_slices_weights_row_for_row(monkeypatch):
    """The slicing MECHANISM, asserted with no production target that uses it.

    08o left `_row_weights` returning None for everything, which would make a test of
    "the weights ride on EvalSplit, sliced with the rows" pass trivially for the rest of
    time -- and then fail to catch a mis-sliced vector the day a weight comes back. So
    the weight is injected here and the slicing is checked as it always was: the split's
    training side is a season-fold subset, so a vector that was not sliced would have
    the wrong length, but one sliced with the WRONG index would not."""
    spec = S.TARGET_BY_NAME["degradation_regressor_p50"]
    bundle = _bundle(spec)
    monkeypatch.setattr(
        E, "_row_weights",
        lambda spec, meta: meta["survival_weight"].to_numpy(dtype=np.float32))

    split = E._evaluation_split(bundle)
    assert split.w_tr is not None and len(split.w_tr) == len(split.y_tr)
    by_lap = dict(zip(bundle.meta_train["lap_id"], bundle.meta_train["survival_weight"]))
    expected = np.asarray([by_lap[i] for i in split.lap_ids_tr], dtype="float32")
    np.testing.assert_allclose(split.w_tr, expected, rtol=0, atol=0)


@pytest.mark.parametrize("target", [t.name for t in S.PRODUCTION_TARGETS])
def test_no_production_target_carries_row_weights(target):
    """Post-08o this covers all five, and it says two different things at once.

    For the quantile trio it is 08o's ruling: the IPW weight is gone from the eval path
    too, so the refit behind every published degradation number is the fit that ships.

    For the classifier it is the older statement, unchanged: balanced weights are a
    per-FIT statistic over the rows being fitted, not a per-row property, so they must
    not be hoisted onto the split and sliced -- balancing a fold against the full
    training set's class mix would be a quieter version of the same bug. `stint_life`
    carries its censoring in the label and must not be weighted on top of it."""
    spec = S.TARGET_BY_NAME[target]
    assert E._row_weights(spec, _bundle(spec).meta_train) is None


# ─── The identity of a fit ──────────────────────────────────────────────────────
def _write_log(dirpath, target, version, **fields):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / f"{target}_{version}_20260101T000000.json").write_text(json.dumps(fields))


def test_refit_refuses_to_replace_a_version_fitted_on_another_target(monkeypatch, tmp_path):
    """The trap Phase 7 sets: same artefact path, same manifest, different quantity.

    Nothing downstream can catch it -- the file exists, the input width is unchanged,
    ONNX parity compares the new booster against itself and passes. The version's own
    training log is the only witness, so the refusal happens before the fit."""
    monkeypatch.setattr(T, "LOGS_DIR", tmp_path)
    spec = S.TARGET_BY_NAME["degradation_regressor_p50"]
    _write_log(tmp_path, spec.name, "v6",
               target_column="next_lap_degradation_jump_detrended_s", fingerprint="abc")

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        T._guard_target_change(spec.name, "v6", spec, "abc", allow_target_change=False)

    # The same call is permitted when it is asked for explicitly.
    T._guard_target_change(spec.name, "v6", spec, "abc", allow_target_change=True)


def test_refit_allows_the_same_target_and_an_unbuilt_version(monkeypatch, tmp_path):
    """The guard must not stand in the way of ordinary retraining: a version fitted on
    this same column, or one that does not exist yet, both proceed silently."""
    monkeypatch.setattr(T, "LOGS_DIR", tmp_path)
    spec = S.TARGET_BY_NAME["degradation_regressor_p50"]
    T._guard_target_change(spec.name, "v9", spec, "abc", allow_target_change=False)  # unbuilt
    _write_log(tmp_path, spec.name, "v9", target_column=spec.source_column, fingerprint="abc")
    T._guard_target_change(spec.name, "v9", spec, "zzz", allow_target_change=False)


def test_a_log_predating_the_field_warns_rather_than_refusing(monkeypatch, tmp_path, capsys):
    """Every artefact built before Phase 7 -- v6 included, which is the one that ships --
    has a log with no `target_column`, so the check cannot be made on exactly the
    version it most matters for. The fingerprint is the fallback witness, and because it
    also moves for legitimate reasons (new seasons, a feature change) it warns and says
    what it does not know rather than blocking a routine retrain."""
    monkeypatch.setattr(T, "LOGS_DIR", tmp_path)
    spec = S.TARGET_BY_NAME["degradation_regressor_p50"]
    _write_log(tmp_path, spec.name, "v6", fingerprint="old-fingerprint")

    T._guard_target_change(spec.name, "v6", spec, "new-fingerprint", allow_target_change=False)
    warned = capsys.readouterr().out
    assert "CANNOT be checked" in warned and spec.source_column in warned

    # Same fingerprint: nothing to say, so nothing is said.
    T._guard_target_change(spec.name, "v6", spec, "old-fingerprint", allow_target_change=False)
    assert capsys.readouterr().out == ""
