"""DA-03 estimator for the micro-sector dirty-air cost (W11 option C), built in DA-02.

    y_{d,l,m} = alpha_{d,l} + sum_k beta_k * 1[entry gap in band k]
                + gamma * aheadResid_{l,m} + delta * (tyre age x micro-sector) + e

y is int_microsector_proximity.y_s (micro-sector time minus the field median for the
same race, lap and micro-sector, seconds, positive = slower). alpha is a driver-lap
fixed effect, so form, fuel and tyres at lap level drop out. Only the ENTRY gap
prices the micro-sector. Standard errors are clustered by race (CRV1).

THIS FILE IS THE ESTIMATOR, NOT A RESULT. It has not been run on the real panel.
The design note (_roadmap/_dirty-air/wi/DA-design-note.md section 3) requires the
pre-registration to be committed BEFORE the fit, and the fit is refused unless the
SHA-256 of the pre-registration file is passed on the command line, so a fit cannot
be run by accident or after quietly editing the registered choices:

    python -m tasks.coefficients.fit_dirty_air_microsector --print-prereg-sha256
    python -m tasks.coefficients.fit_dirty_air_microsector --db <warehouse> \
        --prereg-sha256 <that hash> --out <json>

The unit tests (tests/test_fit_dirty_air_microsector.py) exercise the estimator on a
synthetic panel with a planted effect; they never read the warehouse.

Specs (all on the valid rows: invalid_reason IS NULL, y_s and ahead_y_s present):
    bands   five entry-gap bands, reference >3 s (the design note's step function)
    lt1     merged: gap < 1 s, 1-1.5, 1.5-2, 2-3 (the GATE quantity is beta(lt1))
    p1      lt1 + the car BEHIND within 1 s on the same lap (placebo P1)
    p2      lt1 + a 3-5 s band against >5 s (placebo P2: a level shift not tied to
            the gap would show here). Gate (option (b), 2026-10-27): the 3-5 s
            interval is no wider than 0.008 s and |P2| < 1/3 of |beta(lt1)|, pooled
            AND in each era; "interval includes 0" is reported only.
    lead    exit-gap bands on y (the lead window: must be 0 or below, not a clean
            placebo because losing time opens the gap mechanically)
    p3      placebo P3 (DA-02P amendment): lt1 with each of its four gap-band dummies
            interacted with int_microsector_corner_class.corner_class (low, medium,
            high, flat, mixed, straight, link), plus class main effects; driver-race by
            corner-class fixed effects (which span the class main effects, so those are
            carried by the FE rather than as separate coefficients); tyre_life x
            corner_class in place of tyre_life x micro-sector. The two registered
            exception races 2020_9 and 2020_16 (no geometry) are dropped from p3 only.
            Gate: (a) beta(lt1, high) > 0 with a 95% interval excluding 0; (b)
            beta(lt1, high) - beta(lt1, low) > 0 with a 95% interval excluding 0;
            pooled AND in each era. high is 200 to < 280 km/h; flat (>= 280) is never
            part of high. beta(lt1, flat), flat - straight, straight, high - straight
            and the rest are REPORTED ONLY and cannot pass or fail P3.
    drs_closed    lt1 on rows with drs_open FALSE (gap-based; reported only)
    drs_location  lt1 after dropping every micro-sector where any car had DRS open in
                  that race (location-based; reported only)
    lag_gap the lagged-gap check (DA-02P amendment, owner ruling 1 option (a)): lt1
            with its four bands on the gap at boundary k - 1 (the entry of micro-
            sector m - 1) instead of boundary k. y uses the crossings of boundaries k
            and k + 1, the entry gap uses k, so a timing error at k moves both the
            gap and y; the lagged gap shares no crossing with y. Rows with no valid
            m - 1 row are dropped from lag_gap only. Gated: beta(lag lt1) > 0 with a
            95% interval excluding 0, pooled AND in each era. The primary is
            unchanged; lag_gap never replaces it.

The fit also refuses unless the pre-registration is committed at HEAD unchanged and
its hash equals the one recorded in the build log (DA-02P `prereg_sha256`).

--followup runs DA-03F, the slow-corner follow-up (a separate test with its own
pre-registration, wi/DA-03F-preregistration.md, and build-log item DA-03F): lt1 and p3
unchanged on a venue-restricted, blocking-cut sample, with its own S/R/N verdict. It
refuses unless that file is locked under DA-03F and DA-03F records no run yet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyfixest as pf  # type: ignore
from scipy import stats

from .provenance import get_git_sha

log = logging.getLogger("fit_dirty_air_microsector")

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
PREREG_PATH = REPO_ROOT / "_roadmap" / "_archive" / "_dirty-air" / "wi" / "DA-03-preregistration.md"
BUILD_LOG_PATH = REPO_ROOT / "_roadmap" / "_archive" / "_dirty-air" / "status" / "build-log.json"
# The build-log item whose `prereg_sha256` field records the committed file's hash.
PREREG_LOG_ITEM = "DA-02P"
# DA-03F, the slow-corner follow-up (its own pre-registration, its own build-log item).
FOLLOWUP_PREREG_PATH = (REPO_ROOT / "_roadmap" / "_archive" / "_dirty-air" / "wi"
                        / "DA-03F-preregistration.md")
FOLLOWUP_LOG_ITEM = "DA-03F"

BAND_ORDER = ["0_lt0.5", "1_0.5to1", "2_1to1.5", "3_1.5to2", "4_2to3"]
ERA_BREAK = 2022  # 2022 ground-effect regulations (design note section 7)

# Pre-registered gate constants (DA-03 doc, design note section 6, phase 2)
P1_MAX_SHARE_OF_BETA = 1.0 / 3.0

# P2 size limit (owner note in the DA-02P amendment draft). The owner chose option (b)
# on 2026-10-27, replacing "the P2 interval includes 0", and confirmed its two numbers
# the same day. p2_precision_check is in GATE_CHECKS (as p2_precision_pass).
# Option (a), not chosen: gate 1 would also need beta(lt1) >= share x (lap figure /
# micro-sectors per lap). Its numbers stay None and it is NOT in GATE_CHECKS.
GATE1_LAP_FIGURE_S: float | None = None            # [OWNER TO SET] s per lap, cited source
GATE1_MIN_SHARE_OF_LAP_FIGURE: float | None = None  # [OWNER TO SET]
# Option (b), owner-confirmed 2026-10-27: P2 needs a 3-5 s vs >5 s interval no wider
# than 0.008 s (b1) and a point estimate with |P2| under 1/3 of |beta(lt1)| (b2).
P2_MAX_CI_WIDTH_S: float | None = 0.008
P2_MAX_SHARE_OF_BETA: float | None = 1.0 / 3.0

# P3 (DA-02P amendment). Classes estimated in p3; no_geometry rows are the two
# registered exception races and are dropped with them.
P3_CLASSES = ["low", "medium", "high", "flat", "mixed", "straight", "link"]
P3_EXCEPTION_RACES = ("2020_9", "2020_16")
LT1_BANDS = ["lt1", "g1_1p5", "g1p5_2", "g2_3"]
# lag_gap: the same four bands on the gap at boundary k - 1 (DA-02P amendment).
LAG_BANDS = ["lag_" + b for b in LT1_BANDS]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prereg_lock_errors(prereg: Path = PREREG_PATH,
                       build_log: Path = BUILD_LOG_PATH,
                       log_item: str = PREREG_LOG_ITEM) -> list[str]:
    """Why the pre-registration is not locked; [] when it is.

    Locked means: the file is committed at HEAD, the working copy is byte-identical to
    the committed blob (so the hash the fit checks is the committed file's hash), and
    the build log records that same hash in item `log_item`'s `prereg_sha256` (default
    PREREG_LOG_ITEM, the DA-02P item; the DA-03F follow-up passes its own item)."""
    errors: list[str] = []
    digest = sha256_of(prereg)

    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(prereg.parent), *a], capture_output=True)

    top = git("rev-parse", "--show-toplevel")
    if top.returncode != 0:
        errors.append(f"{prereg} is not inside a git work tree")
    else:
        rel = prereg.resolve().relative_to(Path(top.stdout.decode().strip()).resolve())
        head = git("show", f"HEAD:{rel.as_posix()}")
        if head.returncode != 0:
            errors.append(f"{rel.as_posix()} is not committed at HEAD")
        elif hashlib.sha256(head.stdout).hexdigest() != digest:
            errors.append(f"{rel.as_posix()} differs from its committed version at HEAD")
    try:
        items = json.loads(build_log.read_text())["items"]
        logged = next((i.get("prereg_sha256") for i in items
                       if i.get("id") == log_item), None)
    except (OSError, ValueError, KeyError, TypeError) as e:
        errors.append(f"cannot read the build log {build_log}: {e}")
    else:
        if not logged:
            errors.append(f"build log item {log_item} records no prereg_sha256")
        elif logged != digest:
            errors.append(f"build log {log_item}.prereg_sha256 ({logged}) does not "
                          f"match the file ({digest})")
    return errors


def load_panel(db_path: Path) -> pd.DataFrame:
    """Valid micro-sector rows with the columns every spec needs.

    corner_class comes from int_microsector_corner_class on (race, micro-sector).
    ms_drs_any_open is TRUE when any car, on any lap of the race (valid row or not),
    had DRS open at the entry or exit of that micro-sector: the drs_location drop.
    lag_gap_ahead_s is the same driver's gap_ahead_s at boundary k - 1 (micro-sector
    m - 1, across the lap line for m = 0), taken only when that row exists, is the
    boundary directly before, and is itself valid (invalid_reason IS NULL); NULL
    otherwise. It is read before the validity filter, so the m - 1 row need not have
    y_s."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.sql(
            """
            WITH drs_zone AS (
                SELECT race_year, race_id, microsector,
                       COALESCE(BOOL_OR(drs_open), FALSE) AS ms_drs_any_open
                FROM int_microsector_proximity
                GROUP BY race_year, race_id, microsector
            ),
            n_ms AS (
                SELECT MAX(microsector) + 1 AS n FROM int_microsector_proximity
            ),
            lagged AS (
                SELECT
                    p.microsector_id,
                    p.lap_number * n.n + p.microsector AS boundary_k,
                    LAG(p.lap_number * n.n + p.microsector) OVER w AS prev_boundary_k,
                    LAG(p.invalid_reason IS NULL) OVER w AS prev_valid,
                    LAG(p.gap_ahead_s) OVER w AS prev_gap_ahead_s
                FROM int_microsector_proximity AS p
                CROSS JOIN n_ms AS n
                WINDOW w AS (
                    PARTITION BY p.race_year, p.race_id, p.driver_id
                    ORDER BY p.lap_number, p.microsector
                )
            )
            SELECT
                p.microsector_id, p.lap_id, p.race_year, p.race_id, p.driver_id,
                p.lap_number, p.microsector, p.y_s, p.ahead_y_s, p.gap_ahead_s,
                p.gap_band, p.gap_behind_s, p.behind_lap_number, p.exit_gap_ahead_s,
                l.tyre_life, p.drs_open, z.ms_drs_any_open, c.corner_class,
                CASE
                    WHEN g.prev_boundary_k = g.boundary_k - 1
                        AND COALESCE(g.prev_valid, FALSE)
                        THEN g.prev_gap_ahead_s
                END AS lag_gap_ahead_s
            FROM int_microsector_proximity AS p
            LEFT JOIN stg_laps AS l ON p.lap_id = l.lap_id
            LEFT JOIN int_microsector_corner_class AS c
                ON p.race_year = c.race_year AND p.race_id = c.race_id
                AND p.microsector = c.microsector
            LEFT JOIN drs_zone AS z
                ON p.race_year = z.race_year AND p.race_id = z.race_id
                AND p.microsector = z.microsector
            LEFT JOIN lagged AS g ON p.microsector_id = g.microsector_id
            WHERE p.invalid_reason IS NULL AND p.y_s IS NOT NULL
            """
        ).df()
    finally:
        con.close()


