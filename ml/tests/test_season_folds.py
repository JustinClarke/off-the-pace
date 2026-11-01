"""`_season_folds`: folds come from seasons that have rows, and degrade on thin data."""
import numpy as np
import pytest
from sklearn.model_selection import TimeSeriesSplit

from ml.src import train as T


def _legacy(seasons, training_seasons, n_splits):
    """The pre-fix fold builder, for the real-data identity check."""
    uniq = np.asarray(sorted(training_seasons))
    for a, b in TimeSeriesSplit(n_splits=min(n_splits, len(uniq) - 1)).split(uniq):
        yield (np.where(np.isin(seasons, uniq[a]))[0], np.where(np.isin(seasons, uniq[b]))[0])


def test_full_season_set_is_identical_to_legacy():
    ts = list(range(2018, 2025))                      # 7 seasons, as in the real warehouse
    seasons = np.repeat(ts, 5)
    new = list(T._season_folds(seasons, ts, 5))
    old = list(_legacy(seasons, ts, 5))
    assert len(new) == len(old) == 5
    for (a, b), (c, d) in zip(new, old):
        assert np.array_equal(a, c) and np.array_equal(b, d)


def test_season_without_rows_never_yields_an_empty_fold():
    seasons = np.repeat([2020, 2023, 2024], 4)        # 2021, 2022 listed but rowless
    folds = list(T._season_folds(seasons, [2020, 2021, 2022, 2023, 2024], 5))
    assert len(folds) == 2
    assert all(len(tr) and len(val) for tr, val in folds)


def test_two_seasons_gives_one_fold():
    seasons = np.repeat([2020, 2024], 3)
    (tr, val), = T._season_folds(seasons, [2020, 2021, 2024], 5)
    assert set(seasons[tr]) == {2020} and set(seasons[val]) == {2024}


def test_single_season_raises():
    with pytest.raises(ValueError):
        list(T._season_folds(np.repeat([2024], 3), [2023, 2024], 5))
