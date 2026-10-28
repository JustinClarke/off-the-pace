"""
WC-03 preparation: integrity pre-flight on the registered pass table (decision record L7).

    cd transform && ../.venv/bin/python ../_roadmap/_wake-calibration/_evidence/WC-03-prep-2026-10-28/preflight_integrity.py \
        ../_roadmap/_wake-calibration/_artifacts/WC-01-pass-table-d

Prints pass/fail and counts only. No time, loss or speed value is printed or written. No pass is classified.
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from tasks.wake_calibration import build_pass_table as bpt
from tasks.wake_calibration import estimator as E


def main(pass_dir: str) -> int:
    files = sorted(glob.glob(str(Path(pass_dir) / "pass_table_*.parquet")))
    p = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    out = []
    cal = bpt.race_calendar(bpt.BRONZE)
    try:
        circ = E.circuit_of(p, cal)
        out.append(("calendar covers every race", True, f"{p['race_id'].nunique()} races"))
    except E.EstimatorError as e:
        out.append(("calendar covers every race", False, str(e)[:80]))
        circ = None
    out.append(("one season per race_id", bool((p.groupby("race_id")["season"].nunique() == 1).all()), ""))
    out.append(("unique (race, driver, lap, corner)",
                not p.duplicated(["season", "race_id", "driver", "lap", "corner_id"]).any(), ""))
    if circ is not None:
        per = pd.Series(circ.to_numpy()).groupby(p["race_id"].to_numpy()).nunique()
        out.append(("one circuit per race", bool((per == 1).all()), f"{per.index.size} races"))
    n_meas = int((p["ref_status"] == "measured").sum())
    try:
        s = E.reference_spread(p)
        ok = bool(np.isfinite(s[p["ref_status"] == "measured"]).all())
        out.append(("reference donors reproduce ref_time_s (assertion only)", ok, f"{n_meas} measured rows checked"))
    except E.EstimatorError as e:
        out.append(("reference donors reproduce ref_time_s (assertion only)", False, str(e)[:60]))
    built = p.groupby("season")["race_id"].unique()
    gap = p["gap_s"].to_numpy(dtype=float)
    y = E.is_yielding(p["tag"])
    fit_pre = ((p["segment_basis"] == E.BRAKING_BASIS) & p["reason"].isna() & ~p["clear_ahead"].astype(bool)
               & (p["ref_status"] == "measured") & ~y & np.isfinite(gap) & (gap >= 0) & (gap < 3))
    for era, spec in E.ERAS.items():
        b = sorted({r for s in spec["fit"] for r in built.get(s, [])})
        c = sorted(set(p.loc[fit_pre & p["season"].isin(spec["fit"]), "race_id"]))
        out.append((f"{era}: every built fit-season race contributes a fit pass (before the loss trim)",
                    b == c, f"built {len(b)}, contributing {len(c)}, none: {sorted(set(b) - set(c))}"))
    for name, ok, note in out:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
