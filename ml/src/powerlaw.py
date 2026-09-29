"""WI-17: power-law tyre curves for the Degradation Simulator -- train, grade, export.

A separate module on purpose: the v14 feature contract, train.py and export_onnx.py's targets
are untouched, and nothing here reads or writes ml/models/manifest.json.

The curve (seconds of tyre degradation over the fresh-tyre pace at lap k of a new set):

    tyre(k) = max(0, alpha * (k^beta - 2^beta))          alpha >= 0, beta in [0.2, 3.0]

It is anchored at tyre age 2 (FRESH_ANCHOR_AGE) because that is where the simulator's fresh-tyre
pace is measured (ref_green_pace_s = median lap at tyre age <= 2; the age-1 lap is the out-lap).

Parametrisation (WI-17 Step 0 fallback, see the WI's As built). Step 0 measured the reliability
ceiling of alpha at ~0.07 and of the curve over the fresh pace at 0.58-0.76 (ages 5-20), so the
raw parameters are not identified and the curve is. Two XGBoost regressors are trained:

  deg20   the degradation at age 20 over the age-2 pace (curve_incr_20_s): the curve's LEVEL.
          All eight allowlisted features; monotone non-decreasing in hardness rank (softer never
          predicts less), track temperature and dirty-air share.
  beta    the curve's SHAPE, from era, track and the stint-start fuel / constructor context only.
          Hardness rank, dirty air and temperature are kept out of it on purpose.

and alpha is recovered in closed form, alpha = max(deg20, 0) / (20^beta - 2^beta). Because the
shape never depends on rank, dirty air or temperature, and the level is monotone in all three,
raising any of them scales the whole curve up at every lap: the P3.3 sanity gates ("more dirty
air / more heat never lowers the curve") and the hardness ordering hold by construction, not by
luck on the test cells. The WI's two-anchor fallback (predict the curve at ages 5 and 20, recover
beta from their ratio) cannot promise that -- raising one anchor with the other fixed lowers the
curve on one side of it -- and it graded no better (see As built).

CLI:
  python -m ml.src.powerlaw                        # CV report, final fit, ONNX, manifest, fixtures
  python -m ml.src.powerlaw --leave-out-rank 6     # T54 (reported, not gated)
  python -m ml.src.powerlaw --leave-out-era 2018   # T55 (reported, not gated)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import onnxmltools
import onnxruntime as ort
import pandas as pd
import xgboost as xgb
from onnxmltools.convert.common.data_types import FloatTensorType
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold

from ml.src import powerlaw_fit as PF
from ml.src import schema as S

VERSION = "v1"
MODELS_DIR = Path("ml/models")
MANIFEST_PATH = MODELS_DIR / f"powerlaw_manifest_{VERSION}.json"
REPORT_PATH = Path("ml/artefacts/powerlaw_report.json")
CEILING_PATH = Path("ml/artefacts/powerlaw_ceiling.json")
APP_FIXTURES = Path("app/src/features/degradation-simulator/__fixtures__")
PARITY_FIXTURE = APP_FIXTURES / "powerlaw_parity.json"
BASKET_FIXTURE = APP_FIXTURES / "powerlaw_basket.json"
ACCURACY_BASKET = APP_FIXTURES / "accuracy_basket.json"

TRAINING_TABLE = "fct_power_law_training"
FRESH_ANCHOR_AGE = PF.FRESH_ANCHOR_AGE
LEVEL_AGE = 20
EVAL_AGES = PF.EVAL_AGES
N_FOLDS = 5
MAX_SIM_LAPS = 50
SIZE_LIMIT_BYTES = 500 * 1024
PARITY_ATOL = 1e-5

# ─── The feature allowlist (T51) ─────────────────────────────────────────────────────────────
# Exactly what the simulator can supply at inference (W26). Positional: DO NOT reorder; the
# manifest carries the same order per model (the WI-04 contract, one vector per model).
FEATURES_DEG20: tuple[str, ...] = (
    "compound_hardness_rank",
    "era_code",
    "track_energy_index",
    "circuit_abrasiveness_index",
    "track_temp_c",
    "stint_start_fuel_kg",
    "dirty_air_share",
    "constructor_pace_s",
)
FEATURES_BETA: tuple[str, ...] = (
    "era_code",
    "track_energy_index",
    "circuit_abrasiveness_index",
    "stint_start_fuel_kg",
    "constructor_pace_s",
)
ALLOWLIST: frozenset[str] = frozenset(FEATURES_DEG20) | frozenset(FEATURES_BETA)
MONOTONE_UP_DEG20: frozenset[str] = frozenset({"compound_hardness_rank", "track_temp_c", "dirty_air_share"})
TARGET_DEG20 = f"curve_incr_{LEVEL_AGE}_s"
TARGET_BETA = "beta"
WEIGHT = "n_laps"

# The F2/FD3 guard, as data: no feature, and no column of the training frame, may match.
# transform/tests/assert_power_law_no_seed_columns.sql holds the same list on the dbt side.
# Identity columns (compound_label, compound_code, compound_hardness_rank) are not priced from
# anything and are allowed; the compound_cliff_params parameters and everything computed from
# them are not.
DENYLIST_PATTERNS: tuple[str, ...] = (
    # compound_cliff_params / dim_compounds_season / int_compound_cliff_predicted parameters,
    # and compound_component_s (= expected_compound_pace_s on every lap)
    r"^compound_(grip|wear|optimal|cliff|component)",
    r"^expected_",                            # expected_compound_pace_s, expected_degradation_rate_*
    r"^cliff_onset_passed$", r"^laps_past_cliff$", r"^cliff_candidate_flag$",
    # net of compound_component_s
    r"^driver_skill_residual", r"^pace_delta_s$", r"^total_explained_s$",
    r"^ambient_temp_delta$",                  # track temp minus compound_optimal_temp_low
    # int_field_pace_curve subtracts expected_compound_pace_s from every lap, so its base and the
    # rubber / ambient split fitted from it are priced from the seed too (WI-17 As built)
    r"^base_track_pace_s$", r"^field_pace", r"^rubber_component_s$", r"^ambient_component_s$",
    r"^track_unexplained_s$",
    r"^next_.*jump", r"^laps_until_cliff_class$",   # the v14 labels
)

# Fixed a priori (not tuned on these folds): a few hundred shallow trees, heavy leaf weight
# (min_child_weight is in n_laps units: ~4 median cells), pseudo-Huber so the fat-tailed cell
# targets (curve_incr_20_s runs -6.2..+5.1 s) do not steer the fit.
XGB_PARAMS: dict = dict(
    n_estimators=300, learning_rate=0.03, max_depth=3, subsample=0.8, colsample_bytree=0.8,
    min_child_weight=1500.0, reg_lambda=1.0, objective="reg:pseudohubererror",
    tree_method="exact", random_state=S.RANDOM_STATE, n_jobs=1,
)

ERA_CODE = {"2018": 0, "2019-21": 1, "2022+": 2}
# The app's own per-compound fallback ramp (inputs.ts COMPOUND_DEFAULTS
# expected_degradation_rate_s_per_lap), used only to reproduce the current simulator where a
# circuit has no history. App constants, not the warehouse compound seed.
APP_FALLBACK_RATE = {"HARD": 0.40, "MEDIUM": 0.56, "SOFT": 0.85, "SUPERSOFT": 1.05,
                     "ULTRASOFT": 1.25, "HYPERSOFT": 1.45}
ISO_N_FLOOR = 10          # fit_degradation_isotonic.N_FLOOR
ENVELOPE_MIN_N = 3        # mart_degradation_history_envelope: n_observations >= 3
# T55's alternative 2018 correspondence: Pirelli's 2019 guidance as recalled, not verified
# against a source -- C1 ~ 2018 HARD, C2 ~ MEDIUM, C3 ~ SOFT, C4 ~ ULTRASOFT, C5 ~ HYPERSOFT,
# SUPERSOFT between C3 and C4, SUPERHARD below C1.
ALT_2018_RANK = {"SUPERHARD": 0.5, "HARD": 1.0, "MEDIUM": 2.0, "SOFT": 3.0, "SUPERSOFT": 3.5,
                 "ULTRASOFT": 4.0, "HYPERSOFT": 5.0}


def denied(column: str) -> bool:
    return any(re.search(p, column) for p in DENYLIST_PATTERNS)


# ─── Curve arithmetic (mirrored in app/.../powerLaw.ts) ─────────────────────────────────────
def shape_denominator(beta):
    b = np.asarray(beta, float)
    return np.power(float(LEVEL_AGE), b) - np.power(float(FRESH_ANCHOR_AGE), b)


def clip_beta(beta):
    return np.clip(np.asarray(beta, float), PF.BETA_MIN, PF.BETA_MAX)


def alpha_from(deg20, beta):
    """alpha = max(deg20, 0) / (20^beta - 2^beta): the level pins the curve at age 20."""
    return np.maximum(np.asarray(deg20, float), 0.0) / shape_denominator(clip_beta(beta))


def tyre_curve(alpha, beta, laps) -> np.ndarray:
    """max(0, alpha * (k^beta - 2^beta)) for k in laps; rows = units, cols = laps."""
    a = np.maximum(np.atleast_1d(np.asarray(alpha, float)), 0.0)[:, None]
    b = clip_beta(np.atleast_1d(beta))[:, None]
    k = np.asarray(laps, float)[None, :]
    return np.maximum(0.0, a * (np.power(k, b) - np.power(float(FRESH_ANCHOR_AGE), b)))


# ─── Data ────────────────────────────────────────────────────────────────────────────────────
def load_training(duckdb_path: str = S.DUCKDB_PATH) -> pd.DataFrame:
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        df = con.execute(f"SELECT * FROM {TRAINING_TABLE} ORDER BY cell_id").df()
    finally:
        con.close()
    bad = sorted(c for c in df.columns if denied(c))
    if bad:
        raise ValueError(f"{TRAINING_TABLE} carries guarded columns (T51): {bad}")
    return df.reset_index(drop=True)


def X_of(df: pd.DataFrame, features) -> np.ndarray:
    return df[list(features)].to_numpy(dtype=np.float32)


# ─── Model ───────────────────────────────────────────────────────────────────────────────────
def _monotone(features, up: frozenset[str]) -> str:
    return "(" + ",".join("1" if f in up else "0" for f in features) + ")"


def fit_models(train: pd.DataFrame, features_deg20=FEATURES_DEG20) -> dict:
    w = train[WEIGHT].to_numpy(float)
    m20 = xgb.XGBRegressor(**XGB_PARAMS, monotone_constraints=_monotone(features_deg20, MONOTONE_UP_DEG20))
    m20.fit(X_of(train, features_deg20), train[TARGET_DEG20].to_numpy(float), sample_weight=w)
    mb = xgb.XGBRegressor(**XGB_PARAMS)
    mb.fit(X_of(train, FEATURES_BETA), train[TARGET_BETA].to_numpy(float), sample_weight=w)
    return {"deg20": m20, "beta": mb, "features_deg20": tuple(features_deg20)}


def predict(models: dict, df: pd.DataFrame) -> pd.DataFrame:
    deg20 = models["deg20"].predict(X_of(df, models["features_deg20"])).astype(np.float64)
    beta_raw = models["beta"].predict(X_of(df, FEATURES_BETA)).astype(np.float64)
    beta = clip_beta(beta_raw)
    return pd.DataFrame({"deg20": deg20, "beta_raw": beta_raw, "beta": beta,
                         "alpha": alpha_from(deg20, beta)}, index=df.index)


def curve_at_eval_ages(alpha, beta) -> np.ndarray:
    return tyre_curve(alpha, beta, EVAL_AGES)


# ─── Truths ──────────────────────────────────────────────────────────────────────────────────
def truth_fit(df: pd.DataFrame) -> np.ndarray:
    """T-fit: the held-out cell's own pooled within-stint fit, over the age-2 pace."""
    return df[[f"curve_incr_{a}_s" for a in EVAL_AGES]].to_numpy(float)


