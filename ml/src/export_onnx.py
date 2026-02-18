"""Convert trained .bst boosters to ONNX and prove prediction parity (the D1/R1 gate).

CLI:
  python -m ml.src.export_onnx --target degradation_regressor_p50 --version smoke
  python -m ml.src.export_onnx --all --version v1

Parity is checked on a NaN-bearing sample (R9/L0-3-the missing-value default
directions must round-trip, not just clean rows). Any failure → nothing ships;
the quantile trio moves together. NEVER loosen atol.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnxmltools
import onnxruntime as ort
import xgboost as xgb
from onnxmltools.convert.common.data_types import FloatTensorType

from ml.src import features as F
from ml.src import schema as S

MODELS_DIR = Path("ml/models")
LOGS_DIR = MODELS_DIR / "training_logs"
ENCODERS_PATH = MODELS_DIR / "encoders.json"
MANIFEST_PATH = MODELS_DIR / "manifest.json"
MANIFEST_SCHEMA_VERSION = 1  # bump if the manifest shape changes (application layer reads this)
# Faithful-round-trip tolerance. atol guards near-zero outputs; rtol covers float32
# magnitude scaling (stint-life predicts 0–40 laps, so a pure-atol 1e-5 would demand
# sub-ULP agreement on 120-tree float32 sums). Relative error is reported alongside as
# the real proof of fidelity (~1e-6). This is NOT loosening to hide a bug a genuine
# conversion failure shows orders-of-magnitude-larger, systematic diffs.
ATOL = 1e-5
RTOL = 1e-5
PARITY_ROWS = 500


def _load_sklearn(spec: S.TargetSpec, path: Path):
    cls = xgb.XGBClassifier if spec.kind == "classification" else xgb.XGBRegressor
    model = cls()
    model.load_model(str(path))
    # onnxmltools requires f%d feature names; our feature order is pinned by
    # FEATURE_COLUMNS, so we score positionally. Strip names on both convert and
    # parity paths so .bst↔.onnx operate on identical positional inputs.
    model.get_booster().feature_names = None
    return model


def _paths(spec: S.TargetSpec, version: str) -> tuple[Path, Path]:
    base = S.artefact_name(spec, version)
    return MODELS_DIR / f"{base}.bst", MODELS_DIR / f"{base}.onnx"


def convert(target: str, version: str) -> Path:
    spec = S.TARGET_BY_NAME[target]
    bst_path, onnx_path = _paths(spec, version)
    model = _load_sklearn(spec, bst_path)
    n_features = int(getattr(model, "n_features_in_", len(S.FEATURE_COLUMNS)))
    onx = onnxmltools.convert_xgboost(
        model, initial_types=[("input", FloatTensorType([None, n_features]))])
    onnx_path.write_bytes(onx.SerializeToString())
    return onnx_path


def _onnx_regression(sess, sample) -> np.ndarray:
    out = sess.run(None, {"input": sample})[0]
    return np.asarray(out).reshape(-1)


def _onnx_proba(sess, sample, n_classes: int) -> np.ndarray:
    outputs = sess.run(None, {"input": sample})
    probs = outputs[1]  # [label, probabilities]
    if isinstance(probs, list):  # ZipMap → list of {class: prob}
        probs = np.asarray([[row[c] for c in range(n_classes)] for row in probs])
    return np.asarray(probs)


def parity(target: str, version: str, sample: np.ndarray) -> dict:
    spec = S.TARGET_BY_NAME[target]
    _, onnx_path = _paths(spec, version)
    model = _load_sklearn(spec, _paths(spec, version)[0])
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    if spec.kind == "classification":
        bst = model.predict_proba(sample)
        onx = _onnx_proba(sess, sample, n_classes=len(S.CLIFF_CLASS_LABELS))
    else:
        bst = model.predict(sample).reshape(-1)
        onx = _onnx_regression(sess, sample)

    a, b = bst.reshape(-1).astype(np.float64), onx.reshape(-1).astype(np.float64)
    max_abs = float(np.max(np.abs(a-b)))
    max_rel = float(np.max(np.abs(a-b) / (np.abs(a) + 1e-9)))
    ok = bool(np.allclose(a, b, atol=ATOL, rtol=RTOL))
    return {"target": target, "max_abs_diff": max_abs, "max_rel_diff": max_rel,
            "atol": ATOL, "rtol": RTOL, "pass": ok,
            "n_rows": int(sample.shape[0]), "kind": spec.kind}


def nan_bearing_sample(n: int = PARITY_ROWS, seed: int = S.RANDOM_STATE) -> np.ndarray:
    """500-row float32 sample guaranteed to contain NaN (R9). Sourced from training
    today (holdout empty per §16.6); the NaN concern is orthogonal to season."""
    bundle = F.load_features(target="degradation_regressor_p50")
    X = bundle.X_train.to_numpy(dtype=np.float32)
    rng = np.random.default_rng(seed)
    nan_rows = np.where(np.isnan(X).any(axis=1))[0]
    clean_rows = np.where(~np.isnan(X).any(axis=1))[0]
    half = n // 2
    pick = np.concatenate([
        rng.choice(nan_rows, size=min(half, len(nan_rows)), replace=False),
        rng.choice(clean_rows, size=n-min(half, len(nan_rows)), replace=False),
    ])
    sample = X[pick]
    assert np.isnan(sample).any(), "parity sample must contain NaN (R9)"
    return sample


# ─── Publish manifest (the §3 SoT-chain deliverable application layer reads) ────────────────
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _latest_log(target: str, version: str) -> dict:
    logs = sorted(LOGS_DIR.glob(f"{target}_{version}_*.json"))
    return json.loads(logs[-1].read_text()) if logs else {}


def build_manifest(version: str, parities: dict[str, dict]) -> dict:
    """Single index the browser application reads to discover + correctly score the ONNX models.
    Carries the exact input contract (positional feature order, encoders, sentinels), the per-model
    output interpretation, the 17-col prediction schema, and provenance (fingerprint, seasons,
    versions, parity). Assembled from schema constants + encoders.json + training logs + the
    on-disk artefacts-no warehouse read."""
    encoders = json.loads(ENCODERS_PATH.read_text()) if ENCODERS_PATH.exists() else {}
    rep = _latest_log("degradation_regressor_p50", version)  # representative for shared provenance
    training_seasons = rep.get("training_seasons") or []
    holdout_season = (max(training_seasons) + 1) if training_seasons else None

    models = []
    for spec in S.PRODUCTION_TARGETS:
        base = S.artefact_name(spec, version)
        onnx_path, bst_path = MODELS_DIR / f"{base}.onnx", MODELS_DIR / f"{base}.bst"
        log = _latest_log(spec.name, version)
        entry = {
            "name": spec.name,
            "family": spec.family,
            "kind": spec.kind,
            "objective": spec.objective,
            "onnx": onnx_path.name,
            "onnx_sha256": _sha256(onnx_path) if onnx_path.exists() else None,
            "booster_sha256": _sha256(bst_path) if bst_path.exists() else None,
            "cv_headline": log.get("headline_cv"),
            "headline_metric": log.get("headline_metric"),
        }
        if spec.kind == "quantile":
            entry["quantile_alpha"] = spec.quantile_alpha
            entry["output"] = {"index": 0, "meaning": "degradation_jump_seconds",
                               "bounds": [-S.TARGET_BOUND, S.TARGET_BOUND]}
        elif spec.kind == "classification":
            entry["output"] = {"probabilities_index": 1, "zipmap": True,
                               "class_order": list(S.CLIFF_CLASS_LABELS),
                               "meaning": "laps_until_cliff_class softprob"}
        else:
            entry["output"] = {"index": 0, "meaning": "remaining_stint_life_laps",
                               "postprocess": "clip(>=0)"}
        models.append(entry)

    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "name": "Off the Pace-Tyre Degradation Predictors",
        "model_version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "tensor_name": "input",
            "dtype": "float32",
            "shape": ["batch", len(S.FEATURE_COLUMNS)],
            "feature_order": list(S.FEATURE_COLUMNS),   # positional-DO NOT reorder
            "n_features": len(S.FEATURE_COLUMNS),
            "encoding": {
                "categorical_columns": list(S.CATEGORICAL_COLUMNS),
                "boolean_columns": list(S.BOOLEAN_COLUMNS),
                "missing_ordinal": S.MISSING_ORDINAL,   # NULL/unseen categorical → this
                "boolean_true_false": [1.0, 0.0],
                "continuous_missing": "NaN (XGBoost native-missing; preserve, do not impute)",
                "encoders": encoders,                    # {col: {value: ordinal}}
            },
        },
        "models": models,
        "cliff_class_labels": list(S.CLIFF_CLASS_LABELS),
        "predictions_schema": [f.name for f in S.PREDICTIONS_ARROW_SCHEMA],
        "provenance": {
            "source_mart": S.MART,
            "training_seasons": training_seasons,
            "holdout_season": holdout_season,
            "dataset_fingerprint": rep.get("fingerprint"),
            "random_state": S.RANDOM_STATE,
            "library_versions": rep.get("versions", {}),
            "onnx_parity": {"atol": ATOL, "rtol": RTOL,
                            "max_abs_diff": {t: p["max_abs_diff"] for t, p in parities.items()},
                            "all_pass": all(p["pass"] for p in parities.values())},
        },
        "related": {"model_card": "model_card.json", "encoders": "encoders.json"},
    }


def write_manifest(version: str, parities: dict[str, dict]) -> Path:
    manifest = build_manifest(version, parities)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"wrote {MANIFEST_PATH}  ({len(manifest['models'])} models, "
          f"{manifest['input']['n_features']} features, version={version})")
    return MANIFEST_PATH


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=[t.name for t in S.PRODUCTION_TARGETS])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--version", default="v1")
    ap.add_argument("--no-manifest", action="store_true",
                    help="skip writing manifest.json (e.g. single-target debug runs)")
    args = ap.parse_args()

    targets = [t.name for t in S.PRODUCTION_TARGETS] if args.all else [args.target]
    sample = nan_bearing_sample()
    failed, parities = [], {}
    for t in targets:
        convert(t, args.version)
        r = parity(t, args.version, sample)
        parities[t] = r
        flag = "OK " if r["pass"] else "FAIL"
        print(f"[{flag}] {t:30s} abs={r['max_abs_diff']:.2e} rel={r['max_rel_diff']:.2e} "
              f"(atol={ATOL:.0e} rtol={RTOL:.0e}, {r['kind']}, {r['n_rows']} rows incl NaN)")
        if not r["pass"]:
            failed.append(t)
    if failed:
        print(f"\nPARITY FAILED: {failed}-do NOT loosen atol; escalate (R1/§15-4).")
        return 1
    print("\nONNX parity OK for all targets.")
    # Finalise the publish manifest only on a full, all-pass export (the application layer contract).
    if args.all and not args.no_manifest:
        write_manifest(args.version, parities)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
