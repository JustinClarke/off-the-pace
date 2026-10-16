"""Laps-to-flag cap and the calibrated chance to reach the flag (CO-08 draft).

Two things the stint-life gauge needs on top of the AFT fit, both defined here once
and mirrored in the browser by app/src/ml/flagChance.ts (held together by a parity
fixture, see `write_parity_fixture` and ml/tests/test_flag_chance.py):

1. **The cap.** The AFT median is the tyre's remaining life, which on a final stint
   can run past the chequered flag. A stint cannot outlast the race, so the realised
   ending is min(tyre life, laps to the flag), and the displayed median, p10 and p90
   are capped at laps to the flag. This is display only: the gate's censored
   likelihood already scores min(T, flag), so no score moves.

2. **The chance.** P(tyre life >= laps to the flag) from the same fitted
   distribution, passed through a monotone recalibration fitted on OUT-OF-FOLD
   predictions for the training seasons only. The raw chance is too cautious in the
   middle range (it says 40% where 68% of stints reach the flag), because the AFT
   treats a final stint as one that could still end in a tyre change.

Definitions, chosen so the browser can compute the same thing from its inputs:

* `laps_to_flag` = scheduled_laps - lap_number, floored at 0: laps still to run AFTER
  this one, the same convention as remaining_stint_life_laps. scheduled_laps is the
  seed `race_scheduled_laps`, known before the race, and the one the fuel model is
  built from (int_lap_fuel_state), so in the browser it is fuel_kg / burn_rate - 1
  exactly. Races stopped short of their scheduled distance make it slightly
  optimistic; `fit` reports how many rows that touches.
* The event `reached_flag` follows the gate's censoring: a stint whose end cause is
  'race_end' reached the flag (1); a stint that ended in a pit stop did not (0); a
  retirement, or a stint with no end cause, is CENSORED for this question (we do not
  know whether the tyres would have lasted) and is left out of fitting and scoring.
  The fit uses every lap with a known outcome, not only final-stint laps: restricted
  to final stints the outcome is "did not retire" (97% in 2025) and the rows are
  chosen with hindsight, which says nothing about the tyres.
* The chance is SHOWN only on a final stint: in the predictions parquet, rows on the
  driver's last stint of the race; in the simulator, a stint configured to run to the
  flag. It is null everywhere else.

CLI (writes only under --out; reads the warehouse and ml/models read-only):
  python -m ml.src.flag_chance fit --out DIR --model-version V --booster PATH
  python -m ml.src.flag_chance parity-fixture --lookup PATH --out FIXTURE.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import norm

from ml.src import holdout_config
from ml.src import schema as S

# Defaults follow the pinned holdout, never a literal year: evaluate on the last completed
# season before it (the gate's final CV fold), fit the recalibration on everything before that.
DEFAULT_EVAL_SEASON = holdout_config.HOLDOUT_SEASON - 1
DEFAULT_FIT_MAX_SEASON = DEFAULT_EVAL_SEASON - 1

LOOKUP_SCHEMA_VERSION = 1
EVENT_REACHED = ("race_end",)
EVENT_NOT_REACHED = ("green_pit", "sc_pit", "vsc_pit", "red")
PLATT_GRID_POINTS = 1001          # Platt is stored as a dense table: one browser code path
RELIABILITY_BINS = 10
MEMO_BINS = (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0)   # the options memo's bins, for before/after


# ─── The pieces the browser mirrors ─────────────────────────────────────────────
def laps_to_flag_from_fuel(fuel_kg, burn_rate_kg_per_lap):
    """Laps still to run after this one, from the fuel model: fuel / burn - 1, >= 0."""
    f = np.asarray(fuel_kg, dtype=np.float64) / np.asarray(burn_rate_kg_per_lap, dtype=np.float64)
    return np.maximum(f - 1.0, 0.0)


def cap_to_flag(laps, laps_to_flag):
    """min(laps, laps_to_flag): a stint cannot outlast the race. NaN laps_to_flag = no cap."""
    laps = np.asarray(laps, dtype=np.float64)
    ltf = np.asarray(laps_to_flag, dtype=np.float64)
    return np.where(np.isnan(ltf), laps, np.minimum(laps, ltf))


def raw_flag_chance(median_laps, laps_to_flag, scale: float,
                    label_shift: float = S.AFT_LABEL_SHIFT):
    """P(remaining tyre life >= laps_to_flag) under the fitted log-normal AFT.

    Uses the reported (clipped-at-0) median, as the browser does, so both sides start
    from the same number."""
    mu = np.log(np.asarray(median_laps, dtype=np.float64) + label_shift)
    t = np.log(np.asarray(laps_to_flag, dtype=np.float64) + label_shift)
    return norm.sf((t - mu) / scale)


def apply_lookup(raw, lookup: dict):
    """Piecewise-linear map through the lookup's breakpoints, clamped at both ends.
    np.interp is exactly what sklearn's IsotonicRegression(out_of_bounds='clip') does."""
    return np.interp(np.asarray(raw, dtype=np.float64),
                     np.asarray(lookup["x"], dtype=np.float64),
                     np.asarray(lookup["y"], dtype=np.float64))


