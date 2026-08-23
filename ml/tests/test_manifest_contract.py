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
