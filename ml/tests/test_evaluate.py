"""Headline contract: every model must beat its per-cohort baseline on the headline
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


# ─── Phase 6: the report must carry its own denominators and intervals ──────────
@pytest.mark.parametrize("target", [t.name for t in S.PRODUCTION_TARGETS])
def test_every_model_reports_an_attainable_ceiling(report, target):
    """Corrections §12. A headline with no denominator cannot answer the only question
    it is asked — keep going, or stop."""
    att = report["models"][target].get("attainable")
    assert att and not att.get("error"), f"{target} has no attainable block: {att}"
    var = att["variance"]
    assert 0.0 <= var["between_stint_share"] <= 1.0
    assert var["between_stint_share"] <= var["between_stint_share_naive"] + 1e-9 or \
        var.get("within_stint_is_deterministic"), (
        "the ANOVA estimate should not exceed the naive one it corrects; the exception is "
        "a target whose within-stint variation is deterministic (stint life)")


@pytest.mark.parametrize("target", [t.name for t in S.PRODUCTION_TARGETS])
def test_every_beats_baseline_claim_has_an_interval(report, target):
    m = report["models"][target]
    if not m["beats_baseline"]:
        pytest.skip(f"{target} does not claim to beat its baseline")
    iv = m.get("interval")
    assert iv and not iv.get("error"), f"{target} claims a win with no interval: {iv}"
    fp = iv["fold_paired"]
    assert fp["n_folds"] >= 2 and fp["p_value"] is not None
    assert fp["ci_low"] < fp["ci_high"]
    assert "beats_baseline_significant" in m


def test_stint_grain_is_recorded_and_the_folds_are_stint_pure(report):
    """§15's clustering fact, and the measurement that shows the CV split was never the
    part that was broken."""
    sg = report.get("stint_grain")
    assert sg, "no stint_grain block — the effective sample is undocumented"
    assert sg["stints_straddling_a_season_fold"] == 0, (
        "a stint spans two seasons, which should be impossible: a stint belongs to one "
        "race and a race to one season")
    assert sg["n_stints"] < sg["n_rows"]


def test_claims_inside_noise_is_present_even_when_empty(report):
    assert "claims_inside_noise" in report, (
        "an absent key and 'every claim survived' must not look the same")
    assert set(report["claims_inside_noise"]) <= set(report["models"])