# ─── Fitting the recalibration ──────────────────────────────────────────────────
def _fit_table(raw: np.ndarray, event: np.ndarray, method: str,
               weights: np.ndarray | None = None) -> tuple[list, list]:
    if method == "isotonic":
        from sklearn.isotonic import IsotonicRegression
        ir = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip")
        ir.fit(raw, event, sample_weight=weights)
        return [float(v) for v in ir.X_thresholds_], [float(v) for v in ir.y_thresholds_]
    if method == "platt":
        from sklearn.linear_model import LogisticRegression
        eps = 1e-6
        z = lambda p: np.log(np.clip(p, eps, 1 - eps) / (1 - np.clip(p, eps, 1 - eps)))
        lr = LogisticRegression(C=1e6).fit(z(raw).reshape(-1, 1), event, sample_weight=weights)
        grid = np.linspace(0.0, 1.0, PLATT_GRID_POINTS)
        return [float(v) for v in grid], [float(v) for v in lr.predict_proba(z(grid).reshape(-1, 1))[:, 1]]
    raise ValueError(f"unknown calibration method {method!r}")


def reliability(pred: np.ndarray, event: np.ndarray, edges) -> list[dict]:
    edges = np.asarray(edges, dtype=np.float64)
    idx = np.clip(np.searchsorted(edges, pred, side="right") - 1, 0, len(edges) - 2)
    rows = []
    for b in range(len(edges) - 1):
        m = idx == b
        if m.any():
            rows.append({"bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}", "n": int(m.sum()),
                         "mean_pred": float(pred[m].mean()), "observed": float(event[m].mean()),
                         "gap_pp": float(100 * (pred[m].mean() - event[m].mean()))})
    return rows


def ece(pred: np.ndarray, event: np.ndarray, n_bins: int = RELIABILITY_BINS) -> float:
    rows = reliability(pred, event, np.linspace(0, 1, n_bins + 1))
    return float(sum(r["n"] * abs(r["mean_pred"] - r["observed"]) for r in rows) / len(pred))


def brier(pred, event) -> float:
    return float(np.mean((np.asarray(pred) - np.asarray(event)) ** 2))


# ─── Drift: which training seasons the recalibration sees, and how much each counts ─
# The raw chance is calibrated to a different share each season (46% in 2020, 77% in
# 2025), so a single map over all seasons averages the drift away. Each rule is a way
# of letting recent seasons dominate. `select_weighting` picks one using ONLY seasons
# before the evaluation season, so the evaluation season is never used to choose.
WEIGHTING_RULES = ("uniform", "recent_geometric", "last3", "last2")


def rule_keep_and_weights(seasons: np.ndarray, rule: str) -> tuple[np.ndarray, np.ndarray]:
    """Keep-mask and per-row weights for `rule`, anchored on the newest season given."""
    s = np.asarray(seasons, dtype=np.int64)
    anchor = int(s.max())
    if rule == "uniform":
        return np.ones(len(s), dtype=bool), np.ones(len(s))
    if rule == "recent_geometric":          # doubles each season: 1, 2, 4, 8, 16 over five seasons
        return np.ones(len(s), dtype=bool), 2.0 ** (s - anchor)
    if rule == "last3":
        return s >= anchor - 2, np.ones(len(s))
    if rule == "last2":
        return s >= anchor - 1, np.ones(len(s))
    raise ValueError(f"unknown weighting rule {rule!r}")


