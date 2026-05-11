"""Score every lap with the five models → Arrow-validated predictions parquet.

CLI:
  python -m ml.src.predict --out data/marts/mart_degradation_predictions.parquet [--version v1|smoke]

Output columns and dtypes are pinned by schema.PREDICTIONS_ARROW_SCHEMA (17). The quantile
trio is row-sorted (no p10>p50>p90 crossing); a crossing rate > 1% is logged. Mismatch
against the Arrow schema aborts the write.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import xgboost as xgb

from ml.src import features as F
from ml.src import schema as S

MODELS_DIR = Path("ml/models")
CROSSING_WARN_THRESHOLD = 0.01


def _load_model(spec: S.TargetSpec, version: str):
    path = MODELS_DIR / f"{S.artefact_name(spec, version)}.bst"
    if not path.exists():
        raise FileNotFoundError(f"missing booster {path}-run `make ml-train` (or --version smoke)")
    cls = xgb.XGBClassifier if spec.kind == "classification" else xgb.XGBRegressor
    model = cls()
    model.load_model(str(path))
    model.get_booster().feature_names = None  # positional scoring (FEATURE_COLUMNS order)
    return model


def run(out: str, version: str = S.MODEL_VERSION_DEFAULT) -> pa.Table:
    X_all, meta, _, holdout_season = F.load_scoring_frame()
    Xv = X_all.to_numpy(dtype=np.float32)

    spec = {s.name: s for s in S.PRODUCTION_TARGETS}
    p10 = _load_model(spec["degradation_regressor_p10"], version).predict(Xv)
    p50 = _load_model(spec["degradation_regressor_p50"], version).predict(Xv)
    p90 = _load_model(spec["degradation_regressor_p90"], version).predict(Xv)

    # Quantile crossing guard: row-sort the trio so p10 ≤ p50 ≤ p90.
    trio = np.sort(np.vstack([p10, p50, p90]).T, axis=1)
    crossing_rate = float(np.mean((p10 > p50) | (p50 > p90)))
    if crossing_rate > CROSSING_WARN_THRESHOLD:
        print(f"WARNING: quantile crossing rate {crossing_rate:.2%} > 1% (row-sorted on write)")
    s_p10, s_p50, s_p90 = trio[:, 0], trio[:, 1], trio[:, 2]

    clf = _load_model(spec["cliff_classifier"], version)
    proba = clf.predict_proba(Xv)  # [n, 4] in CLIFF_CLASS_LABELS order
    argmax = proba.argmax(axis=1)
    labels = np.asarray(S.CLIFF_CLASS_LABELS)

    life = np.clip(_load_model(spec["stint_life_regressor"], version).predict(Xv), 0, None)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cols = {
        "lap_id": meta["lap_id"].astype("string"),
        "stint_id": meta["stint_id"].astype("string"),
        "race_year": meta["race_year"].astype("int32"),
        "circuit_key": meta["circuit_key"].astype("string"),
        "is_holdout": (meta["race_year"] == holdout_season).to_numpy(),
        "is_in_envelope": meta["is_training_eligible"].astype("bool").to_numpy(),
        "predicted_degradation_jump_s": s_p50.astype("float64"),
        "predicted_degradation_jump_p10_s": s_p10.astype("float64"),
        "predicted_degradation_jump_p90_s": s_p90.astype("float64"),
        "predicted_cliff_class": labels[argmax].astype("object"),
    }
    for i, pc in enumerate(S.PROB_COLUMNS):
        cols[pc] = proba[:, i].astype("float64")
    cols["predicted_remaining_stint_life_laps"] = life.astype("float64")
    cols["model_version"] = np.full(len(meta), version, dtype=object)
    cols["predicted_at"] = np.full(len(meta), np.datetime64(now, "us"))

    # Build straight onto the schema → any column/type drift aborts here.
    arrays = [pa.array(cols[f.name], type=f.type) for f in S.PREDICTIONS_ARROW_SCHEMA]
    table = pa.Table.from_arrays(arrays, schema=S.PREDICTIONS_ARROW_SCHEMA)

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out)
    n_hold = int(np.count_nonzero(cols["is_holdout"]))
    n_env = int(np.count_nonzero(cols["is_in_envelope"]))
    print(f"wrote {table.num_rows} rows → {out}  "
          f"(holdout={n_hold}, in_envelope={n_env}, crossing={crossing_rate:.2%}, version={version})")
    return table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/marts/mart_degradation_predictions.parquet")
    ap.add_argument("--version", default=S.MODEL_VERSION_DEFAULT)
    args = ap.parse_args()
    run(args.out, args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
