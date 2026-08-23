"""Convert trained .bst boosters to ONNX and prove prediction parity (the D1/R1 gate).

CLI:
  python -m ml.src.export_onnx --target degradation_regressor_p50 --version smoke
  python -m ml.src.export_onnx --all            # MODEL_VERSION_DEFAULT, writes manifest.json

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
from ml.src import survival as SV

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
# The AFT margin offset must be the SAME number on every row, not the mean of a
# scatter. The threshold discriminates float32 noise from a structural error, and
# is set from measurement rather than from taste: on the production sample the
# observed spread is 2.1e-6 about a margin of magnitude 4.1 (relative ~5e-7), which
# is ordinary float32 tree-sum reordering. A real dispatch failure -- the
# unretagged LOGISTIC graph, a wrong base_score, a post-transform left on -- moves
# the offset by O(0.1) to O(10). 1e-4 sits ~50x above the noise floor and three to
# five orders below any genuine break, so it can fail for a real reason and cannot
# fail for a fake one.
OFFSET_CONSTANT_TOL = 1e-4


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


# ─── AFT export: retag the objective, then recover the offset ───────────────────
# onnxmltools dispatches on the booster's objective string, and it has no case for
# survival:aft. Handed one it produces a TreeEnsembleCLASSIFIER with a LOGISTIC
# post-transform and label/probabilities outputs -- a graph whose output is not the
# margin, not the prediction, and not even the right shape. (ml_execution_plan.md
# Phase 3c expected "the raw margin, exp(onnx - 1.193147)". It is not the raw
# margin; that constant was ln(2) + the 0.5 base_score, conflating two different
# extraction points.)
#
# So the objective is retagged to reg:squarederror for export only. The trees are
# untouched -- only the tag the converter dispatches on, and base_score, which is
# zeroed so the graph emits the bare tree sum. That leaves a constant offset
# between the graph and the AFT margin (AFT applies log(base_score) as its
# intercept, so with base_score 0.5 the gap is exactly -ln 2), and rather than
# hardcode it we measure it and assert it is actually constant.
def _retagged_regressor(bst_path: Path) -> xgb.Booster:
    """The same trees, tagged so onnxmltools emits a TreeEnsembleRegressor."""
    src = SV.load_booster(bst_path)
    raw = json.loads(src.save_raw(raw_format="json").decode("utf-8"))
    raw["learner"]["objective"] = {"name": "reg:squarederror",
                                   "reg_loss_param": {"scale_pos_weight": "1"}}
    raw["learner"]["learner_model_param"]["base_score"] = "0E0"
    out = xgb.Booster()
    out.load_model(bytearray(json.dumps(raw), "utf-8"))
    out.feature_names = None
    return out


def _aft_margin_offset(bst_path: Path, sess, sample: np.ndarray) -> float:
    """Recover `margin - onnx_output` and prove it is a constant, not an average.

    The plan says to take the constant from a row rather than hardcoding it. Taking
    it from one row is exactly what happens -- row 0 -- but a single row can only
    ever agree with itself, so the spread across the whole parity sample is checked
    before the number is allowed to ship. That check is the difference between a
    calibration and a coincidence.
    """
    aft = SV.load_booster(bst_path)
    m = SV.margin(aft, sample)
    onx = np.asarray(sess.run(None, {"input": sample})[0]).reshape(-1).astype(np.float64)
    diffs = m - onx
    offset = float(diffs[0])                    # from a row, per the plan
    spread = float(np.max(np.abs(diffs - offset)))
    if spread > OFFSET_CONSTANT_TOL:
        raise ValueError(
            f"AFT margin offset is not constant across the parity sample: "
            f"spread={spread:.3e} > {OFFSET_CONSTANT_TOL:.0e}. The ONNX graph is not "
            f"a fixed shift of the AFT margin, so exp(onnx + offset) cannot be "
            f"parity-correct -- do not ship this conversion.")
    return offset


def convert(target: str, version: str) -> Path:
    spec = S.TARGET_BY_NAME[target]
    bst_path, onnx_path = _paths(spec, version)
    if spec.kind == "survival":
        booster = _retagged_regressor(bst_path)
        n_features = int(json.loads(booster.save_config())
                         ["learner"]["learner_model_param"]["num_feature"])
        onx = onnxmltools.convert_xgboost(
            booster, initial_types=[("input", FloatTensorType([None, n_features]))])
        onnx_path.write_bytes(onx.SerializeToString())
        return onnx_path
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
    bst_path, onnx_path = _paths(spec, version)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    extra: dict = {}

    if spec.kind == "survival":
        # Parity is measured on LAPS -- the number the gauge renders -- not on the
        # graph's raw output. Checking the raw output would pass happily while the
        # post-transform was wrong, which is the failure this whole phase is about.
        aft = SV.load_booster(bst_path)
        aft_scale = SV.aft_params(aft)["scale"]
        offset = _aft_margin_offset(bst_path, sess, sample)
        onnx_raw = np.asarray(sess.run(None, {"input": sample})[0]).reshape(-1)
        bst = SV.predict_laps(aft, sample, aft_scale)
        onx = SV.laps_from_margin(onnx_raw.astype(np.float64) + offset, aft_scale)
        extra = {"aft_margin_offset": offset, "aft_scale": aft_scale}
    elif spec.kind == "classification":
        model = _load_sklearn(spec, bst_path)
        bst = model.predict_proba(sample)
        onx = _onnx_proba(sess, sample, n_classes=len(S.CLIFF_CLASS_LABELS))
    else:
        model = _load_sklearn(spec, bst_path)
        bst = model.predict(sample).reshape(-1)
        onx = _onnx_regression(sess, sample)

    a, b = bst.reshape(-1).astype(np.float64), onx.reshape(-1).astype(np.float64)
    max_abs = float(np.max(np.abs(a-b)))
    max_rel = float(np.max(np.abs(a-b) / (np.abs(a) + 1e-9)))
    ok = bool(np.allclose(a, b, atol=ATOL, rtol=RTOL))
    return {"target": target, "max_abs_diff": max_abs, "max_rel_diff": max_rel,
            "atol": ATOL, "rtol": RTOL, "pass": ok,
            "n_rows": int(sample.shape[0]), "kind": spec.kind, **extra}


def nan_bearing_sample(n: int = PARITY_ROWS, seed: int = S.RANDOM_STATE) -> np.ndarray:
    """500-row float32 sample guaranteed to contain NaN (R9). Sourced from training
    today; the NaN concern is orthogonal to season."""
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


# ─── Publish manifest (the SoT-chain deliverable the application layer reads) ───────────────
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
        elif spec.kind == "survival":
            # Everything the browser needs to turn the graph output into laps. The
            # offset and scale are measured/read at export, never hardcoded in the
            # app -- app/src/ml/survival.ts reads them from here.
            par = parities.get(spec.name, {})
            entry["output"] = {
                "index": 0,
                "meaning": "aft_margin (log remaining_stint_life_laps + shift)",
                "postprocess": "exp(x + margin_offset) - label_shift, clip(>=0)",
                "margin_offset": par.get("aft_margin_offset"),
                "label_shift": S.AFT_LABEL_SHIFT,
                "aft_distribution": S.AFT_DISTRIBUTION,
                "aft_scale": par.get("aft_scale"),
                # quantile q = exp(margin + aft_scale * probit(q)) - label_shift
                "quantiles": {f"p{int(q*100)}": q for q in S.STINT_LIFE_QUANTILES},
                "censored_share_train": (log.get("aft") or {}).get("censored_share"),
                "c_index_cv": (log.get("aft") or {}).get("c_index_cv"),
            }
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
    ap.add_argument("--version", default=S.MODEL_VERSION_DEFAULT,
                    help="artefact version to convert (default: MODEL_VERSION_DEFAULT, "
                         "matching predict.py / evaluate.py / card.py). CI passes --version smoke.")
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
        print(f"\nPARITY FAILED: {failed}-do NOT loosen atol; escalate.")
        return 1
    print("\nONNX parity OK for all targets.")
    # Finalise the publish manifest only on a full, all-pass export (the application layer contract).
    if args.all and not args.no_manifest:
        write_manifest(args.version, parities)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
