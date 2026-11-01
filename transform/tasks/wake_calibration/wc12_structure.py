"""WC-12: per-race circuit STRUCTURE for the placeholder wake rule (seed builder).

Writes transform/seeds/wake_placeholder_race_structure.csv: one row per (season, race) in the WC-03 pass
table, with the number of corners in each class on that race's layout. The placeholder rule
(seeds/wake_placeholder_rule.csv, models/intermediate/int_wake_placeholder_race_loss.sql) turns these counts
into an ASSUMED per-lap loss. Nothing here is fitted.

What is read, and only this:
  * pass_table_<season>.parquet, columns season, race_id, race, corner_id, corner_class, segment_basis.
    These are registered STRUCTURE columns (wc10_io.PASS_STRUCTURE_COLUMNS). No outcome column
    (wc10_io.GUARDED_COLUMNS: segment times, minimum or apex speed, lap times) is opened, for any season,
    so the sealed 2024-25 outcomes stay unread (BUILD-ORDER rule 4, watch W8).
  * layout_checks.csv, columns season, race, n_corners, lap_len_m (FastF1 corner table size and the
    telemetry lap length; layout facts, not outcomes).

Per corner, corner_class (slow < 120 km/h, medium 120-200, fast >= 200) and segment_basis were fixed by the
WC-01 builder once per race and corner. segment_basis 'fixed_before_apex' marks a kink taken flat (fewer than
half of clear-air passes brake); those are counted as `flat`, whatever their class.

Counts are the MEDIAN over every season of the same layout (same circuit slug and same FastF1 corner count),
not the race's own count. One race's classes can be skewed by its conditions (2021 Belgian GP, run behind the
safety car in the wet, puts 11 of its corners in `slow`), and a circuit's structure does not change from year
to year on an unchanged layout. The race's own counts are kept beside the medians for audit.

Run: .venv/bin/python transform/tasks/wake_calibration/wc12_structure.py
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "transform"))
from tasks.wake_calibration.wc10_io import GUARDED_COLUMNS  # noqa: E402  (read-only use of the guard list)

PASS_DIR = ROOT / "_roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table"
OUT = ROOT / "transform/seeds/wake_placeholder_race_structure.csv"
SEASONS = range(2018, 2026)
READ_COLUMNS = ["season", "race_id", "race", "corner_id", "corner_class", "segment_basis"]
LAYOUT_COLUMNS = ["season", "race", "n_corners", "lap_len_m"]
CLASSES = ("fast", "medium", "slow", "flat")


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def build() -> pd.DataFrame:
    bad = set(READ_COLUMNS + LAYOUT_COLUMNS) & GUARDED_COLUMNS
    assert not bad, f"refusing outcome column(s) {bad}"
    frames = []
    for s in SEASONS:
        t = pq.read_table(PASS_DIR / f"pass_table_{s}.parquet", columns=READ_COLUMNS).to_pandas()
        frames.append(t.drop_duplicates(["race_id", "corner_id"]))
    c = pd.concat(frames, ignore_index=True)
    c["race"] = c["race"].map(_nfc)
    c["k"] = c["corner_class"].astype(str).where(c["segment_basis"] == "brake_onset", "flat")
    counts = (c.groupby(["season", "race_id", "race", "k"]).size().unstack(fill_value=0)
              .reindex(columns=list(CLASSES), fill_value=0).reset_index())
    lay = pd.read_csv(PASS_DIR / "layout_checks.csv", usecols=LAYOUT_COLUMNS)
    lay["race"] = lay["race"].map(_nfc)
    out = counts.merge(lay, on=["season", "race"], how="left", validate="1:1")
    assert out["n_corners"].notna().all(), "race with no layout row"
    grp = out.groupby(["race", "n_corners"])
    out["layout_seasons"] = grp["season"].transform("count")
    for k in CLASSES:
        out[f"race_n_{k}"] = out[k]
        out[f"n_{k}"] = grp[k].transform("median")
    out["season"] = out["season"].astype(int)
    out["n_corners"] = out["n_corners"].astype(int)
    out["lap_length_m"] = out["lap_len_m"].round(0).astype(int)
    out = out.sort_values(["season", "race_id"], key=lambda s: s.map(_sort_key) if s.name == "race_id" else s)
    return out[["season", "race_id", "race", "n_corners", "lap_length_m", "layout_seasons"]
               + [f"n_{k}" for k in CLASSES] + [f"race_n_{k}" for k in CLASSES]]


def _sort_key(race_id: str) -> int:
    season, rnd = race_id.split("_")
    return int(season) * 100 + int(rnd)


if __name__ == "__main__":
    df = build()
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(df)} races")
