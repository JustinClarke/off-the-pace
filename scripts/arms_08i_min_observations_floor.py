"""08i — the `min_observations` floor: the trade 08e priced and did not take.

WHY THIS EXISTS. `08e` rebuilt `int_lap_thermal_proxy.stint_baseline_pace` as an
expanding median over valid laps strictly before the scored lap, with a minimum-
observation floor, and priced floors of 1/2/3/5 without taking the trade through the
gate. This script takes it.

CORRECTION THIS SCRIPT ENCODES. The leaf doc says the rebuild "took
min_observations=1". That stopped being true on 2026-09-10, when a prior 08i session
set the SQL to `min_observations=2` inside commit c49473a (whose message is about
something else entirely). `08m` rebuilt the warehouse on 2026-09-16, so the live v12
substrate is FLOOR 2. The BEFORE arm here is floor 2, and floor 1 is a revert.

THE DESIGN.

    arm(F) = the 32-column contract with its four `thermal` columns recomputed at
             min_observations = F, for F in {1, 2, 3, 5}

    arm(2) == the built warehouse, verified bit-for-bit (step 1b below)

WHAT DOES NOT VARY. The contract stays 32 wide and the row set is identical at every
floor: `is_training_eligible` is `age_in_stint > 3 AND anomaly_class NOT IN
('mistake','conditions')` and does not reference the thermal block, so a higher floor
turns values into NaN and never deletes a row. The cross-floor contrast is therefore
CAPACITY-NEUTRAL BY CONSTRUCTION. Step 4 is still run: "not capacity" is not "not
noise".

METHOD (gates.md steps 1-4, plus 7).

    step 1a  E._fit/_score reproduces the published v12 headline, all five families
    step 1b  the floor-parameterised replica reproduces the BUILT floor-2 thermal
             columns bit-for-bit on all 137,447 mart rows, NULL pattern included
    step 2   add-ablation on cv_final_fold through evaluate.py's own _fit/_score
    step 3   each floor arm's own 5-reseed floor; cross-floor deltas quoted against
             the LARGER of the two arms' floors
    step 4   permutation null: the four thermal columns row-shuffled JOINTLY in train
             and eval, within each floor
    step 7   Construction B (paired safe-t), n=5, g=1.0, declared in the leaf doc
             before this ran; reported for every arm including E < 1

Reads the warehouse read-only. Writes nothing to `ml/models/`, nothing to
`ml/artefacts/evaluation_metrics.json`, nothing to the warehouse and nothing to git:
`evaluate.run()` is never called. The only outputs are the JSON and log named below.

Usage:  PYTHONPATH=. python3 scripts/arms_08i_min_observations_floor.py
        PYTHONPATH=. python3 scripts/arms_08i_min_observations_floor.py --families cliff_classifier
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ml.src import attribution as AT
from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S

# ─── The arms ───────────────────────────────────────────────────────────────────────
FLOORS: tuple[int, ...] = (1, 2, 3, 5)
REFERENCE_FLOOR = 2          # the built warehouse == the live v12 substrate
THERMAL_COLS: tuple[str, ...] = S.FEATURE_GROUPS["thermal"]

SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(5))
E_VALUE_G = 1.0              # pre-registered: a one-sd effect, as in 02c and 08h
FAMILIES = ("degradation_regressor_p10", "degradation_regressor_p50",
            "degradation_regressor_p90", "cliff_classifier",
            "stint_life_regressor")
OUT = Path("ml/artefacts/08i_min_observations_floor_arms.json")

# ─── The floor-parameterised replica of int_lap_thermal_proxy ───────────────────────
# `combined` in the dbt model is int_stint_geometry INNER JOIN stg_laps on lap_id.
# int_lap_thermal_proxy IS that join, materialised, and carries lap_time_s through
# untouched -- so re-joining it to geometry for is_valid_lap reproduces `combined`
# exactly without stg_laps, which is a view over bronze parquet at a path relative to
# the dbt project dir. Everything below this CTE is copied from the model verbatim;
# the ONLY parameter is {floor}. surface_bulk_ratio is the mart's own expression.
THERMAL_SQL = """
WITH combined AS (
    SELECT t.stint_id, t.lap_id, t.lap_in_stint, g.is_valid_lap, t.lap_time_s
    FROM int_lap_thermal_proxy AS t
    INNER JOIN int_stint_geometry AS g ON t.lap_id = g.lap_id
),
with_baseline AS (
    SELECT *,
        (CASE
            WHEN COUNT(CASE WHEN is_valid_lap THEN lap_time_s END) OVER w0 >= {floor}
            THEN MEDIAN(CASE WHEN is_valid_lap THEN lap_time_s END) OVER w0
         END) AS stint_baseline_pace,
        COUNT(CASE WHEN is_valid_lap THEN lap_time_s END) OVER w0
            AS baseline_observations_n
    FROM combined
    WINDOW w0 AS (
        PARTITION BY stint_id ORDER BY lap_in_stint
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    )
),
with_residual AS (
    SELECT *, stint_baseline_pace - lap_time_s AS push_residual FROM with_baseline
),
thermal AS (
    SELECT *,
        CASE WHEN push_residual IS NOT NULL THEN ROUND(
            GREATEST(push_residual, 0)
            + 0.717 * GREATEST(COALESCE(LAG(push_residual, 1) OVER w, 0), 0)
            + 0.514 * GREATEST(COALESCE(LAG(push_residual, 2) OVER w, 0), 0)
            + 0.369 * GREATEST(COALESCE(LAG(push_residual, 3) OVER w, 0), 0)
            + 0.264 * GREATEST(COALESCE(LAG(push_residual, 4) OVER w, 0), 0),
            4) END AS cumulative_push_load_surface,
        CASE WHEN push_residual IS NOT NULL THEN ROUND(
            GREATEST(push_residual, 0)
            + 0.819 * GREATEST(COALESCE(LAG(push_residual, 1) OVER w, 0), 0)
            + 0.670 * GREATEST(COALESCE(LAG(push_residual, 2) OVER w, 0), 0)
            + 0.549 * GREATEST(COALESCE(LAG(push_residual, 3) OVER w, 0), 0)
            + 0.449 * GREATEST(COALESCE(LAG(push_residual, 4) OVER w, 0), 0)
            + 0.368 * GREATEST(COALESCE(LAG(push_residual, 5) OVER w, 0), 0)
            + 0.301 * GREATEST(COALESCE(LAG(push_residual, 6) OVER w, 0), 0)
            + 0.247 * GREATEST(COALESCE(LAG(push_residual, 7) OVER w, 0), 0),
            4) END AS cumulative_push_load_bulk
    FROM with_residual
    WINDOW w AS (
        PARTITION BY stint_id ORDER BY lap_in_stint
        ROWS BETWEEN 8 PRECEDING AND CURRENT ROW
    )
)
SELECT lap_id, baseline_observations_n,
       push_residual, cumulative_push_load_surface, cumulative_push_load_bulk,
       COALESCE(cumulative_push_load_surface, 0.0)
       / NULLIF(COALESCE(cumulative_push_load_surface, 0.0)
                + COALESCE(cumulative_push_load_bulk, 0.0), 0.0) AS surface_bulk_ratio
