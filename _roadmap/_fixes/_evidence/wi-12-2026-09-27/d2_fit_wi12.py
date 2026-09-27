"""WI-12: 06b's pre-registered ladder, re-run on the WI-01 label.

Same estimator code as 06b (d2_fit_06b.py / d3_diagnostics_06b.py): pyfixest feols,
CRV1 clustered on race_id, F0-F3 rungs, F2 = stint + six tyre-age bins. Reads the panels
d1_build_panels_wi12.py wrote. Writes wi12_fits.json (every coefficient, SE, CI, n).

Sections
  R  reproduction: 06b's own SQL on the pre-WI-01 warehouse must give 06b's published F2
     table (the "before" column) -- stops if it does not.
  L  the ladder, per season, on the wi01 panel (2018-2025; 2025 is the season 06b named
     in advance as its out-of-sample test).
  P  lead placebo (pre-registered), joint lag+lead fit, with the lag-minus-lead contrast
     and its CI from the fit's own vcov; applied identically to the before panel.
  E  the 2022 question on 06b's pre-registered window (2018-2024): era contrast, era
     levels, placebo boundaries, linear trend, drop-2018 cuts; plus the 2025 check.
  D  decomposition: which change moved the per-season numbers.
  W  W40: which estimator should price the label (pooled 2018-2025, the label's window).
  C  corner split (pre-registered + deviation 2), on the wi01 treatment.

Run from the repo root:
  WI12_SCRATCH=<dir with panel_wi12_corner.parquet> ./.venv/bin/python \
      _roadmap/_fixes/_evidence/wi-12-2026-09-27/d2_fit_wi12.py
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf

warnings.filterwarnings("ignore")
pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 40)

HERE = Path(__file__).resolve().parent
REPO_06B = HERE.parents[3] / "_roadmap/_improvements/implementations/06b"
SCRATCH = Path(os.environ.get("WI12_SCRATCH", HERE))
OUT = HERE / "wi12_fits.json"
PRE_REG = (2018, 2019, 2020, 2021, 2022, 2023, 2024)
ALL = PRE_REG + (2025,)
F2 = "stint_id + age_bin"
RUNGS = {"F0": None, "F1": "driver_race", "F2": F2, "F3": F2}
PUBLISHED_06B_F2 = {2018: 0.396, 2019: 0.151, 2020: 0.170, 2021: 0.083,
                    2022: 0.011, 2023: 0.045, 2024: -0.036}
RES: dict = {}


def fit(df: pd.DataFrame, y: str, x: str, fe: str | None, key: str | None = None) -> dict:
    m = pf.feols(f"{y} ~ {x}" + (f" | {fe}" if fe else ""), data=df,
                 vcov={"CRV1": "race_id"})
    t = m.tidy()
    out = {"formula": f"{y} ~ {x}" + (f" | {fe}" if fe else ""), "n": int(m._N),
           "G": int(df["race_id"].nunique())}
    for term in t.index:
        if term == "Intercept":
            continue
        out[term] = {k: float(t.loc[term, c]) for k, c in
                     (("coef", "Estimate"), ("se", "Std. Error"), ("p", "Pr(>|t|)"),
                      ("ci_lo", "2.5%"), ("ci_hi", "97.5%"))}
    names = list(m._coefnames)
    if "d_lag1" in names and "d_lead1" in names:
        i, j = names.index("d_lag1"), names.index("d_lead1")
        v = np.asarray(m._vcov)
        diff = out["d_lag1"]["coef"] - out["d_lead1"]["coef"]
        se = math.sqrt(v[i, i] + v[j, j] - 2 * v[i, j])
        # t critical with G-1 df, as pyfixest uses for CRV1 intervals
        from scipy import stats
        tc = stats.t.ppf(0.975, out["G"] - 1)
        out["lag_minus_lead"] = {"coef": diff, "se": se, "ci_lo": diff - tc * se,
                                 "ci_hi": diff + tc * se}
    if key:
        RES[key] = out
    return out


def r(x: float, k: int = 3) -> float:
    return round(x, k)


def show(title: str, rows: list[dict]) -> None:
    print("\n" + "=" * 100 + "\n" + title + "\n" + "=" * 100)
    print(pd.DataFrame(rows).to_string(index=False))


def load(name: str) -> pd.DataFrame:
    df = pd.read_parquet(HERE / name)
    df["ground"] = (df["race_year"] >= 2022).astype(float)
    return df


def per_season(lap: pd.DataFrame, y: str, fe: str | None, tag: str, seasons,
               no_boundary: bool = False) -> list[dict]:
    rows = []
    for s in seasons:
        d = lap[lap["race_year"] == s]
        if no_boundary:
            d = d[d["near_boundary"] == 0]
        o = fit(d, y, "d_lag1", fe, f"{tag}|{s}")
        b = o["d_lag1"]
        rows.append({"season": s, "n": o["n"], "G": o["G"], "theta": r(b["coef"]),
                     "se": r(b["se"]), "ci_lo": r(b["ci_lo"]), "ci_hi": r(b["ci_hi"]),
                     "p": r(b["p"], 4)})
    return rows


def placebo(lap: pd.DataFrame, y: str, tag: str, seasons) -> list[dict]:
    rows = []
    for s in seasons:
        d = lap[lap["race_year"] == s]
        lead = fit(d, y, "d_lead1", F2, f"{tag}|lead|{s}")
        j = fit(d, y, "d_lag1 + d_lead1", F2, f"{tag}|joint|{s}")
        lag_c, lead_c = j["d_lag1"]["coef"], j["d_lead1"]["coef"]
        lml = j["lag_minus_lead"]
        ratio = lag_c / lead_c if lead_c > 0 else float("inf")
        # Ruling, stated before looking at the after panel and applied to both panels:
        #   holds    -- joint lag > 0, lag/lead >= 2, and the lag-minus-lead CI excludes 0
        #   marginal -- joint lag > 0 and lag/lead >= 1.3 (06b's 2019 was 1.35), not "holds"
        #   fails    -- otherwise (lag not materially larger than lead)
        if lag_c > 0 and ratio >= 2 and lml["ci_lo"] > 0:
            verdict = "holds"
        elif lag_c > 0 and ratio >= 1.3:
            verdict = "marginal"
        else:
            verdict = "fails"
        rows.append({"season": s, "lead_alone": r(lead["d_lead1"]["coef"]),
                     "joint_lag": r(lag_c), "joint_lead": r(lead_c),
                     "lag/lead": r(ratio, 2) if math.isfinite(ratio) else "inf",
                     "lag-lead": r(lml["coef"]), "ci_lo": r(lml["ci_lo"]),
                     "ci_hi": r(lml["ci_hi"]), "ruling": verdict})
    return rows


def era_block(lap: pd.DataFrame, y: str, tag: str) -> dict:
    out = {}
    o = fit(lap, y, "d_lag1 + d_lag1:ground", F2, f"{tag}|era_interaction")
    out["pre"] = o["d_lag1"]
    out["delta"] = o["d_lag1:ground"]
    out["n"], out["G"] = o["n"], o["G"]
    for name, mask in (("pre_2018_21", lap["race_year"] < 2022),
                       ("ground_2022_on", lap["race_year"] >= 2022)):
        e = fit(lap[mask], y, "d_lag1", F2, f"{tag}|era|{name}")
        out[name] = {**e["d_lag1"], "n": e["n"], "G": e["G"]}
    rows = []
    last = int(lap["race_year"].max())
    for cut in range(2019, last + 1):
        lap = lap.assign(fake=(lap["race_year"] >= cut).astype(float))
        b = fit(lap, y, "d_lag1 + d_lag1:fake", F2, f"{tag}|boundary|{cut}")["d_lag1:fake"]
        rows.append({"boundary": f">= {cut}", "delta": r(b["coef"]), "ci_lo": r(b["ci_lo"]),
                     "ci_hi": r(b["ci_hi"]), "p": r(b["p"], 4)})
    out["boundaries"] = rows
    lap = lap.assign(season_c=lap["race_year"] - 2021)
    tr = fit(lap, y, "d_lag1 + d_lag1:season_c", F2, f"{tag}|trend")
    out["trend"] = {"theta_2021": tr["d_lag1"], "slope": tr["d_lag1:season_c"]}
    drops = []
    for label, d in (("2018 dropped", lap[lap["race_year"] != 2018]),
                     ("2018+2019 dropped", lap[~lap["race_year"].isin([2018, 2019])])):
        b = fit(d, y, "d_lag1 + d_lag1:ground", F2, f"{tag}|drop|{label}")["d_lag1:ground"]
        drops.append({"sample": label, "delta": r(b["coef"]), "ci_lo": r(b["ci_lo"]),
                      "ci_hi": r(b["ci_hi"]), "p": r(b["p"], 4)})
    out["drops"] = drops
    return out


def print_era(title: str, e: dict) -> None:
    print("\n" + "=" * 100 + "\n" + title + "\n" + "=" * 100)
    for k in ("pre_2018_21", "ground_2022_on"):
        b = e[k]
        print(f"  theta({k}) = {b['coef']:+.4f} [{b['ci_lo']:+.4f}, {b['ci_hi']:+.4f}]"
              f"  n={b['n']:,} G={b['G']}")
    d = e["delta"]
    print(f"  Delta (pooled interaction) = {d['coef']:+.4f} [{d['ci_lo']:+.4f}, "
          f"{d['ci_hi']:+.4f}] p={d['p']:.4f}  n={e['n']:,} G={e['G']}")
    t = e["trend"]
    print(f"  trend: theta(2021) = {t['theta_2021']['coef']:+.4f} "
          f"[{t['theta_2021']['ci_lo']:+.4f}, {t['theta_2021']['ci_hi']:+.4f}];  "
          f"dtheta/dseason = {t['slope']['coef']:+.4f} "
          f"[{t['slope']['ci_lo']:+.4f}, {t['slope']['ci_hi']:+.4f}] p={t['slope']['p']:.2e}")
    print("  placebo boundaries:")
    print(pd.DataFrame(e["boundaries"]).to_string(index=False))
    print("  drop cuts:")
    print(pd.DataFrame(e["drops"]).to_string(index=False))


def main() -> None:
    # 06b's own panel as committed at publication (2026-09-15 substrate, 2018-2024). The
    # warehouse it came from no longer exists; this parquet is the "before".
    before = pd.read_parquet(REPO_06B / "panel_06b_lap.parquet")
    before["ground"] = (before["race_year"] >= 2022).astype(float)
    # The last pre-WI-15a / pre-WI-01 warehouse on disk (WI-15a's dev_unfixed, 2026-09-25).
    # NOT 06b's substrate: WI-02a, WI-05, WI-09 and WI-13 had landed by then.
    unfixed = load("panel_wi12_lap_as06b_0925.parquet")
    now06b = load("panel_wi12_lap_as06b_now.parquet")
    wi01 = load("panel_wi12_lap_wi01.parquet")
    Y = "partial_residual_s"

    # ------------------------------------------------------------------ R
    rows = per_season(before, Y, F2, "R|06b_committed_panel|F2", PRE_REG)
    for row in rows:
        row["published"] = PUBLISHED_06B_F2[row["season"]]
    show("R  REPRODUCTION: 06b's committed panel through this script's estimator, F2 "
         "(must match 06b's table)", rows)
    bad = [x for x in rows if abs(x["theta"] - x["published"]) > 0.0015]
    if bad:
        sys.exit(f"REPRODUCTION FAILED: {bad}")
    print("  REPRODUCTION PASS (every season within rounding of the published table)")
    show("R' 06b's SQL on the 2026-09-25 pre-WI-15a/WI-01 warehouse, F2 (intermediate, "
         "not 06b's substrate)", per_season(unfixed, Y, F2, "R|unfixed|F2", ALL))

    # ------------------------------------------------------------------ L
    ladder = {}
    for rung, fe in RUNGS.items():
        rows = per_season(wi01, Y, fe, f"L|{rung}", ALL, no_boundary=(rung == "F3"))
        ladder[rung] = rows
        show(f"L  LADDER on the WI-01 label  --  rung {rung}  (FE: {fe or 'none'})"
             + ("  minus laps within 2 of SC/VSC/red/pit" if rung == "F3" else ""), rows)

    # ------------------------------------------------------------------ P
    show("P  LEAD PLACEBO (pre-registered, F2), WI-01 label", placebo(wi01, Y, "P|wi01", ALL))
    show("P' LEAD PLACEBO, same rule, 06b's committed panel (re-derives 06b's ruling)",
         placebo(before, Y, "P|06b_committed", PRE_REG))
    show("P'' LEAD PLACEBO, F3 sample (no laps near SC/VSC/red/pit), WI-01 label",
         placebo(wi01[wi01["near_boundary"] == 0], Y, "P|wi01_F3", ALL))

    # ------------------------------------------------------------------ E
    pre = wi01[wi01["race_year"] <= 2024]
    e = era_block(pre, Y, "E|wi01_2018_24")
    print_era("E  THE 2022 QUESTION, pre-registered window 2018-2024, WI-01 label", e)
    e_b = era_block(before, Y, "E|06b_committed_2018_24")
    print_era("E' same, 06b's committed panel (reproduces 06b's era numbers)", e_b)
    e25 = era_block(wi01, Y, "E|wi01_2018_25")
    print_era("E'' sensitivity: the same on 2018-2025", e25)
    # 2025 against the 2018-2024 trend (06b named 2025 as its out-of-sample test)
    t = RES["E|wi01_2018_24|trend"]
    pred = t["d_lag1"]["coef"] + 4 * t["d_lag1:season_c"]["coef"]
    obs = RES["L|F2|2025"]["d_lag1"]
    print(f"\n  2025 CHECK: 2018-24 trend extrapolates theta(2025) = {pred:+.4f}; "
          f"observed {obs['coef']:+.4f} [{obs['ci_lo']:+.4f}, {obs['ci_hi']:+.4f}]")
    RES["E|2025_check"] = {"trend_prediction": pred, "observed": obs}

    # ------------------------------------------------------------------ D
    rows = []
    arms = (
        ("0 06b committed panel (published)", before, Y),
        ("1 06b SQL, 09-25 pre-WI-15a/WI-01 warehouse", unfixed, Y),
        ("2 06b SQL, 09-25 warehouse, measured base only", unfixed[~unfixed["base_null"]], Y),
        ("3 06b SQL, WI-01 warehouse (fabricated base, fuel only)", now06b, Y),
        ("4 06b SQL, WI-01 warehouse, measured base only", now06b[~now06b["base_null"]], Y),
        ("5 WI-01 calibration panel, y without the tyre-cost term", wi01, "y_fuel_only_s"),
        ("6 WI-01 calibration panel (headline)", wi01, Y),
    )
    for label, df, y in arms:
        row = {"arm": label}
        for s in ALL:
            d = df[df["race_year"] == s]
            if len(d) == 0:
                row[s] = None
                continue
            o = fit(d, y, "d_lag1", F2, f"D|{label[:1]}|{s}")
            row[s] = r(o["d_lag1"]["coef"])
        rows.append(row)
    show("D  DECOMPOSITION: per-season F2 theta by arm (which change moved the numbers)", rows)

    # ------------------------------------------------------------------ W
    wi01 = wi01.assign(
        y_minus_constructor=wi01[Y] - wi01["constructor_component_s"].fillna(0.0),
        constructor_race=wi01["constructor_id"].astype(str) + "|" + wi01["race_id"])
    # Labels renamed after the W40 ruling (2026-09-27): F0 was "(shipped label value)"
    # and F2 "(06b headline)" in the first run. The numbers are unchanged.
    f2_label = "F2 stint FE + tyre-age bins (06b headline; label value since W40)"
    specs = (
        ("F0 pooled OLS (WI-01 interim label value)", Y, None, wi01),
        ("F0, constructor term also subtracted", "y_minus_constructor", None, wi01),
        ("constructor x race FE", Y, "constructor_race", wi01),
        ("F1 driver x race FE", Y, "driver_race", wi01),
        ("F1 + tyre-age bins", Y, "driver_race + age_bin", wi01),
        ("stint FE only", Y, "stint_id", wi01),
        (f2_label, Y, F2, wi01),
        ("F2 on y without the tyre-cost term", "y_fuel_only_s", F2, wi01),
        ("F3 (F2 minus laps near SC/VSC/red/pit)", Y, F2, wi01[wi01["near_boundary"] == 0]),
    )
    rows = []
    for label, y, fe, df in specs:
        o = fit(df, y, "d_lag1", fe, f"W|{label}")
        b = o["d_lag1"]
        rows.append({"estimator (2018-2025 pooled)": label, "n": o["n"], "theta": r(b["coef"], 4),
                     "ci_lo": r(b["ci_lo"], 4), "ci_hi": r(b["ci_hi"], 4)})
    show("W  W40: which estimator prices the label (pooled over the label's 2018-2025 window)",
         rows)
    # W40 gate: the label's declared theta_air_label_value must be this F2 fit to 3 dp.
    # The model applies the var and no longer fits theta itself, so this is the only
    # place the declared value is tied back to data.
    decl = re.search(r"^\s*theta_air_label_value:\s*([0-9.]+)\s*$",
                     (HERE.parents[3] / "transform/dbt_project.yml").read_text(), re.M)
    f2_coef = RES[f"W|{f2_label}"]["d_lag1"]["coef"]
    if not decl or round(f2_coef, 3) != float(decl.group(1)):
        sys.exit(f"W40 GATE FAILED: F2 {f2_coef:.6f} does not round to the declared "
                 f"theta_air_label_value {decl.group(1) if decl else '(missing)'}")
    print(f"  W40 GATE PASS: declared theta_air_label_value {decl.group(1)} = F2 "
          f"{f2_coef:.6f} to 3 dp")
    for label, fe in (("F2", F2), ("F0", None)):
        j = fit(wi01, Y, "d_lag1 + d_lead1", fe, f"W|pooled_placebo|{label}")
        lml = j["lag_minus_lead"]
        print(f"  pooled 2018-2025 lead placebo, {label}: lag {j['d_lag1']['coef']:+.4f}  "
              f"lead {j['d_lead1']['coef']:+.4f}  lag-lead {lml['coef']:+.4f} "
              f"[{lml['ci_lo']:+.4f}, {lml['ci_hi']:+.4f}]")
    conf = {}
    for col in ("compound_component_s", "constructor_component_s", "y_fuel_only_s", Y):
        g = wi01.groupby("d_lag1")[col].mean()
        conf[col] = {"untreated": float(g.loc[0.0]), "treated": float(g.loc[1.0]),
                     "treated_minus_untreated": float(g.loc[1.0] - g.loc[0.0])}
    RES["W|confounders"] = conf
    print("\n  mean by treatment arm (D_lag1 = 0 / 1), and the difference:")
    for k, v in conf.items():
        print(f"    {k:26s} {v['untreated']:+.4f} / {v['treated']:+.4f}   "
              f"diff {v['treated_minus_untreated']:+.4f}")
    # within-stint: is the lag correlated with the tyre term once stint + age bin are absorbed?
    o = fit(wi01, "compound_component_s", "d_lag1", F2, "W|compound_on_D_within")
    print(f"    compound term on D_lag1 within stint + age bin: "
          f"{o['d_lag1']['coef']:+.4f} [{o['d_lag1']['ci_lo']:+.4f}, {o['d_lag1']['ci_hi']:+.4f}]")

    # ------------------------------------------------------------------ C
    cpath = SCRATCH / "panel_wi12_corner.parquet"
    if cpath.exists():
        corner = pd.read_parquet(cpath)
        corner = corner[corner["race_year"] <= 2024].copy()   # pre-registered window
        corner["ground"] = (corner["race_year"] >= 2022).astype(float)
        FEc = "driver_race_corner + age_bin"
        for outcome in ("mid_corner_residual_s", "corner_residual_total_s"):
            rows = []
            for cls in sorted(corner["corner_class"].unique()):
                sub = corner[corner["corner_class"] == cls]
                p = fit(sub[sub["ground"] == 0], outcome, "d_lag1", FEc, f"C|{outcome}|{cls}|pre")
                g = fit(sub[sub["ground"] == 1], outcome, "d_lag1", FEc, f"C|{outcome}|{cls}|ground")
                dl = fit(sub, outcome, "d_lag1 + d_lag1:ground", FEc, f"C|{outcome}|{cls}|delta")
                rows.append({"class": cls, "n_pre": p["n"], "n_ground": g["n"],
                             "pre": r(p["d_lag1"]["coef"], 4),
                             "ground": r(g["d_lag1"]["coef"], 4),
                             "pct_apex_pre": r(100 * 0.2778 * p["d_lag1"]["coef"], 2),
                             "pct_apex_ground": r(100 * 0.2778 * g["d_lag1"]["coef"], 2),
                             "delta": r(dl["d_lag1:ground"]["coef"], 4),
                             "ci_lo": r(dl["d_lag1:ground"]["ci_lo"], 4),
                             "ci_hi": r(dl["d_lag1:ground"]["ci_hi"], 4)})
            show(f"C  CORNER CLASS x ERA, {outcome}, WI-01 treatment, 2018-2024", rows)
        rows = []
        for s in PRE_REG:
            d = corner[(corner["corner_class"] == "1_slow") & (corner["race_year"] == s)]
            o = fit(d, "mid_corner_residual_s", "d_lag1", FEc, f"C|slow_mid|{s}")
            rows.append({"season": s, "n": o["n"], "slow_mid": r(o["d_lag1"]["coef"], 4),
                         "ci_lo": r(o["d_lag1"]["ci_lo"], 4), "ci_hi": r(o["d_lag1"]["ci_hi"], 4)})
        show("C' slow-corner apex deficit per season (06b's 'precise half')", rows)
    else:
        print(f"\n(corner panel not found at {cpath}; section C skipped)")

    OUT.write_text(json.dumps(RES, indent=1, default=float))
    print(f"\nwrote {OUT} ({len(RES)} entries)")


if __name__ == "__main__":
    main()