def select_weighting(oof_raw: np.ndarray, event: np.ndarray, seasons: np.ndarray,
                     fit_rows: np.ndarray, holdout_season: int) -> tuple[str, dict]:
    """Fit each rule on the out-of-fold seasons BEFORE `holdout_season`, score on
    `holdout_season` alone, and keep the lowest Brier (ties go to the simpler rule)."""
    train = np.where(fit_rows & (seasons < holdout_season))[0]
    test = fit_rows & (seasons == holdout_season)
    if not test.any() or len(train) == 0:
        return "uniform", {"skipped": "no holdout season before the evaluation season"}
    scores = {}
    for rule in WEIGHTING_RULES:
        keep, w = rule_keep_and_weights(seasons[train], rule)
        k = train[keep]
        xs, ys = _fit_table(oof_raw[k], event[k], "platt", w[keep])
        pred = np.interp(oof_raw[test], xs, ys)
        scores[rule] = {"brier": brier(pred, event[test]), "ece_10bin": ece(pred, event[test]),
                        "seasons_fitted": sorted(int(v) for v in set(seasons[k]))}
    best = min(WEIGHTING_RULES, key=lambda r: (scores[r]["brier"], WEIGHTING_RULES.index(r)))
    return best, {"holdout_season": holdout_season, "rules": scores}


# ─── Warehouse context ──────────────────────────────────────────────────────────
def load_flag_context(lap_ids, duckdb_path: str = S.DUCKDB_PATH) -> pd.DataFrame:
    """laps_to_flag, final-stint flag and the event, aligned to `lap_ids` (read-only)."""
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        df = con.execute(f"""
            WITH rd AS (SELECT race_year, race_id, MAX(lap_number) AS race_last_lap
                        FROM int_stint_geometry GROUP BY 1, 2)
            SELECT m.lap_id, m.lap_number, r.scheduled_laps, rd.race_last_lap,
                   s.is_censored_stint, s.stint_end_cause
            FROM {S.MART} AS m
            JOIN {S.STINT_FEATURES} AS s USING (stint_id)
            LEFT JOIN race_scheduled_laps AS r ON r.race_year = m.race_year AND r.race_id = m.race_id
            LEFT JOIN rd ON rd.race_year = m.race_year AND rd.race_id = m.race_id
        """).df().set_index("lap_id")
    finally:
        con.close()
    df = df.reindex(np.asarray(lap_ids)).reset_index()
    df["laps_to_flag"] = np.maximum(df["scheduled_laps"] - df["lap_number"], 0).astype("float64")
    df["race_shortened"] = (df["race_last_lap"] < df["scheduled_laps"]).fillna(False)
    cause = df["stint_end_cause"]
    df["reached_flag"] = np.where(cause.isin(EVENT_REACHED), 1.0,
                                  np.where(cause.isin(EVENT_NOT_REACHED), 0.0, np.nan))
    df["is_final_stint"] = df["is_censored_stint"].fillna(False).astype(bool)
    return df


