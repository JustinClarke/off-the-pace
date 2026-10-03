#!/usr/bin/env python3
"""
WI-16b: validation of the driver-isolation ratings (pure pace and relative pace).

Implements the V1-V5 checks of _roadmap/_fixes/wi/WI-16-cumulative-driver-isolation.md
(section *Validation*) with the thresholds pre-registered there, and compiles the
per-rating method score. Writes validation.json and validation-report.md to
_roadmap/_fixes/_evidence/wi-16-<date>/ (or --output-dir).

Scope after the 2026-09-28 cancellation of the tactical rating:
  * pure and relative are graded. Tactical-only checks (V1a-tactical, V2c-i, V5c and
    the whole of V6, which tests the tactical slope's forward prediction of pit timing)
    are reported as NOT_APPLICABLE and carry no weight: the matrix gives V6 no weight for
    pure or relative, and the other three are tactical rows.
  * Decisions use 2018-2024 only; 2025 is reported as confirmation (FD4).

Implementation choices the doc leaves open are declared in each result's `design`
field; none of them is tuned on a result. Thresholds are the doc's.

The warehouse is opened read-only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parent.parent

DECISION_YEARS = (2018, 2024)
CONFIRM_YEAR = 2025
N_BOOT = 2000
SEED = 42

# Pre-registered thresholds from the WI doc (never tuned on results).
THRESHOLDS = {
    "V1a_pure_spearman": {"pass": 0.60, "marginal": 0.40},
    "V1b_pearson": {"pass": 0.50, "rule_change_ratio": 0.70},
    "V1c_ratio": {"pass": 1.5},
    "V2a_corr": {"pass": 0.15, "marginal": 0.25},  # |corr|
    "V2b_mean_diff": {"pass": 0.05, "marginal": 0.10},  # s
    "V2c_ii_spearman": {"pass": 0.60},
    "V2e_spearman_field": {"pass": 0.60},
    "V2e_spearman_massey": {"pass": 0.50},
    "V3a_corr": {"pass": 0.15},  # |corr|
    "V3b_corr": {"pass": 0.10},  # |corr|
    "V3b_gap_diff": {"pass": 0.05},  # s
    "V3c_spearman": {"pass": 0.70},
    "V3_tier3_coverage": {"pass": 0.80},
    "V4a_fuel": {"pass": (0.025, 0.040)},  # s/kg
    "V4b_fuel_coeff": {"pass": 0.002},  # |s/kg|
    "V5a_autocorr": {"pass": 0.30},  # |rho1|
    "V5b_jitter": {"pass": 1.0, "fail": 1.5},
    "V5d_autocorr": {"pass": 0.40},  # |rho1|
}

# Softer = higher rank. 2018 legacy names from seeds/compound_hardness_scale.csv (era 2018);
# from 2019 the panel carries the race-relative SOFT/MEDIUM/HARD labels.
HARDNESS_2018 = {"SUPERHARD": 1, "HARD": 2, "MEDIUM": 3, "SOFT": 4, "SUPERSOFT": 5,
                 "ULTRASOFT": 6, "HYPERSOFT": 7}
HARDNESS_2019 = {"HARD": 1, "MEDIUM": 2, "SOFT": 3}

NA = "NOT_APPLICABLE"
TACTICAL_NA = "The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only."


def hardness(year: int, compound: str) -> Optional[int]:
    return (HARDNESS_2018 if year == 2018 else HARDNESS_2019).get(compound)


def grade_upper(value: float, pass_thr: float, marginal_thr: Optional[float] = None) -> str:
    """PASS when value <= pass_thr (MARGINAL <= marginal_thr), else FAIL. NaN -> FAIL."""
    if value is None or not np.isfinite(value):
        return "FAIL"
    if value <= pass_thr:
        return "PASS"
    if marginal_thr is not None and value <= marginal_thr:
        return "MARGINAL"
    return "FAIL"


def grade_lower(value: float, pass_thr: float, marginal_thr: Optional[float] = None) -> str:
    """PASS when value >= pass_thr (MARGINAL >= marginal_thr), else FAIL. NaN -> FAIL."""
    if value is None or not np.isfinite(value):
        return "FAIL"
    if value >= pass_thr:
        return "PASS"
    if marginal_thr is not None and value >= marginal_thr:
        return "MARGINAL"
    return "FAIL"


SCORE = {"PASS": 1.0, "MARGINAL": 0.5, "FAIL": 0.0}


def result(status: str, **kw) -> Dict[str, Any]:
    out = {"status": status}
    if status in SCORE:
        out["score"] = SCORE[status]
    out.update(kw)
    return out


def f(x) -> Optional[float]:
    """JSON-safe float."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def spearman(a, b) -> float:
    if len(a) < 3:
        return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(stats.spearmanr(a, b)[0])


def pearson(a, b) -> float:
    if len(a) < 3:
        return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(stats.pearsonr(a, b)[0])


def cluster_bootstrap(df: pd.DataFrame, cluster: str, stat: Callable[[pd.DataFrame], float],
                      n: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    """95% percentile CI of stat(df) resampling whole clusters with replacement."""
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in df.groupby(cluster)}
    keys = np.array(list(groups))
    if len(keys) == 0:  # nothing to resample (e.g. no movers at all): no interval
        return np.nan, np.nan
    vals = []
    for _ in range(n):
        pick = rng.choice(keys, size=len(keys), replace=True)
        v = stat(pd.concat([groups[k] for k in pick], ignore_index=True))
        if np.isfinite(v):
            vals.append(v)
    if not vals:
        return np.nan, np.nan
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def within_ols_fuel(df: pd.DataFrame, y: str, group: List[str]) -> Dict[str, float]:
    """y ~ age + fuel_mass_kg with `group` fixed effects (demeaned), bivariate OLS.
    The design of transform/analyses/deg_slope_fuel_deconfounding.sql."""
    d = df[[y, "age", "fuel_mass_kg"] + group].dropna().copy()
    for c in (y, "age", "fuel_mass_kg"):
        d[c] = d[c] - d.groupby(group)[c].transform("mean")
    sxx = (d.age ** 2).sum()
    sff = (d.fuel_mass_kg ** 2).sum()
    sxf = (d.age * d.fuel_mass_kg).sum()
    sxy = (d.age * d[y]).sum()
    sfy = (d.fuel_mass_kg * d[y]).sum()
    det = sxx * sff - sxf * sxf
    return {
        "n": int(len(d)),
        "b_age": float((sxy * sff - sfy * sxf) / det),
        "b_fuel_s_per_kg": float((sfy * sxx - sxy * sxf) / det),
        "corr_age_fuel": float(sxf / np.sqrt(sxx * sff)),
    }


