"""06b diagnostics and post-hoc cuts. Everything here is labelled POST-HOC in the leaf
doc except the two items it says were pre-registered (the lead placebo already ran in d2).

1. DEVIATION EVIDENCE -- does the treatment mechanically rescale two of the three corner
   phases? braking_loss_s and exit_residual_s both multiply a metre deviation by
   dt_per_dm = 1 / own S2 trap speed. mid_corner_residual_s divides by the FIELD's v_min.
   If following raises own S2 trap speed, the first two are rescaled by the treatment
   itself and the third is not.
2. Phase decomposition of the corner effect, by class and era.
3. Placebo era boundaries on the lap panel -- if 2022 did it, a fake boundary elsewhere
   should not produce a comparable Delta.
4. The era contrast with 2018 dropped.

Run:  ./.venv/bin/python scratchpad/d3_diagnostics_06b.py
"""
from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

import duckdb
import pandas as pd
import pyfixest as pf

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)

OUT = Path("scratchpad/06b_diagnostics.json")
SEASONS = (2018, 2019, 2020, 2021, 2022, 2023, 2024)


def fit(df, y, x, fe):
    m = pf.feols(f"{y} ~ {x}" + (f" | {fe}" if fe else ""), data=df,
                 vcov={"CRV1": "race_id"})
    t = m.tidy()
    return {term: {"coef": float(t.loc[term, "Estimate"]),
                   "se": float(t.loc[term, "Std. Error"]),
                   "ci_lo": float(t.loc[term, "2.5%"]),
                   "ci_hi": float(t.loc[term, "97.5%"]),
                   "p": float(t.loc[term, "Pr(>|t|)"])}
            for term in t.index if term != "Intercept"} | {"n": int(m._N)}


