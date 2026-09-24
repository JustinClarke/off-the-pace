"""06b estimation. Runs exactly the arms pre-registered in work/06-publication.md 06b.

Reads the cached panels from d1_build_panels_06b.py; writes
scratchpad/06b_dirty_air_per_season.json with every coefficient, SE, CI and n so any
number in the leaf doc can be recomputed without refitting.

Run:  ./.venv/bin/python scratchpad/d2_fit_06b.py
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd
import pyfixest as pf

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)

OUT = Path("scratchpad/06b_dirty_air_per_season.json")
SEASONS = (2018, 2019, 2020, 2021, 2022, 2023, 2024)
RUNGS = {
    "F0_pooled_ols": None,
    "F1_driver_race": "driver_race",
    "F2_stint_age": "stint_id + age_bin",
    "F3_no_boundary": "stint_id + age_bin",
}


def fit(df: pd.DataFrame, y: str, x: str, fe: str | None) -> dict:
    """One cluster-robust fit; returns the coefficient block for `x`."""
    formula = f"{y} ~ {x}" + (f" | {fe}" if fe else "")
    m = pf.feols(formula, data=df, vcov={"CRV1": "race_id"})
    tidy = m.tidy()
    out = {"formula": formula, "n": int(m._N), "g_clusters": int(df["race_id"].nunique())}
    for term in tidy.index:
        if term == "Intercept":
            continue
        out[term] = {
            "coef": float(tidy.loc[term, "Estimate"]),
            "se": float(tidy.loc[term, "Std. Error"]),
            "t": float(tidy.loc[term, "t value"]),
            "p": float(tidy.loc[term, "Pr(>|t|)"]),
            "ci_lo": float(tidy.loc[term, "2.5%"]),
            "ci_hi": float(tidy.loc[term, "97.5%"]),
        }
    return out


def show(title: str, rows: list[dict]) -> None:
    print("\n" + "=" * 92)
    print(title)
    print("=" * 92)
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    lap = pd.read_parquet("scratchpad/panel_06b_lap.parquet")
    lap["ground"] = (lap["race_year"] >= 2022).astype(float)
    res: dict = {"note": "06b dirty-air coefficient per season", "fits": {}}

    # ---------------------------------------------------------------- per season
    for rung, fe in RUNGS.items():
        rows = []
        for s in SEASONS:
            d = lap[lap["race_year"] == s]
            if rung == "F3_no_boundary":
                d = d[d["near_boundary"] == 0]
            r = fit(d, "partial_residual_s", "d_lag1", fe)
            res["fits"][f"{rung}|{s}"] = r
            b = r["d_lag1"]
            rows.append({"season": s, "n": r["n"], "G": r["g_clusters"],
                         "theta": round(b["coef"], 4), "se": round(b["se"], 4),
                         "ci_lo": round(b["ci_lo"], 4), "ci_hi": round(b["ci_hi"], 4),
                         "p": round(b["p"], 4)})
        show(f"PER-SEASON theta  --  rung {rung}"
             + (f"  (FE: {fe})" if fe else "  (no FE)"), rows)

    # ------------------------------------------------------- pooled era contrast
    pooled = fit(lap, "partial_residual_s", "d_lag1 + d_lag1:ground",
                 "stint_id + age_bin")
    res["fits"]["F2_pooled_era_interaction"] = pooled
    print("\n" + "=" * 92)
    print("PRE-DECLARED CONTRAST  Delta = theta(2022-24) - theta(2018-21), F2, pooled")
    print("=" * 92)
    print(f"  theta(pre)   = {pooled['d_lag1']['coef']:+.4f} "
          f"[{pooled['d_lag1']['ci_lo']:+.4f}, {pooled['d_lag1']['ci_hi']:+.4f}]")
    dd = pooled["d_lag1:ground"]
    print(f"  Delta        = {dd['coef']:+.4f} "
          f"[{dd['ci_lo']:+.4f}, {dd['ci_hi']:+.4f}]  p={dd['p']:.4f}")
    print(f"  theta(ground)= {pooled['d_lag1']['coef'] + dd['coef']:+.4f}")
    print(f"  n={pooled['n']:,}  G={pooled['g_clusters']}")

    # era levels, separately, for the table
    era_rows = []
    for name, mask in (("pre_2018_21", lap["race_year"] < 2022),
                       ("ground_2022_24", lap["race_year"] >= 2022)):
        r = fit(lap[mask], "partial_residual_s", "d_lag1", "stint_id + age_bin")
        res["fits"][f"F2_era|{name}"] = r
        b = r["d_lag1"]
        era_rows.append({"era": name, "n": r["n"], "G": r["g_clusters"],
                         "theta": round(b["coef"], 4), "se": round(b["se"], 4),
                         "ci_lo": round(b["ci_lo"], 4), "ci_hi": round(b["ci_hi"], 4)})
    show("ERA LEVELS, F2", era_rows)

    # ------------------------------------------------------------ lead placebo
    rows = []
    for s in SEASONS:
        d = lap[lap["race_year"] == s]
        r = fit(d, "partial_residual_s", "d_lead1", "stint_id + age_bin")
        rj = fit(d, "partial_residual_s", "d_lag1 + d_lead1", "stint_id + age_bin")
        res["fits"][f"PLACEBO_lead|{s}"] = r
        res["fits"][f"PLACEBO_joint|{s}"] = rj
        rows.append({"season": s,
                     "lead_alone": round(r["d_lead1"]["coef"], 4),
                     "joint_lag": round(rj["d_lag1"]["coef"], 4),
                     "joint_lead": round(rj["d_lead1"]["coef"], 4),
                     "lag_minus_lead": round(rj["d_lag1"]["coef"]
                                             - rj["d_lead1"]["coef"], 4)})
    show("FALSIFICATION 1  --  lead placebo (F2 spec)", rows)

    # ------------------------------------------------------------ corner classes
    corner = pd.read_parquet("scratchpad/panel_06b_corner.parquet")
    corner["ground"] = (corner["race_year"] >= 2022).astype(float)

    def corner_block(df: pd.DataFrame, label: str, key: str) -> list[dict]:
        rows = []
        for cls in sorted(df[key].unique()):
            for era, mask in (("pre_2018_21", df["race_year"] < 2022),
                              ("ground_2022_24", df["race_year"] >= 2022)):
                d = df[(df[key] == cls) & mask]
                r = fit(d, "corner_residual_total_s", "d_lag1",
                        "driver_race_corner + age_bin")
                res["fits"][f"CORNER|{label}|{cls}|{era}"] = r
                b = r["d_lag1"]
                rows.append({"class": cls, "era": era, "n": r["n"],
                             "theta_corner": round(b["coef"], 5),
                             "se": round(b["se"], 5),
                             "ci_lo": round(b["ci_lo"], 5),
                             "ci_hi": round(b["ci_hi"], 5)})
            # pre-declared within-class era contrast
            d = df[df[key] == cls]
            r = fit(d, "corner_residual_total_s", "d_lag1 + d_lag1:ground",
                    "driver_race_corner + age_bin")
            res["fits"][f"CORNER_DELTA|{label}|{cls}"] = r
            b = r["d_lag1:ground"]
            rows.append({"class": cls, "era": "DELTA", "n": r["n"],
                         "theta_corner": round(b["coef"], 5), "se": round(b["se"], 5),
                         "ci_lo": round(b["ci_lo"], 5), "ci_hi": round(b["ci_hi"], 5)})
        return rows

    show("CORNER CLASS x ERA  (absolute v_min thresholds, headline)",
         corner_block(corner, "abs", "corner_class"))

    show("ROBUSTNESS (a)  within-race speed terciles",
         corner_block(corner, "tercile", "corner_tercile_in_race"))

    both = (set(corner.loc[corner["race_year"] < 2022, "track_id"])
            & set(corner.loc[corner["race_year"] >= 2022, "track_id"]))
    show(f"ROBUSTNESS (b)  the {len(both)} tracks present in both eras",
         corner_block(corner[corner["track_id"].isin(both)], "commontrack",
                      "corner_class"))

    # per-season corner class, for the plot the post will need
    rows = []
    for cls in sorted(corner["corner_class"].unique()):
        for s in SEASONS:
            d = corner[(corner["corner_class"] == cls) & (corner["race_year"] == s)]
            r = fit(d, "corner_residual_total_s", "d_lag1",
                    "driver_race_corner + age_bin")
            res["fits"][f"CORNER_SEASON|{cls}|{s}"] = r
            b = r["d_lag1"]
            rows.append({"class": cls, "season": s, "n": r["n"],
                         "theta_corner": round(b["coef"], 5),
                         "ci_lo": round(b["ci_lo"], 5),
                         "ci_hi": round(b["ci_hi"], 5)})
    show("CORNER CLASS x SEASON", rows)

    OUT.write_text(json.dumps(res, indent=1))
    print(f"\nwrote {OUT}  ({len(res['fits'])} fits)")


if __name__ == "__main__":
    main()