def truth_obs(df: pd.DataFrame, laps: pd.DataFrame) -> np.ndarray:
    """T-obs: model-free and in the P3 truth's own definition, at race-cell grain. Median lap at
    ages a-1..a+1 minus the median lap at age <= 2 (>= 3 laps each), else NaN."""
    out = np.full((len(df), len(EVAL_AGES)), np.nan)
    pos = {(r, k): i for i, (r, k) in enumerate(zip(df["race_id"], df["compound_hardness_rank"]))}
    ranked = laps[laps["compound_hardness_rank"].notna()]
    for key, c in ranked.groupby(["race_id", "compound_hardness_rank"], sort=False):
        i = pos.get((key[0], key[1]))
        if i is None:
            continue
        ref = c.loc[c["age"] <= FRESH_ANCHOR_AGE, "y"]
        if len(ref) < 3:
            continue
        for j, a in enumerate(EVAL_AGES):
            s = c.loc[(c["age"] >= a - 1) & (c["age"] <= a + 1), "y"]
            if len(s) >= 3:
                out[i, j] = s.median() - ref.median()
    return out


# ─── Baselines ───────────────────────────────────────────────────────────────────────────────
def rank_median(train: pd.DataFrame, test: pd.DataFrame, by=("compound_hardness_rank",)) -> np.ndarray:
    cols = [f"curve_incr_{a}_s" for a in EVAL_AGES]
    overall = train[cols].median().to_numpy()
    med = train.groupby(list(by))[cols].median()
    out = np.empty((len(test), len(cols)))
    for i, key in enumerate(test[list(by)].itertuples(index=False, name=None)):
        k = key if len(by) > 1 else key[0]
        out[i] = med.loc[k].to_numpy() if k in med.index else overall
    return out


