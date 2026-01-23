"""Shared, session-cached FeatureBundles so the suite loads the mart only once per target."""
from __future__ import annotations

import functools

import pytest

from ml.src.features import load_features


@functools.lru_cache(maxsize=None)
def _cached_load(target: str | None):
    return load_features(target=target)


@pytest.fixture(scope="session")
def load():
    """Return a cached loader: `load("degradation_regressor_p50")`."""
    return _cached_load


@pytest.fixture(scope="session")
def degradation(load):
    return load("degradation_regressor_p50")
