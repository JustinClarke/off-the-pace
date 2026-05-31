"""Dump real laps + booster-scored ground truth to /tmp/parity_rows.json for the app's
headless ONNX-parity test (app/src/ml/parity.node.test.ts).

Why score with the boosters here (not just read mart_degradation_predictions)?
The shipped mart was generated against an earlier warehouse state whose
fct_cliff_prediction_features still joined in 8 powertrain/air-density features
(n_gear_changes, mean_rpm, max_rpm, pct_full_throttle, pct_drs_active,
short_shift_index, air_density_kgm3, density_ratio_to_ref). The current mart SQL no
longer joins them, so the stored predictions are stale relative to today's parquet.
To keep the parity test a meaningful ONNX↔booster integrity check (not a check against
a stale artefact), we reconstruct the 38-feature vector the training way cliff mart +
int_lap_powertrain_signature + int_air_density, joined on lap_id and score it with the
.bst boosters. The app then proves its ONNX run matches this booster ground truth.

(When the warehouse + mart are regenerated consistently, swap ground truth back to the
mart columns; the reconstruction + tolerance stay identical.)

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
SOURCES = {
    "f": DATA / "facts/fct_cliff_prediction_features/{season}.parquet",
    "p": DATA / "intermediates/int_lap_powertrain_signature/{season}.parquet",
    "a": DATA / "intermediates/int_air_density/{season}.parquet",
}
PRIORITY = ["f", "p", "a"]


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
    m.load_model(str(MODELS / f"{name}_v1.bst"))
    m.get_booster().feature_names = None
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2024)
    ap.add_argument("--limit", type=int, default=48)
    ap.add_argument("--out", default="/tmp/parity_rows.json")
    args = ap.parse_args()

    paths = {a: str(p).format(season=args.season) for a, p in SOURCES.items()}
    con = duckdb.connect()
    cols = {
        a: {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{paths[a]}')").fetchall()}
        for a in PRIORITY
    }
    order = list(S.FEATURE_COLUMNS)

    def owner(c: str) -> str:
        for a in PRIORITY:
            if c in cols[a]:
                return a
        raise SystemExit(f"feature column {c!r} not present in any source")

    select = ",\n      ".join(f'{owner(c)}."{c}" AS "{c}"' for c in order)
    df = con.execute(f"""
      SELECT f.lap_id AS lap_id,
      {select}
      FROM read_parquet('{paths["f"]}') f
      LEFT JOIN read_parquet('{paths["p"]}') p USING (lap_id)
      LEFT JOIN read_parquet('{paths["a"]}') a USING (lap_id)
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