def _era2(year) -> str:
    return "pre2022" if int(year) < 2022 else "post2022"


def build_envelope(laps: pd.DataFrame) -> dict:
    """The current simulator's tyre term, rebuilt on a given set of races: the history envelope's
    obs_deg_from_fresh_p50 (median lap at each lap_in_stint minus the median at tyre age <= 2,
    per circuit x pre/post-2022 x compound label, plus an '_all' rollup) and
    fit_degradation_isotonic's weighted isotonic fit of it."""
    l = laps.assign(era2=np.where(laps["race_year"] < 2022, "pre2022", "post2022"))
    both = pd.concat([l, l.assign(compound_label="_all")], ignore_index=True)
    keys = ["circuit_id", "era2", "compound_label"]
    ref = both[both["age"] <= 2].groupby(keys)["y"].median().rename("ref").reset_index()
    env = (both.groupby(keys + ["lap_in_stint"])["y"].agg(["median", "count"]).reset_index()
           .merge(ref, on=keys))
    env = env[(env["count"] >= ENVELOPE_MIN_N) & (env["lap_in_stint"] <= MAX_SIM_LAPS)]
    env["p50"] = env["median"] - env["ref"]
    out = {}
    for key, c in env.groupby(keys, sort=False):
        c = c.sort_values("lap_in_stint")
        m = (c["count"] >= ISO_N_FLOOR).to_numpy()
        if m.sum() >= 2:
            ir = IsotonicRegression(increasing=True, out_of_bounds="clip")
            ir.fit(c["lap_in_stint"].to_numpy(float)[m], c["p50"].to_numpy(float)[m],
                   sample_weight=c["count"].to_numpy(float)[m])
            mono = ir.predict(c["lap_in_stint"].to_numpy(float))
        else:
            mono = c["p50"].to_numpy(float)
        out[key] = dict(zip(c["lap_in_stint"].astype(int), mono))
    return out


