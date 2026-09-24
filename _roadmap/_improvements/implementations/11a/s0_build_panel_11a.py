"""11a stage 0 - build the out-of-sample panel the conformal layer calibrates on.

WHY A SHADOW FIT EXISTS HERE
----------------------------
Production v11 fits on `race_year < resolve_holdout_season()` = every season 2018-2024
(2025 is unpopulated), and `load_scoring_frame` then scores every lap. So every row of
`data/marts/mart_degradation_predictions.parquet` is IN-SAMPLE. R4's 13.2-point
per-circuit coverage spread is measured on those rows and is the *motivation*, never a
baseline. 11a's acceptance requires coverage "before and after, out of sample", which
cannot be read off a model that trained on the evaluation rows.

So this builds a SHADOW fit: the same 32-feature contract (post-08j), the same tuned
hyperparameters, the same IPW survival weights, the same row-sort of the trio - fitted on
2018-2022 ONLY, leaving 2023 and 2024 genuinely out-of-sample for calibration and test.

It writes NOTHING to ml/models/ and touches no production artefact. Per
foundations/epistemics.md this is a throwaway probe: warehouse opened read-only,
outputs confined to this folder.

Outputs
-------
  panel_shadow.parquet      2023+2024 rows, shadow quantiles, out of sample
  panel_production.parquet  all rows, production v11 quantiles, in-sample except
                            is_training_eligible = False (never trained on)
  s0_manifest.json          row counts, seasons, params digest, fit provenance
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ml.src import features as F
from ml.src import schema as S
from ml.src import train as T

HERE = Path(__file__).resolve().parent
MODELS_DIR = Path("ml/models")
PRED_PARQUET = Path("data/marts/mart_degradation_predictions.parquet")

# The shadow split, 3 / 2 / 2 over the seven ingested seasons.
#
# Both the calibration and the test half must be out of sample: a conformal quantile
# computed on rows the model trained on is optimistically tight, so calibrating in-sample
# would understate the correction. That forces fit / calib / test to be three disjoint
# blocks of seasons.
#
# Why two seasons of TEST and not one: every 2024 circuit hosts exactly one race (the
# constraint 01b hit and had to drop its different-race arm over). With a single test
# season, "per-circuit coverage" IS "per-race coverage" - circuit and race are perfectly
# confounded and no amount of data separates "Mexico is miscalibrated" from "the 2024
# Mexico race was unusual". Two test seasons give most circuits a within-circuit
# replicate, which is what makes the circuit claim testable at all.
#
# Why two seasons of CALIB: one season is ~1 race per circuit, and a per-circuit
# conformal quantile off a single race inherits that race's idiosyncrasy wholesale.
#
# The cost is a 3-season fit (~33k rows against production's ~82k), so the shadow model
# is weaker than production v11. That is a caveat on the LEVEL of coverage, not on the
# mechanism being tested; s1 quantifies it against production's own marginal.
FIT_SEASONS = [2018, 2019, 2020]
CALIB_SEASONS = [2021, 2022]
TEST_SEASONS = [2023, 2024]
POST_SEASONS = CALIB_SEASONS + TEST_SEASONS

QUANTILE_TARGETS = ["degradation_regressor_p10",
                    "degradation_regressor_p50",
                    "degradation_regressor_p90"]

# Columns carried alongside the quantiles for stratified reporting. `compound` and
# `lap_in_stint` reproduce 01b's `compound x lap-in-stint band x circuit` strata;
# `race_id` is the clustering unit for every interval and every e-value in this item.
CARRY = ["lap_id", "race_id", "race_year", "circuit_key", "driver_id",
         "compound", "lap_in_stint", "is_training_eligible", "survival_weight"]

TARGET = S.DEGRADATION_TARGET


def _load_raw() -> pd.DataFrame:
    """Every mart row with the columns this item needs. Read-only, as required."""
    con = duckdb.connect(S.DUCKDB_PATH, read_only=True)
    try:
        holdout_season = F.resolve_holdout_season(con)
        df = con.execute(f"SELECT * FROM {S.MART}").df()
    finally:
        con.close()
    return df, holdout_season


def _fit_shadow(raw: pd.DataFrame) -> pd.DataFrame:
    """Fit p10/p50/p90 on FIT_SEASONS, predict on POST_SEASONS.

    Reuses the production encoding and model-construction paths verbatim
    (`features._build_encoders`, `features._encode_frame`, `train._make_model`,
    `train._fit`). The only departure from `train.train_one` is the season filter and
    that no artefact is written.
    """
    # Training population: exactly load_features' rule, restricted to the fit seasons.
    fit_mask = (raw["is_training_eligible"].astype(bool)
                & raw["race_year"].isin(FIT_SEASONS))
    fit_df = raw[fit_mask].reset_index(drop=True)

    # Encoders from the SHADOW training seasons only. Using production's all-season
    # encoders here would let the fit see category vocabulary from 2023-24; that is a
    # structural leak, small but real, and this item cannot afford one in its baseline.
    encoders = F._build_encoders(fit_df)

    post_df = raw[raw["race_year"].isin(POST_SEASONS)].reset_index(drop=True)

    X_fit = F._encode_frame(fit_df, encoders)[list(S.FEATURE_COLUMNS)]
    X_post = F._encode_frame(post_df, encoders)[list(S.FEATURE_COLUMNS)]

    y_fit = pd.to_numeric(fit_df[TARGET], errors="coerce")
    keep = y_fit.notna().to_numpy()          # L0-7: XGBoost errors on NaN in y
    X_fit, y_fit = X_fit[keep].reset_index(drop=True), y_fit[keep].reset_index(drop=True)
    meta_fit = fit_df[keep].reset_index(drop=True)

    out = post_df[CARRY].copy()
    out[TARGET] = pd.to_numeric(post_df[TARGET], errors="coerce")
    out["split"] = np.where(out["race_year"].isin(CALIB_SEASONS), "calib", "test")

    preds = {}
    for name in QUANTILE_TARGETS:
        spec = S.TARGET_BY_NAME[name]
        params = json.loads((MODELS_DIR / f"{name}_best_params.json").read_text())
        model = T._make_model(spec, params)
        T._fit(model, spec, X_fit, y_fit, meta_fit)   # carries survival_weight IPW
        preds[name] = model.predict(X_post.to_numpy(dtype=np.float32))
        print(f"  [shadow] {name}: fitted on n={len(y_fit):,}, "
              f"scored n={len(X_post):,}")

    # predict.py row-sorts the trio before writing, so the app never sees a crossing.
    # Reproduce that here or the coverage measured is not the coverage the app renders.
    trio = np.vstack([preds[QUANTILE_TARGETS[0]],
                      preds[QUANTILE_TARGETS[1]],
                      preds[QUANTILE_TARGETS[2]]]).T
    raw_crossing = float(np.mean((trio[:, 0] > trio[:, 1]) | (trio[:, 1] > trio[:, 2])))
    trio = np.sort(trio, axis=1)
    out["q10"], out["q50"], out["q90"] = trio[:, 0], trio[:, 1], trio[:, 2]
    out.attrs["raw_crossing_rate"] = raw_crossing
    print(f"  [shadow] raw quantile crossing rate (pre-sort): {raw_crossing:.4%}")
    return out, raw_crossing, int(len(y_fit))


def _production_panel(raw: pd.DataFrame) -> pd.DataFrame:
    """Production v11 quantiles joined to the target, for two reference reads:
    the in-sample motivation (eligible rows) and a no-refit out-of-sample cross-check
    (is_training_eligible = False rows, which the boosters never trained on)."""
    pred = pd.read_parquet(PRED_PARQUET, columns=[
        "lap_id", "predicted_degradation_jump_p10_s",
        "predicted_degradation_jump_s", "predicted_degradation_jump_p90_s"])
    pred = pred.rename(columns={
        "predicted_degradation_jump_p10_s": "q10",
        "predicted_degradation_jump_s": "q50",
        "predicted_degradation_jump_p90_s": "q90"})
    base = raw[CARRY].copy()
    base[TARGET] = pd.to_numeric(raw[TARGET], errors="coerce")
    return base.merge(pred, on="lap_id", how="inner")


def main() -> int:
    print("11a stage 0 - building the out-of-sample panel")
    raw, holdout_season = _load_raw()
    print(f"  mart rows: {len(raw):,}   resolved holdout_season: {holdout_season}")
    assert holdout_season == max(raw["race_year"]) + 1

    shadow, raw_crossing, n_fit = _fit_shadow(raw)
    prod = _production_panel(raw)

    shadow.to_parquet(HERE / "panel_shadow.parquet", index=False)
    prod.to_parquet(HERE / "panel_production.parquet", index=False)

    # Structural diagnostics: the design stands or falls on whether the test half
    # actually carries within-circuit replicates, and on how many test circuits have
    # no calibration data at all (the app's cold-start case).
    elig = shadow[shadow["is_training_eligible"].astype(bool)
                  & shadow[TARGET].notna()]
    cal, tst = elig[elig["split"] == "calib"], elig[elig["split"] == "test"]
    races_per_circuit_test = tst.groupby("circuit_key")["race_id"].nunique()
    cal_circuits, tst_circuits = set(cal["circuit_key"]), set(tst["circuit_key"])
    n_cal_per_circuit = cal.groupby("circuit_key").size()

    manifest = {
        "item": "11a",
        "stage": "s0_build_panel",
        "holdout_season_resolved": int(holdout_season),
        "production_is_in_sample": True,
        "production_training_seasons": sorted(
            int(s) for s in raw["race_year"].unique() if s < holdout_season),
        "shadow_fit_seasons": FIT_SEASONS,
        "shadow_calib_seasons": CALIB_SEASONS,
        "shadow_test_seasons": TEST_SEASONS,
        "shadow_fit_rows": n_fit,
        "eligible_with_target": {
            "calib_rows": int(len(cal)), "test_rows": int(len(tst)),
            "calib_races": int(cal["race_id"].nunique()),
            "test_races": int(tst["race_id"].nunique()),
            "calib_circuits": len(cal_circuits), "test_circuits": len(tst_circuits),
            "test_circuits_with_2plus_races": int((races_per_circuit_test >= 2).sum()),
            "test_circuits_with_1_race": int((races_per_circuit_test == 1).sum()),
            "test_circuits_absent_from_calib": sorted(tst_circuits - cal_circuits),
            "test_rows_with_no_calib_circuit": int(
                tst["circuit_key"].isin(tst_circuits - cal_circuits).sum()),
            "calib_n_per_circuit_min": int(n_cal_per_circuit.min()),
            "calib_n_per_circuit_median": float(n_cal_per_circuit.median()),
            "calib_n_per_circuit_max": int(n_cal_per_circuit.max()),
        },
        "shadow_raw_crossing_rate": raw_crossing,
        "feature_contract_n": len(S.FEATURE_COLUMNS),
        "target": TARGET,
        "shadow_rows": int(len(shadow)),
        "shadow_rows_with_target": int(shadow[TARGET].notna().sum()),
        "production_rows": int(len(prod)),
        "production_rows_ineligible_with_target": int(
            ((~prod["is_training_eligible"].astype(bool)) & prod[TARGET].notna()).sum()),
        "wrote_production_artefact": False,
    }
    (HERE / "s0_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