class DriverIsolationValidator:
    def __init__(self, db_path: str = "data/dev.duckdb"):
        self.db_path = db_path
        self.con = duckdb.connect(db_path, read_only=True)
        self.results: Dict[str, Any] = {}

    def q(self, sql: str) -> pd.DataFrame:
        return self.con.execute(sql).df()

    # ── orchestration ────────────────────────────────────────────────────────────────
    def run_all_validations(self) -> Dict[str, Any]:
        print("Starting WI-16b validation...")
        self.results["substrate"] = self._substrate()
        steps = [
            ("V1", self._validate_v1), ("V2", self._validate_v2), ("V3", self._validate_v3),
            ("V4", self._validate_v4), ("V5", self._validate_v5), ("V6", self._validate_v6),
        ]
        for key, fn in steps:
            print(f"\n{key}...")
            self.results[key] = fn()
        print("\nCoverage of the race mart...")
        self.results["coverage"] = self._coverage()
        print("Season levels...")
        self.results["season_levels"] = self._season_levels()
        print("Worked examples...")
        self.results["examples"] = self._validate_examples()
        print("Method scores...")
        self.results["method_scores"] = self._compute_method_scores()
        return self.results

    def _substrate(self) -> Dict[str, Any]:
        try:
            sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                 text=True, cwd=REPO).stdout.strip() or "unknown"
        except Exception:
            sha = "unknown"
        fit = self.q("SELECT fit_method, MIN(fit_timestamp) AS fit_timestamp, "
                     "COUNT(*) FILTER (WHERE car_iso_s IS NOT NULL) AS n_car_terms, COUNT(*) AS n_cells "
                     "FROM int_constructor_car_fe_isolation GROUP BY 1")
        mtime = datetime.fromtimestamp(os.path.getmtime(self.db_path)).isoformat(timespec="seconds")
        return {
            "git_sha": sha,
            "database": str(self.db_path),
            "database_mtime": mtime,
            "car_fe_fit": fit.to_dict(orient="records"),
        }

    # ── shared frames ────────────────────────────────────────────────────────────────
    def _race(self) -> pd.DataFrame:
        if not hasattr(self, "_race_df"):
            self._race_df = self.q("""
                SELECT race_year, race_id, CAST(split_part(race_id, '_', 2) AS INTEGER) AS rnd,
                       driver_id, constructor_id, car_iso_s, car_term_source, n_laps, n_pure_laps,
                       pure_skill_gain_s AS pure, pure_skill_se_s AS pure_se
                FROM fct_driver_isolation_race
            """)
        return self._race_df

    def _driver_season(self, min_races: int = 1) -> pd.DataFrame:
        """Driver-season pure: mean of race pure, SE^2 = mean(race SE^2)/n (races
        independent), main constructor = the one with most races, and an EB-shrunk value
        (normal-normal, toward the season mean; tau^2 per season from driver-seasons with
        >= 8 races, the V1b floor, NULL-safe floor at 0)."""
        r = self._race().dropna(subset=["pure"])
        g = r.groupby(["race_year", "driver_id"])
        ds = g.agg(n_races=("pure", "size"), pure=("pure", "mean"),
                   se2=("pure_se", lambda s: np.nanmean(np.square(s)))).reset_index()
        ds["se2"] = ds.se2 / ds.n_races
        main = (r.groupby(["race_year", "driver_id", "constructor_id"]).size().reset_index(name="k")
                .sort_values(["race_year", "driver_id", "k", "constructor_id"],
                             ascending=[True, True, False, True])
                .drop_duplicates(["race_year", "driver_id"]))
        ds = ds.merge(main[["race_year", "driver_id", "constructor_id"]], on=["race_year", "driver_id"])
        tau = {}
        for y, gy in ds[ds.n_races >= 8].groupby("race_year"):
            t2 = np.var(gy.pure, ddof=1) - gy.se2.mean()
            tau[y] = max(t2, 0.0) if np.isfinite(t2) else np.nan
        ds["tau2"] = ds.race_year.map(tau)
        ds["lam"] = ds.tau2 / (ds.tau2 + ds.se2)
        season_mean = ds.groupby("race_year").pure.transform("mean")
        ds["pure_shrunk"] = season_mean + ds.lam * (ds.pure - season_mean)
        return ds[ds.n_races >= min_races].reset_index(drop=True)

    # ── V1 ──────────────────────────────────────────────────────────────────────────
    def _validate_v1(self) -> Dict[str, Any]:
        out = {}
        print("  V1a split-half...")
        out["V1a_pure"] = self._validate_v1a()
        out["V1a_tactical"] = result(NA, notes=TACTICAL_NA)
        print("  V1b adjacent seasons...")
        out["V1b"] = self._validate_v1b()
        print("  V1c movers...")
        out["V1c"] = self._validate_v1c()
        return out

    def _validate_v1a(self) -> Dict[str, Any]:
        r = self._race().dropna(subset=["pure"]).copy()
        r["half"] = np.where(r.rnd % 2 == 1, "odd", "even")
        h = r.groupby(["race_year", "driver_id", "half"]).agg(n=("pure", "size"), m=("pure", "mean")).reset_index()
        w = h.pivot_table(index=["race_year", "driver_id"], columns="half", values=["n", "m"]).dropna()
        w = w[(w[("n", "odd")] >= 5) & (w[("n", "even")] >= 5)]
        per = {}
        for y, g in w.groupby(level=0):
            per[int(y)] = {"spearman": f(spearman(g[("m", "odd")], g[("m", "even")])), "n_drivers": int(len(g))}
        dec = [v["spearman"] for y, v in per.items() if DECISION_YEARS[0] <= y <= DECISION_YEARS[1] and v["spearman"] is not None]
        med = float(np.median(dec)) if dec else np.nan
        t = THRESHOLDS["V1a_pure_spearman"]
        return result(grade_lower(med, t["pass"], t["marginal"]), median_spearman=f(med), per_season=per,
                      confirmation_2025=per.get(CONFIRM_YEAR), threshold=t,
                      design="Race-level pure (fct_driver_isolation_race) averaged over odd and even rounds; "
                             "driver-seasons with >= 5 races in each half; median of per-season Spearman over 2018-2024.")

    def _validate_v1b(self) -> Dict[str, Any]:
        ds = self._driver_season(min_races=8)
        per = {}
        for y in range(2018, CONFIRM_YEAR):
            m = ds[ds.race_year == y].merge(ds[ds.race_year == y + 1], on="driver_id", suffixes=("", "_next"))
            per[f"{y}-{y + 1}"] = {"pearson": f(pearson(m.pure_shrunk, m.pure_shrunk_next)), "n_drivers": int(len(m))}
        dec_pairs = {k: v for k, v in per.items() if int(k[5:]) <= DECISION_YEARS[1]}
        dec = [v["pearson"] for v in dec_pairs.values() if v["pearson"] is not None]
        med = float(np.median(dec)) if dec else np.nan
        all7 = [v["pearson"] for v in per.values() if v["pearson"] is not None]
        v2122 = per.get("2021-2022", {}).get("pearson")
        others = [v["pearson"] for k, v in dec_pairs.items() if k != "2021-2022" and v["pearson"] is not None]
        other_med = float(np.median(others)) if others else np.nan
        t = THRESHOLDS["V1b_pearson"]
        rule_broken = bool(v2122 is not None and np.isfinite(other_med) and v2122 < t["rule_change_ratio"] * other_med)
        # The rule-change pair is the check's point: if it cannot be computed (too few rated
        # drivers in both seasons), V1b cannot pass. Found 2026-09-30 when a single-season
        # 2021 era left no 2021-22 pair and V1b read PASS on 2 of 6 pairs.
        rule_uncomputable = v2122 is None or not np.isfinite(other_med)
        status = grade_lower(med, t["pass"])
        if rule_broken or rule_uncomputable:
            status = "FAIL"
        return result(status, median_pearson=f(med), median_pearson_all_7_pairs=f(np.median(all7)) if all7 else None,
                      per_pair=per,
                      reported_individually={k: per.get(k) for k in ("2022-2023", "2023-2024", "2024-2025")},
                      rule_change_check={"pair_2021_2022": f(v2122), "median_other_decision_pairs": f(other_med),
                                         "required_min": f(t["rule_change_ratio"] * other_med) if np.isfinite(other_med) else None,
                                         "rule_broken": rule_broken, "rule_uncomputable": rule_uncomputable},
                      threshold=t,
                      design="EB-shrunk driver-season pure (toward the season mean; tau^2 per season), drivers with "
                             ">= 8 races in both seasons. Verdict on the 6 pairs inside 2018-2024; 2024-2025 reported "
                             "as confirmation, and the doc's 7-pair median alongside.")

    def _validate_v1c(self) -> Dict[str, Any]:
        ds = self._driver_season(min_races=8)
        ds["pure_centred"] = ds.pure - ds.groupby("race_year").pure.transform("mean")
        m = ds.merge(ds.assign(race_year=ds.race_year - 1), on=["driver_id", "race_year"], suffixes=("", "_next"))
        m = m[(m.race_year >= DECISION_YEARS[0]) & (m.race_year + 1 <= DECISION_YEARS[1])].copy()
        m["is_mover"] = m.constructor_id != m.constructor_id_next
        m["delta"] = (m.pure_next - m.pure).abs()
        m["delta_centred"] = (m.pure_centred_next - m.pure_centred).abs()

        def ratio(d: pd.DataFrame, col: str = "delta") -> float:
            mv, st = d[d.is_mover][col], d[~d.is_mover][col]
            if len(mv) == 0 or len(st) == 0 or np.median(st) == 0:
                return np.nan
            return float(np.median(mv) / np.median(st))

        r0 = ratio(m)
        lo, hi = cluster_bootstrap(m, "driver_id", ratio)
        rc = ratio(m, "delta_centred")
        lo_c, hi_c = cluster_bootstrap(m, "driver_id", lambda d: ratio(d, "delta_centred"))
        t = THRESHOLDS["V1c_ratio"]
        return result(grade_upper(r0, t["pass"]), ratio=f(r0), ci95=[f(lo), f(hi)],
                      movers_n=int(m.is_mover.sum()), stayers_n=int((~m.is_mover).sum()),
                      movers_distinct_drivers=int(m[m.is_mover].driver_id.nunique()),
                      movers_median_delta_s=f(m[m.is_mover].delta.median()),
                      stayers_median_delta_s=f(m[~m.is_mover].delta.median()),
                      season_centred_sensitivity={"ratio": f(rc), "ci95": [f(lo_c), f(hi_c)],
                                                  "note": "each season's mean pure removed first (the 2018 level offset, W33 issue 4)"},
                      threshold=t,
                      design="Adjacent-season pairs inside 2018-2024 of drivers with >= 8 races in both seasons; "
                             "mover = main constructor (most races) differs. Ratio of medians |delta pure|; "
                             "bootstrap CI resampling drivers (clustered by driver). PASS iff ratio <= 1.5.")

    # ── V2 ──────────────────────────────────────────────────────────────────────────
    def _validate_v2(self) -> Dict[str, Any]:
        out = {}
        for key, fn in [("V2a", self._validate_v2a), ("V2b", self._validate_v2b), ("V2c", self._validate_v2c),
                        ("V2d", self._validate_v2d), ("V2e", self._validate_v2e)]:
            print(f"  {key}...")
            out[key] = fn()
        return out

    def _v2a_corr(self, lo: int, hi: int) -> tuple[float, int]:
        df = self.q(f"""
            WITH r AS (
                SELECT race_year, driver_id, constructor_id, pure_skill_gain_s AS pure, car_iso_s AS car
                FROM fct_driver_isolation_race
                WHERE pure_skill_gain_s IS NOT NULL AND car_iso_s IS NOT NULL
                  AND race_year BETWEEN {lo} AND {hi}
            )
            SELECT pure - AVG(pure) OVER (PARTITION BY driver_id, race_year) AS pure_dm,
                   car - AVG(car) OVER (PARTITION BY constructor_id, race_year) AS car_dm
            FROM r
        """)
        return pearson(df.pure_dm, df.car_dm), len(df)

    def _validate_v2a(self) -> Dict[str, Any]:
        c, n = self._v2a_corr(*DECISION_YEARS)
        c25, n25 = self._v2a_corr(CONFIRM_YEAR, CONFIRM_YEAR)
        t = THRESHOLDS["V2a_corr"]
        return result(grade_upper(abs(c), t["pass"], t["marginal"]), correlation=f(c), abs_correlation=f(abs(c)),
                      n_rows=n, confirmation_2025={"correlation": f(c25), "n_rows": n25}, threshold=t,
                      design="Race-level pure demeaned within driver-season, car_iso_s within constructor-season; "
                             "Pearson over race rows, 2018-2024.",
                      caveat="With the car term fitted on the same laps pure is averaged over (W33 fix), the "
                             "two-way FE's within-cell residuals are orthogonal to the car term by construction, "
                             "so V2a is close to 0 almost mechanically. It catches sample and plumbing mismatches, "
                             "not a driver x car interaction (that lands in the driver effect). V1c and V3a/V3c "
                             "carry that question.")

    def _validate_v2b(self) -> Dict[str, Any]:
        df = self.q("""
            SELECT race_year, race_id, driver_id, compound,
                   COUNT(*) AS n, AVG(pure_skill_gain_s) AS pure
            FROM fct_driver_isolation_lap
            WHERE NOT pure_is_extrapolated AND pure_skill_gain_s IS NOT NULL
            GROUP BY ALL
            HAVING COUNT(*) >= 3
        """)
        df["rank"] = [hardness(y, c) for y, c in zip(df.race_year, df.compound)]
        df = df.dropna(subset=["rank"])
        m = df.merge(df, on=["race_year", "race_id", "driver_id"], suffixes=("_s", "_h"))
        m = m[m.rank_s > m.rank_h]  # softer vs harder
        m["pair"] = m.compound_s + "-" + m.compound_h
        m["diff"] = m.pure_s - m.pure_h
        cells = (m.groupby(["race_year", "pair"]).agg(n=("diff", "size"), mean=("diff", "mean"), sd=("diff", "std"))
                 .reset_index())
        cells["se"] = cells.sd / np.sqrt(cells.n)
        min_n = 20
        graded = cells[(cells.n >= min_n) & cells.race_year.between(*DECISION_YEARS)]
        worst = float(graded["mean"].abs().max()) if len(graded) else np.nan
        t = THRESHOLDS["V2b_mean_diff"]
        pooled = m[m.race_year.between(*DECISION_YEARS)].groupby("pair")["diff"].agg(["size", "mean"]).reset_index()
        return result(grade_upper(worst, t["pass"], t["marginal"]), max_abs_mean_diff_s=f(worst),
                      worst_cell=graded.loc[graded["mean"].abs().idxmax()].to_dict() if len(graded) else None,
                      cells_graded=int(len(graded)), cells_below_min_n=int(((cells.n < min_n) & cells.race_year.between(*DECISION_YEARS)).sum()),
                      per_cell=[{k: (f(v) if isinstance(v, (float, np.floating)) else (int(v) if isinstance(v, (np.integer,)) else v))
                                 for k, v in row.items()} for row in cells.to_dict(orient="records")],
                      pooled_2018_2024=pooled.to_dict(orient="records"), threshold=t,
                      design="Per driver-race-compound mean of non-extrapolated pure (>= 3 laps, the window floor); "
                             "difference softer - harder within the same driver-race; mean per (season, compound "
                             "pair). Cells with >= 20 driver-races inside 2018-2024 are graded; the verdict is on "
                             "the largest |mean|. Positive = pure reads faster on the softer tyre.")

    def _validate_v2c(self) -> Dict[str, Any]:
        df = self.q("""
            SELECT l.race_year, l.driver_id, l.race_id, l.tyre_phase, l.pure_skill_gain_s AS pure, t.push_residual
            FROM fct_driver_isolation_lap AS l
            LEFT JOIN int_lap_thermal_proxy AS t ON l.lap_id = t.lap_id
            WHERE NOT l.pure_is_extrapolated AND l.pure_skill_gain_s IS NOT NULL
              AND l.tyre_phase IN ('early', 'mid')
        """)
        n_races = df.groupby(["race_year", "driver_id"]).race_id.nunique()
        keep = n_races[n_races >= 5].index
        df = df.set_index(["race_year", "driver_id"]).loc[keep].reset_index()
        early = df[df.tyre_phase == "early"].groupby(["race_year", "driver_id"]).agg(
            pure_early=("pure", "mean"), push=("push_residual", "mean"))
        mid = df[df.tyre_phase == "mid"].groupby(["race_year", "driver_id"]).agg(pure_mid=("pure", "mean"))
        ds = early.join(mid, how="inner").dropna().reset_index()
        for c in ("pure_early", "pure_mid"):
            ds[c] = ds[c] - ds.groupby("race_year")[c].transform("mean")
        ds["tercile"] = ds.groupby("race_year").push.transform(
            lambda s: pd.qcut(s.rank(method="first"), 3, labels=["bottom", "middle", "top"]))
        dec = ds[ds.race_year.between(*DECISION_YEARS)]
        res = {}
        for t_ in ("top", "bottom"):
            g = dec[dec.tercile == t_]
            res[t_] = {"spearman": f(spearman(g.pure_early, g.pure_mid)), "n_driver_seasons": int(len(g))}
        thr = THRESHOLDS["V2c_ii_spearman"]["pass"]
        worst = min((v["spearman"] if v["spearman"] is not None else -1) for v in res.values())
        allg = dec
        ii = result(grade_lower(worst, thr), by_tercile=res,
                    all_driver_seasons_spearman=f(spearman(allg.pure_early, allg.pure_mid)),
                    threshold=thr,
                    design="Driver-seasons with >= 5 races; tercile of the season's driver-season mean "
                           "push_residual on early-phase laps; pure on early vs mid laps (non-extrapolated), each "
                           "centred on its season mean before pooling 2018-2024 (a season level shift would "
                           "otherwise inflate a pooled rank correlation). PASS iff both the top and the bottom "
                           "tercile reach 0.60.")
        return {"V2c_i": result(NA, notes=TACTICAL_NA), "V2c_ii": ii,
                "status": ii["status"], "score": ii["score"]}

    def _validate_v2d(self) -> Dict[str, Any]:
        df = self.q("""
            WITH lc AS (
                SELECT race_year, race_id, lap_number, lap_id, driver_id, pure_skill_gain_s AS pure,
                       pure_is_extrapolated, lift_coast_share,
                       lift_coast_share - MEDIAN(lift_coast_share) OVER (PARTITION BY race_id, lap_number) AS excess
                FROM fct_driver_isolation_lap
                WHERE lift_coast_share IS NOT NULL
            ),
            mad AS (
                SELECT race_id, lap_number, MEDIAN(ABS(excess)) AS mad FROM lc GROUP BY ALL
            )
            SELECT lc.*, mad.mad, (mad.mad > 0 AND lc.excess > mad.mad) AS is_saving
            FROM lc JOIN mad USING (race_id, lap_number)
            WHERE NOT lc.pure_is_extrapolated AND lc.pure IS NOT NULL
        """)
        df = df[df.race_year.between(*DECISION_YEARS)]
        g = df.groupby(["race_id", "driver_id", "is_saving"]).pure.agg(["mean", "size"]).unstack("is_saving").dropna()
        diff = g[("mean", True)] - g[("mean", False)]
        w = np.minimum(g[("size", True)], g[("size", False)])
        return result("REPORT",
                      within_driver_race_mean_diff_s=f(np.average(diff, weights=w)) if len(diff) else None,
                      within_driver_race_median_diff_s=f(np.median(diff)) if len(diff) else None,
                      n_driver_races=int(len(diff)),
                      flagged_lap_share=f(df.is_saving.mean()),
                      raw_mean_diff_s=f(df[df.is_saving].pure.mean() - df[~df.is_saving].pure.mean()),
                      design="Lap flagged when lift_coast_share exceeds the same-(race, lap) median by more than "
                             "1 MAD. Difference in mean non-extrapolated pure, flagged minus other laps, within "
                             "driver-race (weighted by the smaller lap count), 2018-2024. Negative = pure reads "
                             "slower on lift-and-coast laps. Report only (known, uncorrectable confound).")

    def _massey(self) -> pd.DataFrame:
        sys.path.insert(0, str(REPO / "scripts"))
        from driver_network_rating import _massey_solve  # noqa: E402
        agg = self.q(f"""
            SELECT race_year, race_id, ego_driver_id, teammate_driver_id,
                   SUM(pair_quality_weight * driver_skill_proxy_s) / NULLIF(SUM(pair_quality_weight), 0) AS delta,
                   SUM(pair_quality_weight) AS weight
            FROM int_synthetic_teammate
            WHERE teammate_available_flag AND NOT strategic_divergence_flag AND pair_quality_weight > 0
              AND race_year <= {DECISION_YEARS[1]}
              -- Not in driver_network_rating.main(): on the 2026-09-29 dev ~6% of the rows it
              -- uses have a NULL proxy, a group whose rows are all NULL gets a NULL delta, and
              -- one NaN turns the whole lstsq solve into NaN ratings.
              AND driver_skill_proxy_s IS NOT NULL
            GROUP BY race_year, race_id, ego_driver_id, teammate_driver_id
        """)
        out = []
        for era, sub in (("pre2022", agg[agg.race_year < 2022]), ("post2022", agg[agg.race_year >= 2022])):
            rated = _massey_solve(sub)
            rated["era"] = era
            out.append(rated)
        return pd.concat(out, ignore_index=True)

    def _validate_v2e(self) -> Dict[str, Any]:
        ds = self._driver_season(min_races=5)
        ds = ds[ds.race_year.between(*DECISION_YEARS)]
        fld = self.q(f"""
            SELECT race_year, driver_id, -AVG(driver_skill_field_s) AS field_gain_s
            FROM int_driver_race_skill_loro
            WHERE driver_skill_field_s IS NOT NULL AND race_year BETWEEN {DECISION_YEARS[0]} AND {DECISION_YEARS[1]}
            GROUP BY ALL
        """)
        m = ds.merge(fld, on=["race_year", "driver_id"])
        per_field = {int(y): f(spearman(g.pure, g.field_gain_s)) for y, g in m.groupby("race_year")}
        med_field = float(np.nanmedian([v for v in per_field.values() if v is not None]))
        try:
            ms = self._massey()
            ds["era"] = np.where(ds.race_year >= 2022, "post2022", "pre2022")
            mm = ds.merge(ms[["driver_id", "era", "rating"]], on=["driver_id", "era"])
            per_massey = {int(y): f(spearman(g.pure, g.rating)) for y, g in mm.groupby("race_year")}
            med_massey = float(np.nanmedian([v for v in per_massey.values() if v is not None]))
            massey_err = None
        except Exception as e:  # the soft test must not take the run down
            per_massey, med_massey, massey_err = {}, np.nan, repr(e)
        tf, tm = THRESHOLDS["V2e_spearman_field"]["pass"], THRESHOLDS["V2e_spearman_massey"]["pass"]
        ok = np.isfinite(med_field) and med_field >= tf and np.isfinite(med_massey) and med_massey >= tm
        return result("PASS" if ok else "MARGINAL", median_spearman_field=f(med_field), per_season_field=per_field,
                      median_spearman_massey=f(med_massey), per_season_massey=per_massey, massey_error=massey_err,
                      threshold={"field": tf, "massey": tm},
                      design="Driver-seasons with >= 5 races, 2018-2024; per-season Spearman of driver-season pure "
                             "against the season mean of -driver_skill_field_s (sign flipped: that column is "
                             "negative = faster) and against the era Massey rating of "
                             "scripts/driver_network_rating.py (its solver on int_synthetic_teammate, <= 2024, "
                             "pre2022/post2022, rows with a non-NULL proxy only). Median over seasons. Soft "
                             "test: below either bar is MARGINAL.")

    # ── V3 ──────────────────────────────────────────────────────────────────────────
    def _validate_v3(self) -> Dict[str, Any]:
        out = {}
        for key, fn in [("V3a", self._validate_v3a), ("V3b", self._validate_v3b), ("V3c", self._validate_v3c),
                        ("V3d", self._validate_v3d), ("V3_tier3", self._validate_v3_tier3)]:
            print(f"  {key}...")
            out[key] = fn()
        return out

    PAIR_PURE_WHERE = ("pure_gap_gain_s IS NOT NULL AND tyre_phase <> 'cliff' AND peer_tyre_phase <> 'cliff' "
                       f"AND race_year BETWEEN {DECISION_YEARS[0]} AND {DECISION_YEARS[1]}")

    def _validate_v3a(self) -> Dict[str, Any]:
        def corr(where_phase: str) -> tuple[float, int]:
            df = self.q(f"""
                SELECT race_id, driver_id, peer_driver_id,
                       AVG(pure_gap_gain_s) AS pure_gap, AVG(car_advantage_gain_s) AS car_adv, COUNT(*) AS n
                FROM fct_driver_isolation_pair_lap
                WHERE NOT is_teammate AND driver_id < peer_driver_id AND car_advantage_gain_s IS NOT NULL
                  AND pure_gap_gain_s IS NOT NULL AND race_year BETWEEN {DECISION_YEARS[0]} AND {DECISION_YEARS[1]}
                  {where_phase}
                GROUP BY ALL
            """)
            return pearson(df.pure_gap, df.car_adv), len(df)

        c, n = corr("AND tyre_phase <> 'cliff' AND peer_tyre_phase <> 'cliff'")
        c_all, n_all = corr("")
        thr = THRESHOLDS["V3a_corr"]["pass"]
        return result(grade_upper(abs(c), thr), correlation=f(c), n_race_pairs=n,
                      all_phases_sensitivity={"correlation": f(c_all), "n_race_pairs": n_all}, threshold=thr,
                      design="Race-pair means (one row per unordered cross-team pair per race) over pair-laps "
                             "where both drivers are pre-cliff (the doc: pure aggregates use early, mid and "
                             "recovery laps only), 2018-2024. Positive = car under-removed.")

    def _validate_v3b(self) -> Dict[str, Any]:
        df = self.q(f"""
            SELECT race_id, driver_id, peer_driver_id, is_dirty_air_lap, peer_is_dirty_air_lap,
                   pure_gap_gain_s AS pure_gap, traffic_advantage_gain_s AS traffic_adv
            FROM fct_driver_isolation_pair_lap
            WHERE {self.PAIR_PURE_WHERE} AND traffic_advantage_gain_s IS NOT NULL
        """)
        one = df[df.is_dirty_air_lap != df.peer_is_dirty_air_lap]
        one_u = one[one.driver_id < one.peer_driver_id]
        c = pearson(one_u.pure_gap, one_u.traffic_adv)
        # Gap with the driver in dirty air (peer clean) vs the same ordered pair's clean-clean gap.
        a_dirty = one[one.is_dirty_air_lap & ~one.peer_is_dirty_air_lap]
        clean = df[~df.is_dirty_air_lap & ~df.peer_is_dirty_air_lap]
        k = ["race_id", "driver_id", "peer_driver_id"]
        gd = a_dirty.groupby(k).pure_gap.agg(["mean", "size"])
        gc = clean.groupby(k).pure_gap.agg(["mean", "size"])
        j = gd.join(gc, lsuffix="_dirty", rsuffix="_clean", how="inner")
        j = j[(j.size_dirty >= 3) & (j.size_clean >= 3)].reset_index()
        j["d"] = j.mean_dirty - j.mean_clean
        gap = float(j.d.mean()) if len(j) else np.nan
        lo, hi = cluster_bootstrap(j, "race_id", lambda d: float(d.d.mean())) if len(j) else (np.nan, np.nan)
        s_corr = grade_upper(abs(c), THRESHOLDS["V3b_corr"]["pass"])
        s_gap = grade_upper(abs(gap), THRESHOLDS["V3b_gap_diff"]["pass"])
        n_pass = [s_corr, s_gap].count("PASS")
        return result({2: "PASS", 1: "MARGINAL", 0: "FAIL"}[n_pass],
                      correlation=f(c), n_pair_laps_one_dirty=int(len(one_u)), correlation_status=s_corr,
                      dirty_minus_clean_gap_s=f(gap), gap_ci95=[f(lo), f(hi)], n_ordered_pairs=int(len(j)),
                      gap_status=s_gap,
                      threshold={"corr": THRESHOLDS["V3b_corr"]["pass"], "gap_s": THRESHOLDS["V3b_gap_diff"]["pass"]},
                      design="Pre-cliff pair-laps 2018-2024. (i) exactly one of the pair in dirty air: "
                             "Pearson(pure_gap, traffic_advantage) over unordered pair-laps. (ii) per ordered "
                             "(race, driver, peer) with >= 3 laps of each kind: mean pure gap when the driver is "
                             "in dirty air and the peer clean, minus the same pair's clean-clean gap; mean over "
                             "pairs, CI clustered by race. Negative = dirty air under-priced (pure reads slower "
                             "in the wake). PASS both, MARGINAL one, FAIL neither.")

    def _validate_v3c(self) -> Dict[str, Any]:
        df = self.q(f"""
            WITH p AS (
                SELECT race_year, race_id, driver_id, peer_driver_id, AVG(pure_gap_gain_s) AS pure_gap, COUNT(*) AS n
                FROM fct_driver_isolation_pair_lap
                WHERE is_teammate AND driver_id < peer_driver_id AND {self.PAIR_PURE_WHERE}
                GROUP BY ALL
            )
            SELECT p.*, -l.driver_skill_loro_s AS loro_gain_s
            FROM p JOIN int_driver_race_skill_loro AS l USING (race_year, race_id, driver_id)
            WHERE l.driver_skill_loro_s IS NOT NULL
        """)
        s = spearman(df.pure_gap, df.loro_gain_s)
        thr = THRESHOLDS["V3c_spearman"]["pass"]
        return result(grade_lower(s, thr), spearman=f(s), n_race_pairs=int(len(df)), threshold=thr,
                      design="Teammate race-pairs (one row per pair per race), mean pure gap over pre-cliff "
                             "matched laps against -driver_skill_loro_s (int_driver_race_skill_loro: the median "
                             "lap-by-lap teammate gap, negative = faster, so flipped), 2018-2024.")

    def _validate_v3d(self) -> Dict[str, Any]:
        pairs = self.q(f"""
            SELECT race_year, race_id, CAST(split_part(race_id, '_', 2) AS INTEGER) AS rnd,
                   driver_id, peer_driver_id,
                   AVG(relative_pace_gain_s) AS rel, AVG(car_advantage_gain_s) AS car_adv,
                   AVG(traffic_advantage_gain_s) AS traffic_adv, COUNT(*) AS n
            FROM fct_driver_isolation_pair_lap
            WHERE driver_id < peer_driver_id AND relative_pace_gain_s IS NOT NULL
              AND car_advantage_gain_s IS NOT NULL AND traffic_advantage_gain_s IS NOT NULL
              AND race_year BETWEEN {DECISION_YEARS[0]} AND {DECISION_YEARS[1]}
            GROUP BY ALL
        """)
        race = self._race().dropna(subset=["pure"])
        rows = []
        for (y, k), gk in pairs[pairs.rnd >= 5].groupby(["race_year", "rnd"]):
            prior = race[(race.race_year == y) & (race.rnd < k)]
            st = prior.groupby("driver_id").agg(m=("pure", "mean"), n=("pure", "size"),
                                                se2=("pure_se", lambda s: np.nanmean(np.square(s))))
            st = st[st.n >= 3]
            if len(st) < 5:
                continue
            st["se2"] = st.se2 / st.n
            field = st.m.mean()
            tau2 = max(np.var(st.m, ddof=1) - st.se2.mean(), 0.0)
            st["shrunk"] = field + (tau2 / (tau2 + st.se2)) * (st.m - field)
            prev = pairs[(pairs.race_year == y) & (pairs.rnd < k)].sort_values("rnd")
            last = prev.groupby(["driver_id", "peer_driver_id"]).rel.last()
            for r in gk.itertuples():
                if r.driver_id not in st.index or r.peer_driver_id not in st.index:
                    continue
                key = (r.driver_id, r.peer_driver_id)
                if key not in last.index:
                    continue
                pure_gap = st.shrunk[r.driver_id] - st.shrunk[r.peer_driver_id]
                rows.append({"race_id": r.race_id, "rel": r.rel,
                             "model": pure_gap + r.car_adv + r.traffic_adv,
                             "base_car_traffic": r.car_adv + r.traffic_adv,
                             "base_last_delta": last[key]})
        ev = pd.DataFrame(rows)
        if ev.empty:
            return result("FAIL", notes="no evaluable pair-races")
        for c in ("model", "base_car_traffic", "base_last_delta"):
            ev[f"ae_{c}"] = (ev.rel - ev[c]).abs()
        mae = {c: f(ev[f"ae_{c}"].mean()) for c in ("model", "base_car_traffic", "base_last_delta")}
        comp = {}
        for b in ("base_car_traffic", "base_last_delta"):
            stat = lambda d, b=b: float((d[f"ae_{b}"] - d["ae_model"]).mean())  # > 0 = model better
            lo, hi = cluster_bootstrap(ev, "race_id", stat)
            comp[b] = {"mae_gain_s": f(stat(ev)), "ci95": [f(lo), f(hi)], "model_better": bool(lo > 0)}
        ok = all(v["model_better"] for v in comp.values())
        return result("PASS" if ok else "FAIL", mae_s=mae, vs_baselines=comp, n_pair_races=int(len(ev)),
                      n_races=int(ev.race_id.nunique()),
                      design="2018-2024, rounds k >= 5, one row per unordered matched pair per race. Model: "
                             "shrunk pure of each driver over rounds < k of the same season (>= 3 prior races; "
                             "normal-normal shrinkage toward the field's prior mean with tau^2 estimated from "
                             "rounds < k only) differenced, plus race k's car and traffic identity terms. "
                             "Baselines: car + traffic only, and the pair's last matched race-mean relative pace "
                             "earlier in the season. Evaluated on pair-races where all three exist; MAE; paired "
                             "bootstrap clustered by race. PASS iff the model beats both with CI > 0. The car "
                             "term is fitted on all races (retrospective, as the doc allows).")

    def _validate_v3_tier3(self) -> Dict[str, Any]:
        cov = self.q(f"""
            SELECT COUNT(*) AS n, AVG(CASE WHEN n_peers >= 1 THEN 1.0 ELSE 0.0 END) AS share1,
                   AVG(CASE WHEN n_peers >= 2 THEN 1.0 ELSE 0.0 END) AS share2,
                   AVG(CASE WHEN n_peers >= 5 THEN 1.0 ELSE 0.0 END) AS share5
            FROM fct_driver_isolation_lap
            WHERE race_year BETWEEN {DECISION_YEARS[0]} AND {DECISION_YEARS[1]}
        """).iloc[0]
        # Since WI-16b (2026-09-30) relative_pace_gain_s is adjusted by the fitted age curve;
        # the seed-ΔC version is kept in relative_pace_seed_adj_gain_s and reported alongside.
        has_seed = bool(self.q("""
            SELECT COUNT(*) AS n FROM information_schema.columns
            WHERE table_name = 'fct_driver_isolation_pair_lap' AND column_name = 'relative_pace_seed_adj_gain_s'
        """).n.iloc[0])
        seed_col = "relative_pace_seed_adj_gain_s" if has_seed else "NULL::DOUBLE"
        var = self.q(f"""
            WITH p AS (
                SELECT race_id, driver_id, peer_driver_id, relative_pace_gain_s AS adj, relative_pace_raw_gain_s AS raw,
                       {seed_col} AS seed
                FROM fct_driver_isolation_pair_lap
                WHERE driver_id < peer_driver_id AND race_year BETWEEN {DECISION_YEARS[0]} AND {DECISION_YEARS[1]}
                  AND relative_pace_gain_s IS NOT NULL AND relative_pace_raw_gain_s IS NOT NULL
            ),
            g AS (
                SELECT race_id, driver_id, peer_driver_id, COUNT(*) AS n,
                       VAR_SAMP(adj) * (COUNT(*) - 1) AS ss_adj, VAR_SAMP(raw) * (COUNT(*) - 1) AS ss_raw,
                       VAR_SAMP(seed) * (COUNT(*) - 1) AS ss_seed
                FROM p GROUP BY ALL HAVING COUNT(*) >= 3
            )
            SELECT COUNT(*) AS n_pairs, SUM(n) AS n_laps, SUM(ss_adj) / SUM(n - 1) AS var_adj,
                   SUM(ss_raw) / SUM(n - 1) AS var_raw, SUM(ss_seed) / SUM(n - 1) AS var_seed
            FROM g
        """).iloc[0]
        thr = THRESHOLDS["V3_tier3_coverage"]["pass"]
        s_cov = grade_lower(float(cov.share1), thr)
        s_var = "PASS" if float(var.var_adj) < float(var.var_raw) else "FAIL"
        return {
            "status": "PASS" if (s_cov == "PASS" and s_var == "PASS") else "FAIL",
            "V3_tier3_coverage": result(s_cov, share_ge1_peer=f(cov.share1), share_ge2=f(cov.share2),
                                        share_ge5=f(cov.share5), n_omega_laps=int(cov.n), threshold=thr),
            "V3_tier3_age_adjustment": result(s_var, pooled_within_pair_var_adjusted=f(var.var_adj),
                                              pooled_within_pair_var_raw=f(var.var_raw),
                                              reduction=f(1 - var.var_adj / var.var_raw),
                                              report_seed_adjusted_reduction=(
                                                  f(1 - var.var_seed / var.var_raw) if has_seed else None),
                                              n_pairs=int(var.n_pairs), n_pair_laps=int(var.n_laps),
                                              design="Pooled within-pair (race, unordered pair, >= 3 pair-laps) "
                                                     "lap-to-lap variance of the age-adjusted vs the raw delta."),
        }

    # ── V4 ──────────────────────────────────────────────────────────────────────────
    def _validate_v4(self) -> Dict[str, Any]:
        out = {}
        for key, fn in [("V4a", self._validate_v4a), ("V4b", self._validate_v4b), ("V4c", self._validate_v4c)]:
            print(f"  {key}...")
            out[key] = fn()
        return out

    def _validate_v4a(self) -> Dict[str, Any]:
        df = self.q(f"""
            SELECT r.race_year, r.race_id, r.driver_id, CAST(r.age_in_stint AS DOUBLE) AS age,
                   r.driver_skill_residual_s AS resid, r.fuel_mass_kg,
                   s.weight_penalty_s / NULLIF(s.fuel_mass_kg, 0) AS wpf, s.fuel_consumption_rate_kg_per_lap AS burn
            FROM int_lap_residual_decomposed AS r
            JOIN int_lap_fuel_state AS s USING (lap_id)
            WHERE r.correction_weight = 1.0 AND NOT COALESCE(r.rainfall_flag, FALSE)
              AND r.compound IS NOT NULL AND r.compound NOT IN ('INTERMEDIATE', 'WET')
              AND r.lap_in_stint > 1 AND NOT COALESCE(r.cliff_onset_passed, FALSE)
              AND r.driver_skill_residual_s IS NOT NULL AND r.age_in_stint IS NOT NULL
              AND r.fuel_mass_kg IS NOT NULL
              AND r.race_year BETWEEN {DECISION_YEARS[0]} AND {DECISION_YEARS[1]}
        """)
        fit = within_ols_fuel(df, "resid", ["race_id", "driver_id"])
        wpf = float(df.wpf.median())
        total = wpf + fit["b_fuel_s_per_kg"]
        burn = float(df.burn.median())
        per = {}
        for y, g in df.groupby("race_year"):
            fy = within_ols_fuel(g, "resid", ["race_id", "driver_id"])
            per[int(y)] = {"b_fuel_s_per_kg": f(fy["b_fuel_s_per_kg"]),
                           "implied_total_s_per_kg": f(g.wpf.median() + fy["b_fuel_s_per_kg"]), "n": fy["n"]}
        lo, hi = THRESHOLDS["V4a_fuel"]["pass"]
        return result("PASS" if lo <= total <= hi else "FAIL", implied_total_s_per_kg=f(total),
                      seed_weight_penalty_median_s_per_kg=f(wpf), residual_fuel_coef_s_per_kg=f(fit["b_fuel_s_per_kg"]),
                      age_coef_s_per_lap=f(fit["b_age"]), corr_age_fuel_within=f(fit["corr_age_fuel"]),
                      n_laps=fit["n"], burn_kg_per_lap_median=f(burn),
                      implied_burn_off_gain_s_per_lap=f(total * burn), per_season=per, threshold=[lo, hi],
                      design="transform/analyses/deg_slope_fuel_deconfounding.sql's design, pooled 2018-2024: "
                             "driver_skill_residual_s ~ age + fuel_mass_kg, demeaned within (race, driver), on "
                             "clean dry pre-cliff laps with lap_in_stint > 1. Implied total = median seed factor "
                             "(weight_penalty_s / fuel_mass_kg) + the residual coefficient.")

    def _validate_v4b(self) -> Dict[str, Any]:
        df = self.q(f"""
            SELECT l.race_id, l.driver_id, CAST(l.age_in_stint AS DOUBLE) AS age, v.fuel_mass_kg,
                   l.pace_isolated_gain_s AS p
            FROM fct_driver_isolation_lap AS l
            JOIN int_driver_isolation_lap_values AS v USING (lap_id)
            WHERE NOT l.pure_is_extrapolated AND l.pace_isolated_gain_s IS NOT NULL
              AND l.race_year BETWEEN {DECISION_YEARS[0]} AND {DECISION_YEARS[1]}
        """)
        fit = within_ols_fuel(df, "p", ["race_id", "driver_id"])
        thr = THRESHOLDS["V4b_fuel_coeff"]["pass"]
        return result(grade_upper(abs(fit["b_fuel_s_per_kg"]), thr), fuel_coef_s_per_kg=f(fit["b_fuel_s_per_kg"]),
                      age_coef_s_per_lap=f(fit["b_age"]), n_laps=fit["n"], threshold=thr,
                      design="The V4a design on pace_isolated_gain_s over pre-cliff Ω laps, 2018-2024.")

    def _validate_v4c(self) -> Dict[str, Any]:
        df = self.q("""
            WITH l AS (
                SELECT race_year, race_id, lap_number, driver_id, compound, lap_time_s, car_iso_s, dirty_air_tax_s
                FROM int_driver_isolation_lap_values
                WHERE age_in_stint <= 5 AND car_iso_s IS NOT NULL
            )
            SELECT a.race_year, a.race_id, a.compound AS c_a, b.compound AS c_b,
                   (b.lap_time_s - a.lap_time_s) - (b.car_iso_s - a.car_iso_s)
                   - (b.dirty_air_tax_s - a.dirty_air_tax_s) AS a_faster_s
            FROM l AS a JOIN l AS b
              ON a.race_id = b.race_id AND a.lap_number = b.lap_number AND a.compound <> b.compound
        """)
        df["ra"] = [hardness(y, c) for y, c in zip(df.race_year, df.c_a)]
        df["rb"] = [hardness(y, c) for y, c in zip(df.race_year, df.c_b)]
        df = df.dropna(subset=["ra", "rb"])
        df = df[df.ra > df.rb]  # a = softer
        per = {}
        for y, g in df.groupby("race_year"):
            race_means = g.groupby("race_id").a_faster_s.mean()
            per[int(y)] = {"softer_faster_by_s": f(g.a_faster_s.mean()), "n_pairs": int(len(g)),
                           "n_races": int(race_means.size),
                           "share_races_softer_faster": f((race_means > 0).mean())}
        dec = {y: v for y, v in per.items() if DECISION_YEARS[0] <= y <= DECISION_YEARS[1]}
        ok = all(v["softer_faster_by_s"] is not None and v["softer_faster_by_s"] > 0 for v in dec.values())
        return result("PASS" if ok else "FAIL", per_season=per, confirmation_2025=per.get(CONFIRM_YEAR),
                      design="Same-(race, lap) pairs on different dry compounds, both at tyre age <= 5, Ω laps "
                             "with a car term. Raw lap-time gap, net of the two car terms and the two dirty-air "
                             "taxes (the compound component is NOT removed: this checks the direction the seed "
                             "must reproduce). PASS iff the softer tyre is faster on average in every season "
                             "2018-2024.")

    # ── V5 ──────────────────────────────────────────────────────────────────────────
    def _validate_v5(self) -> Dict[str, Any]:
        out = {}
        for key, fn in [("V5a", self._validate_v5a), ("V5b", self._validate_v5b), ("V5d", self._validate_v5d)]:
            print(f"  {key}...")
            out[key] = fn()
        out["V5c"] = result(NA, notes=TACTICAL_NA)
        out["V5_sign_flips_report"] = self._v5_sign_flips()
        return out

    @staticmethod
    def _lag1(df: pd.DataFrame, e: str) -> float:
        d = df.sort_values(["stint_id", "lap_number"]).copy()
        d["e_prev"] = d.groupby("stint_id")[e].shift()
        d["lap_prev"] = d.groupby("stint_id").lap_number.shift()
        d = d[(d.lap_number - d.lap_prev) == 1]
        den = np.sqrt((d[e] ** 2).sum() * (d.e_prev ** 2).sum())
        return float((d[e] * d.e_prev).sum() / den) if den > 0 else np.nan

    def _validate_v5a(self) -> Dict[str, Any]:
        df = self.q("""
            SELECT l.race_year, l.stint_id, l.lap_number,
                   l.pace_isolated_gain_s - (s.line_mean_pace_gain_s
                        + s.line_slope_s_per_lap2 * (l.age_in_stint - s.line_mean_age_laps)) AS e
            FROM fct_driver_isolation_lap AS l
            JOIN int_driver_isolation_stint_tyre AS s USING (stint_id)
            WHERE l.tyre_phase IN ('early', 'mid') AND NOT l.is_recovery AND l.pace_isolated_gain_s IS NOT NULL
              AND s.line_slope_s_per_lap2 IS NOT NULL
        """)
        per = {int(y): f(self._lag1(g, "e")) for y, g in df.groupby("race_year")}
        rho = self._lag1(df[df.race_year.between(*DECISION_YEARS)], "e")
        thr = THRESHOLDS["V5a_autocorr"]["pass"]
        return result(grade_upper(abs(rho), thr), lag1_autocorr=f(rho), per_season=per, threshold=thr,
                      design="Residual of pace_isolated_gain_s around each stint's line (line laps: early/mid, "
                             "not recovery), pooled lag-1 over laps exactly one apart, 2018-2024.")

    def _jitter(self, lap_col: str, stint_col: str, stint_se: str, stint_n: str) -> Dict[str, Any]:
        win = self.q(f"""
            SELECT race_year, stint_id, STDDEV_SAMP({lap_col}) AS sd, COUNT(*) AS n
            FROM fct_driver_isolation_lap WHERE {lap_col} IS NOT NULL
            GROUP BY ALL HAVING COUNT(*) >= 3
        """)
        st = self.q(f"""
            SELECT race_year, VAR_SAMP({stint_col}) - AVG({stint_se} * {stint_se}) AS tau2, COUNT(*) AS n
            FROM fct_driver_isolation_stint
            WHERE stint_phase = 'all' AND {stint_n} >= 6 AND {stint_col} IS NOT NULL
            GROUP BY ALL
        """).set_index("race_year")
        per = {}
        for y, g in win.groupby("race_year"):
            t2 = st.tau2.get(y, np.nan)
            tau = np.sqrt(t2) if np.isfinite(t2) and t2 > 0 else np.nan
            per[int(y)] = {"median_within_stint_sd_s": f(g.sd.median()), "tau_stint_s": f(tau),
                           "ratio": f(g.sd.median() / tau) if np.isfinite(tau) else None, "n_stints": int(len(g))}
        dec = [v["ratio"] for y, v in per.items() if DECISION_YEARS[0] <= y <= DECISION_YEARS[1] and v["ratio"] is not None]
        med = float(np.median(dec)) if dec else np.nan
        t = THRESHOLDS["V5b_jitter"]
        status = "FAIL" if not np.isfinite(med) or med > t["fail"] else ("PASS" if med <= t["pass"] else "MARGINAL")
        return result(status, median_ratio=f(med), per_season=per, threshold=t,
                      design=f"Per season: median over stints (>= 3 windows) of the within-stint SD of {lap_col}, "
                             f"over tau = sqrt(VAR({stint_col}) - mean SE^2) on the stint mart's 'all' rows with "
                             f"{stint_n} >= 6. Verdict on the median of the 2018-2024 season ratios.")

    def _validate_v5b(self) -> Dict[str, Any]:
        return self._jitter("pure_skill_5lap_gain_s", "pure_skill_gain_s", "pure_skill_se_s", "n_pure_laps")

    def _validate_v5d(self) -> Dict[str, Any]:
        df = self.q("""
            SELECT race_year, stint_id, lap_number,
                   relative_pace_gain_s - AVG(relative_pace_gain_s) OVER (PARTITION BY stint_id) AS e
            FROM fct_driver_isolation_lap WHERE relative_pace_gain_s IS NOT NULL
        """)
        rho = self._lag1(df[df.race_year.between(*DECISION_YEARS)], "e")
        thr = THRESHOLDS["V5d_autocorr"]["pass"]
        auto = result(grade_upper(abs(rho), thr), lag1_autocorr=f(rho), threshold=thr,
                      per_season={int(y): f(self._lag1(g, "e")) for y, g in df.groupby("race_year")},
                      design="Lap-level relative_pace_gain_s around its stint mean, pooled lag-1 over laps exactly "
                             "one apart, 2018-2024.")
        jit = self._jitter("relative_pace_5lap_gain_s", "relative_pace_gain_s", "relative_pace_se_s", "n_pair_laps")
        n_pass = sum(SCORE[x["status"]] for x in (auto, jit))
        return {"V5d_autocorr": auto, "V5d_jitter": jit, "score": n_pass / 2,
                "status": "PASS" if n_pass == 2 else ("FAIL" if n_pass == 0 else "MARGINAL")}

    def _v5_sign_flips(self) -> Dict[str, Any]:
        df = self.q(f"""
            SELECT stint_id, lap_number, SIGN(pure_skill_5lap_gain_s) AS s
            FROM fct_driver_isolation_lap
            WHERE pure_skill_5lap_gain_s IS NOT NULL
              AND race_year BETWEEN {DECISION_YEARS[0]} AND {DECISION_YEARS[1]}
            ORDER BY stint_id, lap_number
        """)
        df["flip"] = (df.s != df.groupby("stint_id").s.shift()) & df.groupby("stint_id").s.shift().notna()
        flips = df.groupby("stint_id").flip.sum()
        return result("REPORT", share_stints_2plus_sign_changes=f((flips >= 2).mean()), n_stints=int(flips.size))

    # ── V6 ──────────────────────────────────────────────────────────────────────────
    def _validate_v6(self) -> Dict[str, Any]:
        return {k: result(NA, notes=TACTICAL_NA + " V6 carries no weight for pure or relative in the matrix.")
                for k in ("V6a", "V6b", "V6c")}

    # ── context ─────────────────────────────────────────────────────────────────────
    def _coverage(self) -> Dict[str, Any]:
        r = self._race()
        null = r[r.pure.isna()].copy()
        null["reason"] = np.select(
            [null.car_term_source == "unidentified", null.car_term_source == "not_estimated",
             null.car_iso_s.isna(), null.n_pure_laps.fillna(0) == 0],
            ["car term unidentified: team is an island in the era's teammate network",
             "car term not estimated: only one of the team's drivers has pre-cliff laps in the race",
             "car term missing (other)", "no pre-cliff Ω lap (every clean lap past the cliff)"],
            default="other")
        by_reason = null.groupby("reason").size().to_dict()
        islands = (null[null.car_term_source == "unidentified"]
                   .groupby(["constructor_id"]).agg(n=("driver_id", "size"),
                                                    years=("race_year", lambda s: f"{s.min()}-{s.max()}"),
                                                    drivers=("driver_id", lambda s: sorted(set(s))))
                   .reset_index().to_dict(orient="records"))
        return {"driver_races": int(len(r)), "with_pure": int(r.pure.notna().sum()),
                "without_pure": int(len(null)), "without_pure_share": f(len(null) / len(r)),
                "without_pure_by_reason": {k: int(v) for k, v in by_reason.items()},
                "without_pure_by_year": {int(k): int(v) for k, v in null.groupby("race_year").size().items()},
                "unidentified_by_constructor": islands}

    def _season_levels(self) -> Dict[str, Any]:
        df = self.q("""
            SELECT p.race_year, COUNT(*) AS n_laps,
                   AVG(CASE WHEN p.tyre_phase = 'cliff' THEN 1.0 ELSE 0.0 END) AS cliff_share,
                   AVG(CASE WHEN p.tyre_phase <> 'cliff' THEN p.y_s END) AS y_precliff_s,
                   AVG(CASE WHEN p.tyre_phase = 'cliff' THEN p.y_s END) AS y_cliff_s
            FROM int_driver_isolation_lap_panel AS p GROUP BY 1 ORDER BY 1
        """)
        r = self._race().groupby("race_year").pure.mean().rename("mean_race_pure_gain_s")
        df = df.merge(r, left_on="race_year", right_index=True)
        return {"per_season": [{k: (int(v) if k in ("race_year", "n_laps") else f(v)) for k, v in row.items()}
                               for row in df.to_dict(orient="records")],
                "note": "y_s is centred on each lap's field median over ALL Ω laps; cliff laps read fast (the seed's "
                        "cliff cost over-corrects), so pre-cliff laps sit above that median by roughly the "
                        "season's cliff share x the cliff gap, and mean pure (which uses pre-cliff laps) is shifted "
                        "by the same amount. It is a level shared by every driver in a season, not a ranking effect."}

    # ── examples ────────────────────────────────────────────────────────────────────
    def _validate_examples(self) -> Dict[str, Any]:
        examples = {}
        # Expected values: the 2026-09-29 run's (the WI doc's probe for 2021_19 was +0.05/41 and
        # for 2023_2 -0.40/40; see the build log's 2026-09-29T11:00 entry).
        probes = [
            ("2021_8", "VER", "HAM", 0.24, 57, "Styrian GP"),
            ("2021_19", "HAM", "VER", 0.178, 41, "São Paulo"),
            ("2023_2", "VER", "PER", -0.459, 37, "Saudi Arabian"),
        ]
        for race_id, d1, d2, expected_pace, expected_n, circuit in probes:
            r = self.q(f"""
                SELECT AVG(relative_pace_gain_s) AS rel, COUNT(*) AS n,
                       AVG(pace_gap_gain_s) AS pace_gap, AVG(car_advantage_gain_s) AS car_adv,
                       AVG(traffic_advantage_gain_s) AS traffic_adv
                FROM fct_driver_isolation_pair_lap
                WHERE race_id = '{race_id}' AND driver_id = '{d1}' AND peer_driver_id = '{d2}'
            """).iloc[0]
            pace = float(r.rel) if pd.notna(r.rel) else np.nan
            n = int(r.n)
            pace_diff = abs(pace - expected_pace) if np.isfinite(pace) else np.nan
            lap_diff = abs(n - expected_n) / expected_n * 100 if n > 0 else np.nan
            examples[f"{d1}_vs_{d2}_{race_id}"] = {
                "race": race_id, "circuit": circuit, "driver_1": d1, "driver_2": d2,
                "expected_pace_s_lap": expected_pace, "expected_n_laps": expected_n,
                "measured_pace_s_lap": f(round(pace, 3)) if np.isfinite(pace) else None, "measured_n_laps": n,
                "identity_split": {"pace_gap": f(r.pace_gap), "car_advantage": f(r.car_adv),
                                   "traffic_advantage": f(r.traffic_adv)},
                "pace_diff": f(round(pace_diff, 3)) if np.isfinite(pace_diff) else None,
                "lap_diff_pct": f(round(lap_diff, 1)) if np.isfinite(lap_diff) else None,
                "within_tolerance": bool(np.isfinite(pace_diff) and pace_diff <= 0.05 and lap_diff <= 10),
            }
        return examples

    # ── method scores ───────────────────────────────────────────────────────────────
    def _sub(self, path: str) -> Dict[str, Any]:
        node: Any = self.results
        for k in path.split("."):
            node = node[k]
        return node

    def _compute_method_scores(self) -> Dict[str, Any]:
        """The doc's matrix. Each group's score is the weighted mean of its graded sub-checks;
        method_score = 0 if any critical sub-check FAILs (the strict, literal reading: V1a,
        V1b and V1c are each 'tests' of the critical V1 row). The test-level reading (a
        critical group fails only when its own score is below 0.5) is reported alongside."""
        matrix = {
            "pure": [
                ("V1", 2.0, [("V1.V1a_pure", 1, True), ("V1.V1b", 1, True), ("V1.V1c", 1, True)]),
                ("V2", 2.0, [("V2.V2a", 1, True), ("V2.V2b", 1, False), ("V2.V2c.V2c_ii", 1, False),
                             ("V2.V2e", 1, False)]),
                ("V3", 1.0, [("V3.V3a", 1, False), ("V3.V3b", 1, False), ("V3.V3c", 1, False),
                             ("V3.V3d", 1, False)]),
                ("V4", 0.5, [("V4.V4a", 0.5, False), ("V4.V4b", 1, False), ("V4.V4c", 0.5, False)]),
                ("V5", 1.0, [("V5.V5a", 1, False), ("V5.V5b", 1, False)]),
            ],
            "relative": [
                ("V3_tier3", 2.0, [("V3.V3_tier3.V3_tier3_coverage", 1, True),
                                   ("V3.V3_tier3.V3_tier3_age_adjustment", 1, True)]),
                ("V4", 0.5, [("V4.V4c", 1, False)]),
                ("V5", 1.0, [("V5.V5d.V5d_autocorr", 1, False), ("V5.V5d.V5d_jitter", 1, False)]),
            ],
        }

        def grade_of(s: float, crit_fail: bool) -> str:
            if crit_fail or s < 0.5:
                return "F"
            return "A" if s >= 0.9 else ("B" if s >= 0.75 else "C")

        out = {}
        for rating, groups in matrix.items():
            num = den = 0.0
            n_app = n_pass = 0
            crit_fail_strict, crit_fail_group = [], []
            detail = {}
            for name, weight, subs in groups:
                s_num = s_den = 0.0
                statuses = {}
                for path, w, critical in subs:
                    node = self._sub(path)
                    st = node.get("status")
                    statuses[path] = st
                    if st not in SCORE:
                        continue
                    n_app += 1
                    n_pass += st == "PASS"
                    s_num += w * SCORE[st]
                    s_den += w
                    if critical and st == "FAIL":
                        crit_fail_strict.append(path)
                g_score = s_num / s_den if s_den else None
                if g_score is not None:
                    num += weight * g_score
                    den += weight
                    if any(c for _, _, c in subs) and g_score < 0.5:
                        crit_fail_group.append(name)
                detail[name] = {"weight": weight, "score": f(g_score), "sub_checks": statuses}
            raw = num / den if den else None
            strict = 0.0 if crit_fail_strict else raw
            lenient = 0.0 if crit_fail_group else raw
            out[rating] = {
                "method_score": f(strict), "grade": grade_of(raw or 0.0, bool(crit_fail_strict)),
                "weighted_score_before_critical_rule": f(raw),
                "tests_applicable": n_app, "tests_passed": n_pass,
                "critical_failed": len(crit_fail_strict), "critical_failed_checks": crit_fail_strict,
                "test_level_reading": {"method_score": f(lenient),
                                       "grade": grade_of(raw or 0.0, bool(crit_fail_group)),
                                       "critical_groups_failed": crit_fail_group},
                "groups": detail,
            }
        out["tactical"] = {"method_score": None, "grade": "cancelled", "notes": TACTICAL_NA}
        return out

    # ── outputs ─────────────────────────────────────────────────────────────────────
    def write_seed(self, output_path: str, report_path: str = ""):
        ms = self.results.get("method_scores", {})
        sub = self.results.get("substrate", {})
        rows = []
        for rating in ("pure", "relative"):
            s = ms.get(rating, {})
            rows.append({
                "rating": rating, "method_score": s.get("method_score"), "grade": s.get("grade"),
                "tests_applicable": s.get("tests_applicable"), "tests_passed": s.get("tests_passed"),
                "critical_failed": s.get("critical_failed"),
                "validated_at": datetime.now().isoformat(timespec="seconds"),
                "substrate": f"{sub.get('git_sha')} {sub.get('database_mtime')}",
                "report_path": report_path,
            })
        pd.DataFrame(rows).to_csv(output_path, index=False)
        print(f"Seed written to {output_path}")

    @staticmethod
    def _stat_line(key: str, d: Dict[str, Any]) -> str:
        st = d.get("status", "?")
        keys = ["median_spearman", "median_pearson", "ratio", "correlation", "max_abs_mean_diff_s",
                "spearman", "median_spearman_field", "median_spearman_massey", "dirty_minus_clean_gap_s",
                "implied_total_s_per_kg", "fuel_coef_s_per_kg", "lag1_autocorr", "median_ratio",
                "share_ge1_peer", "reduction", "within_driver_race_mean_diff_s",
                "share_stints_2plus_sign_changes"]
        bits = []
        for k in keys:
            if k in d and d[k] is not None:
                v = d[k]
                bits.append(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}")
        for k in ("ci95", "gap_ci95"):
            if k in d and d[k] and all(x is not None for x in d[k]):
                bits.append(f"{k}=[{d[k][0]:.3f}, {d[k][1]:.3f}]")
        if "mae_s" in d:
            bits.append("MAE " + ", ".join(f"{k}={v:.3f}" for k, v in d["mae_s"].items() if v is not None))
            bits.append("gain " + ", ".join(
                f"{k}={v['mae_gain_s']:.3f} [{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}]"
                for k, v in d["vs_baselines"].items()))
        if "by_tercile" in d:
            bits.append(", ".join(f"{k} tercile spearman={v['spearman']:.3f} (n={v['n_driver_seasons']})"
                                  for k, v in d["by_tercile"].items() if v["spearman"] is not None))
        if key == "V2b" and d.get("worst_cell"):
            w = d["worst_cell"]
            bits.append(f"worst {w['race_year']} {w['pair']} n={w['n']}")
        if key == "V4a" and "residual_fuel_coef_s_per_kg" in d:
            bits.append(f"seed {d['seed_weight_penalty_median_s_per_kg']:.3f} + residual "
                        f"{d['residual_fuel_coef_s_per_kg']:+.4f} s/kg")
        if key == "V4c" and "per_season" in d:
            bits.append("softer faster by (s): " + ", ".join(
                f"{y}: {v['softer_faster_by_s']:.3f}" for y, v in d["per_season"].items()))
        if key == "V1b" and "rule_change_check" in d:
            rc = d["rule_change_check"]
            fmt = lambda x: "n/a" if x is None else f"{x:.3f}"
            bits.append(f"2021-22={fmt(rc['pair_2021_2022'])} vs required >= {fmt(rc['required_min'])}")
        if "notes" in d and st == NA:
            bits.append(d["notes"])
        return f"- **{key}**: {st}" + (f" ({'; '.join(bits)})" if bits else "")

    def write_report(self, output_dir: str):
        out = Path(output_dir) / "validation-report.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        sub = self.results.get("substrate", {})
        lines = ["# WI-16b validation report", "",
                 f"Generated {datetime.now().isoformat(timespec='seconds')} on `{sub.get('database')}` "
                 f"(mtime {sub.get('database_mtime')}, git {sub.get('git_sha')}).",
                 f"Car term: {sub.get('car_fe_fit')}.", "",
                 "Decisions use 2018-2024; 2025 is confirmation only. Thresholds are the WI doc's.", ""]
        for v in ("V1", "V2", "V3", "V4", "V5", "V6"):
            lines.append(f"## {v}")
            lines.append("")
            for k, d in self.results.get(v, {}).items():
                if not isinstance(d, dict):
                    continue
                nested = {kk: vv for kk, vv in d.items() if isinstance(vv, dict) and "status" in vv}
                if nested and k in ("V2c", "V3_tier3", "V5d"):
                    for kk, vv in nested.items():
                        lines.append(self._stat_line(kk, vv))
                else:
                    lines.append(self._stat_line(k, d))
            lines.append("")
        cov = self.results.get("coverage", {})
        lines += ["## Coverage", "",
                  f"- Driver-races without pure: {cov.get('without_pure')} of {cov.get('driver_races')} "
                  f"({(cov.get('without_pure_share') or 0) * 100:.1f}%)"]
        for k, v in cov.get("without_pure_by_reason", {}).items():
            lines.append(f"  - {k}: {v}")
        for row in cov.get("unidentified_by_constructor", []):
            lines.append(f"  - island {row['constructor_id']} {row['years']}: {row['n']} driver-races ({', '.join(row['drivers'])})")
        lines += ["", "## Season levels", "", "| season | cliff share | y pre-cliff | y cliff | mean race pure |",
                  "| --: | --: | --: | --: | --: |"]
        for row in self.results.get("season_levels", {}).get("per_season", []):
            lines.append(f"| {row['race_year']} | {row['cliff_share']:.3f} | {row['y_precliff_s']:+.3f} | "
                         f"{row['y_cliff_s']:+.3f} | {row['mean_race_pure_gain_s']:+.3f} |")
        lines += ["", "## Worked examples", ""]
        sg = lambda x: "n/a" if x is None else f"{x:+.3f}"  # a car term can be missing
        for k, e in self.results.get("examples", {}).items():
            idt = e["identity_split"]
            lines.append(f"- **{k}**: expected {e['expected_pace_s_lap']:+.3f}/{e['expected_n_laps']}, measured "
                         f"{sg(e['measured_pace_s_lap'])}/{e['measured_n_laps']} (within tolerance: "
                         f"{e['within_tolerance']}); split pace gap {sg(idt['pace_gap'])}, car "
                         f"{sg(idt['car_advantage'])}, traffic {sg(idt['traffic_advantage'])}")
        lines += ["", "## Method scores", ""]
        for rating, s in self.results.get("method_scores", {}).items():
            if rating == "tactical":
                lines.append(f"- **tactical**: cancelled")
                continue
            tl = s["test_level_reading"]
            lines.append(f"- **{rating}**: {s['method_score']:.3f} ({s['grade']}); weighted score before the "
                         f"critical rule {s['weighted_score_before_critical_rule']:.3f}; critical fails "
                         f"{s['critical_failed_checks'] or 'none'}; {s['tests_passed']}/{s['tests_applicable']} "
                         f"sub-checks PASS. Test-level reading: {tl['method_score']:.3f} ({tl['grade']}).")
            for g, gd in s["groups"].items():
                lines.append(f"  - {g} (weight {gd['weight']}): {gd['score']:.3f}" if gd["score"] is not None
                             else f"  - {g}: n/a")
        out.write_text("\n".join(lines) + "\n")
        print(f"Report written to {out}")

    def write_validation_json(self, output_dir: str):
        out = Path(output_dir) / "validation.json"
        out.parent.mkdir(parents=True, exist_ok=True)

        def conv(o):
            if isinstance(o, dict):
                return {str(k): conv(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)):
                return [conv(v) for v in o]
            if isinstance(o, (np.bool_, bool)):
                return bool(o)
            if isinstance(o, np.integer):
                return int(o)
            if isinstance(o, (np.floating, float)):
                return f(o)
            return o

        out.write_text(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"),
                                   "database": str(self.db_path), "results": conv(self.results)}, indent=2))
        print(f"Validation JSON written to {out}")


def main():
    parser = argparse.ArgumentParser(description="WI-16b driver isolation validation")
    parser.add_argument("--db", default="data/dev.duckdb", help="DuckDB warehouse (opened read-only)")
    parser.add_argument("--output-dir", default=None,
                        help="default: _roadmap/_fixes/_evidence/wi-16-<date>/")
    parser.add_argument("--write-seed", action="store_true",
                        help="write transform/seeds/driver_isolation_method_scores.csv from the method scores")
    args = parser.parse_args()
    if args.output_dir is None:
        args.output_dir = f"_roadmap/_fixes/_evidence/wi-16-{datetime.now():%Y-%m-%d}"

    v = DriverIsolationValidator(db_path=args.db)
    v.run_all_validations()
    v.write_validation_json(args.output_dir)
    v.write_report(args.output_dir)
    if args.write_seed:
        v.write_seed("transform/seeds/driver_isolation_method_scores.csv",
                     report_path=str(Path(args.output_dir) / "validation-report.md"))
    print("\nValidation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