# ─── fit: OOF on the training seasons, evaluate on the eval season ──────────────
def fit(out_dir: Path, model_version: str, booster_path: Path | None, params_path: Path,
        fit_max_season: int = DEFAULT_FIT_MAX_SEASON, eval_season: int = DEFAULT_EVAL_SEASON,
        n_splits: int = 5, weighting: str = "auto") -> dict:
    from ml.src import features as F
    from ml.src import train as T

    spec = S.TARGET_BY_NAME["stint_life_regressor"]
    params = json.loads(Path(params_path).read_text())
    b = F.load_features(target="stint_life_regressor")
    X, y = b.X_train, b.y_train.to_numpy(dtype=np.float64)
    cens = b.meta_train[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
    seasons = b.groups_train.to_numpy()
    ctx = load_flag_context(b.meta_train["lap_id"].to_numpy())
    ltf, event, final = (ctx["laps_to_flag"].to_numpy(), ctx["reached_flag"].to_numpy(),
                         ctx["is_final_stint"].to_numpy())

    def fit_predict(tr, ev):
        m = T._make_model(spec, params)
        m.fit(X.iloc[tr], y[tr], is_censored=cens[tr])
        return m.predict(X.iloc[ev]), m.scale

    # Out-of-fold raw chance on the training seasons (2025 never enters any fit).
    pre = np.where(seasons <= fit_max_season)[0]
    pre_seasons = sorted(set(int(s) for s in seasons[pre]))
    oof_raw = np.full(len(y), np.nan)
    for tr, va in T._season_folds(seasons[pre], pre_seasons, n_splits):
        med, scale = fit_predict(pre[tr], pre[va])
        oof_raw[pre[va]] = raw_flag_chance(med, ltf[pre[va]], scale)
    fit_rows = ~np.isnan(oof_raw) & ~np.isnan(event)

    # Drift rule, chosen on the season before the evaluation season (see select_weighting).
    # Method is Platt: in the prior leave-one-season-out run Platt and isotonic tied
    # (mean Brier 0.09902 vs 0.09925), and Platt is smooth where isotonic steps.
    if weighting == "auto":
        rule, selection = select_weighting(oof_raw, event, seasons, fit_rows, fit_max_season)
    else:
        if weighting not in WEIGHTING_RULES:
            raise ValueError(f"weighting must be 'auto' or one of {WEIGHTING_RULES}")
        rule, selection = weighting, {"chosen_by": "argument"}
    method = "platt"
    fit_idx = np.where(fit_rows)[0]
    keep, w = rule_keep_and_weights(seasons[fit_idx], rule)
    k = fit_idx[keep]
    xs, ys = _fit_table(oof_raw[k], event[k], method, w[keep])
    oof_seasons = sorted(set(int(s) for s in seasons[k]))
    choice = {"fixed": method, "weighting": rule, "selection": selection}

    booster_sha = (hashlib.sha256(Path(booster_path).read_bytes()).hexdigest()
                   if booster_path else None)
    lookup = {
        "schema_version": LOOKUP_SCHEMA_VERSION,
        "model_version": model_version,
        "booster_sha256": booster_sha,
        "aft_scale": float(params["aft_loss_distribution_scale"]),
        "label_shift": S.AFT_LABEL_SHIFT,
        "method": method,
        "weighting": {"rule": rule, "selection": selection},
        "x": xs, "y": ys,
        "fitted_on": {"oof_seasons": oof_seasons, "models_trained_within": pre_seasons,
                      "fold_scheme": f"season-grouped expanding window, n_splits={n_splits}",
                      "n_rows": int(len(k)),
                      "base_rate": float(np.average(event[k], weights=w[keep]))},
        "laps_to_flag": "scheduled_laps - lap_number, >= 0 (browser: fuel_kg / burn_rate - 1)",
        "event": "stint_end_cause = race_end -> 1; pit-ended -> 0; retirement / no cause -> excluded",
        "shown_on": "final stints only (parquet: is_censored_stint; simulator: stint configured to the flag)",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Evaluation season: model fitted on every training season, lookup applied as fitted.
    ev_all = np.where(seasons == eval_season)[0]
    med_ev, scale_ev = fit_predict(pre, ev_all)
    raw_ev_all = raw_flag_chance(med_ev, ltf[ev_all], scale_ev)
    known = ~np.isnan(event[ev_all]) & ~np.isnan(raw_ev_all)   # NaN raw = no scheduled distance
    raw_ev, e_ev = raw_ev_all[known], event[ev_all][known]
    cal_ev = apply_lookup(raw_ev, lookup)
    base_eval, base_fit = float(e_ev.mean()), lookup["fitted_on"]["base_rate"]
    rel_cal = reliability(cal_ev, e_ev, np.linspace(0, 1, RELIABILITY_BINS + 1))
    qualifying = [r for r in rel_cal if r["n"] >= 100]
    fin_ev = final[ev_all]
    report = {
        "model_version": model_version, "eval_season": eval_season, "method_choice": choice,
        "n_eval_known_outcome": int(known.sum()),
        "n_eval_excluded_retirement_or_no_cause": int((~known).sum()),
        "brier": {"raw": brier(raw_ev, e_ev), "calibrated": brier(cal_ev, e_ev),
                  "base_rate_eval_season": brier(np.full_like(e_ev, base_eval), e_ev),
                  "base_rate_fit_seasons": brier(np.full_like(e_ev, base_fit), e_ev)},
        "ece_10bin": {"raw": ece(raw_ev, e_ev), "calibrated": ece(cal_ev, e_ev)},
        "reliability_10bin": {"raw": reliability(raw_ev, e_ev, np.linspace(0, 1, 11)),
                              "calibrated": rel_cal},
        "reliability_memo_bins": {"raw": reliability(raw_ev, e_ev, MEMO_BINS),
                                  "calibrated": reliability(cal_ev, e_ev, MEMO_BINS)},
        "acceptance": {"bins_with_100_rows": len(qualifying),
                       "bins_within_5pp": sum(abs(r["gap_pp"]) <= 5 for r in qualifying),
                       "worst_gap_pp": max((abs(r["gap_pp"]) for r in qualifying), default=None)},
        "final_stint_view": {
            "n_rows": int(fin_ev.sum()),
            "observed_reached_flag_share_incl_retirements": float(
                np.nanmean(np.where(np.isnan(event[ev_all][fin_ev]), 0.0, event[ev_all][fin_ev]))),
            "mean_calibrated_chance_shown": float(np.nanmean(apply_lookup(raw_ev_all[fin_ev], lookup))),
            "note": "on final stints that ran to the flag every known outcome is 1, so "
                    "calibration cannot be judged on this subset; it is judged on all laps "
                    "with a known outcome above."},
        "rows_in_shortened_races": {
            "all_eligible_seasons": int(ctx["race_shortened"].sum()),
            "eval_season": int(ctx["race_shortened"].to_numpy()[ev_all].sum())},
        "fit_oof_check": {"brier_raw": brier(oof_raw[fit_rows], event[fit_rows]),
                          "brier_calibrated_in_sample": brier(
                              apply_lookup(oof_raw[fit_rows], lookup), event[fit_rows])},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    lookup_path = out_dir / "flag_chance_lookup.json"
    lookup_path.write_text(json.dumps(lookup, indent=2))
    report["lookup_path"] = str(lookup_path)
    report["lookup_sha256"] = hashlib.sha256(lookup_path.read_bytes()).hexdigest()
    (out_dir / "flag_chance_report.json").write_text(json.dumps(report, indent=2))
    return report


# ─── Parity fixture shared by the Python and browser tests ──────────────────────
def write_parity_fixture(lookup: dict, out: Path, n: int = 400, seed: int = S.RANDOM_STATE) -> dict:
    """Sample inputs spanning the lookup's range, with the Python outputs beside them.
    app/src/ml/flagChance.test.ts recomputes them in TypeScript; ml/tests/
    test_flag_chance.py recomputes them in Python. Both must match within ONNX ATOL."""
    rng = np.random.default_rng(seed)
    median = np.concatenate([rng.uniform(0, 60, n - 8), [0.0, 0.0, 1.0, 5.0, 12.0, 40.0, 80.0, 3.0]])
    ltf = np.concatenate([rng.uniform(0, 70, n - 8), [0.0, 12.0, 0.0, 5.0, 12.0, 3.0, 1.0, 60.0]])
    fuel = rng.uniform(1, 110, n)
    burn = rng.uniform(1.4, 2.0, n)
    scale = float(lookup["aft_scale"])
    raw = raw_flag_chance(median, ltf, scale, lookup["label_shift"])
    fixture = {
        "lookup": lookup,
        "rows": [{"median": float(m), "laps_to_flag": float(t), "fuel_kg": float(f),
                  "burn": float(bb), "raw": float(r), "calibrated": float(c),
                  "capped_median": float(cm), "laps_to_flag_from_fuel": float(lf)}
                 for m, t, f, bb, r, c, cm, lf in zip(
                     median, ltf, fuel, burn, raw, apply_lookup(raw, lookup),
                     cap_to_flag(median, ltf), laps_to_flag_from_fuel(fuel, burn))],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fixture, indent=1))
    return fixture


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("--out", required=True)
    f.add_argument("--model-version", required=True)
    f.add_argument("--booster", help="the stint-life .bst the lookup is paired with")
    f.add_argument("--params", default="ml/models/stint_life_regressor_best_params.json")
    f.add_argument("--fit-max-season", type=int, default=DEFAULT_FIT_MAX_SEASON)
    f.add_argument("--eval-season", type=int, default=DEFAULT_EVAL_SEASON)
    f.add_argument("--weighting", default="auto", choices=("auto",) + WEIGHTING_RULES,
                   help="drift rule; 'auto' picks it on the season before the eval season")
    p = sub.add_parser("parity-fixture")
    p.add_argument("--lookup", required=True)
    p.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "fit":
        r = fit(Path(args.out), args.model_version, Path(args.booster) if args.booster else None,
                Path(args.params), args.fit_max_season, args.eval_season, weighting=args.weighting)
        print(json.dumps({k: r[k] for k in ("brier", "ece_10bin", "acceptance", "lookup_sha256")}, indent=1))
    else:
        write_parity_fixture(json.loads(Path(args.lookup).read_text()), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
