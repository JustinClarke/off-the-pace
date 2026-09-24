"""R2-C (part 3): does 06b's "no detectable directional cost from 2022" survive removing F1's
fabricated laps?

Reuses 06b's shipped panel SQL verbatim (_improvements/implementations/06b/d1_build_panels_06b.py)
and its F2 spec (stint_id + age_bin FE, CRV1 by race_id), per season, with the lead placebo.
Arm "as_06b" = the panel as 06b built it. Arm "measured_base" = the same panel minus laps where
int_field_pace_curve has no value (partial_residual_s there is just -fuel: F1's COALESCE).

Current build (v14 substrate, 2018-2025), so 'as_06b' will not equal 06b's published table
exactly (its substrate was pre-08m); the comparison that matters is the two arms side by side.
"""
import importlib.util
import pathlib
import warnings

import pandas as pd
import pyfixest as pf

from _db import REPO, con

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

spec = importlib.util.spec_from_file_location(
    "d1", REPO / "_improvements/implementations/06b/d1_build_panels_06b.py")
d1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d1)

c = con()
lap = c.execute(d1.PANEL_SQL).df()
lap = lap[lap["partial_residual_s"].notna()].copy()
base = c.execute("""select f.lap_id, fp.field_pace_smoothed_s is null as base_null
  from int_lap_fuel_state f left join int_field_pace_curve fp
  on f.race_year = fp.race_year and f.race_id = fp.race_id and f.lap_number = fp.lap_number""").df()
lap = lap.merge(base, on="lap_id", how="left")
print(f"panel rows {len(lap):,}; fabricated-base rows {int(lap.base_null.sum()):,}")


def fit(df, x):
    m = pf.feols(f"partial_residual_s ~ {x} | stint_id + age_bin", data=df, vcov={"CRV1": "race_id"})
    t = m.tidy()
    return t


rows = []
for s in sorted(lap.race_year.unique()):
    for arm, d in (("as_06b", lap), ("measured_base", lap[~lap.base_null])):
        d = d[d.race_year == s]
        t = fit(d, "d_lag1")
        tj = fit(d, "d_lag1 + d_lead1")
        rows.append({"season": s, "arm": arm, "n": len(d),
                     "theta": round(t.loc["d_lag1", "Estimate"], 4),
                     "ci_lo": round(t.loc["d_lag1", "2.5%"], 4),
                     "ci_hi": round(t.loc["d_lag1", "97.5%"], 4),
                     "joint_lag": round(tj.loc["d_lag1", "Estimate"], 4),
                     "joint_lead": round(tj.loc["d_lead1", "Estimate"], 4)})
print(pd.DataFrame(rows).to_string(index=False))

# 06b's trend test: d_lag1 x (season - 2021), F2 FE, pooled 2018-2024 (06b's window).
w = lap[lap.race_year <= 2024].copy()
w["season_c"] = w.race_year - 2021
for arm, d in (("as_06b", w), ("measured_base", w[~w.base_null])):
    m = pf.feols("partial_residual_s ~ d_lag1 + d_lag1:season_c | stint_id + age_bin",
                 data=d, vcov={"CRV1": "race_id"})
    t = m.tidy()
    print(f"{arm:14s} trend 2018-24: theta(2021)={t.loc['d_lag1','Estimate']:+.4f}  "
          f"dtheta/dseason={t.loc['d_lag1:season_c','Estimate']:+.4f} "
          f"[{t.loc['d_lag1:season_c','2.5%']:+.4f}, {t.loc['d_lag1:season_c','97.5%']:+.4f}]  n={m._N:,}")