def add_regressors(panel: pd.DataFrame) -> pd.DataFrame:
    """Dummies for every spec. The reference band is >3 s throughout."""
    d = panel.copy()
    for band in BAND_ORDER:
        d["b_" + band.split("_", 1)[0]] = (d["gap_band"] == band).astype(float)
    g = d["gap_ahead_s"]
    d["lt1"] = (g < 1.0).astype(float)
    d["g1_1p5"] = ((g >= 1.0) & (g < 1.5)).astype(float)
    d["g1p5_2"] = ((g >= 1.5) & (g < 2.0)).astype(float)
    d["g2_3"] = ((g >= 2.0) & (g < 3.0)).astype(float)
    # lag_gap: the same bands on the gap at boundary k - 1. A row with no lagged gap
    # gets 0 here and is dropped by the lag_gap spec, never put in its reference band.
    if "lag_gap_ahead_s" in d.columns:
        lg = d["lag_gap_ahead_s"]
        d["lag_lt1"] = (lg < 1.0).astype(float)
        d["lag_g1_1p5"] = ((lg >= 1.0) & (lg < 1.5)).astype(float)
        d["lag_g1p5_2"] = ((lg >= 1.5) & (lg < 2.0)).astype(float)
        d["lag_g2_3"] = ((lg >= 2.0) & (lg < 3.0)).astype(float)
    # P2: split the reference band. Only rows beyond 3 s enter; 3-5 s against >5 s.
    d["far_3_5"] = ((g >= 3.0) & (g < 5.0)).astype(float)
    # P1: the car behind within 1 s, SAME lap only (a higher-lap car behind is
    # lapping this driver, a blue-flag case and not a following car).
    same_lap_behind = d["behind_lap_number"] == d["lap_number"]
    d["behind_lt1"] = (same_lap_behind & (d["gap_behind_s"] < 1.0)).astype(float)
    # Lead window: the exit gap, banded like the entry gap.
    e = d["exit_gap_ahead_s"]
    d["x_lt1"] = (e < 1.0).astype(float)
    d["x_1_3"] = ((e >= 1.0) & (e < 3.0)).astype(float)
    d["micro"] = d["microsector"].astype("category")
    # P3: band x corner-class dummies and tyre_life x corner-class slopes, and the
    # driver-race by corner-class fixed-effect key.
    if "corner_class" in d.columns:
        cc = d["corner_class"]
        for c in P3_CLASSES:
            in_c = (cc == c).astype(float)
            for b in LT1_BANDS:
                d[f"{b}__{c}"] = d[b] * in_c
            if "tyre_life" in d.columns:
                d[f"tyre__{c}"] = d["tyre_life"] * in_c
        d["dr_cc"] = (d["driver_id"].astype(str) + "|" + d["race_id"].astype(str)
                      + "|" + cc.astype(str))
    return d


