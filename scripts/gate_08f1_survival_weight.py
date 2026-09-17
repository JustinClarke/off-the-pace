"""08f-1 -- gate the survival-weight season-lag, in isolation, on the v12/08m substrate.

WHY THIS EXISTS. `fct_cliff_prediction_features.sql` builds the quantile trio's IPW
sample weight (`survival_weight`) from `total_per_compound` / `stints_reaching`, which
originally pooled every ingested season (`GROUP BY compound[, lap_in_stint]`, no season
key) -- so a 2018 training row's weight was partly estimated from 2024 eval-season data.
`08f-1` (commit `bbe3e48`, 2026-09-09; see the leaf doc `_improvements/work/
08-foundations-repair.md` ~line 573) rebuilt the two counts as an expanding sum over
seasons STRICTLY BEFORE the row's own. That fix is already built and already live --
this script does not change it. What has never been gated: `survival_weight` is not a
FEATURE_COLUMNS member (`ml/src/schema.py`), so no add-ablation can see it; it reaches
the model only as `train.py`'s XGBoost sample weight for the quantile trio
(`train.py::_sample_weight`) -- current `evaluate.py::_score` does NOT weight the eval
pinball loss (checked directly: `T._headline`'s quantile branch is called with no
`meta`, hence unweighted `pinball_loss`; this differs from an earlier characterisation
in the leaf doc and is corrected there). `cliff_classifier` and `stint_life_regressor`
never consume `survival_weight` at all (`train.py::_sample_weight`'s classification arm
computes balanced class weights from y; its survival arm returns None by design, "the
censoring the IPW approximates is now represented exactly, weighting on top would count
it twice").

THE COMMIT, VERIFIED INDEPENDENTLY (not trusted from the leaf doc). `git log --follow`
on this file's own history: `bbe3e48` (2026-09-09) is the commit that introduced the
season-lag rewrite here; its immediate predecessor `c7de693` (2026-09-07) is the
pre-08f-1 content. `git diff c7de693 bbe3e48 -- <path>` shows the season-lag rewrite of
`total_per_compound` / `stints_reaching` / `stint_survival` PLUS one unrelated addition
bundled in the same squashed commit -- `baseline_observations_n` (08e's companion
column). Three later commits (`bf2d9a6`, `63a5095`, `4c79975`) touch this file again for
02c/02b, entirely unrelated CTEs. So the pre-08f-1 form of survival-weight CTEs is NOT
"git show c7de693:<path>" wholesale (that would also strip `baseline_observations_n`,
which must stay shipped, and any 02b/02c columns added since) -- it is a HAND REVERT of
exactly the three CTEs, applied on top of HEAD. See `revert_08f1()`'s docstring below for
the exact before/after SQL.

METHOD (manual steps; this script has three stages selected by --stage).

  1. `export-after`  -- run against the isolated `gate_before` warehouse (bronze
     `external_location` sources; `dev.duckdb` never opened for write; same pattern as
     `08g` ~line 1071 and this session's own 08f-2 probe) while the SQL is UNCHANGED
     (current, shipped, season-lagged). Calls `F.load_features` (production code, not a
     reimplementation) for each of the 5 targets and pickles everything
     `evaluate.py::_evaluation_split` needs, plus the raw `meta_train`/`meta_holdout`
     frames, to `--snapshot-dir`.

       cd transform && dbt seed --select circuit_reference compound_cliff_params \\
           race_to_track seed_manual_lap_exceptions --target gate_before
       dbt run --select +fct_cliff_prediction_features --target gate_before
       PYTHONPATH=. python3 scripts/gate_08f1_survival_weight.py --stage export-after

  2. Hand-revert the three CTEs (`revert_08f1()` prints the exact patch; apply it to
     `transform/models/marts/fct_cliff_prediction_features.sql`), then:

       cd transform && dbt run --select +fct_cliff_prediction_features --target gate_before
       PYTHONPATH=. python3 scripts/gate_08f1_survival_weight.py --stage export-before

     Then `git checkout HEAD -- transform/models/marts/fct_cliff_prediction_features.sql`
     immediately, and confirm with `git diff --stat` that nothing is left modified.

  3. Delete `data/gate_before.duckdb`, remove the `gate_before` target block from
     `transform/profiles/profiles.yml`. Nothing from stages 1-2 persists on disk or in
     git after this.

  4. `--stage analyze` -- pure pandas/numpy from here on, no duckdb, no dbt. Reads both
     snapshots, runs the row-level instrument check (does ANYTHING outside
     `survival_weight` differ between the two snapshots), then the weight-scheme arms
     through `evaluate.py`'s own `_fit`/`_score`/`attribution.refit_noise_floor`.

THE DESIGN (gates.md step 6 -- declared before the arms run, not after).

`survival_weight` is a sample weight, not a feature, so gates.md's add/drop-a-column
framework does not apply literally. Translated:

  - Baseline arm `A`  = UNIFORM weights (w = 1 for every training row). This is the
    zero point a weight-scheme ablation drops TO -- "no IPW scheme at all" is the
    direct analogue of "contract minus the family" for a column ablation. It is not
    what production ships; it is the reference the other two arms are read against.
  - Arm `BEFORE`      = the season-POOLED IPW (pre-08f-1, what shipped before this fix)
  - Arm `AFTER`       = the season-LAGGED IPW (current, shipped, what this gate is FOR)

  Step 1 (instrument check) = (a) full-contract refit with AFTER weights reproduces the
    published v12 headline to 6dp for the quantile trio, exactly as every other item's
    step 1; (b) row-level diff of FEATURE_COLUMNS + every target + censoring flag
    between the AFTER and BEFORE snapshots -- must be EXACTLY zero (not float-noise
    zero: these CTEs share no computation with anything that feeds X or y), which is
    what licenses treating cliff_classifier/stint_life_regressor as invariant to 08f-1
    without refitting them twice.
  Step 2 (the gate's own question) = AFTER vs BEFORE, both refit at the canonical seed
    with `evaluate.py::_fit`, scored with `evaluate.py::_score` (unweighted at eval
    time, per the finding above -- this is a training-time-only effect). Oriented
    positive = AFTER (fixed) improves on BEFORE (leaky), matching every other item's
    convention; the leaf doc's own step-1 finding for 08e/08f-2 combined was that
    de-leaking COST headline performance, so a negative number here is an expected,
    valid outcome, not evidence the harness broke.
  Step 3 (floor) = `attribution.refit_noise_floor`, 5 reseeds (model seed only; the
    weight vector is fixed per arm, matching how a column ablation fixes its columns
    and reseeds the fit), computed on BOTH arms, quoted against the LARGER -- same
    convention as every other item in this tree.
  Step 4 (permutation null, translated) = row-shuffle the AFTER weight VECTOR across
    training rows (not a column -- there is no column to shuffle). This preserves the
    exact multiset of weight values (so aggregate reweighting strength / "capacity" is
    unchanged) while destroying the (compound, lap_in_stint, season) alignment that
    makes the weight informative. capacity = shuffled - A(uniform); information =
    AFTER - shuffled. Run the identical construction on BEFORE for symmetry (does
    pooling's own alignment carry anything, or was its whole effect capacity?).
  Step 5 (feature-contract check) = this change touches zero members of
    FEATURE_COLUMNS (`survival_weight` was never one). `features.py --check` is run
    once this session against the untouched `dev.duckdb` to confirm nothing else in the
    working tree drifted; the isolated snapshots are not re-fingerprinted separately
    because their FEATURE_COLUMNS content is asserted bit-identical by step 1(b).
  Step 6 (pre-registration) = this docstring, written before the arms below ran.
  Step 7 (e-value) = Construction B (paired safe-t, `E_VALUE_G=1.0`, matching every
    other item), over 5 seeds, on the INFORMATION contrast gates.md always names --
    real (AFTER) vs its own row-shuffle -- NOT on AFTER-vs-BEFORE (that is step 2's
    question; e-values formalise whether AFTER's alignment carries information, per
    gates.md's own instruction that "the null is real vs row-shuffled, not arm vs
    baseline"). Includes the Monte Carlo validity check and a shuffle-vs-shuffle
    negative control, exactly as `08e`'s script.

Deltas are oriented so POSITIVE ALWAYS MEANS IMPROVEMENT, on every metric.

Reads the warehouse read-only in every stage. Writes nothing to `ml/models/`, nothing to
`ml/artefacts/evaluation_metrics.json`, nothing to `dev.duckdb` and nothing to git. The
only outputs are the two snapshot pickles (scratch, not committed) and the JSON named by
--out.

Usage:
    PYTHONPATH=. python3 scripts/gate_08f1_survival_weight.py --stage export-after \\
        --duckdb ../data/gate_before.duckdb --snapshot-dir /tmp/08f1_snap
    # (hand-revert, rebuild, ...)
    PYTHONPATH=. python3 scripts/gate_08f1_survival_weight.py --stage export-before \\
        --duckdb ../data/gate_before.duckdb --snapshot-dir /tmp/08f1_snap
    # (git checkout HEAD --, delete gate_before.duckdb, remove profile block)
    PYTHONPATH=. python3 scripts/gate_08f1_survival_weight.py --stage analyze \\
        --snapshot-dir /tmp/08f1_snap
"""
from __future__ import annotations

