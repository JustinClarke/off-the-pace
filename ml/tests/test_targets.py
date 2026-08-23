"""Stint-life target synthesis correctness."""
from __future__ import annotations

import numpy as np

from ml.src import schema as S


def test_stint_life_synthesis(load):
    """remaining_stint_life_laps == clip(stint_length_laps-lap_in_stint, 0),
    and stint_length_laps is never a feature for the stint-life model."""
    b = load("stint_life_regressor")

    # The join-time column must not leak into X.
    assert "stint_length_laps" not in b.X_train.columns
    assert "stint_length_laps" not in S.FEATURE_COLUMNS

    # y matches the synthesis formula, recomputed from carried metadata.
    meta = b.meta_train
    expected = np.clip(meta["stint_length_laps"]-b.X_train["lap_in_stint"].astype("float64"), 0, None)
    assert np.allclose(b.y_train.to_numpy(), expected.to_numpy(), equal_nan=False)
    assert (b.y_train >= 0).all()


def test_censoring_flag_is_carried_and_is_not_a_feature(load):
    """The censoring flag reaches the model as metadata and never as a feature.

    It is the flag that says whether a remaining life of 3 means "the tyre had 3
    laps left" or "the race ended 3 laps later". As a feature it would be a direct
    leak of how the stint ends; as metadata it is what makes the AFT interval
    correct. Both halves are asserted because only having one is how it goes wrong.
    """
    b = load("stint_life_regressor")
    assert S.STINT_LIFE_CENSOR_COLUMN in b.meta_train.columns
    assert S.STINT_LIFE_CENSOR_COLUMN not in b.X_train.columns
    assert S.STINT_LIFE_CENSOR_COLUMN not in S.FEATURE_COLUMNS
    cens = b.meta_train[S.STINT_LIFE_CENSOR_COLUMN]
    assert cens.dtype == bool
    assert cens.notna().all(), "a NULL censoring flag would silently drop rows downstream"
    # Both populations must be present, or the survival framing is inert.
    assert 0.0 < float(cens.mean()) < 1.0


def test_aft_bounds_encode_censoring(load):
    """Uncensored rows get a point interval; censored rows get a half-line."""
    from ml.src import survival as SV

    b = load("stint_life_regressor")
    y = b.y_train.to_numpy()
    cens = b.meta_train[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
    lower, upper = SV.aft_bounds(y, cens)

    assert np.allclose(lower, y + S.AFT_LABEL_SHIFT)
    assert np.isfinite(lower).all(), "log(lower) must be finite -- that is what the shift is for"
    assert (lower > 0).all()
    assert np.allclose(upper[~cens], lower[~cens])
    assert np.isinf(upper[cens]).all()
    # The shift exists for the zero-life rows; check they are actually present.
    assert (y == 0).any()