def current_term(env: dict, circuit_id, year, label, laps=EVAL_AGES) -> tuple[np.ndarray, str]:
    """transform.ts recomposeLapTimes at neutral inputs (M = 1, track scale 1, no cliff term):
    the isotonic p50 held flat past its last lap, '_all' when the compound has no history,
    the app's analytical ramp when the circuit has none."""
    era2 = _era2(year)
    h, src = env.get((circuit_id, era2, label)), "own"
    if h is None:
        h, src = env.get((circuit_id, era2, "_all")), "_all"
    top = max(laps)
    if h is None:
        rate = APP_FALLBACK_RATE.get(label, APP_FALLBACK_RATE["MEDIUM"])
        vals = np.array([max(0.0, rate * (k - 1)) for k in range(1, top + 1)])
        src = "ramp"
    else:
        vals, last = [], 0.0
        for k in range(1, top + 1):
            if k in h:
                last = h[k]
            vals.append(last)
        vals = np.array(vals)
    return vals[[k - 1 for k in laps]], src


# ─── Grading ─────────────────────────────────────────────────────────────────────────────────
def mae_table(pred: np.ndarray, truth: np.ndarray, w: np.ndarray, mask: np.ndarray | None = None) -> dict:
    ok = np.isfinite(truth)
    if mask is not None:
        ok &= mask[:, None]
    err = np.where(ok, np.abs(pred - truth), np.nan)
    with warnings.catch_warnings():             # T_obs leaves some cells with no scorable age
        warnings.simplefilter("ignore", RuntimeWarning)
        per_cell = np.nanmean(err, axis=1)
    has = np.isfinite(per_cell)
    return {
        "n_cells": int(has.sum()),
        "mae_by_age": {str(a): round(float(np.nanmean(err[:, j])), 4) for j, a in enumerate(EVAL_AGES)},
        "mae_mean": round(float(np.nanmean(err)), 4),
        "mae_mean_lap_weighted": round(float(np.sum(per_cell[has] * w[has]) / np.sum(w[has])), 4),
        "bias_by_age": {str(a): round(float(np.nanmean(np.where(ok, pred - truth, np.nan)[:, j])), 4)
                        for j, a in enumerate(EVAL_AGES)},
    }


def _folds(df: pd.DataFrame, n: int = N_FOLDS):
    return list(GroupKFold(n_splits=n).split(df, groups=df["race_id"]))


def oof_predictions(df: pd.DataFrame, folds, features_deg20=FEATURES_DEG20) -> tuple[pd.DataFrame, list]:
    parts, models = [], []
    for tr, te in folds:
        m = fit_models(df.iloc[tr], features_deg20)
        models.append(m)
        parts.append(predict(m, df.iloc[te]))
    return pd.concat(parts).sort_index(), models


def cv_report(df: pd.DataFrame, laps: pd.DataFrame) -> tuple[dict, pd.DataFrame, list, list]:
    folds = _folds(df)
    oof, fold_models = oof_predictions(df, folds)
    pred = curve_at_eval_ages(oof["alpha"], oof["beta"])
    w = df[WEIGHT].to_numpy(float)
    t_fit, t_obs = truth_fit(df), truth_obs(df, laps)

    rank_med = np.empty_like(t_fit)
    era_rank_med = np.empty_like(t_fit)
    cur = np.empty_like(t_fit)
    src = np.empty(len(df), dtype=object)
    for tr, te in folds:
        train, test = df.iloc[tr], df.iloc[te]
        rank_med[te] = rank_median(train, test)
        era_rank_med[te] = rank_median(train, test, by=("era_code", "compound_hardness_rank"))
        env = build_envelope(laps[~laps["race_id"].isin(set(test["race_id"]))])
        for i in te:
            r = df.iloc[i]
            cur[i], src[i] = current_term(env, r["circuit_id"], r["race_year"], r["compound_label"])
    env_all = build_envelope(laps)
    cur_in_sample = np.array([current_term(env_all, r.circuit_id, r.race_year, r.compound_label)[0]
                              for r in df.itertuples()])
    own = src == "own"
    contenders = {"power_law_model": pred, "rank_median": rank_med, "era_rank_median": era_rank_med,
                  "current_term_leave_fold_out": cur, "current_term_in_sample": cur_in_sample}
    report = {"folds": N_FOLDS, "split": "GroupKFold by race_id",
              "current_term_source_counts": {k: int(v) for k, v in pd.Series(src).value_counts().items()}}
    for tname, truth in (("T_fit", t_fit), ("T_obs", t_obs)):
        report[tname] = {
            "all_cells": {k: mae_table(v, truth, w) for k, v in contenders.items()},
            "cells_where_current_term_has_own_history": {k: mae_table(v, truth, w, own)
                                                         for k, v in contenders.items()},
        }
    # R^2 against the Step 0 ceiling (fraction of the achievable)
    ceil = {}
    if CEILING_PATH.exists():
        ceil = json.loads(CEILING_PATH.read_text())["grains"]["cell"]["ceiling"]
    r2 = {
        "deg20": r2_score(df[TARGET_DEG20], oof["deg20"]),
        "beta": r2_score(df[TARGET_BETA], oof["beta"]),
        "alpha": r2_score(df["alpha_s"], oof["alpha"]),
    }
    r2.update({f"incr_{a}": r2_score(t_fit[:, j], pred[:, j]) for j, a in enumerate(EVAL_AGES)})
    ceiling_key = {"deg20": f"incr_{LEVEL_AGE}", "beta": "beta", "alpha": "alpha",
                   **{f"incr_{a}": f"incr_{a}" for a in EVAL_AGES}}
    report["r2_vs_step0_ceiling"] = {
        k: {"r2": round(float(v), 3), "ceiling": ceil.get(ceiling_key[k]),
            "fraction_of_achievable": (round(float(v) / ceil[ceiling_key[k]], 3)
                                       if ceil.get(ceiling_key[k]) and ceil[ceiling_key[k]] > 0 else None)}
        for k, v in r2.items()}
    return report, oof, folds, fold_models