def _tidy(fit, label: str, terms: list[str], n_clusters: int) -> dict:
    # 95% interval on a t distribution with (clusters - 1) degrees of freedom, the
    # usual small-cluster correction for CRV1 standard errors.
    crit = float(stats.t.ppf(0.975, max(n_clusters - 1, 1)))
    coef, se = fit.coef(), fit.se()
    out = {"spec": label, "n_obs": int(fit._N), "terms": {}}
    for t in terms:
        if t in coef.index:
            b, s = float(coef[t]), float(se[t])
            out["terms"][t] = {
                "beta_s": b, "se_s": s,
                "ci_low_s": b - crit * s, "ci_high_s": b + crit * s,
            }
    return out


def _contrast(fit, plus: str, minus: str, n_clusters: int) -> dict | None:
    """beta(plus) - beta(minus) with its race-clustered 95% interval (same t crit)."""
    names = [str(n) for n in fit._coefnames]
    if plus not in names or minus not in names:
        return None
    i, j = names.index(plus), names.index(minus)
    v = np.asarray(fit._vcov)
    b = float(np.asarray(fit._beta_hat)[i] - np.asarray(fit._beta_hat)[j])
    s = float(np.sqrt(max(v[i, i] + v[j, j] - 2.0 * v[i, j], 0.0)))
    crit = float(stats.t.ppf(0.975, max(n_clusters - 1, 1)))
    return {"terms": [plus, minus], "beta_s": b, "se_s": s,
            "ci_low_s": b - crit * s, "ci_high_s": b + crit * s}


def p3_sample(d: pd.DataFrame) -> pd.DataFrame:
    """Rows p3 runs on: the two registered exception races dropped (p3 only), and
    only rows with a P3 class (no_geometry occurs only in those races)."""
    keep = ~d["race_id"].isin(P3_EXCEPTION_RACES) & d["corner_class"].isin(P3_CLASSES)
    return d[keep]


def fit_p3(d: pd.DataFrame, tyre_age: bool, vcov: dict) -> dict | None:
    """Spec p3 (DA-02P amendment). `d` is the shared valid sample of fit_specs."""
    if "corner_class" not in d.columns:
        return None
    s = p3_sample(d)
    if len(s) == 0:
        return None
    present = [c for c in P3_CLASSES if (s["corner_class"] == c).any()]
    inter = [f"{b}__{c}" for c in present for b in LT1_BANDS]
    # Class main effects are spanned by the driver-race x corner-class FE (dr_cc).
    tyre = [f"tyre__{c}" for c in present] if tyre_age else []
    fml = "y_s ~ " + " + ".join(inter + ["ahead_y_s"] + tyre) + " | lap_id + dr_cc"
    n_cl = int(s["race_id"].nunique())
    fit = pf.feols(fml, data=s, vcov=vcov)
    out = _tidy(fit, "p3", inter + ["ahead_y_s"], n_cl)
    out["rows"] = int(len(s))
    out["n_races"] = n_cl
    out["rows_dropped_exception_races"] = int(d["race_id"].isin(P3_EXCEPTION_RACES).sum())
    out["rows_by_class"] = {c: int((s["corner_class"] == c).sum()) for c in present}
    out["class_main_effects"] = "spanned by the driver-race x corner-class fixed effect"
    out["formula"] = fml
    out["contrasts"] = {}
    for name, a, b in (("high_minus_low", "lt1__high", "lt1__low"),
                       ("high_minus_straight", "lt1__high", "lt1__straight"),
                       ("flat_minus_straight", "lt1__flat", "lt1__straight")):
        c = _contrast(fit, a, b, n_cl)
        if c is not None:
            out["contrasts"][name] = c
    return out


