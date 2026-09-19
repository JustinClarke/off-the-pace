"""10e -- re-tune stint_life_regressor under the honest split: S1, S2, X1 on v12.

WHY THIS IS A RE-RUN. `10e` was measured on 2026-09-10 and returned S1x, a parameter set
that beat the incumbent on slope, Brier, AUC and level bias at once. `D4` was resolved on
2026-09-11 in favour of shipping it. The landing never executed, `08m`/`08n` then rebuilt
the warehouse and shipped v12 on 2026-09-16, and the `cv_final_fold` eval fold is 19,973
laps / 9,149 green-pit today against the 20,272 / 9,270 every figure in that verdict was
measured on. So no 2026-09-10 figure can be reproduced, S1x has never been scored on this
substrate, and D4's ruling rests on a measurement that has to be taken again before
anything ships on it.

THE ARMS, as pre-registered in the leaf doc's 2026-09-19 addendum, written before any
trial ran.

    A0   the incumbent -- v12 shipped params, `standard` labels, refit honestly
    S1   fresh 50-trial TPE search, selected on green-pit IPCW-Brier
    S2   fresh 50-trial TPE search, selected on green-pit |calibration slope - 1|
    X1   the 2026-09-10 S1x parameter set, unchanged, re-scored on v12

S1 and S2 are searched by `ml.src.tune` itself -- `--honest-split --censoring-variant
standard --objective ... --no-refit` -- with the folds confined to 2018-2023, so nothing
below was selected on a 2024 row. This script reads the two parameter files that search
wrote and scores them; it does not do its own selection.

METHOD (gates.md).

    gate 5   the cause label must not be inside FEATURE_COLUMNS
    gate 2*  substituted: one split, one label construction, one 32-column matrix for
             every arm -- nothing is added, so the literal add-ablation has no content
    gate 1a  E._fit/_score reproduces today's published v12 headline
    gate 1b  the 8 figures of 10b section 4's A0 row, to every stored digit
    gate 1c  substrate drift against what the 2026-09-10 verdict scored
    gate 1d  the optimism gap -- 10d's original gate-1 finding, re-measured
    gate 6   the searches ran on the training side only; their pins are probed, not read
    gate 3   5-reseed floors, XGBoost's `seed` genuinely varied, each arm its own
    gate 4   inapplicable -- no arm adds a column; the reseed null is the substitute
    gate 7   Construction B as declared, Construction A beside it, e-BH over the family
    boot     paired race-level cluster bootstrap, 200 draws, races the unit

The instrument is 10d's, imported rather than re-implemented, so the two items' numbers
are produced by the same code. Reads the warehouse read-only. Writes nothing to
`ml/models/`, nothing to the warehouse, nothing to `ml/artefacts/evaluation_metrics.json`.

Usage:  PYTHONPATH=. python3 scripts/arms_10e_honest_retune.py \
            --s1-params <scratch>/S1_best_params.json \
            --s2-params <scratch>/S2_best_params.json \
            --studies-dir <scratch>/studies
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S
from ml.src import train as T
from ml.src import tune as TU

import scripts.arms_10d_calibration_arms as A10D

TARGET = "stint_life_regressor"

# ─── Pre-registered constants (leaf doc, addendum of 2026-09-19) ────────────────────
SEEDS = A10D.SEEDS                     # 20260528-32, XGBoost's own seed varied
BOOT_DRAWS = 200
BOOT_SEED = A10D.BOOT_SEED             # 20260910, races the unit
E_VALUE_C = A10D.E_VALUE_C             # Construction A: s = c*sqrt(2)*sd
E_VALUE_G = A10D.E_VALUE_G             # Construction B: safe-t at a one-sd effect
SEARCH_FOLDS = 4                       # what the searches used; the inner CV matches it
DECLARED_ARMS = ("S1", "S2", "X1")     # A0 is the baseline, not a member

# The 2026-09-10 winner, verbatim from the leaf doc's own JSON block. Declared as an arm
# of THIS run (addendum point 3) rather than carried as a previous result.
X1_PARAMS = {
    "aft_loss_distribution_scale": 0.7537929016487691,
    "colsample_bytree": 0.7022777269179408,
    "gamma": 0.00526088099298953,
    "learning_rate": 0.021917329940077092,
    "max_depth": 8,
    "min_child_weight": 3,
    "n_estimators": 100,
    "reg_alpha": 2.6396744208969904,
    "reg_lambda": 0.016254068532870026,
    "subsample": 0.6740434973007393,
}

# What the 2026-09-10 verdict scored, for the drift table. NOT a reproduction target --
# the point of the table is that it cannot be one.
PUBLISHED_0910 = {
    "n_eval_laps": 20272, "n_green_pit": 9270, "n_eval_races": 24,
    "A0_slope": 0.7000, "A0_auc": 0.6935, "A0_brier": 0.1903,
    "S1x_slope": 0.9034, "S1x_auc": 0.7154, "S1x_brier": 0.1674,
    "S1x_mean_log_bias": 0.0681, "S1x_intercept": 0.0068,
    "S1x_boot_slope_ci": [0.643, 1.190],
    "S1x_paired_brier_delta": 0.0237, "S1x_paired_brier_ci": [0.0067, 0.0368],
    "S1x_paired_slope_delta": 0.1731, "S1x_paired_slope_p": 0.930,
    "A0_slope_sd": 0.011786, "A0_slope_floor": 0.033337,
    "A0_brier_sd": 0.000731, "A0_brier_floor": 0.002066,
}

OUT_DIR = Path("_improvements/eval/10e")
OUT = OUT_DIR / "arms_10e_honest_retune.json"
LOG = OUT_DIR / "arms_10e_honest_retune.log"

METRICS = ("green_pit_nll", "green_pit_ipcw_brier", "green_pit_auc",
           "calibration_slope", "mean_log_bias", "calibration_intercept", "margin_sd")


def inner_cv(split, gp_tr: np.ndarray, params: dict, n_splits: int = SEARCH_FOLDS) -> dict:
    """Both declared objectives on the training side only, at the search's own fold count.

    The search minimises the MEAN over folds of its green-pit metric, so that is what is
    reported first; the pooled out-of-fold row set is reported beside it because it is
    the convention `10d` used and the two answer slightly different questions. Nothing
    here has ever seen a 2024 row.
    """
    spec = S.TARGET_BY_NAME[TARGET]
    scale = float(params.get("aft_loss_distribution_scale", S.AFT_SCALE_DEFAULT))
    seasons = np.asarray(split.seasons_tr)
    train_seasons = sorted({int(x) for x in seasons.tolist()})
    folds = list(T._season_folds(seasons, train_seasons, n_splits=n_splits))
    per_fold, oof_idx, oof_pred, xgb_nll = [], [], [], []
    for tr, ev in folds:
        w = None if split.w_tr is None else split.w_tr[tr]
        m = T._make_model(spec, dict(params))
        weights = (np.asarray(w, dtype=np.float32) if w is not None
                   else T._sample_weight(spec, split.y_tr[tr]))
        m.fit(split.X_tr.iloc[tr], split.y_tr[tr], sample_weight=weights,
              is_censored=split.cens_tr[tr])
        Xv = split.X_tr.iloc[ev]
        pred = A10D.median_laps(m.predict_margin(Xv), scale, "normal")
        xgb_nll.append(A10D.xgb_aft_nloglik(m, Xv, split.y_tr[ev], split.cens_tr[ev]))
        g = gp_tr[ev]
        if g.sum() > 50:
            per_fold.append(A10D.green_pit_metrics(split.y_tr[ev][g], pred[g],
                                                   split.cens_tr[ev][g], scale))
        oof_idx.append(ev)
        oof_pred.append(pred)
    idx = np.concatenate(oof_idx)
    pred = np.concatenate(oof_pred)
    g = gp_tr[idx]
    pooled = A10D.green_pit_metrics(split.y_tr[idx][g], pred[g], split.cens_tr[idx][g], scale)
    fold_brier = [m["green_pit_ipcw_brier"] for m in per_fold]
    fold_abs_slope = [A10D.abs_slope_minus_one(m) for m in per_fold]
    return {
        "n_folds": len(folds), "train_seasons": train_seasons,
        "fold_mean_green_pit_brier": float(np.mean(fold_brier)),
        "fold_mean_abs_slope_minus_1": float(np.mean(fold_abs_slope)),
        "fold_brier": [float(v) for v in fold_brier],
        "fold_abs_slope_minus_1": [float(v) for v in fold_abs_slope],
        "fold_slope": [m.get("calibration_slope") for m in per_fold],
        "pooled_oof": pooled,
        "pooled_abs_slope_minus_1": A10D.abs_slope_minus_one(pooled),
        "xgb_aft_nloglik_mean": float(np.mean(xgb_nll)),
    }


def study_summary(studies_dir: Path, version: str) -> dict:
    """What the search did, read out of its own study DB rather than its stdout."""
    try:
        import optuna
        name = S.optuna_study_name(TARGET, version)
        db = Path(studies_dir) / f"{name}.db"
        if not db.exists():
            return {"study_db": str(db), "found": False}
        st = optuna.load_study(study_name=name, storage=f"sqlite:///{db}")
        states = pd.Series([t.state.name for t in st.trials]).value_counts().to_dict()
        return {"study_db": str(db), "found": True, "study_name": name,
                "n_trials": len(st.trials), "trial_states": {k: int(v) for k, v in states.items()},
                "best_value": float(st.best_value), "best_params": dict(st.best_params),
                "best_trial_number": int(st.best_trial.number),
                "best_trial_user_attrs": {k: (float(v) if isinstance(v, (int, float)) else v)
                                          for k, v in st.best_trial.user_attrs.items()}}
    except Exception as exc:                                    # pragma: no cover
        return {"found": False, "error": repr(exc)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--s1-params", required=True)
    ap.add_argument("--s2-params", required=True)
    ap.add_argument("--studies-dir", default=None)
    ap.add_argument("--boot-draws", type=int, default=BOOT_DRAWS)
    ap.add_argument("--skip-boot", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    t_start = time.time()

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        lines.append(msg)

    spec = S.TARGET_BY_NAME[TARGET]
    base_params = E._params_for(TARGET, S.MODEL_VERSION_DEFAULT)
    s1_params = json.loads(Path(args.s1_params).read_text())
    s2_params = json.loads(Path(args.s2_params).read_text())

    report: dict = {
        "item": "10e", "generated_at": pd.Timestamp.utcnow().isoformat(),
        "substrate": {"model_version": S.MODEL_VERSION_DEFAULT,
                      "n_feature_columns": len(S.FEATURE_COLUMNS),
                      "incumbent_params": base_params,
                      "params_source": f"ml/models/{TARGET}_best_params.json"},
        "seeds": list(SEEDS), "declared_arms": list(DECLARED_ARMS),
        "search_space": {**TU.SEARCH_SPACE, **TU.SURVIVAL_SPACE},
    }

    log("=" * 78)
    log("10e -- re-tune stint_life_regressor under the honest split, re-run on v12")
    log(f"substrate {S.MODEL_VERSION_DEFAULT}, {len(S.FEATURE_COLUMNS)} feature columns")
    log("=" * 78)

    # ── gate 5 ──────────────────────────────────────────────────────────────────────
    log("\n[gate 5] label-adjacency: the cause label must not be a feature")
    leak = [c for c in ("stint_end_cause", S.STINT_LIFE_CENSOR_COLUMN,
                        "end_regime", "end_cause_confidence")
            if c in set(S.FEATURE_COLUMNS)]
    report["gate_5"] = {"label_columns_in_feature_contract": leak, "pass": not leak}
    log(f"  columns leaking into FEATURE_COLUMNS: {leak or 'none'}  "
        f"-> {'PASS' if not leak else 'FAIL'}")
    if leak:
        raise SystemExit("gate 5 failed: the cause label is inside the feature contract")

    # ── setup ───────────────────────────────────────────────────────────────────────
    log("\n[setup] loading the `standard` label construction (D5's ruling)")
    bundle = F.load_features(target=TARGET, censoring_variant="standard")
    sp = E._evaluation_split(bundle)
    log(f"  n_tr={len(sp.y_tr)} n_ev={len(sp.y_ev)} cens_tr={sp.cens_tr.mean():.4f} "
        f"cens_ev={sp.cens_ev.mean():.4f} mode={sp.mode} eval_season={sp.eval_season}")

    cause_ev, race_ev = A10D.cause_and_race(sp.lap_ids_ev)
    cause_tr, _ = A10D.cause_and_race(sp.lap_ids_tr)
    gp, gp_tr = cause_ev == "green_pit", cause_tr == "green_pit"
    n_races = len({r for r in race_ev.tolist()})
    report["green_pit_stratum"] = {
        "n_eval_laps": int(len(sp.y_ev)), "n_green_pit": int(gp.sum()),
        "n_eval_races": int(n_races),
        "n_green_pit_races": int(len({r for r in race_ev[gp].tolist()})),
        "censored_within_stratum": float(sp.cens_ev[gp].mean()),
        "n_green_pit_train": int(gp_tr.sum()),
        "eval_cause_counts": {str(k): int(v) for k, v in
                              pd.Series(cause_ev.astype(str)).value_counts().items()},
    }
    log(f"[setup] green-pit stratum: {gp.sum()} eval laps over {n_races} races, "
        f"censoring {sp.cens_ev[gp].mean():.4f}; {gp_tr.sum()} train-side laps")

    # ── gate 2 substitute ───────────────────────────────────────────────────────────
    arms = {
        "A0": {"params": dict(base_params), "what": "incumbent v12 params, honest refit"},
        "S1": {"params": dict(s1_params), "what": "search selected on green-pit IPCW-Brier"},
        "S2": {"params": dict(s2_params), "what": "search selected on |slope - 1|"},
        "X1": {"params": dict(X1_PARAMS), "what": "the 2026-09-10 S1x set, re-scored on v12"},
    }
    report["gate_2_substitute"] = {
        "applicable_literally": False,
        "why": ("the add-ablation adds columns. No arm here adds one: all four are the "
                "same 32-column matrix under the same `standard` label, fitted with "
                "different hyperparameters."),
        "substituted_requirement": "one split and one label construction for every arm",
        "split_mode": sp.mode, "eval_season": int(sp.eval_season),
        "train_seasons": sorted({int(x) for x in sp.seasons_tr.tolist()}),
        "n_eval_rows_shared": int(len(sp.y_ev)),
        "censoring_variant": "standard",
        "arms": {k: v["what"] for k, v in arms.items()},
        "pass": True,
    }
    log("\n[gate 2*] substituted: one split, one label, one matrix; only the "
        "hyperparameters differ")

    # ── gate 1a / 1b ────────────────────────────────────────────────────────────────
    log("\n[gate 1a] reproduce today's published v12 headline through E._fit/_score")
    pub = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())
    pub_headline = float(pub["models"][TARGET]["headline"])
    m_a0 = E._fit(spec, base_params, sp.X_tr, sp.y_tr, sp.cens_tr, sp.w_tr)
    repro = E._score(spec, sp.y_ev, E._predict_index(spec, m_a0, sp.X_ev),
                     sp.cens_ev, m_a0.scale)
    ok_a = repro == pub_headline
    report["gate_1a"] = {"published_headline": pub_headline,
                         "published_version": pub.get("version"),
                         "published_censoring_variant": pub.get("censoring_variant"),
                         "reproduced_headline": repro, "exact": bool(ok_a)}
    log(f"  published  ({pub.get('version')}, {pub.get('censoring_variant')}): {pub_headline!r}")
    log(f"  reproduced (E._fit/_score, A0/standard):        {repro!r}")
    log(f"  exact: {ok_a}  -> {'PASS' if ok_a else 'FAIL'}")
    if not ok_a:
        raise SystemExit("gate 1a failed: the harness does not reproduce the v12 headline")

    log("\n[gate 1b] reproduce 10b section 4's A0 row -- all 8 figures, every digit")
    a0_pred = m_a0.predict(sp.X_ev)
    a0 = A10D.green_pit_metrics(sp.y_ev[gp], a0_pred[gp], sp.cens_ev[gp], m_a0.scale)
    anchor = {k: {"published": v, "reproduced": a0[k], "exact": bool(a0[k] == v)}
              for k, v in A10D.ANCHOR_10B_A0.items()}
    anchor_ok = all(v["exact"] for v in anchor.values())
    report["gate_1b"] = {"anchors": anchor, "all_exact": anchor_ok}
    for k, v in anchor.items():
        log(f"  {k:24s} {v['reproduced']!r}  {'EXACT' if v['exact'] else 'DIFFERS'}")
    log(f"  -> {'PASS' if anchor_ok else 'FAIL'}")
    if not anchor_ok:
        raise SystemExit("gate 1b failed: 10b section 4's A0 row does not reproduce")

    # ── gate 1c ─────────────────────────────────────────────────────────────────────
    report["gate_1c_substrate_drift"] = {
        "published_2026_09_10": PUBLISHED_0910,
        "today_n_eval_laps": int(len(sp.y_ev)), "today_n_green_pit": int(gp.sum()),
        "today_n_eval_races": int(n_races),
        "reproduction_of_the_2026_09_10_figures_possible": False,
        "why": ("08m rebuilt the warehouse and 08n shipped v12 on 2026-09-16, after the "
                "2026-09-10 run. The eval rows are not the same rows, so no figure that "
                "run published can be reproduced; gate 1 is anchored on today's published "
                "v12 headline and on 10b section 4's A0 row instead."),
    }
    log("\n[gate 1c] substrate drift since the 2026-09-10 run")
    log(f"  eval laps  {PUBLISHED_0910['n_eval_laps']} -> {len(sp.y_ev)}")
    log(f"  green-pit  {PUBLISHED_0910['n_green_pit']} -> {int(gp.sum())}")
    log(f"  eval races {PUBLISHED_0910['n_eval_races']} -> {n_races}")

    # ── gate 1d ─────────────────────────────────────────────────────────────────────
    log("\n[gate 1d] the optimism gap -- 10d's original gate-1 finding, re-measured")
    cens_all = bundle.meta_train[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
    m_in = E._fit(spec, base_params, bundle.X_train, bundle.y_train.to_numpy(), cens_all, None)
    a0_in = A10D.green_pit_metrics(sp.y_ev[gp], m_in.predict(sp.X_ev)[gp],
                                   sp.cens_ev[gp], m_in.scale)
    optimism = {k: {"honest": a0[k], "in_sample": a0_in[k],
                    "optimism": float(a0_in[k] - a0[k])}
                for k in ("green_pit_nll", "green_pit_ipcw_brier", "green_pit_auc",
                          "calibration_slope", "mean_log_bias")}
    report["gate_1d_optimism"] = {
        "honest_n_fit_rows": int(len(sp.y_tr)),
        "in_sample_n_fit_rows": int(len(bundle.X_train)), "metrics": optimism}
    for k, v in optimism.items():
        log(f"  {k:22s} honest {v['honest']:+.6f}  in-sample {v['in_sample']:+.6f}  "
            f"optimism {v['optimism']:+.6f}")

    # ── gate 6: what the searches did, and where they stopped ───────────────────────
    log("\n[gate 6] the two searches: selected params, boundary check, inner-fold values")
    searches = {}
    for arm, version, objective, path in (
            ("S1", "10e_v12_S1", "green_pit_brier", args.s1_params),
            ("S2", "10e_v12_S2", "green_pit_calibration", args.s2_params)):
        sel = arms[arm]["params"]
        pinned = TU.boundary_params(sel, spec)
        summ = study_summary(Path(args.studies_dir), version) if args.studies_dir else {}
        searches[arm] = {"objective": objective, "params_file": path,
                         "selected_params": sel, "boundary_pinned": pinned,
                         "study": summ}
        log(f"  {arm} ({objective}) -> depth {sel.get('max_depth')}, "
            f"{sel.get('n_estimators')} trees, lr {sel.get('learning_rate'):.4f}, "
            f"scale {sel.get('aft_loss_distribution_scale'):.4f}")
        log(f"     boundary: {pinned or 'interior on every axis'}; "
            f"best inner value {summ.get('best_value')}")
    report["gate_6_searches"] = {
        "declared": ("selection on the training side only (2018-2023), 50 TPE trials, "
                     f"{SEARCH_FOLDS} expanding season folds, MedianPruner, seeded "
                     f"{S.RANDOM_STATE}; neither objective is the mixture AFT NLL"),
        "searches": searches,
        "x1_note": ("X1 is not searched: it is the 2026-09-10 parameter set, declared as "
                    "an arm of this run so that D4's candidate is scored on fresh rows."),
    }

    log("\n[gate 6] inner-fold values for every arm, on the training side only")
    inner: dict[str, dict] = {}
    for arm, cfg in arms.items():
        t0 = time.time()
        inner[arm] = inner_cv(sp, gp_tr, cfg["params"])
        log(f"  {arm:3s} fold-mean Brier {inner[arm]['fold_mean_green_pit_brier']:.4f}  "
            f"fold-mean |slope-1| {inner[arm]['fold_mean_abs_slope_minus_1']:.4f}  "
            f"pooled slope {inner[arm]['pooled_oof']['calibration_slope']:.4f}  "
            f"xgb-NLL {inner[arm]['xgb_aft_nloglik_mean']:.4f}  ({time.time()-t0:.0f}s)")
    report["inner_cv"] = inner

    # ── gate 3 ──────────────────────────────────────────────────────────────────────
    log("\n[gate 3] every arm on the 2024 eval fold, 5 seeds, XGBoost's seed varied")
    by_seed: dict[str, dict[str, list]] = {}
    canonical: dict[str, dict] = {}
    canonical_pred: dict[str, tuple[np.ndarray, float]] = {}
    for arm, cfg in arms.items():
        scale = float(cfg["params"].get("aft_loss_distribution_scale", S.AFT_SCALE_DEFAULT))
        by_seed[arm] = {m: [] for m in METRICS}
        for i, seed in enumerate(SEEDS):
            t0 = time.time()
            m = A10D.fit_seeded(spec, cfg["params"], sp.X_tr, sp.y_tr, sp.cens_tr,
                                sp.w_tr, seed)
            pred = A10D.median_laps(m.predict_margin(sp.X_ev), scale, "normal")
            gpm = A10D.green_pit_metrics(sp.y_ev[gp], pred[gp], sp.cens_ev[gp], scale)
            for k in METRICS:
                by_seed[arm][k].append(gpm[k])
            if i == 0:
                canonical[arm], canonical_pred[arm] = gpm, (pred, scale)
            log(f"  {arm:3s} seed {seed}: slope {gpm['calibration_slope']:.6f}  "
                f"AUC {gpm['green_pit_auc']:.6f}  "
                f"Brier {gpm['green_pit_ipcw_brier']:.6f}  "
                f"mlb {gpm['mean_log_bias']:+.6f}  ({time.time()-t0:.0f}s)")

    assert canonical["A0"]["calibration_slope"] == a0["calibration_slope"], \
        "the canonical A0 refit drifted from the gate-1b anchor"

    floors: dict[str, dict] = {}
    for arm in arms:
        floors[arm] = {}
        for k in METRICS:
            a = np.asarray([v for v in by_seed[arm][k] if v is not None], dtype=np.float64)
            sd = float(a.std(ddof=1))
            floors[arm][k] = {"by_seed": a.tolist(), "mean": float(a.mean()), "sd": sd,
                              "delta_noise_2sd": float(2.0 * np.sqrt(2.0) * sd)}
    report["gate_3_reseed_floors"] = floors
    log("\n[gate 3] floors (2*sqrt(2)*sd), each arm its own")
    for arm in arms:
        log(f"  {arm:3s} slope sd {floors[arm]['calibration_slope']['sd']:.6f} "
            f"floor {floors[arm]['calibration_slope']['delta_noise_2sd']:.6f}   "
            f"Brier sd {floors[arm]['green_pit_ipcw_brier']['sd']:.6f} "
            f"floor {floors[arm]['green_pit_ipcw_brier']['delta_noise_2sd']:.6f}   "
            f"AUC floor {floors[arm]['green_pit_auc']['delta_noise_2sd']:.6f}")

    # ── paired reseed deltas, both declared orientations ────────────────────────────
    paired: dict[str, dict] = {}
    for arm in DECLARED_ARMS:
        a0s = np.asarray(by_seed["A0"]["calibration_slope"], dtype=np.float64)
        ars = np.asarray(by_seed[arm]["calibration_slope"], dtype=np.float64)
        d_slope = np.abs(a0s - 1.0) - np.abs(ars - 1.0)
        d_brier = (np.asarray(by_seed["A0"]["green_pit_ipcw_brier"], dtype=np.float64)
                   - np.asarray(by_seed[arm]["green_pit_ipcw_brier"], dtype=np.float64))
        d_auc = (np.asarray(by_seed[arm]["green_pit_auc"], dtype=np.float64)
                 - np.asarray(by_seed["A0"]["green_pit_auc"], dtype=np.float64))
        d_bias = (np.abs(np.asarray(by_seed["A0"]["mean_log_bias"], dtype=np.float64))
                  - np.abs(np.asarray(by_seed[arm]["mean_log_bias"], dtype=np.float64)))
        f = floors[arm]
        paired[arm] = {
            "slope_deltas_by_seed": d_slope.tolist(), "slope_delta": float(d_slope.mean()),
            "brier_deltas_by_seed": d_brier.tolist(), "brier_delta": float(d_brier.mean()),
            "auc_deltas_by_seed": d_auc.tolist(), "auc_delta": float(d_auc.mean()),
            "abs_mean_log_bias_delta": float(d_bias.mean()),
            "slope_x_own_floor": float(d_slope.mean() / f["calibration_slope"]["delta_noise_2sd"]),
            "brier_x_own_floor": float(d_brier.mean() / f["green_pit_ipcw_brier"]["delta_noise_2sd"]),
            "auc_x_own_floor": float(d_auc.mean() / f["green_pit_auc"]["delta_noise_2sd"]),
        }
    report["gate_3_paired_reseed_deltas"] = paired
    log("\n[gate 3] paired reseed deltas vs A0 (positive = the arm improves), x its own floor")
    for arm in DECLARED_ARMS:
        p = paired[arm]
        log(f"  {arm:3s} |slope-1| {p['slope_delta']:+.4f} ({p['slope_x_own_floor']:+.2f}x)  "
            f"Brier {p['brier_delta']:+.4f} ({p['brier_x_own_floor']:+.2f}x)  "
            f"AUC {p['auc_delta']:+.4f} ({p['auc_x_own_floor']:+.2f}x)")

    # ── gate 4 ──────────────────────────────────────────────────────────────────────
    report["gate_4"] = {
        "applicable": False,
        "why": ("the permutation null row-shuffles NEW columns and no arm adds one. And "
                "the decomposition it would feed is not available here either: max_depth, "
                "n_estimators and learning_rate ARE capacity, and capacity is the whole "
                "content of a hyperparameter arm, so there is no information-versus-"
                "capacity split to make. The e-value's null below is therefore stated as "
                "what it is -- no difference beyond refit noise."),
        "substitute": "the 5-seed reseed null; its floors are gate_3_reseed_floors",
    }

    # ── gate 7 ──────────────────────────────────────────────────────────────────────
    log("\n[gate 7] Construction B as declared, Construction A beside it")
    validity = A10D.construction_b_validity()
    report["gate_7_construction_b_validity"] = validity
    log(f"  B validity: worked example t={validity['reference_worked_example']['t']:.2f} "
        f"E={validity['reference_worked_example']['E']:.2f} (published 17.0)")
    for k, v in validity.items():
        if k.startswith("sigma="):
            log(f"  B null mean E at {k}: {v['mean_E']:.4f} (+/- {v['mc_se']:.4f})")

    sd_slope = floors["A0"]["calibration_slope"]["sd"]
    sd_brier = floors["A0"]["green_pit_ipcw_brier"]["sd"]
    e_a, e_b = {}, {}
    for arm in DECLARED_ARMS:
        e_a[arm] = {"slope": A10D.construction_a(paired[arm]["slope_delta"], sd_slope),
                    "brier": A10D.construction_a(paired[arm]["brier_delta"], sd_brier)}
        e_b[arm] = {"slope": A10D.construction_b(np.asarray(paired[arm]["slope_deltas_by_seed"])),
                    "brier": A10D.construction_b(np.asarray(paired[arm]["brier_deltas_by_seed"]))}
    report["gate_7_construction_a"] = {
        "declared": "E = exp(0.8889*(z-1)), z = delta/(sqrt(2)*sd), c=1.5, lambda=4/3",
        "sd_source": "A0's 5-seed reseed sd of the metric in question",
        "sd_slope": sd_slope, "sd_brier": sd_brier, "arms": e_a,
        "caveat": ("the declared scale is REFIT noise; the estimand's uncertainty is "
                   "SAMPLING noise, which the paired race-cluster bootstrap puts far "
                   "larger. Reported because it was declared; read through the bootstrap.")}
    report["gate_7_construction_b"] = {
        "g": E_VALUE_G, "n": len(SEEDS), "arms": e_b,
        "ceiling": float((1.0 + len(SEEDS) * E_VALUE_G) ** ((len(SEEDS) - 1) / 2.0))}
    for arm in DECLARED_ARMS:
        log(f"  {arm:3s} slope: A E {e_a[arm]['slope']['E']:.4g}  B t "
            f"{e_b[arm]['slope']['t']:+.2f} E {e_b[arm]['slope']['E']:.4g}   |   "
            f"Brier: A E {e_a[arm]['brier']['E']:.4g}  B t "
            f"{e_b[arm]['brier']['t']:+.2f} E {e_b[arm]['brier']['E']:.4g}")

    for tag, table, key in (("A/slope", e_a, "slope"), ("A/Brier", e_a, "brier"),
                            ("B/slope", e_b, "slope"), ("B/Brier", e_b, "brier")):
        res = A10D.ebh({a: table[a][key]["E"] for a in DECLARED_ARMS})
        report[f"gate_7_ebh_{tag.replace('/', '_').lower()}"] = res
        log(f"  e-BH ({tag}) at alpha=0.05 over {res['n_declared_arms']} arms: "
            f"k*={res['k_star']}, rejects {res['rejected']} "
            f"(lone-rejection threshold {res['threshold_for_a_lone_rejection']:.0f})")
    report["gate_7_ceiling_note"] = (
        "Construction B's ceiling at n=5, g=1 is 36, and e-BH over a family of three "
        "needs E >= 60 for a lone rejection. A single-arm rejection is therefore "
        "arithmetically unreachable and was declared unreachable before the run; only a "
        "joint two-arm (E >= 30 each) or three-arm (E >= 20 each) rejection can fire. "
        "This is 09c's finding and g was not moved after the fact to dodge it.")

    # ── the paired race-level cluster bootstrap ─────────────────────────────────────
    if not args.skip_boot:
        log(f"\n[boot] paired race-cluster bootstrap, {args.boot_draws} draws, "
            f"seed {BOOT_SEED}, races the unit")
        gp_idx = np.flatnonzero(gp)
        races = np.array([str(r) for r in race_ev[gp]], dtype=object)
        uniq = np.array(sorted(set(races.tolist())), dtype=object)
        rows_by_race = {r: gp_idx[races == r] for r in uniq}
        rng = np.random.default_rng(BOOT_SEED)
        marg = {a: {"calibration_slope": [], "green_pit_auc": [],
                    "green_pit_ipcw_brier": [], "mean_log_bias": []} for a in arms}
        pair = {a: {"slope": [], "auc": [], "brier": [], "abs_mean_log_bias": []}
                for a in DECLARED_ARMS}
        t0 = time.time()
        for i in range(args.boot_draws):
            pick = rng.choice(len(uniq), size=len(uniq), replace=True)
            idx = np.concatenate([rows_by_race[uniq[j]] for j in pick])
            y_b, c_b = sp.y_ev[idx], sp.cens_ev[idx]
            mm = {}
            for a in arms:
                pr, sc_ = canonical_pred[a]
                mm[a] = A10D.green_pit_metrics(y_b, pr[idx], c_b, sc_)
                for k in marg[a]:
                    if mm[a][k] is not None:
                        marg[a][k].append(float(mm[a][k]))
            for a in DECLARED_ARMS:
                if mm[a]["calibration_slope"] is not None and mm["A0"]["calibration_slope"] is not None:
                    pair[a]["slope"].append(abs(mm["A0"]["calibration_slope"] - 1.0)
                                            - abs(mm[a]["calibration_slope"] - 1.0))
                if mm[a]["green_pit_auc"] is not None and mm["A0"]["green_pit_auc"] is not None:
                    pair[a]["auc"].append(mm[a]["green_pit_auc"] - mm["A0"]["green_pit_auc"])
                pair[a]["brier"].append(mm["A0"]["green_pit_ipcw_brier"]
                                        - mm[a]["green_pit_ipcw_brier"])
                pair[a]["abs_mean_log_bias"].append(abs(mm["A0"]["mean_log_bias"])
                                                    - abs(mm[a]["mean_log_bias"]))
            if (i + 1) % 50 == 0:
                log(f"  {i+1}/{args.boot_draws} draws ({time.time()-t0:.0f}s)")

        def summarise(a: list[float]) -> dict:
            x = np.asarray(a, dtype=np.float64)
            if len(x) == 0:
                return {"n_draws": 0}
            return {"n_draws": int(len(x)), "mean": float(x.mean()),
                    "ci95_low": float(np.percentile(x, 2.5)),
                    "ci95_high": float(np.percentile(x, 97.5)),
                    "p_improves": float((x > 0).mean()),
                    "p_below_one": float((x < 1.0).mean())}

        report["bootstrap_marginal"] = {a: {k: summarise(v) for k, v in marg[a].items()}
                                        for a in arms}
        report["bootstrap_paired"] = {a: {k: summarise(v) for k, v in pair[a].items()}
                                      for a in DECLARED_ARMS}
        report["bootstrap_meta"] = {
            "draws": args.boot_draws, "seed": BOOT_SEED, "n_races": int(len(uniq)),
            "unit": "race_id",
            "note": ("paired intervals score both arms on the SAME resampled races, so "
                     "the shared race-draw noise cancels. 10d section 4 ruled the paired "
                     "bootstrap authoritative where the floor, the e-value and the "
                     "bootstrap disagree, and this run does not re-litigate that.")}
        log("\n[boot] marginal intervals")
        for a in arms:
            m_ = report["bootstrap_marginal"][a]
            log(f"  {a:3s} slope {canonical[a]['calibration_slope']:.4f} "
                f"[{m_['calibration_slope']['ci95_low']:.4f}, "
                f"{m_['calibration_slope']['ci95_high']:.4f}]  "
                f"Brier {canonical[a]['green_pit_ipcw_brier']:.4f} "
                f"[{m_['green_pit_ipcw_brier']['ci95_low']:.4f}, "
                f"{m_['green_pit_ipcw_brier']['ci95_high']:.4f}]")
        log("\n[boot] paired deltas vs A0 (positive = the arm improves)")
        for a in DECLARED_ARMS:
            p_ = report["bootstrap_paired"][a]
            log(f"  {a:3s} Brier {p_['brier']['mean']:+.4f} "
                f"[{p_['brier']['ci95_low']:+.4f}, {p_['brier']['ci95_high']:+.4f}] "
                f"P {p_['brier']['p_improves']:.3f}   "
                f"slope {p_['slope']['mean']:+.4f} "
                f"[{p_['slope']['ci95_low']:+.4f}, {p_['slope']['ci95_high']:+.4f}] "
                f"P {p_['slope']['p_improves']:.3f}")

    report["canonical_arms"] = canonical

    # ── the verdict, against the declared three-leg criterion ───────────────────────
    verdict = {"declared_criterion": (
        "(1) green-pit IPCW-Brier improves vs A0; (2) the paired race-cluster bootstrap "
        "on that Brier delta returns P(improves) >= 0.95 AND a 95% interval excluding "
        "zero; (3) neither |slope-1| nor AUC worsens by more than that arm's own gate-3 "
        "reseed floor. The calibration-SLOPE improvement is reported with its own P and "
        "is deliberately NOT a leg -- 24 races could not resolve it in 10d or in this "
        "item's 2026-09-10 run, and that was written down before this one."),
        "arms": {}}
    for a in DECLARED_ARMS:
        p_ = report.get("bootstrap_paired", {}).get(a, {})
        b_p = p_.get("brier", {}).get("p_improves")
        b_lo = p_.get("brier", {}).get("ci95_low")
        slope_cost = -paired[a]["slope_delta"]
        auc_cost = -paired[a]["auc_delta"]
        legs = {
            "1_brier_improves": bool(paired[a]["brier_delta"] > 0),
            "2_bootstrap_p95_and_ci_excludes_zero":
                (None if b_p is None else bool(b_p >= 0.95 and b_lo is not None and b_lo > 0)),
            "3_no_slope_or_auc_regression_beyond_floor": bool(
                slope_cost <= floors[a]["calibration_slope"]["delta_noise_2sd"]
                and auc_cost <= floors[a]["green_pit_auc"]["delta_noise_2sd"]),
        }
        verdict["arms"][a] = {
            "brier": canonical[a]["green_pit_ipcw_brier"],
            "brier_delta": paired[a]["brier_delta"],
            "bootstrap_brier_p_improves": b_p, "bootstrap_brier_ci95_low": b_lo,
            "slope": canonical[a]["calibration_slope"],
            "slope_delta": paired[a]["slope_delta"],
            "bootstrap_slope_p_improves": p_.get("slope", {}).get("p_improves"),
            "auc": canonical[a]["green_pit_auc"], "auc_delta": paired[a]["auc_delta"],
            "mean_log_bias": canonical[a]["mean_log_bias"],
            "legs": legs,
            "passes": bool(legs["1_brier_improves"]
                           and legs["2_bootstrap_p95_and_ci_excludes_zero"] is True
                           and legs["3_no_slope_or_auc_regression_beyond_floor"])}
    verdict["any_arm_passes"] = any(v["passes"] for v in verdict["arms"].values())
    verdict["x1_passes_so_d4_landing_condition_is_met"] = bool(
        verdict["arms"].get("X1", {}).get("passes"))
    report["verdict"] = verdict

    log("\n" + "=" * 78)
    log("VERDICT against the pre-registered three-leg criterion")
    for a in DECLARED_ARMS:
        v = verdict["arms"][a]
        log(f"  {a:3s} Brier {v['brier']:.4f} (delta {v['brier_delta']:+.4f}, "
            f"P {v['bootstrap_brier_p_improves']})  slope {v['slope']:.4f}  "
            f"legs 1/2/3 = {v['legs']['1_brier_improves']}/"
            f"{v['legs']['2_bootstrap_p95_and_ci_excludes_zero']}/"
            f"{v['legs']['3_no_slope_or_auc_regression_beyond_floor']}  "
            f"passes {v['passes']}")
    log(f"  ANY ARM PASSES: {verdict['any_arm_passes']}")
    log(f"  D4's landing condition (X1 passes): "
        f"{verdict['x1_passes_so_d4_landing_condition_is_met']}")
    log("=" * 78)

    report["runtime_s"] = round(time.time() - t_start, 1)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    LOG.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}\nwrote {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
