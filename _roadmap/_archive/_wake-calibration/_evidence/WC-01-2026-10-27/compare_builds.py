"""WC-01 before/after reason transition between two scratch builds. Counts only; nothing is fitted.

    python compare_builds.py <before scratch dir> <after scratch dir> <evidence dir>

Passes are joined on (season, race, driver, lap, corner_id). Writes reason_transition.csv
(before reason x after reason, "kept" = no reason) and prints the flat-out corner summary.
"""
import glob
import sys
from pathlib import Path

import pandas as pd

KEY = ["season", "race", "driver", "lap", "corner_id"]
before, after, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])


def load(folder: Path, cols: list[str]) -> pd.DataFrame:
    return pd.concat([pd.read_parquet(p, columns=cols) for p in sorted(glob.glob(str(folder / "pass_table_*.parquet")))],
                     ignore_index=True)


b = load(before, KEY + ["reason", "seg_offset_m"])
a = load(after, KEY + ["reason", "seg_offset_m", "segment_basis"])
m = b.merge(a, on=KEY, how="outer", suffixes=("_before", "_after"), indicator=True)
print("join:", m["_merge"].value_counts().to_dict())
tr = pd.crosstab(m["reason_before"].fillna("kept"), m["reason_after"].fillna("kept"), margins=True, margins_name="total")
tr.to_csv(dst / "reason_transition.csv")
print(tr.to_string())
same = m["segment_basis"] == "brake_onset"
moved = (m["seg_offset_m_before"] - m["seg_offset_m_after"]).abs() > 1e-9
print("brake_onset passes whose segment start changed:", int((same & moved).sum()))
flat = m["reason_before"] == "flat_kink"
print("former flat_kink passes by segment_basis:", m.loc[flat, "segment_basis"].value_counts().to_dict())
rc = a.drop_duplicates(["season", "race", "corner_id"])
print("race-corners by segment_basis:", rc["segment_basis"].value_counts().to_dict())