def fit_specs(panel: pd.DataFrame, tyre_age: bool = True) -> dict:
    """All specs on one sample, race-clustered. `panel` is add_regressors() output."""
    d = panel.dropna(subset=["y_s", "ahead_y_s"]).copy()
    if tyre_age:
        d = d.dropna(subset=["tyre_life"])
    clusters = int(d["race_id"].nunique())
    vcov = {"CRV1": "race_id"}
    tyre = " + tyre_life:C(micro)" if tyre_age else ""
    bands = " + ".join(f"b_{b.split('_', 1)[0]}" for b in BAND_ORDER)
    forms = {
        "bands": f"y_s ~ {bands} + ahead_y_s{tyre} | lap_id",
        "lt1": f"y_s ~ lt1 + g1_1p5 + g1p5_2 + g2_3 + ahead_y_s{tyre} | lap_id",
        "p1": f"y_s ~ lt1 + g1_1p5 + g1p5_2 + g2_3 + behind_lt1 + ahead_y_s{tyre} | lap_id",
    }
    res = {"n_rows": int(len(d)), "n_races": clusters, "specs": {}}
    for name, fml in forms.items():
        fit = pf.feols(fml, data=d, vcov=vcov)
        res["specs"][name] = _tidy(
            fit, name,
            [c.strip() for c in fml.split("~")[1].split("|")[0].split("+")
             if ":" not in c and c.strip() != "ahead_y_s"] + ["ahead_y_s"],
            clusters,
        )
    # P2 runs on the rows beyond 3 s only: does 3-5 s differ from >5 s?
    far = d[d["gap_ahead_s"] >= 3.0]
    if len(far) > 0 and far["far_3_5"].nunique() > 1:
        fit = pf.feols(f"y_s ~ far_3_5 + ahead_y_s{tyre} | lap_id", data=far, vcov=vcov)
        res["specs"]["p2"] = _tidy(
            fit, "p2", ["far_3_5", "ahead_y_s"], int(far["race_id"].nunique()))
        res["specs"]["p2"]["rows"] = int(len(far))
    # Lead window: exit gap on y. No ahead_y_s (the exit gap is an outcome).
    lead = d.dropna(subset=["exit_gap_ahead_s"])
    if len(lead) > 0:
        fit = pf.feols(f"y_s ~ x_lt1 + x_1_3{tyre} | lap_id", data=lead, vcov=vcov)
        res["specs"]["lead"] = _tidy(
            fit, "lead", ["x_lt1", "x_1_3"], int(lead["race_id"].nunique()))
        res["specs"]["lead"]["rows"] = int(len(lead))
    # Lagged-gap check: the lt1 bands on the gap at boundary k - 1, which shares no
    # crossing with y (boundaries k and k + 1). Rows with no valid m - 1 row are
    # dropped here only.
    if "lag_gap_ahead_s" in d.columns:
        lag = d.dropna(subset=["lag_gap_ahead_s"])
        if len(lag) > 0 and lag["lag_lt1"].nunique() > 1:
            fit = pf.feols(f"y_s ~ {' + '.join(LAG_BANDS)} + ahead_y_s{tyre} | lap_id",
                           data=lag, vcov=vcov)
            res["specs"]["lag_gap"] = _tidy(fit, "lag_gap", LAG_BANDS + ["ahead_y_s"],
                                            int(lag["race_id"].nunique()))
            res["specs"]["lag_gap"]["rows"] = int(len(lag))
    # P3 mechanism placebo.
    p3 = fit_p3(d, tyre_age, vcov)
    if p3 is not None:
        res["specs"]["p3"] = p3
    # DRS specs, reported only (never gate P3, never rescue a failed main result).
    lt1_fml = forms["lt1"]
    drs_samples = {}
    if "drs_open" in d.columns:
        drs_samples["drs_closed"] = d[d["drs_open"].astype("boolean").eq(False).fillna(False)]
    if "ms_drs_any_open" in d.columns:
        drs_samples["drs_location"] = d[
            d["ms_drs_any_open"].astype("boolean").eq(False).fillna(False)]
    for name, sub in drs_samples.items():
        if len(sub) == 0 or sub["lt1"].nunique() < 2:
            continue
        fit = pf.feols(lt1_fml, data=sub, vcov=vcov)
        res["specs"][name] = _tidy(fit, name, LT1_BANDS + ["ahead_y_s"],
                                   int(sub["race_id"].nunique()))
        res["specs"][name]["rows"] = int(len(sub))
        res["specs"][name]["gated"] = False
    return res


def _ci_excludes_0_positive(t: dict | None) -> bool:
    return bool(t is not None and t["beta_s"] > 0 and t["ci_low_s"] > 0)


def gate1_minimum_effect_check(lt1: dict | None,
                               lap_figure_s: float | None = GATE1_LAP_FIGURE_S,
                               min_share: float | None = GATE1_MIN_SHARE_OF_LAP_FIGURE,
                               n_microsectors: int = 20) -> bool | None:
    """P2 size-limit option (a), STUB: beta(lt1) must be at least min_share of a lap-time
    figure spread over the lap's micro-sectors. None while either number is unset
    ([OWNER TO SET]); a missing beta(lt1) is False. Not in GATE_CHECKS."""
    if lap_figure_s is None or min_share is None:
        return None
    if lt1 is None:
        return False
    return bool(lt1["beta_s"] >= min_share * lap_figure_s / n_microsectors)


def p2_precision_check(p2: dict | None, lt1: dict | None,
                       max_ci_width_s: float | None = P2_MAX_CI_WIDTH_S,
                       max_share_of_beta: float | None = P2_MAX_SHARE_OF_BETA
                       ) -> bool | None:
    """P2 size-limit option (b), the registered P2 pass rule: the 3-5 s vs >5 s
    interval is no wider than max_ci_width_s (so P2 cannot pass by imprecision), and
    its point estimate is below max_share_of_beta x |beta(lt1)| (so a tiny, significant
    shift is not a fail; the P1 rule's form). Whichever limits are set must all hold.
    None if both are unset; a missing spec is False. In GATE_CHECKS via
    evaluate_gates' p2_precision_pass."""
    if max_ci_width_s is None and max_share_of_beta is None:
        return None
    if p2 is None or (max_share_of_beta is not None and lt1 is None):
        return False
    ok = True
    if max_ci_width_s is not None:
        ok = ok and (p2["ci_high_s"] - p2["ci_low_s"]) <= max_ci_width_s
    if max_share_of_beta is not None:
        ok = ok and abs(p2["beta_s"]) < max_share_of_beta * abs(lt1["beta_s"])
    return bool(ok)


