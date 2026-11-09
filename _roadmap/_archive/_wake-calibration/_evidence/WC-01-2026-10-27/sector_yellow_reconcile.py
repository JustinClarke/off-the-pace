"""WC-01 third pass ("c"): before/after for the sector-yellow rule, and reconciliation with the second-pass
measure (sector_yellow_measure.csv, 55,842 to kept / 743 to excluded). Counts only; nothing is fitted.

    python sector_yellow_reconcile.py <before scratch dir (pass b)> <after scratch dir (pass c)> <evidence dir>

Writes:
  reason_transition_2026-10-27c.csv  before reason x after reason ("kept" = no reason), joined on
                                     (season, race, driver, lap, corner_id)
  sector_yellow_reconcile.csv        per season: the built rule against two re-computed variants, to show
                                     where the built count differs from the second-pass measure:
    v0_measure      the second-pass measure's interval logic (time sort not stable, no AllClear cap)
    v1_stable       message order kept for same-timestamp messages, no AllClear cap
    v2_built        v1 plus "a sector yellow ends at the next track status AllClear" (= the builder)
  sector_yellow_kept_to_excluded.csv passes kept in pass b that each variant would exclude, by race
                                     (v0_measure gives the second pass's 743; v2_built = pass c's yellow_sector)
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "transform"))
from tasks.wake_calibration import build_pass_table as bpt  # noqa: E402

KEY = ["season", "race", "driver", "lap", "corner_id"]
before, after, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
B = bpt.BRONZE


def load(folder: Path, cols: list[str]) -> pd.DataFrame:
    return pd.concat([pd.read_parquet(p, columns=cols) for p in sorted(glob.glob(str(folder / "pass_table_*.parquet")))],
                     ignore_index=True)


b = load(before, KEY + ["reason", "reason_if_no_yellow", "yellow_only", "seg_offset_m"])
a = load(after, KEY + ["reason", "seg_offset_m", "marshal_sector", "ts_yellow_on_lap", "segment_basis"])
m = b.merge(a, on=KEY, how="outer", suffixes=("_b", "_c"), indicator=True)
print("join:", m["_merge"].value_counts().to_dict())
same_seg = np.isclose(m["seg_offset_m_b"], m["seg_offset_m_c"], equal_nan=True)
print("segment start unchanged on", int(same_seg.sum()), "of", len(m))
tr = pd.crosstab(m["reason_b"].fillna("kept"), m["reason_c"].fillna("kept"), margins=True, margins_name="total")
tr.to_csv(dst / "reason_transition_2026-10-27c.csv")
print(tr.to_string())



def measure_intervals(rc: pd.DataFrame) -> list[tuple[int, float, float]]:
    """The second-pass measure's logic, copied: plain time sort, no AllClear cap."""
    rc = rc.dropna(subset=["t"]).sort_values("t")
    open_, out = {}, []
    for flag, scope, sector, t in rc[["Flag", "Scope", "Sector", "t"]].itertuples(index=False, name=None):
        flag = str(flag).upper()
        if scope == "Sector" and pd.notna(sector):
            k = int(sector)
            if flag in bpt.YELLOW_FLAGS:
                open_.setdefault(k, t)
            elif flag == "CLEAR" and k in open_:
                out.append((k, open_.pop(k), t))
        elif scope == "Track" and flag in bpt.TRACK_END_FLAGS:
            out += [(k, t0, t) for k, t0 in open_.items()]
            open_ = {}
    out += [(k, t0, np.inf) for k, t0 in open_.items()]
    return out


n_sec_cache: dict[str, int] = {}
rows = []
cols = KEY + ["reason", "reason_if_no_yellow", "yellow_only", "marshal_sector"]
for (season, race), g in m[m["_merge"] == "both"].groupby(["season", "race"]):
    laps_raw = pq.read_table(next((B / "laps" / f"season={season}" / f"race={race}").glob("*.parquet"))).to_pandas()
    laps = bpt.lap_table(laps_raw)[["driver", "lap", "t0", "t1"]]
    rc = pq.read_table(B / "race_control" / f"season={season}" / f"race={race}" / "race_control.parquet").to_pandas()
    if "index" in rc:
        rc = rc.sort_values("index", kind="stable").reset_index(drop=True)
    rc["t"] = bpt.race_control_session_seconds(rc, laps_raw)
    ts = pq.read_table(B / "track_status" / f"season={season}" / f"race={race}" / "track_status.parquet").to_pandas()
    n = n_sec_cache.setdefault(race, bpt.marshal_sector_count(race))
    g = g.merge(laps, on=["driver", "lap"], how="left")
    t0, t1, ms = g["t0"].to_numpy(float), g["t1"].to_numpy(float), g["marshal_sector"].to_numpy(float)
    no_cap = pd.DataFrame({"Status": [], "session_time_s": []})
    variants = {
        "v0_measure": measure_intervals(rc),
        "v1_stable": bpt.sector_yellow_intervals(rc, no_cap),
        "v2_built": bpt.sector_yellow_intervals(rc, ts),
    }
    out = g[["season", "race", "reason_b", "reason_c", "reason_if_no_yellow", "yellow_only"]].copy()
    for name, iv in variants.items():
        out[name] = bpt.in_sector_yellow(t0, t1, ms, iv, n)
    rows.append(out)

r = pd.concat(rows, ignore_index=True)
# The second-pass measure's candidate set: neutralised by yellow only, and no other reason behind it.
cand = (r["reason_b"] == "neutralised") & r["yellow_only"].astype(bool) & r["reason_if_no_yellow"].isna()
kept_b = r["reason_b"].isna()


def summary(g: pd.DataFrame) -> dict:
    c = (g["reason_b"] == "neutralised") & g["yellow_only"].astype(bool) & g["reason_if_no_yellow"].isna()
    k = g["reason_b"].isna()
    row = {"passes": len(g), "yellow_only_candidates": int(c.sum())}
    for v in ("v0_measure", "v1_stable", "v2_built"):
        row[f"to_kept_{v}"] = int((c & ~g[v]).sum())
        row[f"kept_to_excluded_{v}"] = int((k & g[v]).sum())
    row["built_neutralised_to_kept"] = int(((g["reason_b"] == "neutralised") & g["reason_c"].isna()).sum())
    row["built_kept_to_yellow_sector"] = int((k & (g["reason_c"] == "yellow_sector")).sum())
    return row


rec = pd.DataFrame([{"season": s, **summary(g)} for s, g in r.groupby("season")] + [{"season": "all", **summary(r)}])
rec.to_csv(dst / "sector_yellow_reconcile.csv", index=False)
by_race = r[kept_b].groupby(["season", "race"])[["v0_measure", "v1_stable", "v2_built"]].sum()
by_race = by_race[by_race.sum(axis=1) > 0].astype(int).sort_values("v0_measure", ascending=False)
by_race.to_csv(dst / "sector_yellow_kept_to_excluded.csv")
print(by_race.to_string())
print(rec.T.to_string())
