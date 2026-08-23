"""Leakage spine-written before features.py was trusted; these gate the whole build.

Covers: no leaked columns, no forward-looking features, holdout purity,
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


def _lineage_sql() -> dict[str, str]:
    """The same {node_uid: compiled SQL} map audit_forward_window builds."""
    import json

    manifest_path = Path(F.MANIFEST_PATH)
    manifest = json.loads(manifest_path.read_text())
    nodes = manifest["nodes"]
    mart_uid = next(uid for uid, n in nodes.items()
                    if n.get("name") == S.MART and n.get("resource_type") == "model")
    parent_map = manifest.get("parent_map", {})
    lineage, frontier = set(), [mart_uid]
    while frontier:
        uid = frontier.pop()
        if uid in lineage or uid not in nodes:
            continue
        lineage.add(uid)
        frontier.extend(parent_map.get(uid, []))
    return {uid: F._model_sql(nodes[uid], manifest_path.parent)
            for uid in lineage if nodes[uid].get("resource_type") == "model"}


@pytest.mark.parametrize("target", ["degradation_regressor_p50", "stint_life_regressor", "cliff_classifier"])
def test_no_leaked_columns(load, target):
    X = load(target).X_train
    leaked = set(X.columns) & S.EXCLUDED_LEAKAGE_COLUMNS
    assert not leaked, f"leaked/identity columns in X for {target}: {sorted(leaked)}"


def test_no_forward_looking_features():
    violations = F.audit_forward_window()
    assert violations == [], f"forward-looking feature definitions: {violations}"


def test_forward_window_audit_actually_reads_the_lineage():
    """Coverage, not cleanliness. `audit_forward_window` returns [] both when it has
    inspected every feature and found nothing, and when it inspected nothing at all —
    which is what happened for as long as `transform/target/manifest.json` carried a
    null `compiled_code` and the walker fell back to unparseable Jinja raw_code: 0 of
    21 lineage models parsed, 0 of 42 features resolved, CLEAN on every run. This
    asserts the audit can still see, so the test above means something."""
    defs, unparsed = F._alias_definitions(_lineage_sql())
    assert not unparsed, f"lineage models the audit cannot parse: {sorted(unparsed)}"
    undefined = [c for c in S.FEATURE_COLUMNS if c not in defs]
    assert not undefined, (
        f"{len(undefined)}/{len(S.FEATURE_COLUMNS)} features resolve to no SQL definition: "
        f"{undefined}. The audit is blind to them; a CLEAN result would be meaningless.")


def test_forward_window_audit_catches_a_self_join_horizon():
    """A forward reach does not have to be a window. The cliff scan walks a whole
    horizon through `a.lap_in_stint < f.lap_in_stint` in a JOIN ON, with no LEAD and
    no FOLLOWING frame in any projection. A *feature* built that way passed this audit
    silently until the walker learned to read the enclosing scope."""
    original = S.FEATURE_COLUMNS
    try:
        S.FEATURE_COLUMNS = ["laps_until_cliff"]   # produced by the cliff_scan CTE
        violations = F.audit_forward_window()
    finally:
        S.FEATURE_COLUMNS = original
    assert any("self-join inequality" in v for v in violations), (
        f"self-join horizon not detected; got {violations}")


def test_audit_features_clear_forward_window():
    """The label-adjacent features (cliff_candidate_flag, anomaly_class) kept in the feature set
    must themselves clear the audit, else they belong in EXCLUDED_LEAKAGE_COLUMNS."""
    violations = F.audit_forward_window()
    flagged = [v for v in violations if any(a in v for a in S.AUDIT_FEATURES)]
    assert not flagged, f"label-adjacent feature peeks forward-exclude it: {flagged}"


def test_feature_contract_subset_of_mart():
    """Column contract guard: every column the ml layer reads features,
    identifiers/metadata, and target source columns must exist in the live mart.
    Catches schema drift in both directions of a prior break: dropped feature
    columns (powertrain/air-density) and un-projected metadata (circuit_key)."""
    import duckdb

    con = duckdb.connect(S.DUCKDB_PATH, read_only=True)
    try:
        mart_cols = {
            r[0] for r in con.execute(
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_name = '{S.MART}'"
            ).fetchall()
        }
    finally:
        con.close()
    assert mart_cols, f"{S.MART} not found in {S.DUCKDB_PATH} build the mart first"

    # Target source columns that come from the mart (stint-life is synthesised in
    # features.py from stint_length_laps, so it is exempt).
    mart_target_cols = {
        t.source_column for t in S.PRODUCTION_TARGETS
        if t.source_column != S.STINT_LIFE_TARGET
    }
    required = set(S.FEATURE_COLUMNS) | set(S.IDENTIFIER_COLUMNS) | mart_target_cols
    missing = sorted(required - mart_cols)
    assert not missing, (
        f"ml contract references columns absent from {S.MART}: {missing}. "
        "Either project them in the mart or remove them from schema.py."
    )


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