def evaluate_p3(res: dict) -> dict:
    """P3 gate on one sample (pooled or one era), as registered in the DA-02P amendment.

    (a) beta(lt1, high) > 0 with a 95% interval excluding 0.
    (b) beta(lt1, high) - beta(lt1, low) > 0 with a 95% interval excluding 0.
    high is 200 to < 280 km/h; flat is excluded from it. Everything else is REPORTED,
    never gated."""
    p3 = res["specs"].get("p3")
    if p3 is None:
        return {"p3_status": "NOT_RUN: spec p3 missing (no corner_class)", "p3_pass": False}
    t, c = p3["terms"], p3["contrasts"]
    high, hml = t.get("lt1__high"), c.get("high_minus_low")
    out = {
        "p3_status": "RUN",
        "p3_a_beta_lt1_high": high,
        "p3_a_pass": _ci_excludes_0_positive(high),
        "p3_b_high_minus_low": hml,
        "p3_b_pass": _ci_excludes_0_positive(hml),
    }
    out["p3_pass"] = bool(out["p3_a_pass"] and out["p3_b_pass"])
    b = {k: t.get(f"lt1__{k}", {}).get("beta_s") for k in ("high", "medium", "low")}
    order = (None if any(v is None for v in b.values())
             else bool(b["high"] >= b["medium"] >= b["low"]))
    out["p3_report_only"] = {
        "gated": False,
        "beta_lt1_flat": t.get("lt1__flat"),
        "flat_minus_straight": c.get("flat_minus_straight"),
        "beta_lt1_straight": t.get("lt1__straight"),
        "high_minus_straight": c.get("high_minus_straight"),
        "beta_lt1_medium": t.get("lt1__medium"),
        "beta_lt1_mixed": t.get("lt1__mixed"),
        "beta_lt1_link": t.get("lt1__link"),
        "order_high_ge_medium_ge_low": order,
    }
    return out


def evaluate_gates(res: dict) -> dict:
    """The registered gate, as code, on one sample (pooled or one era)."""
    s = res["specs"]
    lt1 = s["lt1"]["terms"]["lt1"]
    # Registered gate 1: the interval excludes 0 AND beta(lt1) is positive. (The old
    # two-sided beta_lt1_ci_excludes_0 is retired: it passed a negative interval.)
    out = {"beta_lt1_s": lt1["beta_s"],
           "beta_lt1_positive_ci_excludes_0": _ci_excludes_0_positive(lt1)}
    # Lagged-gap check (gate 6): beta(lag lt1) positive with an interval excluding 0.
    lag = s.get("lag_gap", {}).get("terms", {}).get("lag_lt1")
    out["lag_gap_beta_lt1_s"] = None if lag is None else lag["beta_s"]
    out["lag_gap_pass"] = _ci_excludes_0_positive(lag)
    p1 = s["p1"]["terms"].get("behind_lt1")
    if p1 is not None:
        out["p1_beta_s"] = p1["beta_s"]
        out["p1_ci_includes_0"] = bool(p1["ci_low_s"] <= 0 <= p1["ci_high_s"])
        out["p1_below_third_of_beta"] = bool(
            abs(p1["beta_s"]) < P1_MAX_SHARE_OF_BETA * abs(lt1["beta_s"]))
        out["p1_pass"] = bool(out["p1_ci_includes_0"] and out["p1_below_third_of_beta"])
    p2 = s.get("p2", {}).get("terms", {}).get("far_3_5")
    if p2 is not None:
        out["p2_beta_s"] = p2["beta_s"]
        # Reported only: "includes 0" was replaced by option (b) on 2026-10-27.
        out["p2_ci_includes_0"] = bool(p2["ci_low_s"] <= 0 <= p2["ci_high_s"])
        out["p2_ci_width_s"] = p2["ci_high_s"] - p2["ci_low_s"]
        out["p2_precision_pass"] = bool(p2_precision_check(p2, lt1))
    lead = s.get("lead", {}).get("terms", {}).get("x_lt1")
    if lead is not None:
        out["lead_x_lt1_beta_s"] = lead["beta_s"]
        out["lead_at_or_below_0"] = bool(lead["ci_high_s"] <= 0 or lead["beta_s"] <= 0)
    out.update(evaluate_p3(res))
    out["drs_report_only"] = {
        name: {"gated": False, "lt1": s.get(name, {}).get("terms", {}).get("lt1")}
        for name in ("drs_closed", "drs_location") if name in s
    }
    return out


def run_panel(panel: pd.DataFrame, tyre_age: bool = True) -> dict:
    """Pooled and per-era fits and gates on an add_regressors() panel."""
    out = {"pooled": None, "eras": {}}
    out["pooled"] = fit_specs(panel, tyre_age=tyre_age)
    out["pooled"]["gates"] = evaluate_gates(out["pooled"])
    for era, mask in (("pre2022", panel["race_year"] < ERA_BREAK),
                      ("post2022", panel["race_year"] >= ERA_BREAK)):
        sub = panel[mask]
        out["eras"][era] = fit_specs(sub, tyre_age=tyre_age)
        out["eras"][era]["gates"] = evaluate_gates(out["eras"][era])
    # Stop rule: the sign of beta(lt1) flips between eras
    b = [out["eras"][e]["gates"]["beta_lt1_s"] for e in ("pre2022", "post2022")]
    out["stop_sign_flips_by_era"] = bool(np.sign(b[0]) != np.sign(b[1]))
    # P3 passes only if (a) and (b) hold pooled AND in each era.
    per = {"pooled": out["pooled"]["gates"]["p3_pass"],
           **{e: out["eras"][e]["gates"]["p3_pass"] for e in out["eras"]}}
    out["p3_verdict"] = {"by_sample": per, "pass": bool(all(per.values()))}
    out["gate_verdict"] = gate_verdict(out)
    return out