FROM thermal
"""


def load_thermal_by_floor() -> tuple[dict[int, pd.DataFrame], dict]:
    """The four thermal columns at each floor, plus step 1b's bit-for-bit check.

    The check is not decoration. Floors 1/3/5 are this query with one integer
    changed; if the query at floor 2 does not reproduce what dbt built, then none of
    the other three is the thing the SQL would have produced either, and every delta
    below is measuring the reimplementation rather than the floor.
    """
    con = duckdb.connect(S.DUCKDB_PATH, read_only=True)
    prod = con.execute(
        f"SELECT lap_id, {', '.join(THERMAL_COLS)}, is_training_eligible "
        f"FROM {S.MART}"
    ).df().set_index("lap_id")

    frames: dict[int, pd.DataFrame] = {}
    for f in FLOORS:
        r = con.execute(THERMAL_SQL.format(floor=f)).df().set_index("lap_id")
        frames[f] = r.loc[prod.index]        # restrict to the mart's own row set
    con.close()

    # ── step 1b ────────────────────────────────────────────────────────────────
    ref = frames[REFERENCE_FLOOR]
    check: dict = {"reference_floor": REFERENCE_FLOOR, "n_mart_rows": int(len(prod)),
                   "columns": {}}
    exact_all = True
    for c in THERMAL_COLS:
        a, b = prod[c], ref[c]
        both_null = a.isna() & b.isna()
        ok = (a == b) | both_null
        n_bad = int((~ok).sum())
        exact_all &= (n_bad == 0)
        check["columns"][c] = {
            "n_exact": int(ok.sum()), "n_mismatch": n_bad,
            "n_null_built": int(a.isna().sum()), "n_null_replica": int(b.isna().sum()),
        }
    check["bit_for_bit"] = bool(exact_all)

    # ── coverage per floor, on the training-eligible panel ──────────────────────
    elig = prod.index[prod["is_training_eligible"].fillna(False).astype(bool)]
    cov: dict = {}
    n_e = len(elig)
    for f in FLOORS:
        n_null = int(frames[f].loc[elig, "push_residual"].isna().sum())
        cov[f] = {"n_eligible": n_e, "n_thermal_null": n_null,
                  "coverage_pct": 100.0 * (1 - n_null / n_e),
                  "null_pct": 100.0 * n_null / n_e}
    for f in FLOORS:
        cov[f]["coverage_pp_vs_floor_1"] = cov[f]["coverage_pct"] - cov[1]["coverage_pct"]
        cov[f]["coverage_pp_vs_reference"] = (
            cov[f]["coverage_pct"] - cov[REFERENCE_FLOOR]["coverage_pct"])
    check["eligible_coverage_by_floor"] = cov
    return frames, check


# ─── Fit / score, through evaluate.py's own paths (08h's helpers, unchanged) ─────────
def fit_seeded(spec: S.TargetSpec, params: dict, X, y, cens, w, seed: int):
    """E._fit with the seed overridden, and nothing else changed.

    The override differs by API and both are exercised here. `T._make_model` passes
    `random_state` positionally into the sklearn constructors, so injecting it through
    `params` would collide; it is set afterwards instead. `AFTBooster` has no
    `set_params` -- it takes `seed` inside its own params dict, where `**p` merges
    AFTER the default, so injecting it there is the supported route.
    """
    from ml.src import train as T
    if spec.kind == "survival":
        model = T._make_model(spec, {**params, "seed": int(seed)})
    else:
        model = T._make_model(spec, params)
        model.set_params(random_state=int(seed))
    if spec.kind == "quantile" and w is None:
        raise ValueError("quantile fit needs the IPW row weights production fits with")
    weights = np.asarray(w, dtype=np.float32) if w is not None else T._sample_weight(spec, y)
    if spec.kind == "survival":
        model.fit(X, y, sample_weight=weights, is_censored=np.asarray(cens, dtype=bool))
    else:
        model.fit(X, y, sample_weight=weights)
    return model


def score_model(spec: S.TargetSpec, model, X_ev, y_ev, cens_ev) -> float:
    """The headline, through evaluate.py's own scorer.

    The AFT scale is a term in the likelihood, so it must be the scale of the model
    being scored -- `evaluate.run()` takes it off the fitted model and so does this.
    """
    scale = getattr(model, "scale", None) if spec.kind == "survival" else None
    return E._score(spec, y_ev, E._predict_index(spec, model, X_ev), cens_ev, scale)


def delta(arm_value: float, base_value: float, higher_is_better: bool) -> float:
    """Positive = improvement, on every metric."""
    return (arm_value - base_value) if higher_is_better else (base_value - arm_value)


def shuffled_block(X: pd.DataFrame, cols: tuple[str, ...],
                   rng: np.random.Generator) -> pd.DataFrame:
    """Row-shuffle the thermal columns JOINTLY, one permutation for the block.

    Jointly, not column-by-column: the four are three transforms of one residual plus
    their ratio, so their internal correlation is part of the block's capacity. The
    null being scored is "this block carries no information about the label", not
    "these four are unrelated to each other". NaNs move with their values, so the NaN
    count -- which is exactly what the floor changes -- is preserved within each arm.
    """
    out = X.copy()
    perm = rng.permutation(len(X))
    block = out[list(cols)].to_numpy()[perm]
    for i, c in enumerate(cols):
        out[c] = block[:, i]
    return out


# ─── E-value, Construction B (paired safe-t) ────────────────────────────────────────
def safe_t_e_value(d: np.ndarray, g: float = E_VALUE_G) -> dict:
    """E = (1+ng)^(-1/2) * [(1+t^2/(n-1)) / (1+t^2/((1+ng)(n-1)))]^(n/2).

    Grunwald / de Heide / Koolen's safe t-test: the one-sample Bayes factor under a
    right-Haar prior on sigma and N(0,g) on the effect size. Exact for any unknown
    sigma, which is why it needs no prior reseed study of this substrate.
    """
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    d_bar = float(d.mean())
    s_d = float(d.std(ddof=1))
    cap = (1.0 + n * g) ** ((n - 1) / 2.0)
    if s_d == 0.0:
        t = 0.0 if d_bar == 0.0 else float(np.copysign(np.inf, d_bar))
    else:
        t = float(np.sqrt(n) * d_bar / s_d)
    if np.isfinite(t):
        num = 1.0 + t * t / (n - 1)
        den = 1.0 + t * t / ((1.0 + n * g) * (n - 1))
        e = (1.0 + n * g) ** -0.5 * (num / den) ** (n / 2.0)
    else:
        e = cap
    # The formula is symmetric in t, so a consistently NEGATIVE delta also returns a
    # large E -- evidence against exchangeability in the wrong direction. Direction is
    # carried beside the number rather than folded into it: applying a one-sided
    # transform after seeing the data is the one thing that voids an e-value.
    return {"n": n, "g": g, "d_bar": d_bar, "s_d": s_d, "t": t, "E": float(e),
            "direction_is_improvement": bool(d_bar > 0),
            "max_attainable_E": float(cap)}


def e_value_validity_check(n_draws: int = 100_000, seed: int = S.RANDOM_STATE) -> dict:
    """Push i.i.d. N(0, sigma) deltas through the implementation; mean(E) must be 1.

    Required by `e_value_construction.md` section 4: a construction whose null mean is
    not 1 is not an e-value.
    """
    rng = np.random.default_rng(seed)
    out = {}
    n, g = len(SEEDS), E_VALUE_G
    for sigma in (0.001, 0.01, 0.1, 1.0):
        d = rng.normal(0.0, sigma, size=(n_draws, n))
        t = np.sqrt(n) * d.mean(axis=1) / d.std(axis=1, ddof=1)
        num = 1.0 + t ** 2 / (n - 1)
        den = 1.0 + t ** 2 / ((1.0 + n * g) * (n - 1))
        e = (1.0 + n * g) ** -0.5 * (num / den) ** (n / 2.0)
        out[f"sigma={sigma}"] = {"mean_E": float(e.mean()),
                                 "mc_se": float(e.std(ddof=1) / np.sqrt(n_draws)),
                                 "p_E_gt_20": float((e > 20).mean())}
    return out


# ─── One family ─────────────────────────────────────────────────────────────────────
def run_family(target: str, split, frames: dict[int, pd.DataFrame], log) -> dict:
    spec = S.TARGET_BY_NAME[target]
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    hib = E._higher_is_better(spec)
    w_tr, c_tr, c_ev = split.w_tr, split.cens_tr, split.cens_ev
    y_tr, y_ev = split.y_tr, split.y_ev

    def arm_X(floor: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        """The 32-column contract with its thermal block recomputed at `floor`."""
        src = frames[floor]
        Xt, Xe = split.X_tr.copy(), split.X_ev.copy()
        tr = src.loc[split.lap_ids_tr]
        ev = src.loc[split.lap_ids_ev]
        for c in THERMAL_COLS:
            # float32 to match features.py::_encode_frame, which casts every numeric
            # contract column; a float64 splice would change the split thresholds.
            Xt[c] = tr[c].to_numpy(dtype="float32")
            Xe[c] = ev[c].to_numpy(dtype="float32")
        return Xt, Xe

    res: dict = {
        "target": target,
        "metric": E._headline_metric_name(spec),
        "higher_is_better": hib,
        "n_train": int(len(split.X_tr)), "n_eval": int(len(split.X_ev)),
        "n_features": int(split.X_tr.shape[1]),
        "thermal_columns": list(THERMAL_COLS),
        "split_mode": split.mode, "eval_season": split.eval_season,
        "seeds": list(SEEDS), "reference_floor": REFERENCE_FLOOR,
        "floors": {},
    }

    # ── step 1b, per family: the floor-2 arm must BE the split, not merely match it ──
    Xr_tr, Xr_ev = arm_X(REFERENCE_FLOOR)
    ident = {}
    for c in THERMAL_COLS:
        for nm, a, b in (("train", split.X_tr[c], Xr_tr[c]), ("eval", split.X_ev[c], Xr_ev[c])):
            same = int((((a == b) | (a.isna() & b.isna()))).sum())
            ident[f"{c}:{nm}"] = {"n_same": same, "n": int(len(a)),
                                  "identical": bool(same == len(a))}
    res["reference_arm_reproduces_split"] = ident
    bad = [k for k, v in ident.items() if not v["identical"]]
    if bad:
        raise RuntimeError(f"[{target}] floor-{REFERENCE_FLOOR} splice is not the "
                           f"built substrate on: {bad}")
    log(f"  [{target}] step 1b: floor-{REFERENCE_FLOOR} splice reproduces the split "
        f"exactly on all {len(THERMAL_COLS)} thermal columns, train and eval")

    # ── per-floor arms ─────────────────────────────────────────────────────────────
    reals_by_floor: dict[int, np.ndarray] = {}
    floor_noise: dict[int, float] = {}

    for f in FLOORS:
        t0 = time.time()
        Xa_tr, Xa_ev = arm_X(f)
        nan_tr = int(Xa_tr["push_residual"].isna().sum())
        nan_ev = int(Xa_ev["push_residual"].isna().sum())

        # step 2 -- headline at the canonical seed
        headline = score_model(
            spec, E._fit(spec, params, Xa_tr, y_tr, cens=c_tr, w=w_tr), Xa_ev, y_ev, c_ev)

        # step 3 -- this arm's own reseed floor; the 5 fits double as the paired reals
        nf = AT.refit_noise_floor(
            lambda s: fit_seeded(spec, params, Xa_tr, y_tr, c_tr, w_tr, s),
            lambda yt, m, X: score_model(spec, m, X, yt, c_ev),
            Xa_ev, y_ev, SEEDS)
        reals_by_floor[f] = np.asarray(nf["headline_by_seed"])
        floor_noise[f] = float(nf["delta_noise_2sd"])

        # step 4 -- permutation null within this floor, canonical seed
        Xs_tr = shuffled_block(Xa_tr, THERMAL_COLS, np.random.default_rng([S.RANDOM_STATE, 0]))
        Xs_ev = shuffled_block(Xa_ev, THERMAL_COLS, np.random.default_rng([S.RANDOM_STATE, 1]))
        shuf = score_model(
            spec, E._fit(spec, params, Xs_tr, y_tr, cens=c_tr, w=w_tr), Xs_ev, y_ev, c_ev)

        # step 7 -- paired information contrast, shuffle redrawn per seed
        shufs = []
        for s in SEEDS:
            sh_tr = shuffled_block(Xa_tr, THERMAL_COLS, np.random.default_rng([int(s), 0]))
            sh_ev = shuffled_block(Xa_ev, THERMAL_COLS, np.random.default_rng([int(s), 1]))
            shufs.append(score_model(
                spec, fit_seeded(spec, params, sh_tr, y_tr, c_tr, w_tr, s), sh_ev, y_ev, c_ev))
        shufs = np.asarray(shufs)
        d_info = np.asarray([delta(r, sh, hib)
                             for r, sh in zip(reals_by_floor[f], shufs)])
        ev_info = safe_t_e_value(d_info)

        F2 = floor_noise[f]
        capacity = delta(shuf, headline, hib)          # shuffled vs this arm's own real
        information = delta(headline, shuf, hib)
        res["floors"][str(f)] = {
            "min_observations": f,
            "headline": headline,
            "n_thermal_nan_train": nan_tr, "n_thermal_nan_eval": nan_ev,
            "thermal_nan_pct_eval": 100.0 * nan_ev / len(Xa_ev),
            "reseed_floor": nf,
            "floor_2sqrt2sd": F2,
            "permutation_null": {
                "headline_shuffled": shuf,
                "capacity_delta_vs_own_real": capacity,
                "information_delta": information,
                "information_floor_ratio": (information / F2) if F2 else None,
                "information_clears_floor": bool(information > F2) if F2 else None,
            },
            "information_e_value": ev_info,
            "shuffled_by_seed": shufs.tolist(),
            "information_deltas_by_seed": d_info.tolist(),
        }
        log(f"  [{target}] floor {f}: headline={headline:.10f}  "
            f"shuffled={shuf:.10f}  info={information:+.8f} ({information/F2:+.2f}x own floor)  "
            f"E_info={ev_info['E']:.4g}  nan_ev={nan_ev} ({100.0*nan_ev/len(Xa_ev):.2f}%)  "
            f"floor={F2:.8f}  ({time.time()-t0:.0f}s)")

    # ── the shipping contrast: every floor against the built substrate ──────────────
    ref_real = reals_by_floor[REFERENCE_FLOOR]
    ref_headline = res["floors"][str(REFERENCE_FLOOR)]["headline"]
    ref_shuf = res["floors"][str(REFERENCE_FLOOR)]["permutation_null"]["headline_shuffled"]
    cross: dict = {}
    for f in FLOORS:
        if f == REFERENCE_FLOOR:
            continue
        F2 = max(floor_noise[f], floor_noise[REFERENCE_FLOOR])
        d_point = delta(res["floors"][str(f)]["headline"], ref_headline, hib)
        d_paired = np.asarray([delta(a, b, hib)
                               for a, b in zip(reals_by_floor[f], ref_real)])
        ev_cross = safe_t_e_value(d_paired)
        # The declared missingness control: both sides shuffled, so only NaN density
        # differs. If this moves as much as the real contrast, the floor changed the
        # NaN pattern and not the information.
        d_shuf_only = delta(
            res["floors"][str(f)]["permutation_null"]["headline_shuffled"], ref_shuf, hib)
        cross[str(f)] = {
            "vs_floor": REFERENCE_FLOOR,
            "delta_point_estimate": d_point,
            "delta_paired_mean": float(d_paired.mean()),
            "paired_deltas_by_seed": d_paired.tolist(),
            "floor_2sqrt2sd_larger_of_two": F2,
            "floor_ratio": (d_point / F2) if F2 else None,
            "paired_floor_ratio": (float(d_paired.mean()) / F2) if F2 else None,
            "clears_floor": bool(d_point > F2) if F2 else None,
            "paired_clears_floor": bool(d_paired.mean() > F2) if F2 else None,
            "e_value": ev_cross,
            "missingness_only_control_shuffled_vs_shuffled": {
                "delta": d_shuf_only,
                "floor_ratio": (d_shuf_only / F2) if F2 else None,
                "note": ("both arms row-shuffled, so the signal is destroyed in both "
                         "and only the NaN density differs. Read the real contrast "
                         "against this, not against zero."),
            },
        }
        log(f"  [{target}] floor {f} vs {REFERENCE_FLOOR}: "
            f"delta={d_point:+.8f} ({d_point/F2:+.2f}x)  "
            f"paired={d_paired.mean():+.8f} ({d_paired.mean()/F2:+.2f}x)  "
            f"E={ev_cross['E']:.4g} (improvement={ev_cross['direction_is_improvement']})  "
            f"missingness-only={d_shuf_only:+.8f} ({d_shuf_only/F2:+.2f}x)")
    res["cross_floor_vs_reference"] = cross
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", nargs="*", default=list(FAMILIES))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    lines: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    published = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())

    log(f"contract {S.MODEL_VERSION_DEFAULT}, {len(S.FEATURE_COLUMNS)} features")
    log(f"floors {FLOORS}, reference (built substrate) = {REFERENCE_FLOOR}")
    log(f"thermal block = {THERMAL_COLS}")

    log("\n=== step 1b: floor-parameterised replica vs the built warehouse ===")
    frames, check = load_thermal_by_floor()
    for c, v in check["columns"].items():
        log(f"  {c:<32} exact {v['n_exact']}/{check['n_mart_rows']}  "
            f"mismatch {v['n_mismatch']}  nulls built={v['n_null_built']} "
            f"replica={v['n_null_replica']}")
    log(f"  BIT-FOR-BIT: {check['bit_for_bit']}")
    if not check["bit_for_bit"]:
        log("  ABORT: the replica is not the built substrate; no arm below is readable.")
        return 1
    log("  eligible-panel coverage by floor:")
    for f in FLOORS:
        cv = check["eligible_coverage_by_floor"][f]
        log(f"    floor {f}: {cv['coverage_pct']:.2f}%  "
            f"({cv['n_thermal_null']}/{cv['n_eligible']} thermal-NULL)  "
            f"{cv['coverage_pp_vs_floor_1']:+.2f}pp vs floor 1, "
            f"{cv['coverage_pp_vs_reference']:+.2f}pp vs floor {REFERENCE_FLOOR}")

    out: dict = {
        "item": "08i",
        "purpose": ("price the min_observations floor of int_lap_thermal_proxy's "
                    "stint baseline through gate steps 1-4 (+7) on the v12 substrate"),
        "ran_at": pd.Timestamp.utcnow().isoformat(),
        "contract_version": S.MODEL_VERSION_DEFAULT,
        "published_artefact_version": published.get("version"),
        "n_contract_features": len(S.FEATURE_COLUMNS),
        "floors": list(FLOORS),
        "reference_floor": REFERENCE_FLOOR,
        "reference_floor_note": (
            "min_observations=2 has been the built value since 2026-09-10 (commit "
            "c49473a) and is what 08m rebuilt the v12 warehouse on. The leaf doc's "
            "claim that the rebuild 'took min_observations=1' is stale."),
        "thermal_columns": list(THERMAL_COLS),
        "seeds": list(SEEDS),
        "row_set_invariance": (
            "is_training_eligible = age_in_stint > 3 AND anomaly_class NOT IN "
            "('mistake','conditions'); it does not reference the thermal block, so "
            "the floor changes NaN density and never the row set. The cross-floor "
            "contrast is capacity-neutral by construction."),
        "e_value_construction": {"name": "B (paired safe-t)", "n": len(SEEDS),
                                 "g": E_VALUE_G,
                                 "null_within_floor": "real vs its own row-shuffle",
                                 "null_cross_floor": "floor F vs floor 2, paired on seed"},
        "e_value_validity_check": e_value_validity_check(),
        "step_1b_replica_check": check,
        "step_1a_published_headline_check": {},
        "families": {},
    }
    cap = (1.0 + len(SEEDS) * E_VALUE_G) ** ((len(SEEDS) - 1) / 2.0)
    out["e_value_construction"]["max_attainable_E"] = cap
    log("\ne-value validity check (mean E under H0 must be 1.00):")
    for k, v in out["e_value_validity_check"].items():
        log(f"  {k:<14} mean_E={v['mean_E']:.4f} +/- {2*v['mc_se']:.4f}  "
            f"P(E>20)={v['p_E_gt_20']:.4f}")
    log(f"  max attainable E at n={len(SEEDS)}, g={E_VALUE_G}: {cap:.1f}")

    # One bundle serves the whole degradation trio: same rows, same target column,
    # same per-family mask; only the quantile alpha and the tuned params differ.
    bundles: dict[str, object] = {}
    for target in args.families:
        spec = S.TARGET_BY_NAME[target]
        fam = spec.family
        if fam not in bundles:
            bundles[fam] = E._evaluation_split(F.load_features(target=target))
        split = bundles[fam]
        log(f"\n=== {target} ({fam}) ===")
        fam_res = run_family(target, split, frames, log)

        # ── step 1a: does the floor-2 arm reproduce the PUBLISHED v12 headline? ────
        pub = published["models"].get(target, {}).get("headline")
        got = fam_res["floors"][str(REFERENCE_FLOOR)]["headline"]
        diff = abs(got - pub) if pub is not None else None
        out["step_1a_published_headline_check"][target] = {
            "published_v12": pub, "floor_2_arm": got, "abs_diff": diff,
            "reproduces_to_1e-6": bool(diff is not None and diff < 1e-6),
        }
        log(f"  [{target}] step 1a: published v12 {pub:.10f} vs floor-"
            f"{REFERENCE_FLOOR} arm {got:.10f}  |diff|={diff:.2e}  "
            f"reproduces={diff < 1e-6}")

        out["families"][target] = fam_res
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2, default=float))

    Path(args.out).with_suffix(".log").write_text("\n".join(lines) + "\n")
    log(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
