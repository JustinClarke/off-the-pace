"""Stint-life target synthesis correctness (§8)."""
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
