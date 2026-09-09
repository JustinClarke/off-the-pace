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


# ─── Aggregation-scope audit (08b) ──────────────────────────────────────────────
# A forward reach can live in the scope of a GROUP BY, where neither the window
# walker nor the self-join walker looks. These tests do for the aggregation audit
# what test_forward_window_audit_catches_a_self_join_horizon does for the window
# one: prove it sees the shapes it was built for, rather than only that it is quiet.

def test_no_undeclared_aggregation_scope():
    violations = F.audit_aggregation_scope()
    assert violations == [], f"undeclared aggregation scopes: {violations}"


def test_aggregation_audit_catches_a_cross_season_pooled_rate():
    """int_sc_hazard_history's shape: a per-circuit rate with no season key, so every
    season is pooled and a 2018 row's feature is computed partly from 2024. No LEAD,
    no FOLLOWING frame, no self-join -- invisible to the other two walkers."""
    sql = """
        SELECT circuit_slug, SUM(n_onsets) / SUM(racing_laps) AS sc_hazard_per_lap
        FROM per_race GROUP BY circuit_slug
    """
    findings, unparsed = F._aggregation_findings("probe", sql)
    assert not unparsed
    assert len(findings) == 1
    assert "pools every ingested season" in findings[0][1]


def test_aggregation_audit_catches_a_bucketed_lap_key():
    """int_corner_skill_residuals' shape: FLOOR(lap_number / 5.0) * 5.0 AS lap_window,
    then GROUP BY it. The bucket spans five laps, four of them in the future at the
    first one, and the reach lives entirely in the grouping key."""
    sql = """
        WITH b AS (
            SELECT race_year, race_id, corner_name, braking_point_m,
                   FLOOR(CAST(lap_number AS DOUBLE) / 5.0) * 5.0 AS lap_window
            FROM corners
        )
        SELECT race_year, race_id, corner_name, lap_window,
               MEDIAN(braking_point_m) AS field_median
        FROM b GROUP BY race_year, race_id, corner_name, lap_window
    """
    findings, unparsed = F._aggregation_findings("probe", sql)
    assert not unparsed
    assert len(findings) == 1


def test_aggregation_audit_rejects_a_bucket_aliased_onto_a_lap_key():
    """The hole a name-based check would leave: alias the bucket back onto
    `lap_number` and the key set looks like it pins a lap. It does not."""
    sql = """
        WITH b AS (
            SELECT race_id, lap_time_s, FLOOR(lap_number / 5.0) * 5.0 AS lap_number
            FROM laps
        )
        SELECT race_id, lap_number, MEDIAN(lap_time_s) AS m
        FROM b GROUP BY race_id, lap_number
    """
    findings, _ = F._aggregation_findings("probe", sql)
    assert len(findings) == 1
    assert "derived key here" in findings[0][1]


def test_aggregation_audit_passes_a_lap_pinned_group():
    """The negative control. A cast is not a coarsening, and (race_id, lap_number)
    confines a group to one lap of one race -- no forward reach to have."""
    sql = """
        SELECT race_id, CAST(lap_number AS INTEGER) AS lap_number,
               AVG(lap_time_s) AS field_pace
        FROM laps GROUP BY race_id, lap_number
    """
    findings, unparsed = F._aggregation_findings("probe", sql)
    assert not unparsed
    assert findings == [], f"lap-pinned group wrongly flagged: {findings}"


def test_aggregation_survey_names_the_two_known_instances():
    """08b's premise. Both of the programme's known leakage suspects sit outside the
    mart's lineage today and are scheduled to enter it (02c, 02d). The survey is the
    advance notice; when they are wired into a feature they move into
    audit_aggregation_scope's scope and stop the build until someone rules on them."""
    survey = F.survey_aggregation_scope()
    assert any(f.startswith("int_corner_skill_residuals:") for f in survey)
    assert any(f.startswith("int_sc_hazard_history:") and "pools every ingested season" in f
               for f in survey)