# The registered gate (pre-registration, "Primary quantity and gate"), per sample.
# A check whose spec did not run counts as a FAIL, never as a pass.
GATE_CHECKS = (
    ("beta_lt1_positive", "beta_lt1_positive_ci_excludes_0"),
    ("p1", "p1_pass"),
    ("p2", "p2_precision_pass"),   # option (b): width <= 0.008 s and |P2| < beta/3
    ("p3", "p3_pass"),
    ("lag_gap", "lag_gap_pass"),
)


def gate_verdict(out: dict) -> dict:
    """One mechanical PASS/FAIL across the registered gates: gates 1-4 and 6 (the
    lagged-gap check) pooled AND in each era, and gate 5 (the sign of beta(lt1) does
    not flip between eras). Lead,
    the P2 monotone check, the P3 report-only blocks and the DRS specs are reported
    elsewhere and never enter this verdict."""
    samples = {"pooled": out["pooled"], **out["eras"]}
    checks = {}
    for sample, res in samples.items():
        g = res["gates"]
        for name, key in GATE_CHECKS:
            checks[f"{name}__{sample}"] = bool(g.get(key, False))
    checks["no_sign_flip_by_era"] = not out["stop_sign_flips_by_era"]
    failed = [k for k, v in checks.items() if not v]
    return {"pass": not failed, "verdict": "PASS" if not failed else "FAIL",
            "checks": checks, "failed": failed}


# ---------------------------------------------------------------------------------------
# DA-03F: slow-corner follow-up (a new test with its own pre-registration). It does not
# rescue, amend or reinterpret DA-03; nothing above is changed by it. It runs the
# registered lt1 and p3 specs (through fit_specs, unchanged) on a restricted sample:
#   venue rule   a venue is kept only if it has a p3-sample race in every season
#                2018-2025, and then all its p3-sample races are kept;
#   blocking cut keep a row only if ahead_y_s <= 0 (every band, every corner class);
#                a valid row with no ahead_y_s stops the run.
# Verdict: D = beta(lt1, low) - beta(lt1, high) from p3, T = |beta(lt1)| / 3 from lt1,
# both on the same restricted sample, per sample (pooled, 2018-21, 2022-25).
# ---------------------------------------------------------------------------------------

FOLLOWUP_SEASONS = tuple(range(2018, 2026))
FOLLOWUP_SHARE_OF_BETA = 1.0 / 3.0   # the registered P1/P2 size logic
FOLLOWUP_SAMPLES = ("pooled", "pre2022", "post2022")
FOLLOWUP_LOW, FOLLOWUP_HIGH = "low", "high"

# Venue of each race_to_track.track_id. The estimator groups by race_id; race_to_track
# maps race_id to an event slug (track_id). One-off events held at a regular venue map
# to that venue (owner choice: group by venue). Any track_id not listed is its own venue.
VENUE_OF_TRACK = {
    "abu_dhabi_grand_prix": "abu_dhabi",
    "austrian_grand_prix": "austria",
    "styrian_grand_prix": "austria",            # Red Bull Ring, 2020 and 2021
    "belgian_grand_prix": "belgium",
    "british_grand_prix": "britain",
    "70th_anniversary_grand_prix": "britain",   # Silverstone, 2020
    "hungarian_grand_prix": "hungary",
    "italian_grand_prix": "italy",              # Monza
    "spanish_grand_prix": "spain",
    "bahrain_grand_prix": "bahrain",
    "sakhir_grand_prix": "bahrain",             # Bahrain outer loop, 2020 (P3 exception)
}
# The registered venue list. A run whose venue rule keeps any other set stops (NOT_RUN):
# the sample must be the one the pre-registration names.
FOLLOWUP_EXPECTED_VENUES = frozenset(
    {"abu_dhabi", "austria", "belgium", "britain", "hungary", "italy", "spain"})

FOLLOWUP_VERDICTS = ("PASS", "REFUTED", "INCONCLUSIVE", "NOT_RUN")


class FollowupProxyMissing(ValueError):
    """A valid row has no ahead_y_s: the blocking cut cannot be applied."""


def venue_of_track(track_id: str) -> str:
    return VENUE_OF_TRACK.get(track_id, track_id)


def load_race_tracks(db_path: Path) -> pd.DataFrame:
    """race_id -> track_id from the race_to_track seed (read-only)."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.sql("SELECT race_id, track_id FROM race_to_track").df()
    finally:
        con.close()


def followup_race_table(panel: pd.DataFrame, race_tracks: pd.DataFrame) -> pd.DataFrame:
    """One row per p3-sample race: race_id, venue, race_year. A race with no
    race_to_track row stops the run (it would otherwise drop out silently)."""
    races = p3_sample(panel)[["race_id", "race_year"]].drop_duplicates()
    m = races.merge(race_tracks[["race_id", "track_id"]], on="race_id", how="left")
    if m["track_id"].isna().any():
        missing = sorted(m.loc[m["track_id"].isna(), "race_id"].astype(str))
        raise ValueError(f"races with no race_to_track row: {missing}")
    m["venue"] = m["track_id"].map(venue_of_track)
    return m[["race_id", "venue", "race_year"]].reset_index(drop=True)


def followup_venue_races(races: pd.DataFrame,
                         seasons: tuple[int, ...] = FOLLOWUP_SEASONS) -> pd.DataFrame:
    """The venue rule. `races` has race_id, venue, race_year (one row per p3-sample
    race). A venue is kept only if it has a race in every one of `seasons`; all its
    races are then kept. Returns the kept rows of `races`."""
    need = set(seasons)
    have = races.groupby("venue")["race_year"].agg(lambda s: set(int(x) for x in s))
    kept = [v for v, yrs in have.items() if need <= yrs]
    return races[races["venue"].isin(kept)].reset_index(drop=True)


def blocking_cut_mask(d: pd.DataFrame) -> pd.Series:
    """The blocking cut: True where ahead_y_s <= 0 (the car ahead at or quicker than
    the field median in that micro-sector). Applies to every row, the >3 s reference
    band and every corner class included. Raises FollowupProxyMissing if any row has
    no ahead_y_s; nothing is dropped or imputed."""
    n_missing = int(d["ahead_y_s"].isna().sum())
    if n_missing:
        raise FollowupProxyMissing(
            f"{n_missing} valid rows have no ahead_y_s; the blocking cut cannot be "
            f"applied (nothing imputed, run stopped)")
    return d["ahead_y_s"] <= 0


def apply_blocking_cut(d: pd.DataFrame) -> pd.DataFrame:
    return d[blocking_cut_mask(d)]


def followup_sample(panel: pd.DataFrame, race_tracks: pd.DataFrame
                    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The restricted sample: the proxy check on every valid row, the venue rule on the
    p3-sample races, then the blocking cut. Returns (sample, kept race table)."""
    blocking_cut_mask(panel)  # proxy check on the whole valid panel, before anything
    kept = followup_venue_races(followup_race_table(panel, race_tracks))
    sub = panel[panel["race_id"].isin(kept["race_id"])]
    return apply_blocking_cut(sub), kept


