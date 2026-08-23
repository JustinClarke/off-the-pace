"""Version-consistency gate — the third blind gate (ml_execution_plan.md Phase 4).

Every existing check in the ML pipeline is *internally* consistent. `parity()` compares
each `.bst` against its own `.onnx`, so v1-against-v1 agrees perfectly. A manifest is
valid JSON whatever version it names. Nothing compared the version the pipeline produced
against the version the rest of the system expects — which is why `train.py` and
`export_onnx.py` could both default to `"v1"`, three versions stale, reachable from a
one-word `make` target, and produce no failure anywhere.

The concrete hazard: `build_manifest` takes `feature_order` from `S.FEATURE_COLUMNS`
(42) rather than from the booster it just converted. Point `make ml-onnx` at the v1
boosters — 38 features — and it publishes a manifest describing a 42-feature contract in
front of models that cannot accept one. `make app-models` copies by manifest version, so
that ships to the browser.

These assertions close the class rather than the two instances.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from ml.src import schema as S

MODELS_DIR = Path("ml/models")
MANIFEST_PATH = MODELS_DIR / "manifest.json"
APP_MODELS_DIR = Path("app/public/models")

pytestmark = pytest.mark.skipif(
    not MANIFEST_PATH.exists(), reason="no ml/models/manifest.json (run `make ml-onnx`)")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def _artefacts_complete(version: str) -> bool:
    return all((MODELS_DIR / f"{S.artefact_name(t, version)}{ext}").exists()
               for t in S.PRODUCTION_TARGETS for ext in (".bst", ".onnx"))


def _booster_n_features(target_name: str, version: str) -> int:
    import xgboost as xgb

    spec = next(t for t in S.PRODUCTION_TARGETS if t.name == target_name)
    booster = xgb.Booster()
    with warnings.catch_warnings():          # ".bst" extension → UBJSON-guess warning
        warnings.simplefilter("ignore")
        booster.load_model(str(MODELS_DIR / f"{S.artefact_name(spec, version)}.bst"))
    return booster.num_features()


def test_manifest_version_has_a_complete_artefact_set(manifest):
    """The manifest must name a version that actually exists on disk in full."""
    version = manifest["model_version"]
    missing = [f"{S.artefact_name(t, version)}{ext}"
               for t in S.PRODUCTION_TARGETS for ext in (".bst", ".onnx")
               if not (MODELS_DIR / f"{S.artefact_name(t, version)}{ext}").exists()]
    assert not missing, f"manifest names version '{version}' but these are absent: {missing}"


def test_manifest_ships_the_version_the_system_expects(manifest):
    """If a complete MODEL_VERSION_DEFAULT set is on disk, the manifest must name it.

    Inert in CI, where the artefacts are the `smoke` set and no complete v5 exists —
    there the two assertions above and below carry the weight. Locally this is the whole
    point: it is the assertion that would have caught `make ml-onnx` publishing v1.
    """
    expected = S.MODEL_VERSION_DEFAULT
    if not _artefacts_complete(expected):
        pytest.skip(f"no complete '{expected}' artefact set on disk (CI smoke run)")
    assert manifest["model_version"] == expected, (
        f"manifest ships '{manifest['model_version']}' while a complete '{expected}' set "
        f"exists on disk and every other CLI defaults to it. `make app-models` copies by "
        f"manifest version, so this is what reaches the browser.")


@pytest.mark.parametrize("target", [t.name for t in S.PRODUCTION_TARGETS])
def test_manifest_input_width_matches_the_actual_booster(manifest, target):
    """`shape[1]` is written from `len(S.FEATURE_COLUMNS)`, never read back off the
    booster — so it is a claim, not a measurement, until something checks it here."""
    version = manifest["model_version"]
    declared = manifest["input"]["shape"][1]
    actual = _booster_n_features(target, version)
    assert declared == actual, (
        f"manifest declares a {declared}-feature input; {target} at '{version}' takes "
        f"{actual}. The browser builds its feature vector from this manifest.")


def test_manifest_input_block_is_self_consistent(manifest):
    inp = manifest["input"]
    assert inp["n_features"] == inp["shape"][1] == len(inp["feature_order"]), (
        f"n_features={inp['n_features']}, shape[1]={inp['shape'][1]}, "
        f"len(feature_order)={len(inp['feature_order'])}")


@pytest.mark.skipif(not APP_MODELS_DIR.is_dir(), reason="app/public/models/ not present")
def test_app_manifest_matches_ml_manifest(manifest):
    """`make app-models` copies the manifest verbatim; drift means someone re-exported
    without re-copying, and the browser is scoring against a stale contract."""
    app_manifest_path = APP_MODELS_DIR / "manifest.json"
    assert app_manifest_path.exists(), (
        f"{APP_MODELS_DIR} exists but has no manifest.json — run `make app-models`")
    app_manifest = json.loads(app_manifest_path.read_text())
    assert app_manifest == manifest, (
        "app/public/models/manifest.json differs from ml/models/manifest.json "
        f"(app version '{app_manifest.get('model_version')}' vs "
        f"'{manifest['model_version']}') — run `make app-models`")


@pytest.mark.skipif(not APP_MODELS_DIR.is_dir(), reason="app/public/models/ not present")
def test_app_onnx_files_match_the_manifest_hashes(manifest):
    """The manifest carries an sha256 per model; the copies the browser loads must be
    those exact bytes, not an older export left behind by a partial copy."""
    import hashlib

    mismatched = []
    for entry in manifest["models"]:
        path = APP_MODELS_DIR / entry["onnx"]
        if not path.exists():
            mismatched.append(f"{entry['onnx']}: missing from {APP_MODELS_DIR}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if entry.get("onnx_sha256") and digest != entry["onnx_sha256"]:
            mismatched.append(f"{entry['onnx']}: sha256 {digest[:12]}… ≠ manifest "
                              f"{entry['onnx_sha256'][:12]}…")
    assert not mismatched, f"app ONNX copies differ from the manifest: {mismatched}"


# ─── Survival output block (Phase 3c) ───────────────────────────────────────────
# The stint-life graph does not emit laps. It emits a shifted log-scale margin, and
# the browser turns it into laps using constants that only exist in the manifest. If
# any of them goes missing or arrives null, app/src/ml/survival.ts produces numbers
# that look like laps and are not — the same silent-wrongness shape as Corrections
# §5–§8. These assert the constants are present, sane, and actually correct.
def _survival_entry(manifest: dict) -> dict:
    return next(m for m in manifest["models"] if m["name"] == "stint_life_regressor")


def test_stint_life_ships_as_a_survival_model(manifest):
    e = _survival_entry(manifest)
    assert e["kind"] == "survival"
    assert e["objective"] == "survival:aft"
    assert e["headline_metric"] == "aft_nloglik", (
        "the stint-life headline must not be an RMSE: ml_headroom_ii.md #3 shows "
        "RMSE-on-uncensored crowns the worst model on the page")


def test_survival_output_block_is_complete(manifest):
    out = _survival_entry(manifest)["output"]
    for key in ("margin_offset", "label_shift", "aft_scale", "aft_distribution", "quantiles"):
        assert out.get(key) is not None, f"survival output block is missing {key}"
    assert out["label_shift"] == S.AFT_LABEL_SHIFT
    assert out["aft_distribution"] == S.AFT_DISTRIBUTION
    assert 0.0 < out["aft_scale"] < 5.0
    assert set(out["quantiles"]) >= {"p10", "p90"}, (
        "the gauge renders a band; without these the app falls back to guessing it")


def test_survival_margin_offset_actually_reconstructs_the_booster(manifest):
    """The end-to-end proof, from the shipped artefacts only.

    export_onnx measures the offset and asserts it is constant, but that check runs
    inside the process that wrote it. This one re-reads the .onnx and the .bst off
    disk and shows that the manifest's constants really do turn one into the other —
    the property the browser depends on and nothing else re-verifies.
    """
    import numpy as np
    import onnxruntime as ort

    from ml.src import export_onnx as E
    from ml.src import survival as SV

    version = manifest["model_version"]
    spec = S.TARGET_BY_NAME["stint_life_regressor"]
    bst_path, onnx_path = E._paths(spec, version)
    if not (bst_path.exists() and onnx_path.exists()):
        pytest.skip(f"no stint-life artefact pair at '{version}'")

    out = _survival_entry(manifest)["output"]
    sample = E.nan_bearing_sample(200)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        booster = SV.load_booster(bst_path)

    expected = SV.predict_laps(booster, sample, out["aft_scale"])
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    raw = np.asarray(sess.run(None, {"input": sample})[0]).reshape(-1).astype(np.float64)
    got = SV.laps_from_margin(raw + out["margin_offset"], out["aft_scale"])

    assert np.allclose(expected, got, atol=E.ATOL, rtol=E.RTOL), (
        f"manifest margin_offset={out['margin_offset']} does not reconstruct the "
        f"booster: max|diff|={np.max(np.abs(expected - got)):.3e}")


def test_predictions_schema_carries_the_life_band(manifest):
    """The parquet and the browser must describe the same object. If the app renders
    a band the mart does not store, verifyParity has nothing to compare it against."""
    cols = manifest["predictions_schema"]
    for c in ("predicted_remaining_stint_life_laps",
              "predicted_remaining_stint_life_p10_laps",
              "predicted_remaining_stint_life_p90_laps"):
        assert c in cols, f"predictions schema is missing {c}"
