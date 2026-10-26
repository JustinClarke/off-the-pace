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
            the gap would show here)
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
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
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
PREREG_PATH = REPO_ROOT / "_roadmap" / "_dirty-air" / "wi" / "DA-03-preregistration.md"

BAND_ORDER = ["0_lt0.5", "1_0.5to1", "2_1to1.5", "3_1.5to2", "4_2to3"]
ERA_BREAK = 2022  # 2022 ground-effect regulations (design note section 7)

# Pre-registered gate constants (DA-03 doc, design note section 6, phase 2)
P1_MAX_SHARE_OF_BETA = 1.0 / 3.0

# P3 (DA-02P amendment). Classes estimated in p3; no_geometry rows are the two
# registered exception races and are dropped with them.
P3_CLASSES = ["low", "medium", "high", "flat", "mixed", "straight", "link"]
P3_EXCEPTION_RACES = ("2020_9", "2020_16")
LT1_BANDS = ["lt1", "g1_1p5", "g1p5_2", "g2_3"]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_panel(db_path: Path) -> pd.DataFrame:
    """Valid micro-sector rows with the columns every spec needs.

    corner_class comes from int_microsector_corner_class on (race, micro-sector).
    ms_drs_any_open is TRUE when any car, on any lap of the race (valid row or not),
    had DRS open at the entry or exit of that micro-sector: the drs_location drop."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.sql(
            """
            WITH drs_zone AS (
                SELECT race_year, race_id, microsector,
                       COALESCE(BOOL_OR(drs_open), FALSE) AS ms_drs_any_open
                FROM int_microsector_proximity
                GROUP BY race_year, race_id, microsector
            )
            SELECT
                p.microsector_id, p.lap_id, p.race_year, p.race_id, p.driver_id,
                p.lap_number, p.microsector, p.y_s, p.ahead_y_s, p.gap_ahead_s,
                p.gap_band, p.gap_behind_s, p.behind_lap_number, p.exit_gap_ahead_s,
                l.tyre_life, p.drs_open, z.ms_drs_any_open, c.corner_class
            FROM int_microsector_proximity AS p
            LEFT JOIN stg_laps AS l ON p.lap_id = l.lap_id
            LEFT JOIN int_microsector_corner_class AS c
                ON p.race_year = c.race_year AND p.race_id = c.race_id
                AND p.microsector = c.microsector
            LEFT JOIN drs_zone AS z
                ON p.race_year = z.race_year AND p.race_id = z.race_id
                AND p.microsector = z.microsector
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
    beta_ci_excludes_0 = lt1["ci_low_s"] > 0 or lt1["ci_high_s"] < 0
    out = {"beta_lt1_s": lt1["beta_s"],
           "beta_lt1_ci_excludes_0": bool(beta_ci_excludes_0)}
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
        out["p2_ci_includes_0"] = bool(p2["ci_low_s"] <= 0 <= p2["ci_high_s"])
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
    return out


def run(db_path: Path) -> dict:
    panel = add_regressors(load_panel(db_path))
    out = {"git_sha": get_git_sha(), "db": str(db_path)}
    out.update(run_panel(panel))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--print-prereg-sha256", action="store_true",
                    help="print the SHA-256 of the pre-registration and exit")
    ap.add_argument("--prereg-sha256", help="must equal the pre-registration's SHA-256")
    ap.add_argument("--db", type=Path, default=DB_PATH, help="warehouse, read-only")
    ap.add_argument("--out", type=Path, default=None, help="JSON to write")
    args = ap.parse_args(argv)

    if not PREREG_PATH.exists():
        log.error("no pre-registration at %s", PREREG_PATH)
        return 2
    digest = sha256_of(PREREG_PATH)
    if args.print_prereg_sha256:
        print(digest)
        return 0
    if args.prereg_sha256 != digest:
        log.error("refusing to fit: --prereg-sha256 must equal the registered file's "
                  "hash (%s). Commit the pre-registration first, then pass its hash.", digest)
        return 2
    result = run(args.db)
    result["prereg_sha256"] = digest
    text = json.dumps(result, indent=2, default=float)
    if args.out:
        args.out.write_text(text)
        log.info("wrote %s", args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