def followup_d(p3: dict | None) -> dict | None:
    """D = beta(lt1, low) - beta(lt1, high): the registered high_minus_low contrast with
    the sign reversed (same race-clustered interval)."""
    hml = (p3 or {}).get("contrasts", {}).get("high_minus_low")
    if hml is None:
        return None
    return {"D_s": -hml["beta_s"], "ci_low_s": -hml["ci_high_s"],
            "ci_high_s": -hml["ci_low_s"], "se_s": hml.get("se_s")}


def followup_sample_class(D: float, ci_low: float, ci_high: float, T: float) -> str:
    """S if the lower 95% bound of D > 0 and D >= T; R if the upper bound < T; N
    otherwise. (S and R cannot both hold: S needs D >= T, R needs ci_high < T.)"""
    if ci_low > 0 and D >= T:
        return "S"
    if ci_high < T:
        return "R"
    return "N"


def followup_verdict(by_sample: dict) -> dict:
    """The DA-03F verdict, a pure function of the per-sample numbers.

    `by_sample` maps each of FOLLOWUP_SAMPLES to {"D_s", "ci_low_s", "ci_high_s",
    "T_s"} or to {"not_run": reason} / None. PASS if S in all three; REFUTED if R in
    at least one (label "reversed" if an R sample's upper bound is below 0);
    INCONCLUSIVE if no R and at least one N; NOT_RUN if any sample is missing, did not
    run, or has a non-finite number."""
    classes: dict[str, str] = {}
    for name in FOLLOWUP_SAMPLES:
        s = by_sample.get(name)
        if not s or s.get("not_run"):
            why = (s or {}).get("not_run") or "missing"
            return {"verdict": "NOT_RUN", "label": None, "classes": classes,
                    "reason": f"{name}: {why}"}
        nums = [s.get(k) for k in ("D_s", "ci_low_s", "ci_high_s", "T_s")]
        if any(v is None or not np.isfinite(v) for v in nums):
            return {"verdict": "NOT_RUN", "label": None, "classes": classes,
                    "reason": f"{name}: non-finite or missing D, interval or T"}
        classes[name] = followup_sample_class(*nums)
    r = [n for n, c in classes.items() if c == "R"]
    if all(c == "S" for c in classes.values()):
        verdict, label = "PASS", None
    elif r:
        verdict = "REFUTED"
        label = ("reversed" if any(by_sample[n]["ci_high_s"] < 0 for n in r)
                 else None)
    else:
        verdict, label = "INCONCLUSIVE", None
    return {"verdict": verdict, "label": label, "classes": classes, "reason": None}


def fit_followup_one(sample: pd.DataFrame, tyre_age: bool = True) -> dict:
    """lt1 and p3, registered and unchanged (through fit_specs), on one restricted
    sample. Only lt1, p3, D and T are kept; fit_specs' other specs are not reported."""
    s3 = p3_sample(sample)
    for c in (FOLLOWUP_LOW, FOLLOWUP_HIGH):
        if not (s3["corner_class"] == c).any():
            return {"not_run": f"no {c} corner rows"}
    res = fit_specs(sample, tyre_age=tyre_age)
    lt1 = res["specs"]["lt1"]["terms"].get("lt1")
    d = followup_d(res["specs"].get("p3"))
    if lt1 is None or d is None:
        return {"not_run": "beta(lt1) or the low/high contrast was not estimated"}
    return {**d, "T_s": FOLLOWUP_SHARE_OF_BETA * abs(lt1["beta_s"]),
            "beta_lt1": lt1, "n_rows": res["n_rows"], "n_races": res["n_races"],
            "lt1_spec": res["specs"]["lt1"], "p3_spec": res["specs"]["p3"]}


def run_followup_panel(panel: pd.DataFrame, race_tracks: pd.DataFrame,
                       tyre_age: bool = True,
                       expected_venues: frozenset | None = FOLLOWUP_EXPECTED_VENUES
                       ) -> dict:
    """The DA-03F run on an add_regressors() panel. Never raises: a missing proxy, a
    venue set other than the registered one, or a crash gives NOT_RUN."""
    out: dict = {"test": "DA-03F", "by_sample": {}}
    try:
        sample, kept = followup_sample(panel, race_tracks)
    except FollowupProxyMissing as e:
        out["followup_verdict"] = {"verdict": "NOT_RUN", "label": None, "classes": {},
                                   "reason": f"missing proxy: {e}"}
        return out
    except Exception as e:  # noqa: BLE001 - a crash is a NOT_RUN, logged
        out["followup_verdict"] = {"verdict": "NOT_RUN", "label": None, "classes": {},
                                   "reason": f"crash: {e!r}"}
        return out
    venues = sorted(kept["venue"].unique())
    out["venues"] = venues
    out["races"] = sorted(kept["race_id"].astype(str))
    out["rows_after_cut"] = int(len(sample))
    if expected_venues is not None and set(venues) != set(expected_venues):
        out["followup_verdict"] = {
            "verdict": "NOT_RUN", "label": None, "classes": {},
            "reason": f"venue rule kept {venues}, not the registered "
                      f"{sorted(expected_venues)}"}
        return out
    masks = {"pooled": slice(None),
             "pre2022": sample["race_year"] < ERA_BREAK,
             "post2022": sample["race_year"] >= ERA_BREAK}
    for name in FOLLOWUP_SAMPLES:
        try:
            out["by_sample"][name] = fit_followup_one(sample[masks[name]], tyre_age)
        except Exception as e:  # noqa: BLE001
            out["by_sample"][name] = {"not_run": f"crash: {e!r}"}
    out["followup_verdict"] = followup_verdict(out["by_sample"])
    return out