import argparse
import json
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ml.src import attribution as AT
from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S
from ml.src import train as T

SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(5))
E_VALUE_G = 1.0
QUANTILE_TARGETS = ("degradation_regressor_p10", "degradation_regressor_p50",
                    "degradation_regressor_p90")
STRUCTURAL_TARGETS = ("cliff_classifier", "stint_life_regressor")
ALL_TARGETS = QUANTILE_TARGETS + STRUCTURAL_TARGETS
OUT = Path("_improvements/eval/08f/08f1_gate_arms.json")

INSTRUMENT_COLS_NOTE = (
    "every FEATURE_COLUMNS member, every target column, and the censoring flag -- "
    "everything survival_weight's CTEs do not feed"
)


def revert_08f1() -> str:
    """The hand-revert patch, printed for the record (not applied by this script --
    apply by hand to transform/models/marts/fct_cliff_prediction_features.sql, matching
    08g's method of hand-editing rather than wholesale git-show when a commit bundles
    unrelated changes)."""
    return """
--- pre-08f-1 (commit c7de693) form, hand-applied on top of HEAD ---

total_per_compound AS (
    SELECT compound, COUNT(DISTINCT stint_id) AS n_total
    FROM {{ ref('int_lap_residual_decomposed') }}
    GROUP BY compound
),

stints_reaching AS (
    SELECT
        d.compound,
        d.lap_in_stint,
        COUNT(DISTINCT d.stint_id) AS n_reaching
    FROM {{ ref('int_lap_residual_decomposed') }} AS d
    GROUP BY d.compound, d.lap_in_stint
),

stint_survival AS (
    SELECT
        sr.compound,
        sr.lap_in_stint,
        sr.n_reaching * 1.0 / tp.n_total AS survival_prob
    FROM stints_reaching AS sr
    INNER JOIN total_per_compound AS tp ON sr.compound = tp.compound
),

-- and in `base`'s join list:
    LEFT JOIN
        stint_survival AS ss
        ON r.compound = ss.compound AND r.lap_in_stint = ss.lap_in_stint

-- (season_compound_totals / season_stints_reaching CTEs deleted entirely --
--  they exist only to feed the season-lagged windows.
--  baseline_observations_n, corner_inputs, qualifying and everything else in the
--  file is left EXACTLY as shipped.)
"""