def verdict_criterion2(report: dict) -> dict:
    out = {}
    for tname in ("T_fit", "T_obs"):
        for subset in ("all_cells", "cells_where_current_term_has_own_history"):
            blk = report[tname][subset]
            model = blk["power_law_model"]
            beats = {}
            for base in ("rank_median", "current_term_leave_fold_out"):
                beats[base] = all(model["mae_by_age"][a] < blk[base]["mae_by_age"][a]
                                  for a in model["mae_by_age"])
            out[f"{tname}/{subset}"] = beats
    out["pass"] = all(all(v.values()) for k, v in out.items() if k.startswith("T_fit"))
    return out


def season_forward(df: pd.DataFrame, laps: pd.DataFrame) -> dict:
    """Train on every season before the last one with cells, test on that one (2024 today).
    NOT a holdout claim (FD4 is open; see the WI). The WI's train <= 2024 / test 2025 fold
    cannot run: 2025 has no hardness rank until tyre_allocations carries it (W50)."""
    last = int(df["race_year"].max())
    tr, te = df[df["race_year"] < last], df[df["race_year"] == last]
    m = fit_models(tr)
    p = predict(m, te)
    pred = curve_at_eval_ages(p["alpha"], p["beta"])
    env = build_envelope(laps[laps["race_year"] < last])
    cur = np.array([current_term(env, r.circuit_id, r.race_year, r.compound_label)[0]
                    for r in te.itertuples()])
    w = te[WEIGHT].to_numpy(float)
    t = truth_fit(te)
    return {"label": f"season-forward, train < {last} / test {last} -- NOT a holdout claim",
            "n_test_cells": int(len(te)),
            "T_fit": {"power_law_model": mae_table(pred, t, w),
                      "rank_median": mae_table(rank_median(tr, te), t, w),
                      "current_term": mae_table(cur, t, w)}}


# ─── T54 / T55 (reported, not gated) ─────────────────────────────────────────────────────────
def leave_out_rank(df: pd.DataFrame, rank: int) -> dict:
    held = df["compound_hardness_rank"] == rank
    if not held.any():
        return {"rank": rank, "n_cells": 0,
                "note": f"No rank-{rank} cells in {TRAINING_TABLE}; nothing to measure."}
    m = fit_models(df[~held])
    te = df[held]
    p = predict(m, te)
    pred = curve_at_eval_ages(p["alpha"], p["beta"])
    t = truth_fit(te)
    w = te[WEIGHT].to_numpy(float)
    # the same races' next-harder cell: how far apart the true curves are
    below = df[df["compound_hardness_rank"] == rank - 1].set_index("race_id")
    same = te["race_id"].isin(below.index).to_numpy()
    gap = None
    if same.any():
        tb = truth_fit(below.loc[te.loc[same, "race_id"]])
        gap = mae_table(tb, t[same], w[same])
    eras = te["hardness_era"].value_counts().to_dict()
    return {"rank": rank, "n_cells": int(held.sum()), "eras": {str(k): int(v) for k, v in eras.items()},
            "model_trained_without_rank": mae_table(pred, t, w),
            "true_gap_to_rank_below_same_races": gap,
            "rank_median_of_rank_below": mae_table(
                np.tile(df[df["compound_hardness_rank"] == rank - 1][
                    [f"curve_incr_{a}_s" for a in EVAL_AGES]].median().to_numpy(), (len(te), 1)), t, w)}


def leave_out_era(df: pd.DataFrame, era: str, laps: pd.DataFrame) -> dict:
    held = df["hardness_era"] == era
    tr, te = df[~held], df[held].copy()
    t = truth_fit(te)
    w = te[WEIGHT].to_numpy(float)
    m = fit_models(tr)
    out = {"era": era, "n_cells": int(held.sum())}
    variants = {"declared_scale": te}
    if era == "2018":
        alt = te.copy()
        alt["compound_hardness_rank"] = alt["compound_label"].map(ALT_2018_RANK).astype(float)
        variants["alternative_mapping"] = alt
    nan_rank = te.copy()
    nan_rank["compound_hardness_rank"] = np.nan
    variants["era_flag_only"] = nan_rank
    for name, frame in variants.items():
        p = predict(m, frame)
        out[name] = mae_table(curve_at_eval_ages(p["alpha"], p["beta"]), t, w)
    scores = {k: out[k]["mae_mean"] for k in variants}
    out["winner"] = min(scores, key=scores.get)
    if era == "2018":
        out["alternative_mapping_definition"] = ALT_2018_RANK
    return out


