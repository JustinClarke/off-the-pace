"""Leakage spine-written before features.py was trusted; these gate the whole build.

Covers: no leaked columns, no forward-looking features, holdout purity,
no hardcoded holdout year, bounded target (D5), and no NULL targets in training (L0-7).
"""
from __future__ import annotations

import io
import json
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


def test_the_sc_hazard_instance_left_the_survey_by_being_fixed_not_by_being_hidden():
    """08b's premise, now FULLY discharged -- and this test is the record of the second
    half closing.

    WHAT THIS TEST USED TO ASSERT, and why it was wrong to keep asserting it. Until
    2026-09-20 this was `test_aggregation_survey_still_names_the_outstanding_instance`,
    and it required the survey to keep reporting int_sc_hazard_history with the words
    "pools every ingested season". That was correct when written: the model was one row
    per circuit over all time, so a 2018 consumer read a hazard estimated partly from
    2024 races. 02d rebuilt it as an expanding, season-lagged rate on 2026-09-11 and the
    test went red the same day -- it was asserting the continued presence of a defect
    that had been fixed. A red test that means "the bug is gone" is worse than no test,
    because the next reader cannot tell it from a regression. It is replaced here by the
    shape 02c used for the corner instance.

    int_sc_hazard_history is gone from the survey for TWO reasons that had to hold
    together, and checking only one of them would let the guard rot:

      1. 02d removed the defect itself. The model is keyed (circuit_slug, season) and
         every aggregate ends at 1 PRECEDING on the season axis, so the groups it still
         has pin a race or a season rather than pooling all of time. The survey's
         "pools every ingested season" finding therefore cannot be produced from this
         model any more -- which is why asserting its ABSENCE by that exact string is
         the meaningful half of reason 1.
      2. 02d wired five of its columns into fct_cliff_prediction_features, so it is no
         longer OUTSIDE the lineage the survey walks. The survey is defined over models
         the mart does not read; entering the contract is itself an exit from it.

    Reason 2 alone would be an alarming way to leave a survey -- a model can drop off it
    by being read by a feature while still carrying the defect, which is exactly the
    hand-off the survey exists to flag. So assert both: it is IN the lineage, and the
    real audit over that lineage is clean on it. That audit is not vacuous here: the
    model's four GROUP BYs are all non-pinning, so they are clean only because 02d wrote
    rulings for them into schema.yml, and `test_declared_exemptions_are_well_formed`
    plus the stale-exemption check in `audit_aggregation_scope` both bear on them."""
    survey = F.survey_aggregation_scope()
    assert not any(f.startswith("int_sc_hazard_history:") for f in survey), (
        "int_sc_hazard_history is back in the survey — it should be in the mart "
        "lineage, read directly by fct_cliff_prediction_features (02d)")
    assert not any("pools every ingested season" in f and "int_sc_hazard_history" in f
                   for f in survey), (
        "int_sc_hazard_history's all-time pooled-rate shape is back; 02d's ruling was "
        "that it is a temporal leak the moment it reaches a feature")

    # Scoped to this model ON PURPOSE. The same "pools every ingested season" shape is
    # still reported for four OTHER models outside the lineage, measured 2026-09-20:
    # int_driver_circuit_affinity (3 groups), int_driver_circuit_era_affinity (4),
    # int_era_normalized_driver_rating (2) and int_pit_loss_circuit (1). None feeds a
    # feature today, so none is a live leak -- they are the survey's advance notice,
    # working as designed, and asserting the string is absent survey-wide would fail on
    # them and say nothing about 02d. If one of those is ever wired into the mart it
    # arrives in audit_aggregation_scope automatically and the build stops until someone
    # rules on it, which is the same route 02d took here.

    manifest = json.loads(Path(F.MANIFEST_PATH).read_text())
    lineage_names = {manifest["nodes"][uid]["name"] for uid in F._mart_lineage(manifest)}
    assert "int_sc_hazard_history" in lineage_names

    violations = F.audit_aggregation_scope()
    assert not any("int_sc_hazard_history" in v for v in violations), violations


