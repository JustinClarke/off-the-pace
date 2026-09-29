"""WI-17: the power-law tyre curve -- the F2/FD3 guard (T51), the export (T53) and the arithmetic.

T51: the feature allowlist in ml/src/powerlaw.py holds no compound_cliff_params column, no
     expected_* column, no cliff_onset_passed / laps_past_cliff and nothing net of
     compound_component_s; neither does the training frame. The dbt side is
     transform/tests/assert_power_law_no_seed_columns.sql.
T53: the two ONNX files together are under 500 KB, and ONNX agrees with XGBoost to 1e-5 on the
     GroupKFold test fold (plus a NaN-bearing copy of it).

Warehouse- and artefact-backed tests skip when `data/dev.duckdb` or the exported files are
absent (run `python -m ml.src.powerlaw`).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ml.src import powerlaw as P
from ml.src import powerlaw_fit as PF
from ml.src import schema as S

HAVE_DB = Path(S.DUCKDB_PATH).exists()
ONNX = {k: P.MODELS_DIR / f"powerlaw_{k}_{P.VERSION}.onnx" for k in ("deg20", "beta")}
BST = {k: P.MODELS_DIR / f"powerlaw_{k}_{P.VERSION}.bst" for k in ("deg20", "beta")}
HAVE_EXPORT = all(p.exists() for p in [*ONNX.values(), *BST.values(), P.MANIFEST_PATH])

GUARDED = [
    "compound_grip_peak", "compound_wear_gradient", "compound_optimal_temp_low",
    "compound_optimal_temp_high", "compound_cliff_onset_laps", "compound_cliff_severity",
    "compound_wear_s", "compound_component_s", "expected_compound_pace_s",
    "expected_degradation_rate_s_per_lap", "cliff_onset_passed", "laps_past_cliff",
    "cliff_candidate_flag", "driver_skill_residual_s", "pace_delta_s", "total_explained_s",
    "ambient_temp_delta", "rubber_component_s", "ambient_component_s", "base_track_pace_s",
    "next_5_lap_cumulative_jump_s", "laps_until_cliff_class",
]


# ─── T51: the guard ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("column", GUARDED)
def test_denylist_catches_every_guarded_column(column):
    assert P.denied(column), f"{column} is priced from the compound seed and must be denied"


@pytest.mark.parametrize("column", ["compound_hardness_rank", "compound_label", "compound_code",
                                    "track_temp_c", "dirty_air_share", "constructor_pace_s"])
def test_denylist_allows_identity_and_allowlisted_columns(column):
    assert not P.denied(column)


def test_feature_allowlist_is_clean():
    assert set(P.FEATURES_DEG20) | set(P.FEATURES_BETA) == set(P.ALLOWLIST)
    bad = sorted(f for f in P.ALLOWLIST if P.denied(f))
    assert not bad, f"guarded columns in the power-law feature allowlist: {bad}"
    assert not (set(P.ALLOWLIST) & set(S.EXCLUDED_LEAKAGE_COLUMNS))


def test_shape_model_never_sees_the_level_only_features():
    """The structural P3.3 / ordering guarantee: rank, dirty air and temperature move the level
    (monotone up) and never the shape, so they scale the whole curve at every lap."""
    assert P.MONOTONE_UP_DEG20 <= set(P.FEATURES_DEG20)
    assert not (P.MONOTONE_UP_DEG20 & set(P.FEATURES_BETA))


@pytest.mark.skipif(not HAVE_DB, reason="no data/dev.duckdb")
def test_training_frame_carries_no_guarded_column():
    df = P.load_training()          # raises on a guarded column
    assert set(P.ALLOWLIST) <= set(df.columns)
    assert len(df) > 0


# ─── the numpy fit is the dbt fit ────────────────────────────────────────────────────────────
@pytest.mark.skipif(not HAVE_DB, reason="no data/dev.duckdb")
def test_cell_fit_matches_dbt():
    import duckdb
    laps = PF.load_laps(S.DUCKDB_PATH)
    con = duckdb.connect(S.DUCKDB_PATH, read_only=True)
    try:
        cells = con.execute("SELECT race_id, compound_hardness_rank, alpha_s, beta, r2_within, "
                            "fit_eligible FROM int_cell_power_law_fit").df()
    finally:
        con.close()
    got = {}
    ranked = laps[laps["compound_hardness_rank"].notna()]
    for (race, rank), g in ranked.groupby(["race_id", "compound_hardness_rank"]):
        parts = PF.cell_parts(g)
        if parts:
            got[(race, int(rank))] = (*PF.fit_cell_from_sums(PF.cell_sums(parts)), PF.cell_eligible(parts))
    assert len(got) == len(cells)
    for r in cells.itertuples():
        a, b, r2, elig = got[(r.race_id, int(r.compound_hardness_rank))]
        assert b == r.beta and elig == r.fit_eligible
        assert a == pytest.approx(r.alpha_s, abs=1e-9)
        assert r2 == pytest.approx(r.r2_within, abs=1e-9)


# ─── curve arithmetic (mirrored in powerLaw.ts) ──────────────────────────────────────────────
def test_alpha_from_level_pins_age_20():
    for beta in (0.2, 0.8, 1.0, 2.2, 3.0):
        a = P.alpha_from(0.9, beta)
        assert P.tyre_curve(a, beta, [P.LEVEL_AGE])[0, 0] == pytest.approx(0.9, abs=1e-12)
    assert P.alpha_from(-0.3, 1.0) == 0.0


def test_tyre_curve_is_monotone_and_zero_at_the_anchor():
    laps = np.arange(1, 51)
    c = P.tyre_curve([0.03, 0.2, 0.0, -1.0], [1.4, 0.3, 2.0, 1.0], laps)
    assert np.all(c[:, : P.FRESH_ANCHOR_AGE] == 0)
    assert np.all(np.diff(c, axis=1) >= 0)
    assert np.all(c[2:] == 0)                        # alpha <= 0 is a flat curve
    up_a = P.tyre_curve(0.04, 1.4, laps)
    up_b = P.tyre_curve(0.03, 1.6, laps)
    assert np.all(up_a >= c[0]) and np.all(up_b >= c[0])


# ─── T53: size and parity ────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not HAVE_EXPORT, reason="no power-law export (run `python -m ml.src.powerlaw`)")
def test_onnx_combined_size_under_500kb():
    total = sum(p.stat().st_size for p in ONNX.values())
    assert total < P.SIZE_LIMIT_BYTES, f"{total} bytes"


@pytest.mark.skipif(not (HAVE_EXPORT and HAVE_DB), reason="needs the export and data/dev.duckdb")
def test_onnx_matches_xgboost_on_the_test_fold():
    import xgboost as xgb
    df = P.load_training()
    test_fold = df.iloc[P._folds(df)[0][1]]
    models = {"features_deg20": P.FEATURES_DEG20}
    for k, p in BST.items():
        m = xgb.XGBRegressor()
        m.load_model(str(p))
        models[k] = m
    par = P.parity(models, ONNX, test_fold)
    for k, v in par.items():
        assert v["max_abs_diff"] <= P.PARITY_ATOL, f"{k}: {v}"
        assert v["n_rows"] == len(test_fold)


@pytest.mark.skipif(not HAVE_EXPORT, reason="no power-law export (run `python -m ml.src.powerlaw`)")
def test_manifest_is_separate_and_per_model():
    man = json.loads(P.MANIFEST_PATH.read_text())
    orders = {m["name"]: m["feature_order"] for m in man["models"]}
    assert orders == {"powerlaw_deg20": list(P.FEATURES_DEG20), "powerlaw_beta": list(P.FEATURES_BETA)}
    for m in man["models"]:
        assert m["n_features"] == len(m["feature_order"])
        assert m["onnx_sha256"] and (P.MODELS_DIR / m["onnx"]).exists()
    v14 = P.MODELS_DIR / "manifest.json"
    if v14.exists():                                  # the v14 manifest is not touched (WI-17)
        assert not any("powerlaw" in m["name"] for m in json.loads(v14.read_text())["models"])