# ─── Export ──────────────────────────────────────────────────────────────────────────────────
def _retagged(model: xgb.XGBRegressor) -> xgb.Booster:
    """The same trees tagged reg:squarederror, which onnxmltools can dispatch on (it has no case
    for reg:pseudohubererror). The link is the identity for both, and base_score is carried, so
    the graph's output is the prediction -- parity below proves it rather than assuming it."""
    raw = json.loads(model.get_booster().save_raw(raw_format="json").decode("utf-8"))
    raw["learner"]["objective"] = {"name": "reg:squarederror", "reg_loss_param": {"scale_pos_weight": "1"}}
    out = xgb.Booster()
    out.load_model(bytearray(json.dumps(raw), "utf-8"))
    out.feature_names = None
    return out


def export_onnx(models: dict) -> dict[str, Path]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, feats in (("deg20", models["features_deg20"]), ("beta", FEATURES_BETA)):
        booster = _retagged(models[name])
        onx = onnxmltools.convert_xgboost(
            booster, initial_types=[("input", FloatTensorType([None, len(feats)]))])
        p = MODELS_DIR / f"powerlaw_{name}_{VERSION}.onnx"
        p.write_bytes(onx.SerializeToString())
        models[name].save_model(str(MODELS_DIR / f"powerlaw_{name}_{VERSION}.bst"))
        paths[name] = p
    return paths


def onnx_predict(path: Path, X: np.ndarray) -> np.ndarray:
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    return np.asarray(sess.run(None, {"input": X.astype(np.float32)})[0]).reshape(-1)


def parity(models: dict, paths: dict, frame: pd.DataFrame) -> dict:
    """ONNX vs XGBoost on the given rows, plus a NaN-bearing copy (native-missing directions)."""
    out = {}
    rng = np.random.default_rng(S.RANDOM_STATE)
    for name, feats in (("deg20", models["features_deg20"]), ("beta", FEATURES_BETA)):
        X = X_of(frame, feats)
        Xn = X.copy()
        Xn[rng.random(Xn.shape) < 0.2] = np.nan
        diffs = []
        for M in (X, Xn):
            a = models[name].predict(M).astype(np.float64)
            b = onnx_predict(paths[name], M).astype(np.float64)
            diffs.append(float(np.max(np.abs(a - b))))
        out[name] = {"max_abs_diff": max(diffs), "max_abs_diff_clean": diffs[0],
                     "max_abs_diff_nan_bearing": diffs[1], "n_rows": int(len(X)),
                     "pass": max(diffs) <= PARITY_ATOL}
    return out


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_manifest(models: dict, paths: dict, par: dict, report: dict, n_train: int) -> dict:
    total = sum(p.stat().st_size for p in paths.values())
    return {
        "name": "Off the Pace - power-law tyre curve (WI-17)",
        "model_version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "not published; the v14 manifest.json is untouched",
        "input": {"tensor_name": "input", "dtype": "float32",
                  "continuous_missing": "NaN (XGBoost native-missing)",
                  "era_code": ERA_CODE,
                  "compound_hardness_rank": "compound_hardness_scale seed: 2018 legacy names 1-7, "
                                            "C1-C6 1-6 (1 = hardest)"},
        "models": [
            {"name": "powerlaw_deg20", "onnx": paths["deg20"].name, "onnx_sha256": _sha256(paths["deg20"]),
             "feature_order": list(models["features_deg20"]), "n_features": len(models["features_deg20"]),
             "shape": ["batch", len(models["features_deg20"])],
             "monotone_increasing": sorted(MONOTONE_UP_DEG20 & set(models["features_deg20"])),
             "output": {"index": 0, "meaning": "tyre degradation at age 20 over the age-2 fresh pace (s)",
                        "target_column": TARGET_DEG20}},
            {"name": "powerlaw_beta", "onnx": paths["beta"].name, "onnx_sha256": _sha256(paths["beta"]),
             "feature_order": list(FEATURES_BETA), "n_features": len(FEATURES_BETA),
             "shape": ["batch", len(FEATURES_BETA)],
             "output": {"index": 0, "meaning": "power-law exponent beta", "target_column": TARGET_BETA,
                        "postprocess": f"clip to [{PF.BETA_MIN}, {PF.BETA_MAX}]"}},
        ],
        "curve": {
            "fresh_anchor_age": FRESH_ANCHOR_AGE, "level_age": LEVEL_AGE,
            "alpha": "max(deg20, 0) / (20^beta - 2^beta)",
            "tyre_s_at_lap_k": "max(0, alpha * (k^beta - 2^beta))",
            "implemented_in": ["ml/src/powerlaw.py", "app/src/features/degradation-simulator/powerLaw.ts"],
        },
        "provenance": {
            "training_table": TRAINING_TABLE, "n_training_cells": n_train,
            "xgb_params": {k: v for k, v in XGB_PARAMS.items()},
            "random_state": S.RANDOM_STATE,
            "library_versions": {"xgboost": xgb.__version__, "onnxmltools": onnxmltools.__version__,
                                 "onnxruntime": ort.__version__},
            "onnx_parity": par, "onnx_total_bytes": total, "onnx_size_limit_bytes": SIZE_LIMIT_BYTES,
            "cv_headline_T_fit_mae_mean": report["T_fit"]["all_cells"]["power_law_model"]["mae_mean"],
        },
    }