def show(title, rows):
    print("\n" + "=" * 92)
    print(title)
    print("=" * 92)
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    res: dict = {}
    lap = pd.read_parquet("scratchpad/panel_06b_lap.parquet")
    lap["ground"] = (lap["race_year"] >= 2022).astype(float)

    # ---- 1. does the treatment move the denominator of two of the three phases? ----
    # stg_sector_times is a VIEW over stg_laps, whose parquet glob is relative to
    # transform/. Run the read from there, then come straight back.
    root = os.getcwd()
    con = duckdb.connect(os.path.join(root, "data/dev.duckdb"), read_only=True)
    os.chdir(os.path.join(root, "transform"))
    try:
        trap = con.execute(
            "SELECT lap_id, speed_trap_kph AS s2_trap_kph FROM stg_sector_times "
            "WHERE sector = 2 AND speed_trap_kph > 0"
        ).df()
    finally:
        os.chdir(root)
        con.close()
    lt = lap.merge(trap, on="lap_id", how="inner")
    rows = []
    for s in SEASONS:
        r = fit(lt[lt["race_year"] == s], "s2_trap_kph", "d_lag1", "stint_id + age_bin")
        res[f"TRAP|{s}"] = r
        rows.append({"season": s, "n": r["n"],
                     "d_s2_trap_kph": round(r["d_lag1"]["coef"], 3),
                     "ci_lo": round(r["d_lag1"]["ci_lo"], 3),
                     "ci_hi": round(r["d_lag1"]["ci_hi"], 3)})
    show("DEVIATION EVIDENCE  effect of following on OWN S2 trap speed (km/h), F2 spec\n"
         "  braking_loss_s and exit_residual_s are both scaled by 1/(own S2 trap speed);\n"
         "  mid_corner_residual_s is scaled by the FIELD's v_min and is not.", rows)

    # ------------------------- 2. phase decomposition by class x era -------------------
    corner = pd.read_parquet("scratchpad/panel_06b_corner.parquet")
    corner["ground"] = (corner["race_year"] >= 2022).astype(float)
    phases = ["braking_loss_s", "mid_corner_residual_s", "exit_residual_s",
              "corner_residual_total_s"]
    rows = []
    for ph in phases:
        for cls in sorted(corner["corner_class"].unique()):
            sub = corner[corner["corner_class"] == cls]
            pre = fit(sub[sub["ground"] == 0], ph, "d_lag1",
                      "driver_race_corner + age_bin")
            gnd = fit(sub[sub["ground"] == 1], ph, "d_lag1",
                      "driver_race_corner + age_bin")
            dl = fit(sub, ph, "d_lag1 + d_lag1:ground", "driver_race_corner + age_bin")
            res[f"PHASE|{ph}|{cls}"] = {"pre": pre, "ground": gnd, "delta": dl}
            rows.append({
                "phase": ph.replace("_s", ""), "class": cls,
                "pre": round(pre["d_lag1"]["coef"], 5),
                "ground": round(gnd["d_lag1"]["coef"], 5),
                "delta": round(dl["d_lag1:ground"]["coef"], 5),
                "delta_lo": round(dl["d_lag1:ground"]["ci_lo"], 5),
                "delta_hi": round(dl["d_lag1:ground"]["ci_hi"], 5)})
    show("PHASE DECOMPOSITION  x corner class x era (POST-HOC)", rows)

    # mid-corner per season x class -- the headline corner series
    rows = []
    for cls in sorted(corner["corner_class"].unique()):
        for s in SEASONS:
            d = corner[(corner["corner_class"] == cls) & (corner["race_year"] == s)]
            r = fit(d, "mid_corner_residual_s", "d_lag1", "driver_race_corner + age_bin")
            res[f"MID_SEASON|{cls}|{s}"] = r
            rows.append({"class": cls, "season": s, "n": r["n"],
                         "mid_theta": round(r["d_lag1"]["coef"], 5),
                         "ci_lo": round(r["d_lag1"]["ci_lo"], 5),
                         "ci_hi": round(r["d_lag1"]["ci_hi"], 5)})
    show("APEX-SPEED DEFICIT (mid_corner_residual_s) x class x season", rows)

    # ---------------------------- 3. placebo era boundaries ----------------------------
    rows = []
    for cut in (2019, 2020, 2021, 2022, 2023, 2024):
        lap["fake"] = (lap["race_year"] >= cut).astype(float)
        r = fit(lap, "partial_residual_s", "d_lag1 + d_lag1:fake", "stint_id + age_bin")
        res[f"PLACEBO_ERA|{cut}"] = r
        b = r["d_lag1:fake"]
        rows.append({"boundary": f">= {cut}", "delta": round(b["coef"], 4),
                     "se": round(b["se"], 4), "ci_lo": round(b["ci_lo"], 4),
                     "ci_hi": round(b["ci_hi"], 4), "p": round(b["p"], 4)})
    show("FALSIFICATION 2 (POST-HOC)  placebo era boundaries -- is 2022 special?", rows)

    # -------------------------- 4. era contrast without 2018 ---------------------------
    rows = []
    for drop, label in ((None, "all seasons"), (2018, "2018 dropped"),
                        ("1819", "2018+2019 dropped")):
        d = lap
        if drop == 2018:
            d = lap[lap["race_year"] != 2018]
        elif drop == "1819":
            d = lap[~lap["race_year"].isin([2018, 2019])]
        r = fit(d, "partial_residual_s", "d_lag1 + d_lag1:ground", "stint_id + age_bin")
        res[f"DROP|{label}"] = r
        b = r["d_lag1:ground"]
        rows.append({"sample": label, "n": r["n"],
                     "theta_pre": round(r["d_lag1"]["coef"], 4),
                     "delta": round(b["coef"], 4), "ci_lo": round(b["ci_lo"], 4),
                     "ci_hi": round(b["ci_hi"], 4), "p": round(b["p"], 4)})
    show("FALSIFICATION 3 (POST-HOC)  does the era contrast survive dropping 2018?", rows)

    # ------- linear trend in season, as the alternative to a step at 2022 -------------
    lap["season_c"] = lap["race_year"] - 2021
    r_trend = fit(lap, "partial_residual_s", "d_lag1 + d_lag1:season_c",
                  "stint_id + age_bin")
    res["TREND"] = r_trend
    print("\n" + "=" * 92)
    print("POST-HOC  a linear season trend in theta, as the alternative to a 2022 step")
    print("=" * 92)
    print(f"  theta at 2021      = {r_trend['d_lag1']['coef']:+.4f}")
    b = r_trend["d_lag1:season_c"]
    print(f"  d(theta)/d(season) = {b['coef']:+.4f} "
          f"[{b['ci_lo']:+.4f}, {b['ci_hi']:+.4f}]  p={b['p']:.4f}")

    OUT.write_text(json.dumps(res, indent=1))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
