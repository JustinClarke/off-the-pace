"""Dump real laps + booster-scored ground truth to /tmp/parity_rows.json for the app's
headless ONNX-parity test (app/src/ml/parity.node.test.ts).

Why score with the boosters here (not just read mart_degradation_predictions)?
To keep the parity test a true ONNX↔booster integrity check we score the .bst boosters
directly on the same feature vector the app reconstructs, rather than trusting a stored
artefact. The full v3 feature frame lives in fct_cliff_prediction_features (the telemetry/
air columns that once lived in int_lap_powertrain_signature + int_air_density were folded
in during ml-v0.2 §2), so the vector is read straight from that one mart. Boosters are
loaded at S.MODEL_VERSION_DEFAULT so ground truth tracks whatever version the app ships.

Usage:
    ./.venv/bin/python scripts/dump_parity_rows.py [--season 2024] [--limit 48]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import xgboost as xgb

from ml.src import schema as S

DATA = Path("app/public/data")
MODELS = Path("ml/models")
SOURCE = str(DATA / "facts/fct_cliff_prediction_features/{season}.parquet")


def _encode(df: pd.DataFrame, encoders: dict, order: list[str]) -> np.ndarray:
    """Mirror ml.src.features._encode_frame, using the persisted encoders.json."""
    out = {}
    for c in order:
        if c in S.CATEGORICAL_COLUMNS:
            out[c] = df[c].astype("object").map(encoders[c]).fillna(S.MISSING_ORDINAL).astype("float32")
        elif c in S.BOOLEAN_COLUMNS:
            out[c] = df[c].map({True: 1.0, False: 0.0}).astype("float32")
        else:
            out[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")
    return pd.DataFrame(out)[order].to_numpy(np.float32)


def _load(name: str):
    spec = S.TARGET_BY_NAME[name]
    cls = xgb.XGBClassifier if spec.kind == "classification" else xgb.XGBRegressor
    m = cls()
    m.load_model(str(MODELS / f"{name}_{S.MODEL_VERSION_DEFAULT}.bst"))
    m.get_booster().feature_names = None
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2024)
    ap.add_argument("--limit", type=int, default=48)
    ap.add_argument("--out", default="/tmp/parity_rows.json")
    args = ap.parse_args()

    path = SOURCE.format(season=args.season)
    con = duckdb.connect()
    available = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()}
    order = list(S.FEATURE_COLUMNS)
    missing = [c for c in order if c not in available]
    if missing:
        raise SystemExit(f"feature columns missing from fct_cliff_prediction_features: {missing}")

    select = ",\n      ".join(f'f."{c}" AS "{c}"' for c in order)
    df = con.execute(f"""
      SELECT f.lap_id AS lap_id,
      {select}
      FROM read_parquet('{path}') f
      ORDER BY f.lap_id
      LIMIT {args.limit}
    """).df()

    encoders = json.loads((MODELS / "encoders.json").read_text())
    X = _encode(df, encoders, order)

    # Ground truth via the boosters, post-processed exactly like predict.py / the app's infer.ts.
    p10 = _load("degradation_regressor_p10").predict(X)
    p50 = _load("degradation_regressor_p50").predict(X)
    p90 = _load("degradation_regressor_p90").predict(X)
    trio = np.clip(np.sort(np.vstack([p10, p50, p90]).T, axis=1), -10, 10)
    life = np.clip(_load("stint_life_regressor").predict(X), 0, None)
    proba = _load("cliff_classifier").predict_proba(X)
    labels = np.asarray(S.CLIFF_CLASS_LABELS)[proba.argmax(axis=1)]

    recs = json.loads(df.to_json(orient="records"))  # NaN → null
    for i, r in enumerate(recs):
        r["m_p10"] = float(trio[i, 0])
        r["m_p50"] = float(trio[i, 1])
        r["m_p90"] = float(trio[i, 2])
        r["m_life"] = float(life[i])
        r["m_cliff"] = str(labels[i])

    Path(args.out).write_text(json.dumps(recs))
    dist = {str(k): int(v) for k, v in pd.Series(labels).value_counts().items()}
    print(f"wrote {len(recs)} rows → {args.out}  (booster ground truth; cliff dist: {dist})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