# ─── App fixtures ────────────────────────────────────────────────────────────────────────────
PARITY_LAPS: tuple[int, ...] = (1, 2, 3, 4, 5, 7, 10, 12, 15, 18, 20, 25, 30, 40, 50)


def _vec(row: pd.Series, feats) -> list:
    return [None if pd.isna(row[f]) else float(row[f]) for f in feats]


def write_parity_fixture(models: dict, df: pd.DataFrame) -> dict:
    """Every cell (so every race), scored by the final exported models: the browser must
    reproduce these from the ONNX files. Feature vectors are positional, in each model's order."""
    p = predict(models, df)
    curves = tyre_curve(p["alpha"], p["beta"], PARITY_LAPS)
    rows = []
    for j, (i, r) in enumerate(df.iterrows()):
        rows.append({"cell_id": r["cell_id"],
                     "x_deg20": _vec(r, models["features_deg20"]), "x_beta": _vec(r, FEATURES_BETA),
                     "deg20": float(p.at[i, "deg20"]), "beta": float(p.at[i, "beta"]),
                     "alpha": float(p.at[i, "alpha"]),
                     "tyre_s": [round(float(v), 9) for v in curves[j]]})
    fx = {"_doc": ("WI-17 criterion 4a. Every training cell (all 2018-2024 races) scored by the "
                   "exported power-law models in Python (xgboost). powerLaw.test.ts scores the "
                   "same feature vectors through the ONNX files with onnxruntime-web and must "
                   "match to 1e-5, on deg20, beta and the tyre curve at `laps`. Generated by "
                   "`python -m ml.src.powerlaw`."),
          "version": VERSION, "onnx": {k: f"powerlaw_{k}_{VERSION}.onnx" for k in ("deg20", "beta")},
          "feature_order": {"deg20": list(models["features_deg20"]), "beta": list(FEATURES_BETA)},
          "laps": list(PARITY_LAPS), "rows": rows}
    PARITY_FIXTURE.write_text(json.dumps(fx, separators=(",", ":")))
    return fx


def write_basket_fixture(df: pd.DataFrame, oof_models: list, folds: list) -> dict:
    """Criterion 4b: the P3 basket's dry cells, each race scored by the fold model that never
    saw it, at the race's own conditions and at the P3.2/P3.3 perturbations."""
    basket = json.loads(ACCURACY_BASKET.read_text())["basket"]
    fold_of = {}
    for f, (_, te) in enumerate(folds):
        for i in te:
            fold_of[df.index[i]] = f
    variants = {"own": {}, "dirty_0": {"dirty_air_share": 0.0}, "dirty_0_8": {"dirty_air_share": 0.8},
                "dirty_1": {"dirty_air_share": 1.0}, "temp_25": {"track_temp_delta": 25.0},
                "temp_30": {"track_temp_delta": 30.0}}
    cells = []
    for b in basket:
        era_rows = df[(df["circuit_id"] == b["circuit_id"]) & (df["compound_label"] == b["compound"])
                      & ((df["race_year"] >= 2022) if b["era"] == "post2022" else (df["race_year"] < 2022))]
        entry = {"circuit_id": b["circuit_id"], "era": b["era"], "compound": b["compound"], "races": []}
        if era_rows.empty:
            entry["excluded"] = ("no race x hardness-rank cell: " +
                                 ("not a slick, outside the hardness scale" if b["compound"] in ("INTERMEDIATE", "WET")
                                  else "no eligible cell"))
            cells.append(entry)
            continue
        for idx, r in era_rows.iterrows():
            m = oof_models[fold_of[idx]]
            race = {"race_id": r["race_id"], "cell_id": r["cell_id"], "rank": int(r["compound_hardness_rank"]),
                    "n_laps": int(r["n_laps"]), "fold": int(fold_of[idx]),
                    # the cell's own in-sample fit (the training target): the best any curve
                    # anchored at the fresh-tyre pace could do on this race -- an oracle, not a model
                    "target": {"alpha": float(r["alpha_s"]), "beta": float(r["beta"]),
                               "deg20": float(r[TARGET_DEG20])},
                    "variants": {}}
            for vname, change in variants.items():
                row = r.copy()
                if "dirty_air_share" in change:
                    row["dirty_air_share"] = change["dirty_air_share"]
                if "track_temp_delta" in change:
                    row["track_temp_c"] = r["track_temp_c"] + change["track_temp_delta"]
                p = predict(m, pd.DataFrame([row]))
                race["variants"][vname] = {"deg20": float(p["deg20"].iat[0]), "beta": float(p["beta"].iat[0]),
                                           "alpha": float(p["alpha"].iat[0])}
            entry["races"].append(race)
        cells.append(entry)
    fx = {"_doc": ("WI-17 criterion 4b. For each P3 accuracy-basket cell, every race x hardness-rank "
                   "cell behind it (same circuit, era and compound label, 2018-2024; 2025 has no "
                   "hardness rank) with (alpha, beta) from the GroupKFold-by-race fold model that "
                   "never saw that race. 'own' is the race's observed conditions; dirty_* set the "
                   "dirty-air share, temp_* add degrees to the circuit-season track temperature. "
                   "'target' is the cell's own in-sample fit, an oracle for what a curve anchored "
                   "at the fresh-tyre pace can reach at all. powerLaw.test.ts averages the "
                   "per-race curves (n_laps-weighted) and runs P3.1-P3.3 on them. Generated by "
                   "`python -m ml.src.powerlaw`."),
          "version": VERSION, "fresh_anchor_age": FRESH_ANCHOR_AGE, "cells": cells}
    BASKET_FIXTURE.write_text(json.dumps(fx, indent=1))
    return fx


