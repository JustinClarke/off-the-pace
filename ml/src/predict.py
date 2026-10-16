"""Score every lap with the five models → Arrow-validated predictions parquet.

CLI:
  python -m ml.src.predict --out data/marts/mart_degradation_predictions.parquet [--version v1|smoke]

Output columns and dtypes are pinned by schema.PREDICTIONS_ARROW_SCHEMA (19). The quantile
trio is row-sorted (no p10>p50>p90 crossing); a crossing rate > 1% is logged. Mismatch
against the Arrow schema aborts the write.

Stint life is an AFT fit, so it is written as a median plus the 10th/90th percentile
of the same log-normal rather than as a lone point estimate -- see ml/src/survival.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import xgboost as xgb

from ml.src import features as F
from ml.src import schema as S
from ml.src import survival as SV

MODELS_DIR = Path("ml/models")
CROSSING_WARN_THRESHOLD = 0.01


def _load_model(spec: S.TargetSpec, version: str, models_dir: Path | None = None):
    path = (models_dir or MODELS_DIR) / f"{S.artefact_name(spec, version)}.bst"
    if not path.exists():
        raise FileNotFoundError(f"missing booster {path}-run `make ml-train` (or --version smoke)")
    cls = xgb.XGBClassifier if spec.kind == "classification" else xgb.XGBRegressor
    model = cls()
    model.load_model(str(path))
    model.get_booster().feature_names = None  # positional scoring (FEATURE_COLUMNS order)
    return model


def _flag_chance_columns(lookup_path: str, version: str, life_path: Path, life_scale: float,
                         life: np.ndarray, lap_ids: np.ndarray) -> dict[str, pa.Array]:
    """CO-08: calibrated + raw chance to reach the flag, final-stint rows only (NULL elsewhere).

    Refuses a lookup fitted for a different model: the recalibration is a property of one
    booster's predictions, so pairing it with another is a silent miscalibration."""
    from ml.src import flag_chance as FC

    lookup = json.loads(Path(lookup_path).read_text())
    life_sha = hashlib.sha256(life_path.read_bytes()).hexdigest()
    problems = []
    if lookup.get("model_version") != version:
        problems.append(f"lookup model_version {lookup.get('model_version')!r} != {version!r}")
    if lookup.get("booster_sha256") != life_sha:
        problems.append(f"lookup booster_sha256 {str(lookup.get('booster_sha256'))[:12]} != "
                        f"{life_path.name} {life_sha[:12]}")
    if abs(float(lookup.get("aft_scale", np.nan)) - life_scale) > 1e-6:
        problems.append(f"lookup aft_scale {lookup.get('aft_scale')} != booster {life_scale}")
    if problems:
        raise ValueError("flag-chance lookup does not match the stint-life booster: "
                         + "; ".join(problems))
    ctx = FC.load_flag_context(lap_ids)
    ltf = ctx["laps_to_flag"].to_numpy(dtype=np.float64)
    show = ctx["is_final_stint"].to_numpy(dtype=bool) & ~np.isnan(ltf)
    raw = FC.raw_flag_chance(life, np.where(show, ltf, 0.0), life_scale, lookup["label_shift"])
    cal = FC.apply_lookup(raw, lookup)
    return {"flag_chance": pa.array(cal, type=pa.float64(), mask=~show),
            "flag_chance_raw": pa.array(raw, type=pa.float64(), mask=~show)}


