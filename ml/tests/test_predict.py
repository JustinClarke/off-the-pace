"""Predictions output-schema parity (§8)-generated against the smoke models."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from ml.src import predict as P
from ml.src import schema as S

MODELS_DIR = Path("ml/models")
HAVE_SMOKE = all((MODELS_DIR / f"{S.artefact_name(t, 'smoke')}.bst").exists()
                 for t in S.PRODUCTION_TARGETS)
pytestmark = pytest.mark.skipif(not HAVE_SMOKE, reason="smoke boosters absent (run train --all --smoke)")


@pytest.fixture(scope="module")
def table(tmp_path_factory):
    out = tmp_path_factory.mktemp("pred") / "preds.parquet"
    P.run(str(out), version="smoke")
    return pq.read_table(out)


def test_output_schema(table):
    assert table.schema.equals(S.PREDICTIONS_ARROW_SCHEMA), (
        f"schema drift:\nGOT  {table.schema}\nWANT {S.PREDICTIONS_ARROW_SCHEMA}")
    assert table.num_columns == 17


def test_holdout_and_envelope_flags(table):
    df = table.to_pandas()
    # is_holdout is all-False today (2025 absent); both flags present and boolean.
    assert df["is_holdout"].dtype == bool and df["is_in_envelope"].dtype == bool
    assert not df["is_holdout"].any(), "no holdout rows expected before 2025 ingests"
    assert df["is_in_envelope"].sum() > 0


def test_quantiles_monotonic_and_probs_normalised(table):
    df = table.to_pandas()
    assert (df["predicted_degradation_jump_p10_s"] <= df["predicted_degradation_jump_s"] + 1e-6).all()
    assert (df["predicted_degradation_jump_s"] <= df["predicted_degradation_jump_p90_s"] + 1e-6).all()
    probs = df[list(S.PROB_COLUMNS)].to_numpy()
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-5)
    assert df["predicted_cliff_class"].isin(S.CLIFF_CLASS_LABELS).all()
    assert (df["predicted_remaining_stint_life_laps"] >= 0).all()