def test_the_sc_hazard_join_key_still_carries_the_season():
    """The one regression that would silently reinstate 02d's leak without tripping any
    audit above.

    int_sc_hazard_history is point-in-time as of the start of a season, so the season is
    HALF THE KEY. A consumer that joins on circuit_slug alone gets a 5-7x fan-out AND a
    2018 row estimated partly from 2024 -- and neither the forward-window walker nor the
    aggregation-scope walker looks at join keys, so both would stay green. The dbt test
    assert_sc_hazard_no_forward_leakage checks the MODEL's own window; this checks that
    the mart reading it did not drop half the key on the way in.

    Asserted structurally rather than by row count, so it fails on the edit that causes
    the bug rather than on the rebuild that reveals it."""
    manifest = json.loads(Path(F.MANIFEST_PATH).read_text())
    node = next(n for n in manifest["nodes"].values()
                if n["name"] == "fct_cliff_prediction_features")
    sql = F._model_sql(node, Path(F.MANIFEST_PATH).parent)
    normalised = " ".join(sql.split()).lower()

    assert "sch.circuit_slug" in normalised, (
        "the mart no longer joins int_sc_hazard_history on circuit_slug")
    assert "r.race_year = sch.season" in normalised, (
        "fct_cliff_prediction_features joins int_sc_hazard_history WITHOUT the season "
        "half of its key. That is 02d's original leak reinstated: the hazard a 2018 "
        "training row reads would be estimated partly from the 2024 evaluation season, "
        "and the join would fan the mart out 5-7x besides.")


def test_the_corner_instance_left_the_survey_by_being_fixed_not_by_being_hidden():
    """The other half, discharged by 02c, and asserted in a shape that a regression
    cannot satisfy by accident.

    int_corner_skill_residuals is gone from the survey for TWO reasons that had to hold
    together, and checking only one of them would let the guard rot:

      1. 02g removed the aggregation itself. The FLOOR(lap/5)*5 block bucket that 02a
         ruled on -- mean forward reach 1.877 laps, every contaminating lap inside the
         label's own t+1..t+5 window -- is now a trailing RANGE window, so the model has
         no non-pinning GROUP BY left to report.
      2. 02c wired it into the mart through int_lap_corner_inputs, so it is no longer
         OUTSIDE the lineage the survey walks. The survey is defined over models the
         mart does not read; entering the contract is itself an exit from it.

    Reason 2 alone would be an alarming way to leave a survey -- a model can drop off it
    by being read by a feature while still carrying the defect, which is exactly the
    hand-off the survey exists to flag. So assert both: it is IN the lineage, and the
    real audit over that lineage is clean on it."""
    survey = F.survey_aggregation_scope()
    assert not any(f.startswith("int_corner_skill_residuals:") for f in survey), (
        "int_corner_skill_residuals is back in the survey — it should be in the mart "
        "lineage via int_lap_corner_inputs (02c)")

    manifest = json.loads(Path(F.MANIFEST_PATH).read_text())
    lineage_names = {manifest["nodes"][uid]["name"] for uid in F._mart_lineage(manifest)}
    assert "int_corner_skill_residuals" in lineage_names
    assert "int_lap_corner_inputs" in lineage_names

    violations = F.audit_aggregation_scope()
    assert not any("int_corner_skill_residuals" in v for v in violations), violations
    assert not any("int_lap_corner_inputs" in v for v in violations), violations


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


def test_baseline_observations_n_is_never_a_feature():
    """08h: measured as an add-ablation, rejected, and pinned so it stays rejected.

    `baseline_observations_n` ships in the mart on purpose -- it is the column the four
    thermal features' NULLs are deterministic on, so a consumer needs it to condition on
    that missingness. It is NOT a feature. 08h ran the add-ablation (32 -> 33 columns) on
    `cv_final_fold` through `evaluate.py`'s own `_fit`/`_score`: no family cleared its own
    5-reseed floor (best 0.98x, on p50), and the declarability hazard 08e named is real --
    the count is not derivable from any contract column, and it rises with SC and pit
    disruption.

    The reason this is a test and not just a note: the column is sitting in the mart
    looking like a feature, its rank correlation with `lap_in_stint` is 0.97, and the
    cheapest way for a later session to "improve" the contract is to add it back without
    re-running the gate. If a future item wants it in `X`, it re-runs 08h's arms and
    deletes this test deliberately."""
    assert "baseline_observations_n" not in S.FEATURE_COLUMNS, (
        "baseline_observations_n was measured and rejected by 08h; adding it to "
        "FEATURE_COLUMNS requires re-running the add-ablation gate, not just an edit."
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