def run_followup(db_path: Path) -> dict:
    out = {"git_sha": get_git_sha(), "db": str(db_path)}
    try:
        panel = add_regressors(load_panel(db_path))
        tracks = load_race_tracks(db_path)
    except Exception as e:  # noqa: BLE001
        out["followup_verdict"] = {"verdict": "NOT_RUN", "label": None, "classes": {},
                                   "reason": f"crash while loading: {e!r}"}
        return out
    out.update(run_followup_panel(panel, tracks))
    return out


def followup_run_recorded(build_log: Path, log_item: str = FOLLOWUP_LOG_ITEM) -> bool:
    """True if the build log already records a DA-03F run: the item has a truthy
    `run_recorded` or a non-empty `runs`, or a top-level history entry carries
    `"run_recorded": "<log_item>"`. Unreadable log counts as recorded (refuse)."""
    try:
        data = json.loads(build_log.read_text())
    except (OSError, ValueError):
        return True
    item = next((i for i in data.get("items", []) if i.get("id") == log_item), {}) or {}
    if item.get("run_recorded") or item.get("runs"):
        return True
    return any(isinstance(h, dict) and h.get("run_recorded") == log_item
               for h in data.get("history", []))


def followup_lock_errors(prereg: Path, build_log: Path = BUILD_LOG_PATH) -> list[str]:
    """The DA-03F lock: the DA-02P-style lock on item DA-03F, plus a refusal if DA-03F
    already has a recorded run (a run that produced numbers is final)."""
    errors = prereg_lock_errors(prereg, build_log, log_item=FOLLOWUP_LOG_ITEM)
    if followup_run_recorded(build_log, FOLLOWUP_LOG_ITEM):
        errors.append(f"build log item {FOLLOWUP_LOG_ITEM} already records a run; "
                      f"the follow-up runs once")
    return errors


def _main_followup(args: argparse.Namespace) -> int:
    prereg = FOLLOWUP_PREREG_PATH
    if not prereg.exists():
        log.error("no follow-up pre-registration at %s", prereg)
        return 2
    digest = sha256_of(prereg)
    if args.print_prereg_sha256:
        print(digest)
        return 0
    lock_errors = followup_lock_errors(prereg, BUILD_LOG_PATH)
    if args.check_prereg_lock:
        print("\n".join(lock_errors) if lock_errors else f"LOCKED {digest}")
        return 2 if lock_errors else 0
    if args.prereg_sha256 != digest:
        log.error("refusing to run DA-03F: --prereg-sha256 must equal the follow-up "
                  "pre-registration's hash (%s).", digest)
        return 2
    if lock_errors:
        log.error("refusing to run DA-03F: %s", "; ".join(lock_errors))
        return 2
    result = run_followup(args.db)
    result["prereg_sha256"] = digest
    result["prereg_locked"] = (f"committed at HEAD, matches build log "
                               f"{FOLLOWUP_LOG_ITEM}.prereg_sha256")
    text = json.dumps(result, indent=2, default=float)
    if args.out:
        args.out.write_text(text)
        log.info("wrote %s", args.out)
    else:
        print(text)
    v = result["followup_verdict"]
    print(f"DA-03F VERDICT: {v['verdict']}"
          + (f" ({v['label']})" if v.get("label") else "")
          + (f" [{v['reason']}]" if v.get("reason") else ""), file=sys.stderr)
    return 3 if v["verdict"] == "NOT_RUN" else 0


def run(db_path: Path) -> dict:
    panel = add_regressors(load_panel(db_path))
    out = {"git_sha": get_git_sha(), "db": str(db_path)}
    out.update(run_panel(panel))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--print-prereg-sha256", action="store_true",
                    help="print the SHA-256 of the pre-registration and exit")
    ap.add_argument("--check-prereg-lock", action="store_true",
                    help="check the pre-registration is committed and its hash logged, "
                         "and exit")
    ap.add_argument("--prereg-sha256", help="must equal the pre-registration's SHA-256")
    ap.add_argument("--db", type=Path, default=DB_PATH, help="warehouse, read-only")
    ap.add_argument("--out", type=Path, default=None, help="JSON to write")
    ap.add_argument("--followup", action="store_true",
                    help="DA-03F slow-corner follow-up: use wi/DA-03F-preregistration.md "
                         "and build-log item DA-03F instead of DA-03 / DA-02P")
    args = ap.parse_args(argv)

    if args.followup:
        return _main_followup(args)
    if not PREREG_PATH.exists():
        log.error("no pre-registration at %s", PREREG_PATH)
        return 2
    digest = sha256_of(PREREG_PATH)
    if args.print_prereg_sha256:
        print(digest)
        return 0
    lock_errors = prereg_lock_errors(PREREG_PATH, BUILD_LOG_PATH)
    if args.check_prereg_lock:
        print("\n".join(lock_errors) if lock_errors else f"LOCKED {digest}")
        return 2 if lock_errors else 0
    if args.prereg_sha256 != digest:
        log.error("refusing to fit: --prereg-sha256 must equal the registered file's "
                  "hash (%s). Commit the pre-registration first, then pass its hash.", digest)
        return 2
    if lock_errors:
        log.error("refusing to fit: the pre-registration is not locked: %s",
                  "; ".join(lock_errors))
        return 2
    result = run(args.db)
    result["prereg_sha256"] = digest
    result["prereg_locked"] = (f"committed at HEAD, matches build log "
                               f"{PREREG_LOG_ITEM}.prereg_sha256")
    text = json.dumps(result, indent=2, default=float)
    if args.out:
        args.out.write_text(text)
        log.info("wrote %s", args.out)
    else:
        print(text)
    v = result["gate_verdict"]
    print(f"DA-03 GATE VERDICT: {v['verdict']}"
          + (f" (failed: {', '.join(v['failed'])})" if v["failed"] else ""),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