# ─── CLI ─────────────────────────────────────────────────────────────────────────────────────
def _print_block(title: str, blk: dict) -> None:
    print(f"\n  {title}")
    for k, v in blk.items():
        ages = " ".join(f"{v['mae_by_age'][str(a)]:.3f}" for a in EVAL_AGES)
        print(f"    {k:30s} n={v['n_cells']:3d}  MAE@5/10/15/20 {ages}  mean {v['mae_mean']:.3f}"
              f"  (lap-wtd {v['mae_mean_lap_weighted']:.3f})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duckdb", default=S.DUCKDB_PATH)
    ap.add_argument("--leave-out-rank", type=int, help="T54 only: train without this rank, report")
    ap.add_argument("--leave-out-era", help="T55 only: train without this hardness era, report")
    ap.add_argument("--no-export", action="store_true", help="CV report only")
    args = ap.parse_args()

    df = load_training(args.duckdb)
    laps = PF.load_laps(args.duckdb)
    if args.leave_out_rank is not None:
        print(json.dumps(leave_out_rank(df, args.leave_out_rank), indent=1))
        return 0
    if args.leave_out_era is not None:
        print(json.dumps(leave_out_era(df, args.leave_out_era, laps), indent=1))
        return 0

    print(f"{TRAINING_TABLE}: {len(df)} cells, {df['race_id'].nunique()} races, "
          f"{int(df[WEIGHT].sum())} laps")
    report, oof, folds, fold_models = cv_report(df, laps)
    report["criterion_2"] = verdict_criterion2(report)
    report["season_forward"] = season_forward(df, laps)
    report["T54_leave_out_rank_6"] = leave_out_rank(df, 6)
    report["T54_leave_out_rank_7_extrapolation_proxy"] = leave_out_rank(df, 7)
    report["T55_leave_out_era_2018"] = leave_out_era(df, "2018", laps)
    for tname in ("T_fit", "T_obs"):
        _print_block(f"{tname}, all held-out cells", report[tname]["all_cells"])
        _print_block(f"{tname}, cells where the current term has own-compound history",
                     report[tname]["cells_where_current_term_has_own_history"])
    print("\n  R^2 vs Step 0 ceiling:", json.dumps(report["r2_vs_step0_ceiling"]))
    print("  criterion 2:", json.dumps(report["criterion_2"]))
    print("  season-forward (NOT a holdout claim):",
          json.dumps({k: v["mae_mean"] for k, v in report["season_forward"]["T_fit"].items()}))
    print("  T55 2018:", {k: report["T55_leave_out_era_2018"][k]["mae_mean"]
                          for k in ("declared_scale", "alternative_mapping", "era_flag_only")},
          "winner:", report["T55_leave_out_era_2018"]["winner"])

    if not args.no_export:
        final = fit_models(df)
        paths = export_onnx(final)
        test_fold = df.iloc[folds[0][1]]
        par = parity(final, paths, test_fold)
        par_all = parity(final, paths, df)
        total = sum(p.stat().st_size for p in paths.values())
        report["export"] = {"files": {k: {"path": str(p), "bytes": p.stat().st_size} for k, p in paths.items()},
                            "total_bytes": total, "under_500kb": total < SIZE_LIMIT_BYTES,
                            "parity_test_fold": par, "parity_all_cells": par_all}
        manifest = build_manifest(final, paths, par, report, len(df))
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
        write_parity_fixture(final, df)
        write_basket_fixture(df, fold_models, folds)
        print(f"\n  ONNX: {', '.join(f'{p.name} {p.stat().st_size} B' for p in paths.values())}; "
              f"total {total} B (< {SIZE_LIMIT_BYTES} B: {total < SIZE_LIMIT_BYTES})")
        print(f"  parity (test fold): {json.dumps({k: v['max_abs_diff'] for k, v in par.items()})}; "
              f"all cells: {json.dumps({k: v['max_abs_diff'] for k, v in par_all.items()})}")
        print(f"  wrote {MANIFEST_PATH}, {PARITY_FIXTURE}, {BASKET_FIXTURE}")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str))
    print(f"  wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
