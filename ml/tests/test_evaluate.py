"""The headline contract (§8): every model must beat its per-cohort baseline on the headline
metric. Reads ml/artefacts/evaluation_metrics.json (produced by `make ml-evaluate`); skips when
absent, exactly like test_predict / test_onnx_parity skip when their artefacts are missing.

Direction: regressors lower-is-better (pinball / rmse), the classifier higher-is-better (macro-F1).
`beats_baseline` is computed with the correct direction in evaluate.py; here we re-assert the raw
numbers too so the gate can't be silently inverted.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ml.src import schema as S

METRICS_PATH = Path("ml/artefacts/evaluation_metrics.json")
pytestmark = pytest.mark.skipif(
    not METRICS_PATH.exists(),
    reason="evaluation_metrics.json absent (run `make ml-evaluate`)")


@pytest.fixture(scope="module")
def report():
    return json.loads(METRICS_PATH.read_text())


def test_all_targets_evaluated(report):
    assert set(report["models"]) == {t.name for t in S.PRODUCTION_TARGETS}


@pytest.mark.parametrize("target", [t.name for t in S.PRODUCTION_TARGETS])
def test_model_beats_baseline_overall(report, target):
    m = report["models"][target]
    model, baseline = m["headline"], m["baseline_headline"]
    better = model > baseline if m["higher_is_better"] else model < baseline
    assert m["beats_baseline"] is better, "beats_baseline flag disagrees with the raw metrics"
    assert better, (f"{target} ({m['headline_metric']}): model={model:.4f} "
                    f"did not beat baseline={baseline:.4f}")


def test_underperforming_cohorts_present(report):
    """Losing cohorts are surfaced, never silently dropped (the block must exist per model)."""
    for target, m in report["models"].items():
        assert "underperforming_cohorts" in m, f"{target} missing underperforming_cohorts block"
