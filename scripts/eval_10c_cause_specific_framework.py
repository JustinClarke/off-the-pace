"""10c — competing-risks evaluation, with the dependent-censoring caveat quantified.

WHY THIS IS A RE-RUN. `10c`'s 2026-09-10 verdict is doubly superseded and `10b` §10 says
so in writing: its AUC 0.844 / Brier 0.141 headline was in-sample (`10d`'s gate-1 finding)
AND measured under the `10b` label, which `10b` has since rejected on the arm's own
declared metric. Two of the three things this item's method asks for were also never
delivered -- there was no per-cause comparison (under the `10b` label green-pit is the
only uncensored cause, so the other five strata had no events), and the dependence band
was stated but never quantified. This run delivers both on the v12 substrate `08m`/`08n`
rebuilt on 2026-09-16.

THE DESIGN -- three framings, one split, and the difference between them is the finding.

    F1  stratum        rows whose stint ended green_pit. Zero censoring, so IPCW does
                       nothing and the dependence band is zero BY CONSTRUCTION. Estimand:
                       the REALISED green-pit ending, conditional on it having been one.
                       This is what 10b/10d/10e scored and what D5 says the gauge means.
    F2  cause-specific the whole eval fold; endings of cause c are events and EVERY other
                       ending -- race_end and retirement included -- is censored at its
                       observed time. Estimand: the LATENT cause-c limit. The only framing
                       in which IPCW does any work, so the only one that can carry a band.
    F3  mixture        diagnostic, labelled as one. 10c already ruled this out as a
                       headline and the ruling stands.

F1 buys freedom from censoring by conditioning on the outcome; F2 buys an unconditioned
population at the price of 54% censoring that is not independent. Neither is free, and
quoting either without the other is what this item exists to stop.

THE BAND. Clayton copula between the latent cause time T and the censoring time C, via
the Rivest & Wells closed form for the Zheng-Klein copula-graphic estimator of the
censoring marginal. Kendall's tau in {-0.50, -0.25, 0, +0.25, +0.50}, declared in the leaf
doc before this existed. At tau = 0 the estimator IS Kaplan-Meier and the Brier IS
`survival.py::ipcw_brier` -- asserted here on the real eval rows, to machine precision,
before either is used.

Reads the warehouse read-only. Writes nothing to `ml/models/`, nothing to the warehouse,
nothing to `ml/artefacts/evaluation_metrics.json`. `evaluate.run()` is never called.

Usage:  PYTHONPATH=. python3 scripts/eval_10c_cause_specific_framework.py
        PYTHONPATH=. python3 scripts/eval_10c_cause_specific_framework.py --boot-draws 20
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, linregress

from ml.src import attribution as AT
from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S
from ml.src import survival as SV

TARGET = "stint_life_regressor"
VARIANT = "standard"          # D5's ruling, confirmed by 10b. Stated, not defaulted.

# ─── Pre-registered constants (leaf doc, 2026-09-18, before anything was scored) ─────
TAU_GRID: tuple[float, ...] = (-0.50, -0.25, 0.0, 0.25, 0.50)
SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(5))   # 20260528-32
BOOT_DRAWS = 200
BOOT_SEED = 20260910          # races the unit, as 10d and 10e both used
MIN_EVENTS_FOR_F2 = 100       # declared: a cause-specific framing needs >=100 events
D_CAL_BINS = 10

# 10b §4's A0 row, measured on THIS substrate on 2026-09-18 at the canonical seed.
# Unlike 10b, this item has a published figure whose rows still exist, so gate 1's
# literal six-decimal requirement is meetable rather than merely explained away.
ANCHOR_10B_A0 = {
    "green_pit_nll": 3.4376675618143007,
    "green_pit_ipcw_brier": 0.1903917717687864,
    "green_pit_auc": 0.6895774514309989,
    "calibration_slope": 0.6735936337052354,
    "calibration_intercept": 0.23187910000373496,
    "mean_log_bias": -0.27413700814322794,
    "margin_sd": 0.5818239268804684,
    "full_fold_nll": 1.9913358778933028,
}

OUT_DIR = Path("_improvements/eval/10c")
OUT = OUT_DIR / "eval_10c_cause_specific_framework.json"
LOG = OUT_DIR / "eval_10c_cause_specific_framework.log"


# ─── Fit, through evaluate.py's own paths ───────────────────────────────────────────
def fit_seeded(spec, params, X, y, cens, w, seed: int):
    """E._fit with the seed overridden and nothing else changed. Varying it is the
    point: `subsample` and `colsample_bytree` redraw, so the refits genuinely differ."""
    from ml.src import train as T
    model = T._make_model(spec, {**params, "seed": int(seed)})
    weights = np.asarray(w, dtype=np.float32) if w is not None else T._sample_weight(spec, y)
    model.fit(X, y, sample_weight=weights, is_censored=np.asarray(cens, dtype=bool))
    return model


# ─── The metric blocks ──────────────────────────────────────────────────────────────
def level_and_slope(y, pred, cens, scale, n_bins: int = 5) -> dict:
    """The four continuity figures, computed exactly as 10b/10d/10e computed them so the
    numbers stay comparable across the group: binned calibration slope and intercept from
    one linregress over five points, the 5-bin table, and the mean log-scale bias."""
    out: dict = {}
    cal = SV.d_calibration(y, pred, cens, scale, n_bins=n_bins)
    slope = cal.get("calibration_slope")
    out["calibration_slope"] = None if slope is None or np.isnan(slope) else float(slope)
    exp_r = np.asarray(cal["exp_event_rates"], dtype=np.float64)
    obs_r = np.asarray(cal["obs_event_rates"], dtype=np.float64)
    out["calibration_intercept"] = (float(linregress(exp_r, obs_r).intercept)
                                    if len(exp_r) > 2 else None)
    out["calibration_bins"] = {"predicted": exp_r.tolist(), "observed": obs_r.tolist()}
    sh = S.AFT_LABEL_SHIFT
    y = np.asarray(y, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    # 10d's sign convention: NEGATIVE = the model over-predicts remaining life.
    out["mean_log_bias"] = float(np.mean(np.log(y + sh)
                                         - np.log(np.maximum(pred + sh, 1e-12))))
    out["margin_sd"] = float(np.std(np.log(np.maximum(pred + sh, 1e-12)), ddof=1))
    return out


def framing_metrics(y, pred, cens, scale, tau: float = 0.0, with_level: bool = True,
                    times=None) -> dict:
    """Every metric for one framing at one assumed dependence.

    `ipcw_brier_dependent` at tau = 0 is `ipcw_brier` to machine precision (asserted in
    gate 1c on these very rows), so the fast path is used everywhere and the incumbent
    path only where a published figure is being reproduced.
    """
    y = np.asarray(y, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    cens = np.asarray(cens, dtype=bool)
    n_ev = int((~cens).sum())
    out: dict = {"n": int(len(y)), "n_events": n_ev, "n_censored": int(cens.sum()),
                 "censoring_rate": float(cens.mean()), "tau": float(tau)}
    if n_ev < 2:
        out["status"] = "no_events"
        return out

    brier, per_t = SV.ipcw_brier_dependent(y, pred, cens, scale, tau=tau, times=times)
    out["ipcw_brier"] = float(brier)
    out["ipcw_brier_per_horizon"] = [float(v) for v in per_t]
    auc_u, _ = SV.time_dependent_auc(y, pred, cens, scale, times=times)
    out["auc_unweighted"] = None if np.isnan(auc_u) else float(auc_u)
    auc_w, _ = SV.time_dependent_auc_ipcw(y, pred, cens, scale, tau=tau, times=times)
    out["auc_ipcw"] = None if np.isnan(auc_w) else float(auc_w)
    out["aft_nloglik"] = float(SV.aft_nloglik(y, pred, cens, scale))
    if with_level:
        out.update(level_and_slope(y, pred, cens, scale))
        dc = SV.d_calibration_chisq(y, pred, cens, scale, n_bins=D_CAL_BINS)
        out["d_calibration"] = {k: dc[k] for k in
                                ("statistic", "dof", "p_value", "bin_counts",
                                 "expected_per_bin", "mean_abs_deviation_ratio")}
    return out


def horizon_grid(y, cens) -> np.ndarray:
    """The grid both `ipcw_brier` and `time_dependent_auc` derive by default: deciles of
    the UNCENSORED observed times. Computed once and passed in so F1 and F2 are scored on
    the identical horizons -- they must be, because F2's green-pit events are exactly
    F1's rows, and a band measured on a different grid from its own centre is not a band.
    """
    y = np.asarray(y, dtype=np.float64)
    return np.percentile(y[~np.asarray(cens, dtype=bool)], np.linspace(10, 90, 9))


def band_of(values: dict[float, float | None]) -> dict:
    v = {k: x for k, x in values.items() if x is not None and np.isfinite(x)}
    if not v:
        return {"width": None}
    lo, hi = min(v.values()), max(v.values())
    return {"by_tau": {str(k): float(x) for k, x in v.items()},
            "centre_tau0": float(v.get(0.0)) if 0.0 in v else None,
            "low": float(lo), "high": float(hi), "width": float(hi - lo)}


# ─── Cause labels and race ids on the eval rows ─────────────────────────────────────
def cause_and_race(lap_ids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    con = duckdb.connect(S.DUCKDB_PATH, read_only=True)
    try:
        df = con.execute(
            f"""SELECT DISTINCT m.lap_id, sf.stint_end_cause, m.race_id
                FROM {S.MART} m
                JOIN {S.STINT_FEATURES} sf ON m.stint_id = sf.stint_id""").df()
    finally:
        con.close()
    cause = dict(zip(df["lap_id"], df["stint_end_cause"]))
    race = dict(zip(df["lap_id"], df["race_id"]))
    return (np.array([cause.get(l) for l in lap_ids], dtype=object),
            np.array([race.get(l) for l in lap_ids], dtype=object))


# ─── Main ───────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot-draws", type=int, default=BOOT_DRAWS)
    ap.add_argument("--skip-boot", action="store_true")
    ap.add_argument("--skip-reseed", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    t_start = time.time()

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        lines.append(msg)

    spec = S.TARGET_BY_NAME[TARGET]
    params = E._params_for(TARGET, S.MODEL_VERSION_DEFAULT)
    report: dict = {
        "item": "10c",
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "substrate": {"model_version": S.MODEL_VERSION_DEFAULT,
                      "n_feature_columns": len(S.FEATURE_COLUMNS),
                      "censoring_variant": VARIANT, "params": params},
        "pre_registered": {"tau_grid": list(TAU_GRID), "seeds": list(SEEDS),
                           "boot_draws": args.boot_draws, "boot_seed": BOOT_SEED,
                           "min_events_for_f2": MIN_EVENTS_FOR_F2,
                           "d_cal_bins": D_CAL_BINS,
                           "declared_hypotheses": [],
                           "e_value_family_contribution": 0},
    }

    log("=" * 80)
    log("10c -- competing-risks evaluation, with the dependence band quantified")
    log(f"substrate {S.MODEL_VERSION_DEFAULT}, {len(S.FEATURE_COLUMNS)} features, "
        f"label={VARIANT} (D5)")
    log("=" * 80)

    # ── gate 5 ─────────────────────────────────────────────────────────────────────
    log("\n[gate 5] label adjacency -- the cause label DEFINES the framings, so it must "
        "not be a feature")
    leak = [c for c in ("stint_end_cause", S.STINT_LIFE_CENSOR_COLUMN, "end_regime",
                        "end_cause_confidence") if c in set(S.FEATURE_COLUMNS)]
    report["gate_5"] = {"label_columns_in_feature_contract": leak, "pass": not leak}
    log(f"  leaking into FEATURE_COLUMNS: {leak or 'none'} -> "
        f"{'PASS' if not leak else 'FAIL'}")
    if leak:
        raise SystemExit("gate 5 failed")

    # ── setup ──────────────────────────────────────────────────────────────────────
    log(f"\n[setup] loading the {VARIANT} label construction")
    bundle = F.load_features(target=TARGET, censoring_variant=VARIANT)
    split = E._evaluation_split(bundle)
    y_ev, cens_ev = split.y_ev, split.cens_ev
    cause_ev, race_ev = cause_and_race(split.lap_ids_ev)
    log(f"  split {split.mode}: train n={len(split.y_tr)} eval n={len(y_ev)} "
        f"(season {split.eval_season}), eval censoring {cens_ev.mean():.4f}")

    counts = {str(k): int(v) for k, v in
              pd.Series(cause_ev.astype(str)).value_counts().items()}
    log(f"  eval cause counts: {counts}")

    # ── gate 1a ────────────────────────────────────────────────────────────────────
    log("\n[gate 1a] reproduce today's published v12 headline through E._fit/_score")
    pub = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())
    pub_headline = float(pub["models"][TARGET]["headline"])
    model = E._fit(spec, params, split.X_tr, split.y_tr, split.cens_tr, split.w_tr)
    scale = float(model.scale)
    pred = model.predict(split.X_ev)
    repro = E._score(spec, y_ev, E._predict_index(spec, model, split.X_ev), cens_ev, scale)
    ok_1a = repro == pub_headline
    report["gate_1a"] = {"published": pub_headline, "reproduced": repro,
                         "exact": bool(ok_1a),
                         "abs_diff": abs(repro - pub_headline),
                         "published_version": pub.get("version"),
                         "published_variant": pub.get("censoring_variant")}
    log(f"  published  : {pub_headline!r}")
    log(f"  reproduced : {repro!r}")
    log(f"  identical to every stored digit: {ok_1a}")

    # ── the three framings' masks ──────────────────────────────────────────────────
    gp = cause_ev == "green_pit"
    uncens_causes = sorted({str(c) for c in cause_ev[~cens_ev]})
    f2_causes = [c for c in uncens_causes
                 if int(((cause_ev == c) & ~cens_ev).sum()) >= MIN_EVENTS_FOR_F2]
    log(f"\n[setup] uncensored causes present: {uncens_causes}")
    log(f"  cause-specific framings with >= {MIN_EVENTS_FOR_F2} events: {f2_causes}")

    # ── gate 2 substitute ──────────────────────────────────────────────────────────
    log("\n[gate 2, substituted] one split, one set of eval rows, framings that partition it")
    part = {"n_eval": int(len(y_ev)),
            "sum_of_cause_counts": int(sum(counts.values())),
            "f1_rows": int(gp.sum()),
            "f1_censored": int(cens_ev[gp].sum()),
            "f2_green_pit_events": int((gp & ~cens_ev).sum()),
            "f1_equals_f2_event_set": bool(np.array_equal(np.flatnonzero(gp),
                                                          np.flatnonzero(gp & ~cens_ev))),
            "no_null_causes": bool(pd.isna(pd.Series(cause_ev)).sum() == 0)}
    part["pass"] = bool(part["sum_of_cause_counts"] == part["n_eval"]
                        and part["f1_equals_f2_event_set"] and part["no_null_causes"])
    report["gate_2_substitute"] = part
    log(f"  cause labels cover every eval row: {part['sum_of_cause_counts']} of "
        f"{part['n_eval']}; F1 rows == F2 green-pit events: "
        f"{part['f1_equals_f2_event_set']}; green-pit censoring {part['f1_censored']}")
    if not part["pass"]:
        raise SystemExit("gate 2 substitute failed: the framings do not share the rows")

    # One horizon grid for F1 and F2-green-pit, since the event rows are the same rows.
    grid = horizon_grid(y_ev[gp], cens_ev[gp])
    f2_gp_cens = ~(gp & ~cens_ev)
    grid_f2 = horizon_grid(y_ev, f2_gp_cens)
    same_grid = bool(np.allclose(grid, grid_f2, atol=1e-12, rtol=0))
    report["horizon_grid"] = {"grid": [float(v) for v in grid],
                              "f1_and_f2_share_the_grid": same_grid}
    log(f"  horizon grid (deciles of uncensored y): "
        f"{np.round(grid, 3).tolist()};  F1 and F2 share it: {same_grid}")

    # ── gate 1c: the new estimator against the incumbent, on these very rows ───────
    log("\n[gate 1c] the new estimator vs the incumbent, on the real eval rows")
    from lifelines import KaplanMeierFitter
    kmf = KaplanMeierFitter().fit(y_ev, event_observed=f2_gp_cens)
    tt, ss = SV.copula_graphic_survival(y_ev, f2_gp_cens, tau=0.0)
    probe = np.unique(y_ev)
    max_km_gap = float(np.max(np.abs(SV.step_eval(tt, ss, probe)
                                     - np.asarray(kmf.survival_function_.asof(probe)).ravel())))
    b_inc, _ = SV.ipcw_brier(y_ev, pred, f2_gp_cens, scale, times=grid)
    b_new, _ = SV.ipcw_brier_dependent(y_ev, pred, f2_gp_cens, scale, tau=0.0, times=grid)
    report["gate_1c"] = {
        "max_abs_gap_copula_graphic_tau0_vs_kaplan_meier": max_km_gap,
        "ipcw_brier_incumbent": float(b_inc),
        "ipcw_brier_new_at_tau0": float(b_new),
        "abs_gap": float(abs(b_inc - b_new)),
        "pass": bool(max_km_gap < 1e-12 and abs(b_inc - b_new) < 1e-12)}
    log(f"  copula-graphic(tau=0) vs Kaplan-Meier, max |gap| over {len(probe)} times: "
        f"{max_km_gap:.3e}")
    log(f"  ipcw_brier incumbent {b_inc!r}  vs new(tau=0) {b_new!r}  "
        f"|gap| {abs(b_inc - b_new):.3e}")
    if not report["gate_1c"]["pass"]:
        raise SystemExit("gate 1c failed: the band's centre is not the incumbent estimate")

    # ── F1: the stratum ────────────────────────────────────────────────────────────
    log("\n[F1] the green-pit stratum -- zero censoring, therefore zero band, at the "
        "price of conditioning on the outcome")
    f1 = framing_metrics(y_ev[gp], pred[gp], cens_ev[gp], scale, tau=0.0, times=grid)
    f1["estimand"] = ("the REALISED green-pit ending, conditional on the ending having "
                      "been green-pit. What D5 says the gauge means.")
    report["F1_stratum_green_pit"] = f1
    log(f"  n={f1['n']} ({f1['n_censored']} censored)  Brier {f1['ipcw_brier']:.4f}  "
        f"AUC(unw) {f1['auc_unweighted']:.4f}  AUC(ipcw) {f1['auc_ipcw']:.4f}  "
        f"slope {f1['calibration_slope']:.4f}  NLL {f1['aft_nloglik']:.4f}")
    log(f"  D-calibration chi2 {f1['d_calibration']['statistic']:.1f} "
        f"(dof {f1['d_calibration']['dof']}, p {f1['d_calibration']['p_value']:.3g}), "
        f"mean |dev|/expected {f1['d_calibration']['mean_abs_deviation_ratio']:.3f}")

    # ── gate 1b: reproduce 10b §4's A0 row ─────────────────────────────────────────
    log("\n[gate 1b] reproduce 10b §4's A0 green-pit row (same substrate, 2026-09-18)")
    b_anchor, _ = SV.ipcw_brier(y_ev[gp], pred[gp], cens_ev[gp], scale)
    got = {"green_pit_nll": f1["aft_nloglik"], "green_pit_ipcw_brier": float(b_anchor),
           "green_pit_auc": f1["auc_unweighted"],
           "calibration_slope": f1["calibration_slope"],
           "calibration_intercept": f1["calibration_intercept"],
           "mean_log_bias": f1["mean_log_bias"], "margin_sd": f1["margin_sd"],
           "full_fold_nll": repro}
    rows, all_ok = [], True
    for k, want in ANCHOR_10B_A0.items():
        have = got[k]
        six = round(have, 6) == round(want, 6)
        exact = have == want
        all_ok &= six
        rows.append({"metric": k, "published_by_10b": want, "reproduced": have,
                     "matches_to_six_decimals": bool(six), "identical": bool(exact)})
        log(f"  {k:<24} 10b {want!r}")
        log(f"  {'':<24} now {have!r}  six-dp {six}  exact {exact}")
    report["gate_1b"] = {"anchor": "10b section 4, arm A0, canonical seed", "rows": rows,
                         "pass": bool(all_ok)}
    log(f"  gate 1 literal requirement (six decimal places): "
        f"{'PASS' if all_ok else 'FAIL'}")
    if not all_ok:
        raise SystemExit("gate 1b failed: the harness no longer reproduces 10b's A0 row")

    # ── F2: cause-specific, across the declared tau grid ──────────────────────────
    log("\n[F2] cause-specific framings across the declared dependence grid")
    f2: dict = {}
    for c in f2_causes:
        ev_c = (cause_ev == c) & ~cens_ev
        cens_c = ~ev_c
        g_c = horizon_grid(y_ev, cens_c)
        per_tau = {}
        for tau in TAU_GRID:
            per_tau[tau] = framing_metrics(y_ev, pred, cens_c, scale, tau=tau,
                                           with_level=(tau == 0.0), times=g_c)
        f2[c] = {
            "n_events": int(ev_c.sum()),
            "censoring_rate": float(cens_c.mean()),
            "horizon_grid": [float(v) for v in g_c],
            "by_tau": {str(t): per_tau[t] for t in TAU_GRID},
            "band_ipcw_brier": band_of({t: per_tau[t].get("ipcw_brier") for t in TAU_GRID}),
            "band_auc_ipcw": band_of({t: per_tau[t].get("auc_ipcw") for t in TAU_GRID}),
            "auc_unweighted_invariant": per_tau[0.0].get("auc_unweighted"),
        }
        bb, ba = f2[c]["band_ipcw_brier"], f2[c]["band_auc_ipcw"]
        log(f"  {c:<10} events {f2[c]['n_events']:>5}  censoring "
            f"{f2[c]['censoring_rate']:.3f}")
        log(f"  {'':<10} Brier    {bb['centre_tau0']:.4f}  band "
            f"[{bb['low']:.4f}, {bb['high']:.4f}]  width {bb['width']:.4f}")
        log(f"  {'':<10} AUC ipcw {ba['centre_tau0']:.4f}  band "
            f"[{ba['low']:.4f}, {ba['high']:.4f}]  width {ba['width']:.4f}")
    report["F2_cause_specific"] = f2

    # ── the framing gap: the same model, the same predictions, two estimands ──────
    gpb = f2["green_pit"]
    gap = {
        "f1_ipcw_brier": f1["ipcw_brier"],
        "f2_ipcw_brier_tau0": gpb["band_ipcw_brier"]["centre_tau0"],
        "gap_brier": float(f1["ipcw_brier"] - gpb["band_ipcw_brier"]["centre_tau0"]),
        "f2_brier_band": [gpb["band_ipcw_brier"]["low"], gpb["band_ipcw_brier"]["high"]],
        "gap_brier_band": [float(f1["ipcw_brier"] - gpb["band_ipcw_brier"]["high"]),
                           float(f1["ipcw_brier"] - gpb["band_ipcw_brier"]["low"])],
        "f1_auc_ipcw": f1["auc_ipcw"], "f2_auc_ipcw_tau0": gpb["band_auc_ipcw"]["centre_tau0"],
        "f1_ipcw_equals_unweighted": bool(
            f1["auc_ipcw"] is not None and f1["auc_unweighted"] is not None
            and abs(f1["auc_ipcw"] - f1["auc_unweighted"]) < 1e-12),
        "note": ("The SAME model and the SAME per-row predictions, scored against two "
                 "estimands: F1's realised green-pit ending on the green-pit-selected "
                 "population, and F2's latent green-pit limit on the whole fold. Neither "
                 "is wrong and they are NOT ranked here -- the gap is the size of the "
                 "framing choice, which is the quantity this item exists to make visible. "
                 "F1's IPCW AUC being identical to its unweighted AUC is the structural "
                 "check that F1 carries no censoring: every weight is exactly 1."),
    }
    report["framing_gap"] = gap
    log(f"\n[framing gap] F1 Brier {gap['f1_ipcw_brier']:.4f} vs F2(tau=0) "
        f"{gap['f2_ipcw_brier_tau0']:.4f}  gap {gap['gap_brier']:+.4f}  "
        f"(across the band: {gap['gap_brier_band'][0]:+.4f} to "
        f"{gap['gap_brier_band'][1]:+.4f})")
    log(f"  F1 IPCW AUC == unweighted AUC (no censoring in the stratum): "
        f"{gap['f1_ipcw_equals_unweighted']}")

    # ── F3: the mixture, diagnostic only ──────────────────────────────────────────
    f3 = framing_metrics(y_ev, pred, cens_ev, scale, tau=0.0, times=horizon_grid(y_ev, cens_ev))
    f3["interpretation"] = ("DIAGNOSTIC ONLY. Scores events against an at-risk pool that "
                            "is majority a different cause, and the causes differ in "
                            "length by construction, so part of the discrimination is "
                            "cause membership. 10c ruled this out as a headline on "
                            "2026-09-10 and the ruling stands.")
    report["F3_mixture"] = f3
    log(f"\n[F3] mixture (DIAGNOSTIC ONLY): Brier {f3['ipcw_brier']:.4f}  "
        f"AUC(unw) {f3['auc_unweighted']:.4f}  NLL {f3['aft_nloglik']:.4f}")

    # ── the dependence anchor ─────────────────────────────────────────────────────
    log("\n[anchor] observable association between predicted tyre state and censoring "
        "arrival")
    anchors = {}
    for name, mask in (("all_censoring", f2_gp_cens),
                       ("sc_or_vsc_only", np.isin(cause_ev.astype(str),
                                                  ["sc_pit", "vsc_pit"])),
                       ("administrative_only", np.isin(cause_ev.astype(str),
                                                       ["race_end", "retirement"]))):
        if mask.sum() < 50:
            continue
        kt = kendalltau(pred[mask], y_ev[mask])
        anchors[name] = {"n": int(mask.sum()), "kendall_tau": float(kt.statistic),
                         "p_value": float(kt.pvalue)}
        log(f"  {name:<20} n={mask.sum():>6}  Kendall tau {kt.statistic:+.4f} "
            f"(p {kt.pvalue:.3g})")
    anchors["note"] = (
        "Kendall's tau between the model's predicted median life -- a function of X alone "
        "-- and the observed time at which the green-pit clock was stopped. Under "
        "independent censoring it is 0. It is an OBSERVABLE association and NOT the "
        "latent T-C dependence the copula parameterises, which is not identifiable from "
        "this data at all. Declared before the run as a diagnostic for which part of the "
        "grid is plausible; it does not select the band and the band is reported across "
        "the full declared grid whatever it says.")
    report["dependence_anchor"] = anchors

    # ── gate 3: the reseed floors ─────────────────────────────────────────────────
    floors: dict = {}
    if not args.skip_reseed:
        log(f"\n[gate 3] reseed floors, seeds {SEEDS[0]}-{SEEDS[-1]}, XGBoost's seed varied")
        by_seed: dict[str, list] = {}
        band_by_seed: list[float] = []
        auc_band_by_seed: list[float] = []
        for sd in SEEDS:
            m = fit_seeded(spec, params, split.X_tr, split.y_tr, split.cens_tr,
                           split.w_tr, sd)
            p_s, sc_s = m.predict(split.X_ev), float(m.scale)
            g1 = framing_metrics(y_ev[gp], p_s[gp], cens_ev[gp], sc_s, 0.0, times=grid)
            for k in ("ipcw_brier", "auc_unweighted", "auc_ipcw", "calibration_slope",
                      "aft_nloglik"):
                by_seed.setdefault(f"F1_{k}", []).append(g1[k])
            by_seed.setdefault("F1_d_cal_mad", []).append(
                g1["d_calibration"]["mean_abs_deviation_ratio"])
            per_tau_b, per_tau_a = {}, {}
            for tau in TAU_GRID:
                g2 = framing_metrics(y_ev, p_s, f2_gp_cens, sc_s, tau=tau,
                                     with_level=False, times=grid)
                per_tau_b[tau], per_tau_a[tau] = g2["ipcw_brier"], g2["auc_ipcw"]
            for k, v in (("F2gp_ipcw_brier", per_tau_b[0.0]),
                         ("F2gp_auc_ipcw", per_tau_a[0.0])):
                by_seed.setdefault(k, []).append(v)
            band_by_seed.append(max(per_tau_b.values()) - min(per_tau_b.values()))
            auc_band_by_seed.append(max(per_tau_a.values()) - min(per_tau_a.values()))
            log(f"  seed {sd}: F1 Brier {g1['ipcw_brier']:.6f}  slope "
                f"{g1['calibration_slope']:.6f}  F2gp Brier {per_tau_b[0.0]:.6f}  "
                f"band {band_by_seed[-1]:.6f}")
        for k, vals in by_seed.items():
            a = np.asarray([v for v in vals if v is not None], dtype=np.float64)
            sd_ = float(a.std(ddof=1))
            floors[k] = {"values": a.tolist(), "mean": float(a.mean()), "sd": sd_,
                         "delta_noise_2sd": float(2.0 * np.sqrt(2.0) * sd_)}
        floors["_band_width_across_seeds"] = {
            "F2gp_ipcw_brier": band_by_seed, "F2gp_auc_ipcw": auc_band_by_seed,
            "note": ("the dependence band is recomputed at every seed; if the band's "
                     "own width moved with the seed it would be refit noise wearing a "
                     "band's clothes.")}
        # Cross-check the arithmetic against the helper rather than trusting it twice.
        nf = AT.refit_noise_floor(
            lambda s: fit_seeded(spec, params, split.X_tr, split.y_tr, split.cens_tr,
                                 split.w_tr, s),
            lambda yy, mm, XX: SV.ipcw_brier_dependent(
                yy[gp], mm.predict(XX)[gp], cens_ev[gp], mm.scale, 0.0, grid)[0],
            split.X_ev, y_ev, SEEDS)
        floors["F1_ipcw_brier"]["attribution_py_cross_check"] = {
            "delta_noise_2sd": nf["delta_noise_2sd"],
            "agrees": bool(abs(nf["delta_noise_2sd"]
                               - floors["F1_ipcw_brier"]["delta_noise_2sd"]) < 1e-12)}
        report["gate_3_floors"] = floors
        log("\n[gate 3] floors (2*sqrt(2)*sd)")
        for k in sorted(k for k in floors if not k.startswith("_")):
            log(f"  {k:<26} sd {floors[k]['sd']:.6f}  floor "
                f"{floors[k]['delta_noise_2sd']:.6f}")

    # ── the bootstrap ─────────────────────────────────────────────────────────────
    boot: dict = {}
    if not args.skip_boot:
        log(f"\n[boot] race-level cluster bootstrap, {args.boot_draws} draws, seed "
            f"{BOOT_SEED}, races the unit (UNPAIRED: one model, so the interval is on "
            f"the level)")
        races = np.array([str(r) for r in race_ev], dtype=object)
        uniq = np.array(sorted(set(races.tolist())), dtype=object)
        rows_by_race = {r: np.flatnonzero(races == r) for r in uniq}
        rng = np.random.default_rng(BOOT_SEED)
        draws: dict[str, list[float]] = {}
        t0 = time.time()
        for i in range(args.boot_draws):
            pick = rng.choice(len(uniq), size=len(uniq), replace=True)
            idx = np.concatenate([rows_by_race[uniq[j]] for j in pick])
            g_b = idx[gp[idx]]
            if len(g_b) < 200:
                continue
            m1 = framing_metrics(y_ev[g_b], pred[g_b], cens_ev[g_b], scale, 0.0,
                                 times=grid)
            for k in ("ipcw_brier", "auc_unweighted", "auc_ipcw", "calibration_slope"):
                if m1.get(k) is not None:
                    draws.setdefault(f"F1_{k}", []).append(float(m1[k]))
            cb = f2_gp_cens[idx]
            for tau in TAU_GRID:
                m2 = framing_metrics(y_ev[idx], pred[idx], cb, scale, tau=tau,
                                     with_level=False, times=grid)
                if m2.get("ipcw_brier") is not None:
                    draws.setdefault(f"F2gp_ipcw_brier_tau{tau}", []).append(
                        float(m2["ipcw_brier"]))
                if m2.get("auc_ipcw") is not None:
                    draws.setdefault(f"F2gp_auc_ipcw_tau{tau}", []).append(
                        float(m2["auc_ipcw"]))
            if (i + 1) % 50 == 0:
                log(f"  {i+1}/{args.boot_draws} draws ({time.time()-t0:.0f}s)")
        for k, v in draws.items():
            a = np.asarray(v, dtype=np.float64)
            boot[k] = {"n_draws": int(len(a)), "mean": float(a.mean()),
                       "ci95_low": float(np.percentile(a, 2.5)),
                       "ci95_high": float(np.percentile(a, 97.5)),
                       "ci95_width": float(np.percentile(a, 97.5)
                                           - np.percentile(a, 2.5))}
        report["bootstrap_race_cluster"] = {
            "draws": args.boot_draws, "seed": BOOT_SEED, "n_races": int(len(uniq)),
            "unit": "race_id", "paired": False, "levels": boot,
            "note": ("the instrument 10d section 4 ruled authoritative. Unpaired here: "
                     "there is one model and no arm, so this is sampling noise on the "
                     "LEVEL, not on a delta. The standing 24-race limit applies to the "
                     "slope and is restated rather than rediscovered.")}
        log("\n[boot] 95% intervals on the level")
        for k in sorted(boot):
            b = boot[k]
            log(f"  {k:<32} {b['mean']:.4f}  [{b['ci95_low']:.4f}, "
                f"{b['ci95_high']:.4f}]  width {b['ci95_width']:.4f}")

    # ── the three widths, and the declared decision rule ──────────────────────────
    log("\n" + "=" * 80)
    log("THE THREE WIDTHS -- refit noise, identification, sampling noise")
    log("=" * 80)
    widths = []
    for label, band_key, floor_key, boot_key in (
            ("F2 green_pit IPCW-Brier", ("F2_cause_specific", "green_pit",
                                         "band_ipcw_brier"), "F2gp_ipcw_brier",
             "F2gp_ipcw_brier_tau0.0"),
            ("F2 green_pit Uno AUC", ("F2_cause_specific", "green_pit",
                                      "band_auc_ipcw"), "F2gp_auc_ipcw",
             "F2gp_auc_ipcw_tau0.0"),
            ("F1 stratum IPCW-Brier", None, "F1_ipcw_brier", "F1_ipcw_brier"),
            ("F1 stratum Uno AUC", None, "F1_auc_ipcw", "F1_auc_ipcw"),
            ("F1 stratum calib slope", None, "F1_calibration_slope",
             "F1_calibration_slope")):
        band_w = 0.0
        centre = None
        if band_key:
            node = report[band_key[0]][band_key[1]][band_key[2]]
            band_w, centre = node["width"], node["centre_tau0"]
        else:
            centre = report["F1_stratum_green_pit"].get(
                {"F1_ipcw_brier": "ipcw_brier", "F1_auc_ipcw": "auc_ipcw",
                 "F1_calibration_slope": "calibration_slope"}[floor_key])
        fl = floors.get(floor_key, {}).get("delta_noise_2sd")
        bw = boot.get(boot_key, {}).get("ci95_width")
        row = {"metric": label, "point_at_tau0": centre, "dependence_band_width": band_w,
               "reseed_floor": fl, "bootstrap_ci95_width": bw,
               "band_over_floor": (None if not fl else band_w / fl),
               "band_over_bootstrap": (None if not bw else band_w / bw),
               "report_as_a_band": bool(fl is not None and band_w > fl)}
        widths.append(row)
        log(f"  {label:<26} point {centre if centre is None else round(centre, 4)}  "
            f"band {band_w:.4f}  floor {fl if fl is None else round(fl, 4)}  "
            f"boot95 {bw if bw is None else round(bw, 4)}")
        log(f"  {'':<26} band/floor "
            f"{'n/a' if row['band_over_floor'] is None else round(row['band_over_floor'], 2)}"
            f"   band/boot "
            f"{'n/a' if row['band_over_bootstrap'] is None else round(row['band_over_bootstrap'], 2)}"
            f"   -> report as a band: {row['report_as_a_band']}")
    report["three_widths"] = widths
    report["decision_rule"] = (
        "Declared before the numbers existed: a metric is reported AS A BAND whenever "
        "the dependence band exceeds the reseed floor. A band inside the floor still has "
        "its caveat stated and is priced as immaterial AT THIS SAMPLE SIZE, never "
        "silently dropped. No cause-specific number is quoted as a point in any case.")

    report["runtime_s"] = round(time.time() - t_start, 1)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    LOG.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}\nwrote {LOG}")
    LOG.write_text("\n".join(lines) + f"\n\nwrote {OUT}\nwrote {LOG}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
