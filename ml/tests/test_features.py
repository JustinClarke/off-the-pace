"""Leakage spine-written before features.py was trusted; these gate the whole build.

Covers §8: no leaked columns, no forward-looking features, holdout purity,
no hardcoded holdout year, bounded target (D5), and no NULL targets in training (L0-7).
"""
from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

from ml.src import features as F
from ml.src import schema as S

PROD_TARGETS = [t.name for t in S.PRODUCTION_TARGETS]
SRC_DIR = Path("ml/src")


@pytest.mark.parametrize("target", ["degradation_regressor_p50", "stint_life_regressor", "cliff_classifier"])
def test_no_leaked_columns(load, target):
    X = load(target).X_train
    leaked = set(X.columns) & S.EXCLUDED_LEAKAGE_COLUMNS
    assert not leaked, f"leaked/identity columns in X for {target}: {sorted(leaked)}"


def test_no_forward_looking_features():
    violations = F.audit_forward_window()
    assert violations == [], f"forward-looking feature definitions: {violations}"


def test_audit_features_clear_forward_window():
    """The label-adjacent features (cliff_candidate_flag, anomaly_class) kept per §15-5
    must themselves clear the audit, else they belong in EXCLUDED_LEAKAGE_COLUMNS."""
    violations = F.audit_forward_window()
    flagged = [v for v in violations if any(a in v for a in S.AUDIT_FEATURES)]
    assert not flagged, f"label-adjacent feature peeks forward-exclude it: {flagged}"


def test_holdout_purity(degradation):
    b = degradation
    # Holdout season is strictly after every training season (derived as MAX+1).
    assert b.holdout_season == max(b.training_seasons) + 1
    assert b.holdout_season not in b.training_seasons
    # No training row leaks into / past the holdout season.
    assert (b.groups_train < b.holdout_season).all()
    # Today the holdout is empty (2025 not ingested); on ingest this becomes nunique()==1.
    if len(b.X_holdout) == 0:
        assert b.meta_holdout.empty
    else:
        assert b.meta_holdout["race_year"].nunique() == 1
        assert int(b.meta_holdout["race_year"].iloc[0]) == b.holdout_season


def test_no_hardcoded_holdout():
    """No numeric literal 2024/2025 in ml/src code (docstrings/comments are fine -
    the holdout is derived as MAX(race_year)+1)."""
    offenders = []
    for path in SRC_DIR.glob("*.py"):
        src = path.read_text()
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.NUMBER and tok.string in {"2024", "2025"}:
                offenders.append(f"{path.name}:{tok.start[0]} -> {tok.string}")
    assert not offenders, f"hardcoded holdout year(s) in code: {offenders}"


def test_target_bounded(load):
    """D5: degradation target is bounded [-10, 10] (negatives legitimate). Only
    stint-life is non-negative."""
    deg = load("degradation_regressor_p50").y_train
    assert deg.between(-S.TARGET_BOUND, S.TARGET_BOUND).all(), "degradation target out of [-10, 10]"
    assert (deg < 0).mean() > 0.2, "expected a substantial negative fraction (~44%)-D5"

    life = load("stint_life_regressor").y_train
    assert (life >= 0).all(), "remaining_stint_life_laps must be >= 0"


@pytest.mark.parametrize("target", ["degradation_regressor_p50", "stint_life_regressor", "cliff_classifier"])
def test_no_null_targets_in_training(load, target):
    """L0-7: NULL targets (last-lap-of-stint) must be dropped before training -
    XGBoost errors on NaN in y."""
    y = load(target).y_train
    assert y is not None and y.notna().all(), f"NULL target rows reached training for {target}"