def test_declared_exemptions_are_well_formed():
    """A blank reason, an unknown status, or a `known_leak` with nothing scheduled to
    fix it is itself a violation -- the point of putting these in schema.yml is that
    someone signed them. Covered by the audit above; asserted separately so a
    malformed declaration is not mistaken for a new aggregation."""
    import json

    manifest = json.loads(Path(F.MANIFEST_PATH).read_text())
    nodes = manifest["nodes"]
    problems = []
    for uid in F._mart_lineage(manifest):
        _, malformed = F._exemptions(nodes[uid], nodes[uid]["name"])
        problems += malformed
    assert not problems, f"malformed aggregation-scope exemptions: {problems}"


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
    """D5: the degradation target is bounded at source (negatives legitimate). Only
    stint-life is non-negative."""
    deg = load("degradation_regressor_p50").y_train
    b = S.TARGET_BOUND
    assert deg.between(-b, b).all(), f"degradation target out of [-{b}, {b}]"
    assert (deg < 0).mean() > 0.2, "expected a substantial negative fraction-D5"

    life = load("stint_life_regressor").y_train
    assert (life >= 0).all(), "remaining_stint_life_laps must be >= 0"


def test_target_bound_follows_the_target_column():
    """Phase 7: the bound is a fact about the SQL clip on whichever column
    DEGRADATION_TARGET names, not a constant that happens to fit the 1-lap one.

    Inheriting +/-10 after the flip to the 5-lap column would have been silent: the
    5-lap target is clipped at +/-50 in the mart, so a +/-10 assertion would fail
    honestly, but the manifest export_onnx writes would have carried a bound five times
    tighter than the data - a claim about the model's range that nothing checks
    downstream."""
    assert S.TARGET_BOUND == S.TARGET_BOUND_BY_COLUMN[S.DEGRADATION_TARGET]
    for t in S.PRODUCTION_TARGETS:
        if t.kind == "quantile":
            assert t.source_column in S.TARGET_BOUND_BY_COLUMN, (
                f"{t.source_column} is modelled but carries no source clip")


def test_target_bound_is_the_clip_the_warehouse_applies(load):
    """The bound must be tight against the real column, not merely not-violated.

    A bound loose by 5x passes `test_target_bounded` forever. This asserts the data
    actually reaches the bound, which is what makes it the SQL's clip rather than an
    arbitrary envelope drawn around it."""
    deg = load("degradation_regressor_p50").y_train
    reach = max(abs(float(deg.min())), abs(float(deg.max()))) / S.TARGET_BOUND
    assert reach > 0.9, (
        f"target reaches only {reach:.1%} of TARGET_BOUND={S.TARGET_BOUND} - "
        "the bound does not describe this column")


@pytest.mark.parametrize("target", PROD_TARGETS)
def test_target_columns_are_never_features(target):
    """No column is ever both a target and a feature, at any horizon.

    Phase 7 moves the modelled column between horizons, and the failure it invites is
    the alt-horizon column that has just been vacated quietly becoming available as a
    predictor. Both directions are asserted: the target of every production model is
    barred, and every alt-horizon degradation column stays barred whether or not it is
    the one being modelled."""
    spec = S.TARGET_BY_NAME[target]
    assert spec.source_column not in S.FEATURE_COLUMNS
    if spec.source_column != S.STINT_LIFE_TARGET:
        assert spec.source_column in S.EXCLUDED_LEAKAGE_COLUMNS

    for col in S.TARGET_HORIZON_LAPS:
        assert col not in S.FEATURE_COLUMNS, f"{col} is a forward-looking target column"


@pytest.mark.parametrize("target", ["degradation_regressor_p50", "stint_life_regressor", "cliff_classifier"])
def test_no_null_targets_in_training(load, target):
    """L0-7: NULL targets (last-lap-of-stint) must be dropped before training -
    XGBoost errors on NaN in y."""
    y = load(target).y_train
    assert y is not None and y.notna().all(), f"NULL target rows reached training for {target}"