# ─── Stage 1/2: export a snapshot from the (AFTER- or BEFORE-state) warehouse ───────
def export_snapshot(duckdb_path: str, label: str, out_path: Path) -> None:
    bundles: dict[str, F.FeatureBundle] = {}
    snap: dict = {"label": label, "duckdb_path": duckdb_path,
                  "exported_at": pd.Timestamp.utcnow().isoformat(), "targets": {}}
    for target in ALL_TARGETS:
        fam = S.TARGET_BY_NAME[target].family
        if fam not in bundles:
            bundles[fam] = F.load_features(duckdb_path=duckdb_path, target=target)
        b = bundles[fam]
        split = E._evaluation_split(b)
        snap["targets"][target] = {
            "mode": split.mode, "eval_season": split.eval_season,
            "X_tr": split.X_tr, "y_tr": split.y_tr,
            "X_ev": split.X_ev, "y_ev": split.y_ev,
            "cens_tr": split.cens_tr, "cens_ev": split.cens_ev,
            "w_tr": split.w_tr,
            "lap_ids_tr": split.lap_ids_tr, "lap_ids_ev": split.lap_ids_ev,
            "fingerprint": b.fingerprint, "n_features": len(b.feature_columns),
        }
        print(f"[{label}] {target}: n_tr={len(split.X_tr)} n_ev={len(split.X_ev)} "
              f"mode={split.mode} eval_season={split.eval_season} "
              f"w_tr={'yes' if split.w_tr is not None else 'no'}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fh:
        pickle.dump(snap, fh)
    print(f"wrote {out_path}")


# ─── Stage 3: pure-pandas analysis from the two snapshots ──────────────────────────
def fit_seeded(spec: S.TargetSpec, params: dict, X, y, cens, w, seed: int):
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
    scale = getattr(model, "scale", None) if spec.kind == "survival" else None
    return E._score(spec, y_ev, E._predict_index(spec, model, X_ev), cens_ev, scale)


def delta(arm_value: float, base_value: float, higher_is_better: bool) -> float:
    return (arm_value - base_value) if higher_is_better else (base_value - arm_value)


def shuffle_weights(w: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Row-shuffle the weight VECTOR. Preserves the exact multiset of values
    (capacity: aggregate reweighting strength unchanged); destroys which row gets
    which weight (the (compound, lap_in_stint, season) alignment that is the whole
    content of the IPW scheme)."""
    return w[rng.permutation(len(w))]


def safe_t_e_value(d: np.ndarray, g: float = E_VALUE_G) -> dict:
    """Construction B (paired safe-t), identical to scripts/arms_08e_thermal_family.py."""
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
    return {"n": n, "g": g, "d_bar": d_bar, "s_d": s_d, "t": t, "E": float(e),
            "direction_is_improvement": bool(d_bar > 0), "max_attainable_E": float(cap)}


def e_value_validity_check(n_draws: int = 100_000, seed: int = S.RANDOM_STATE) -> dict:
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


def instrument_check_rowdiff(after: dict, before: dict, target: str, log) -> dict:
    """Row-level diff of X_tr/X_ev/y_tr/y_ev/cens between the two snapshots, aligned on
    lap_id. Must be EXACTLY zero -- these columns share no upstream computation with
    the reverted CTEs, so even float-noise nonzero would mean the isolation leaked."""
    a, b = after[target], before[target]
    res = {}
    for side, ka, kb, lap_ids in (
        ("train", "X_tr", "X_tr", "lap_ids_tr"), ("eval", "X_ev", "X_ev", "lap_ids_ev")
    ):
        Xa, Xb = a[ka], b[kb]
        ids_a, ids_b = a[lap_ids], b[lap_ids]
        assert list(ids_a) == list(ids_b), f"{target}/{side}: lap_id order differs"
        assert list(Xa.columns) == list(Xb.columns), f"{target}/{side}: column set differs"
        diffs = {}
        for c in Xa.columns:
            if pd.api.types.is_numeric_dtype(Xa[c]):
                d = (Xa[c].to_numpy(dtype=np.float64) - Xb[c].to_numpy(dtype=np.float64))
                d = d[~np.isnan(d)]
                maxabs = float(np.max(np.abs(d))) if len(d) else 0.0
            else:
                maxabs = float((Xa[c].astype(str) != Xb[c].astype(str)).sum())
            if maxabs != 0.0:
                diffs[c] = maxabs
        res[f"{side}_X_max_abs_diff_by_col"] = diffs
        res[f"{side}_n_rows"] = int(len(Xa))
    ya, yb = np.asarray(a["y_tr"], dtype=np.float64), np.asarray(b["y_tr"], dtype=np.float64)
    res["y_tr_max_abs_diff"] = float(np.nanmax(np.abs(ya - yb))) if len(ya) else 0.0
    yea, yeb = np.asarray(a["y_ev"], dtype=np.float64), np.asarray(b["y_ev"], dtype=np.float64)
    res["y_ev_max_abs_diff"] = float(np.nanmax(np.abs(yea - yeb))) if len(yea) else 0.0
    if a["cens_tr"] is not None:
        res["cens_tr_n_diff"] = int((a["cens_tr"] != b["cens_tr"]).sum())
    if a["cens_ev"] is not None:
        res["cens_ev_n_diff"] = int((a["cens_ev"] != b["cens_ev"]).sum())
    res["clean"] = (not res["train_X_max_abs_diff_by_col"]
                    and not res["eval_X_max_abs_diff_by_col"]
                    and res["y_tr_max_abs_diff"] == 0.0
                    and res["y_ev_max_abs_diff"] == 0.0
                    and res.get("cens_tr_n_diff", 0) == 0
                    and res.get("cens_ev_n_diff", 0) == 0)
    log(f"  [{target}] instrument row-diff: clean={res['clean']} "
        f"(train X cols differing={len(res['train_X_max_abs_diff_by_col'])}, "
        f"eval X cols differing={len(res['eval_X_max_abs_diff_by_col'])}, "
        f"y_tr Δ={res['y_tr_max_abs_diff']:.3g}, y_ev Δ={res['y_ev_max_abs_diff']:.3g})")
    return res


def run_quantile_target(target: str, after: dict, before: dict, published: float, log) -> dict:
    spec = S.TARGET_BY_NAME[target]
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    hib = E._higher_is_better(spec)
    a = after[target]
    X_tr, y_tr, X_ev, y_ev = a["X_tr"], a["y_tr"], a["X_ev"], a["y_ev"]
    w_after = np.asarray(a["w_tr"], dtype=np.float32)
    w_before = np.asarray(before[target]["w_tr"], dtype=np.float32)
    w_uniform = np.ones_like(w_after)

    res: dict = {"target": target, "metric": E._headline_metric_name(spec),
                "higher_is_better": hib, "n_train": int(len(X_tr)), "n_eval": int(len(X_ev)),
                "seeds": list(SEEDS),
                "w_after_summary": {"mean": float(w_after.mean()), "sd": float(w_after.std()),
                                    "min": float(w_after.min()), "max": float(w_after.max())},
                "w_before_summary": {"mean": float(w_before.mean()), "sd": float(w_before.std()),
                                     "min": float(w_before.min()), "max": float(w_before.max())},
                "w_max_abs_diff": float(np.max(np.abs(w_after - w_before))),
                "w_n_changed": int((w_after != w_before).sum())}

    # Step 1: instrument check -- AFTER (= production) reproduces published v12.
    t0 = time.time()
    m_after = E._fit(spec, params, X_tr, y_tr, cens=None, w=w_after)
    h_after = score_model(spec, m_after, X_ev, y_ev, None)
    res["after_headline"] = h_after
    res["published_v12_headline"] = published
    res["instrument_check_6dp"] = bool(abs(h_after - published) < 5e-7)
    log(f"  [{target}] AFTER={h_after:.10f} published_v12={published:.10f} "
        f"instrument_check={res['instrument_check_6dp']} ({time.time()-t0:.0f}s)")
    if not res["instrument_check_6dp"]:
        res["aborted"] = "instrument check failed"
        log(f"  [{target}] ABORTED -- {res['aborted']}")
        return res

    # Step 2: the gate's own question -- AFTER vs BEFORE, both vs uniform A.
    t0 = time.time()
    m_before = E._fit(spec, params, X_tr, y_tr, cens=None, w=w_before)
    h_before = score_model(spec, m_before, X_ev, y_ev, None)
    m_a = E._fit(spec, params, X_tr, y_tr, cens=None, w=w_uniform)
    h_a = score_model(spec, m_a, X_ev, y_ev, None)
    res["before_headline"] = h_before
    res["uniform_A_headline"] = h_a
    d_after_before = delta(h_after, h_before, hib)
    d_after_a = delta(h_after, h_a, hib)
    d_before_a = delta(h_before, h_a, hib)
    log(f"  [{target}] BEFORE={h_before:.10f} uniform_A={h_a:.10f}  "
        f"AFTER-vs-BEFORE delta={d_after_before:+.8f}  AFTER-vs-A={d_after_a:+.8f}  "
        f"BEFORE-vs-A={d_before_a:+.8f} ({time.time()-t0:.0f}s)")

    # Step 3: each arm's own reseed floor; quote against the LARGER.
    t0 = time.time()
    floor_after = AT.refit_noise_floor(
        lambda s: fit_seeded(spec, params, X_tr, y_tr, None, w_after, s),
        lambda yt, m, X: score_model(spec, m, X, yt, None), X_ev, y_ev, SEEDS)
    floor_before = AT.refit_noise_floor(
        lambda s: fit_seeded(spec, params, X_tr, y_tr, None, w_before, s),
        lambda yt, m, X: score_model(spec, m, X, yt, None), X_ev, y_ev, SEEDS)
    F2 = max(floor_after["delta_noise_2sd"], floor_before["delta_noise_2sd"])
    res["refit_noise_after"] = floor_after
    res["refit_noise_before"] = floor_before
    res["floor_2sqrt2sd"] = F2
    res["floor_quoted_from"] = ("after" if floor_after["delta_noise_2sd"] >= floor_before["delta_noise_2sd"]
                                else "before")
    log(f"  [{target}] floor 2*sqrt(2)*sd = {F2:.8f} (from {res['floor_quoted_from']}; "
        f"after={floor_after['delta_noise_2sd']:.8f}, before={floor_before['delta_noise_2sd']:.8f}) "
        f"({time.time()-t0:.0f}s)")

    # Step 4: permutation null, translated -- shuffle the WEIGHT VECTOR across rows.
    t0 = time.time()
    rng_a = np.random.default_rng([S.RANDOM_STATE, 0])
    rng_b = np.random.default_rng([S.RANDOM_STATE, 1])
    w_after_shuf = shuffle_weights(w_after, rng_a)
    w_before_shuf = shuffle_weights(w_before, rng_b)
    h_after_shuf = score_model(spec, E._fit(spec, params, X_tr, y_tr, None, w_after_shuf), X_ev, y_ev, None)
    h_before_shuf = score_model(spec, E._fit(spec, params, X_tr, y_tr, None, w_before_shuf), X_ev, y_ev, None)
    cap_after = delta(h_after_shuf, h_a, hib)
    info_after = delta(h_after, h_after_shuf, hib)
    cap_before = delta(h_before_shuf, h_a, hib)
    info_before = delta(h_before, h_before_shuf, hib)
    log(f"  [{target}] AFTER: shuffled={h_after_shuf:.10f} capacity={cap_after:+.8f} "
        f"({cap_after/F2:+.2f}x) information={info_after:+.8f} ({info_after/F2:+.2f}x)")
    log(f"  [{target}] BEFORE: shuffled={h_before_shuf:.10f} capacity={cap_before:+.8f} "
        f"({cap_before/F2:+.2f}x) information={info_before:+.8f} ({info_before/F2:+.2f}x) "
        f"({time.time()-t0:.0f}s)")

    # Step 7: paired five-seed information contrast (real AFTER vs its own shuffle) -> e-value.
    t0 = time.time()
    reals, shufs = [], []
    for s in SEEDS:
        reals.append(score_model(
            spec, fit_seeded(spec, params, X_tr, y_tr, None, w_after, s), X_ev, y_ev, None))
        w_shuf_s = shuffle_weights(w_after, np.random.default_rng([int(s), 0]))
        shufs.append(score_model(
            spec, fit_seeded(spec, params, X_tr, y_tr, None, w_shuf_s, s), X_ev, y_ev, None))
    reals, shufs = np.asarray(reals), np.asarray(shufs)
    d_paired = np.asarray([delta(r, sh, hib) for r, sh in zip(reals, shufs)])
    ev = safe_t_e_value(d_paired)
    log(f"  [{target}] E(information, AFTER real-vs-shuffle) = {ev['E']:.4g} "
        f"(d_bar={ev['d_bar']:+.8f}) ({time.time()-t0:.0f}s)")

    # Negative control: shuffle vs shuffle.
    t0 = time.time()
    d_ctrl = []
    for s in SEEDS:
        wa = shuffle_weights(w_after, np.random.default_rng([int(s), 2]))
        wb = shuffle_weights(w_after, np.random.default_rng([int(s), 3]))
        va = score_model(spec, fit_seeded(spec, params, X_tr, y_tr, None, wa, s), X_ev, y_ev, None)
        vb = score_model(spec, fit_seeded(spec, params, X_tr, y_tr, None, wb, s), X_ev, y_ev, None)
        d_ctrl.append(delta(va, vb, hib))
    ctrl_ev = safe_t_e_value(np.asarray(d_ctrl))
    log(f"  [{target}] control(shuffle vs shuffle) E={ctrl_ev['E']:.4g} ({time.time()-t0:.0f}s)")

    res.update({
        "gate_question_after_vs_before": {
            "delta": d_after_before, "floor_ratio": (d_after_before / F2) if F2 else None,
            "clears_floor": bool(abs(d_after_before) > F2) if F2 else None,
            "direction": "AFTER improves on BEFORE" if d_after_before > 0 else "AFTER costs vs BEFORE",
        },
        "after_vs_uniform_A": {"delta": d_after_a, "floor_ratio": (d_after_a / F2) if F2 else None},
        "before_vs_uniform_A": {"delta": d_before_a, "floor_ratio": (d_before_a / F2) if F2 else None},
        "permutation_null_after": {
            "headline_shuffled": h_after_shuf, "capacity_delta": cap_after,
            "capacity_floor_ratio": (cap_after / F2) if F2 else None,
            "information_delta": info_after, "information_floor_ratio": (info_after / F2) if F2 else None,
        },
        "permutation_null_before": {
            "headline_shuffled": h_before_shuf, "capacity_delta": cap_before,
            "capacity_floor_ratio": (cap_before / F2) if F2 else None,
            "information_delta": info_before, "information_floor_ratio": (info_before / F2) if F2 else None,
        },
        "paired_seeds": {"real_by_seed": reals.tolist(), "shuffled_by_seed": shufs.tolist(),
                         "information_deltas": d_paired.tolist(), "e_value": ev},
        "negative_control_shuffle_vs_shuffle": {"paired_deltas": d_ctrl, "e_value": ctrl_ev},
    })
    return res


def run_structural_target(target: str, after: dict, before: dict, published: float, log) -> dict:
    """cliff_classifier / stint_life_regressor never consume survival_weight
    (train.py::_sample_weight ignores meta for these kinds). One fit reproduces
    published v12; the BEFORE-arm delta is reported as exactly 0 BY CONSTRUCTION,
    backed by two independent checks: the code trace above, and the row-level
    instrument check confirming X/y/cens are bit-identical between the AFTER and
    BEFORE snapshots for this target."""
    spec = S.TARGET_BY_NAME[target]
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    a = after[target]
    X_tr, y_tr, X_ev, y_ev = a["X_tr"], a["y_tr"], a["X_ev"], a["y_ev"]
    cens_tr, cens_ev = a["cens_tr"], a["cens_ev"]
    t0 = time.time()
    model = E._fit(spec, params, X_tr, y_tr, cens=cens_tr, w=None)
    headline = score_model(spec, model, X_ev, y_ev, cens_ev)
    ok = bool(abs(headline - published) < 5e-7)
    log(f"  [{target}] headline={headline:.10f} published_v12={published:.10f} "
        f"instrument_check={ok} ({time.time()-t0:.0f}s)")
    return {"target": target, "metric": E._headline_metric_name(spec),
            "headline": headline, "published_v12_headline": published,
            "instrument_check_6dp": ok,
            "survival_weight_reaches_this_target": False,
            "before_vs_after_delta": 0.0,
            "note": ("structurally invariant to 08f-1: train.py::_sample_weight ignores "
                     "meta['survival_weight'] for classification/survival kinds; not "
                     "re-fit under BEFORE weights because there is no code path for "
                     "them to differ -- confirmed by the row-level instrument check.")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["export-after", "export-before", "analyze"])
    ap.add_argument("--duckdb", default=None)
    ap.add_argument("--snapshot-dir", required=True)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    snap_dir = Path(args.snapshot_dir)

    if args.stage == "export-after":
        export_snapshot(args.duckdb, "after", snap_dir / "after.pkl")
        return 0
    if args.stage == "export-before":
        export_snapshot(args.duckdb, "before", snap_dir / "before.pkl")
        return 0

    # --- analyze ---
    lines: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    with open(snap_dir / "after.pkl", "rb") as fh:
        after = pickle.load(fh)["targets"]
    with open(snap_dir / "before.pkl", "rb") as fh:
        before = pickle.load(fh)["targets"]

    published = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())
    pub_version = published.get("version")

    out: dict = {
        "item": "08f-1", "purpose": "gate the survival-weight season-lag in isolation",
        "ran_at": pd.Timestamp.utcnow().isoformat(),
        "published_artefact_version": pub_version,
        "seeds": list(SEEDS),
        "e_value_construction": {"name": "B (paired safe-t)", "n": len(SEEDS), "g": E_VALUE_G,
                                 "null": "information contrast: real AFTER vs its own shuffle"},
        "e_value_validity_check": e_value_validity_check(),
        "instrument_row_diff": {}, "targets": {},
    }
    log(f"published artefact version {pub_version}")
    log("e-value validity check (mean E under H0 must be 1.00):")
    for k, v in out["e_value_validity_check"].items():
        log(f"  {k:<14} mean_E={v['mean_E']:.4f} +/- {2*v['mc_se']:.4f}  P(E>20)={v['p_E_gt_20']:.4f}")

    log("\n=== Step 1(b): instrument check -- row-level diff outside survival_weight ===")
    for target in ALL_TARGETS:
        out["instrument_row_diff"][target] = instrument_check_rowdiff(after, before, target, log)

    for target in QUANTILE_TARGETS:
        log(f"\n=== {target} ===")
        out["targets"][target] = run_quantile_target(
            target, after, before, published["models"][target]["headline"], log)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2, default=float))

    for target in STRUCTURAL_TARGETS:
        log(f"\n=== {target} (structurally invariant to 08f-1) ===")
        out["targets"][target] = run_structural_target(
            target, after, before, published["models"][target]["headline"], log)
        Path(args.out).write_text(json.dumps(out, indent=2, default=float))

    Path(args.out).with_suffix(".log").write_text("\n".join(lines) + "\n")
    log(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