def run(out: str, version: str = S.MODEL_VERSION_DEFAULT, *,
        models_dir: str | None = None, flag_lookup: str | None = None) -> pa.Table:
    """`models_dir` reads the boosters from somewhere other than ml/models (a scratch build).
    `flag_lookup` adds the CO-08 columns and writes PREDICTIONS_ARROW_SCHEMA_WITH_FLAG;
    without it the output is the 19-column contract, unchanged."""
    mdir = Path(models_dir) if models_dir else MODELS_DIR
    X_all, meta, _, holdout_season = F.load_scoring_frame()

    # 02b/D12: the contract is no longer one width. `load_scoring_frame` returns the FULL
    # FEATURE_COLUMNS frame, so each model has to be handed its OWN masked matrix -- the
    # qualifying columns belong to cliff_classifier and nothing else. Scoring is positional
    # (feature_names is cleared in _load_model), so the column ORDER here has to be the order
    # the booster was fitted in; S.feature_columns_for preserves FEATURE_COLUMNS order, which
    # is what features.py fits in. Handing every model one shared matrix, as this did before,
    # now raises a shape mismatch on the four 32-wide families.
    def _mat(target: str) -> np.ndarray:
        return X_all[list(S.feature_columns_for(target))].to_numpy(dtype=np.float32)

    spec = {s.name: s for s in S.PRODUCTION_TARGETS}
    p10 = _load_model(spec["degradation_regressor_p10"], version, mdir).predict(_mat("degradation_regressor_p10"))
    p50 = _load_model(spec["degradation_regressor_p50"], version, mdir).predict(_mat("degradation_regressor_p50"))
    p90 = _load_model(spec["degradation_regressor_p90"], version, mdir).predict(_mat("degradation_regressor_p90"))

    # Quantile crossing guard: row-sort the trio so p10 ≤ p50 ≤ p90.
    trio = np.sort(np.vstack([p10, p50, p90]).T, axis=1)
    crossing_rate = float(np.mean((p10 > p50) | (p50 > p90)))
    if crossing_rate > CROSSING_WARN_THRESHOLD:
        print(f"WARNING: quantile crossing rate {crossing_rate:.2%} > 1% (row-sorted on write)")
    s_p10, s_p50, s_p90 = trio[:, 0], trio[:, 1], trio[:, 2]

    clf = _load_model(spec["cliff_classifier"], version, mdir)
    proba = clf.predict_proba(_mat("cliff_classifier"))  # [n, 4] in CLIFF_CLASS_LABELS order
    argmax = proba.argmax(axis=1)
    labels = np.asarray(S.CLIFF_CLASS_LABELS)

    # Stint life: raw Booster, not the sklearn wrapper. The AFT margin has to be
    # post-transformed here in exactly the way infer.ts does it in the browser, and
    # the scale comes off the artefact itself so the two cannot drift apart.
    life_path = mdir / f"{S.artefact_name(spec['stint_life_regressor'], version)}.bst"
    if not life_path.exists():
        raise FileNotFoundError(f"missing booster {life_path}-run `make ml-train` (or --version smoke)")
    life_bst = SV.load_booster(life_path)
    life_scale = SV.aft_params(life_bst)["scale"]
    life_margin = SV.margin(life_bst, _mat("stint_life_regressor"))
    life = SV.laps_from_margin(life_margin, life_scale)
    life_p10 = SV.laps_from_margin(life_margin, life_scale, S.STINT_LIFE_QUANTILES[0])
    life_p90 = SV.laps_from_margin(life_margin, life_scale, S.STINT_LIFE_QUANTILES[2])

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
    cols["predicted_remaining_stint_life_p10_laps"] = life_p10.astype("float64")
    cols["predicted_remaining_stint_life_p90_laps"] = life_p90.astype("float64")
    cols["model_version"] = np.full(len(meta), version, dtype=object)
    cols["predicted_at"] = np.full(len(meta), np.datetime64(now, "us"))

    # Build straight onto the schema → any column/type drift aborts here.
    schema = S.PREDICTIONS_ARROW_SCHEMA
    arrays = [pa.array(cols[f.name], type=f.type) for f in schema]
    if flag_lookup:
        flag = _flag_chance_columns(flag_lookup, version, life_path, life_scale, life,
                                    meta["lap_id"].to_numpy())
        schema = S.PREDICTIONS_ARROW_SCHEMA_WITH_FLAG
        arrays += [flag[c] for c in S.FLAG_CHANCE_COLUMNS]
    table = pa.Table.from_arrays(arrays, schema=schema)

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
    ap.add_argument("--models-dir", help="read boosters from here instead of ml/models")
    ap.add_argument("--flag-lookup", help="CO-08 flag-chance lookup JSON; adds flag_chance columns")
    args = ap.parse_args()
    run(args.out, args.version, models_dir=args.models_dir, flag_lookup=args.flag_lookup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
