"""WC-01 Task C (measure only): passes that would change under a sector-level yellow rule.

    python sector_yellow_measure.py <scratch dir with pass_table_*.parquet> <evidence dir>

Counts only; the builder's rule is not changed. Current rule: any track status 2 (yellow) during the lap
neutralises the whole lap. Candidate rule: a race_control yellow with Scope == Sector in marshal sector k,
active during the follower's lap, excludes only the corners in sector k and k+1.

LIMIT: bronze circuit_info holds corner positions only, not marshal-sector positions, so the corner's
marshal sector is APPROXIMATED: marshal sectors are taken as evenly spaced along the lap, with the count =
the highest Sector number seen in race_control for that race slug over 2018-2025, and the corner's lap
fraction = circuit_info Distance / median telemetry lap length. A wide band (k-1 .. k+2) is also counted
to show how much a one-sector misassignment matters.
"""
import glob
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "transform"))
from tasks.wake_calibration import build_pass_table as bpt  # noqa: E402

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
B = bpt.BRONZE
YELLOW = {"YELLOW", "DOUBLE YELLOW"}
# Pass-time variant: the yellow must be active from this many seconds before the segment start (about the
# 300 m gap window) to the segment end, instead of at any time in the lap.
PASS_LEAD_S = 10.0

# Marshal-sector count per slug: highest Sector seen in any season.
n_sec = {}
for f in glob.glob(str(B / "race_control/season=*/race=*/race_control.parquet")):
    slug = re.search(r"race=([^/]+)", f).group(1)
    rc = pq.read_table(f, columns=["Scope", "Sector"]).to_pandas()
    s = rc.loc[rc["Scope"] == "Sector", "Sector"].max()
    if pd.notna(s):
        n_sec[slug] = max(n_sec.get(slug, 0), int(s))


def sector_intervals(rc: pd.DataFrame) -> list[tuple[int, float, float]]:
    """(sector, start, end) for each sector yellow, ended by CLEAR in that sector or a track CLEAR/GREEN."""
    rc = rc.dropna(subset=["t"]).sort_values("t")
    open_, out = {}, []
    for flag, scope, sector, t in rc[["Flag", "Scope", "Sector", "t"]].itertuples(index=False, name=None):
        flag = str(flag).upper()
        if scope == "Sector" and pd.notna(sector):
            k = int(sector)
            if flag in YELLOW:
                open_.setdefault(k, t)
            elif flag == "CLEAR" and k in open_:
                out.append((k, open_.pop(k), t))
        elif scope == "Track" and flag in {"CLEAR", "GREEN", "CHEQUERED"}:
            out += [(k, t0, t) for k, t0 in open_.items()]
            open_ = {}
    out += [(k, t0, np.inf) for k, t0 in open_.items()]
    return out


rows = []
for path in sorted(glob.glob(str(src / "pass_table_*.parquet"))):
    t = pd.read_parquet(path, columns=["season", "race", "driver", "lap", "corner_id", "reason", "yellow_only",
                                       "reason_if_no_yellow", "seg_start_t", "seg_end_t", "circuit_info_season"])
    for (season, race), g in t.groupby(["season", "race"]):
        laps_raw = pq.read_table(next((B / "laps" / f"season={season}" / f"race={race}").glob("*.parquet"))).to_pandas()
        laps = bpt.lap_table(laps_raw)[["driver", "lap", "t0", "t1"]]
        rc = pq.read_table(B / "race_control" / f"season={season}" / f"race={race}" / "race_control.parquet",
                           columns=["Time", "Flag", "Scope", "Sector"]).to_pandas()
        rc["t"] = bpt.race_control_session_seconds(rc, laps_raw)
        iv = sector_intervals(rc)
        ci_season = int(g["circuit_info_season"].iloc[0])
        ci = pq.read_table(next((B / "circuit_info" / f"season={ci_season}" / f"race={race}").glob("*.parquet"))).to_pandas()
        ci["corner_id"] = ci["Number"].astype(int).astype(str) + ci["Letter"].fillna("").astype(str).str.strip()
        tel = pq.read_table(B / "telemetry" / f"season={season}" / f"race={race}" / "telemetry.parquet",
                            columns=["driver_id", "lap_number", "distance_m"]).to_pandas()
        lap_len = float(tel.groupby(["driver_id", "lap_number"])["distance_m"].max().median())
        n = n_sec.get(race, 0)
        frac = (ci.set_index("corner_id")["Distance"] / lap_len).clip(0, 0.999999)
        msec = (np.floor(frac * n) + 1).astype(int) if n else frac * np.nan
        g = g.merge(laps, on=["driver", "lap"], how="left")
        g["msec"] = g["corner_id"].map(msec)
        hit_lap = np.zeros(len(g), dtype=bool)
        hit_lap_wide = np.zeros(len(g), dtype=bool)
        hit_pass = np.zeros(len(g), dtype=bool)
        any_lap = np.zeros(len(g), dtype=bool)
        t0, t1, ms = g["t0"].to_numpy(float), g["t1"].to_numpy(float), g["msec"].to_numpy(float)
        s0, s1 = g["seg_start_t"].to_numpy(float), g["seg_end_t"].to_numpy(float)
        for k, a, b in iv:
            on_lap = (t0 < b) & (t1 > a)
            any_lap |= on_lap
            near = (ms == k) | (ms == (k % n) + 1 if n else False)
            wide = near | (ms == k - 1) | (ms == ((k + 1) % n) + 1 if n else False)
            hit_lap |= on_lap & near
            hit_lap_wide |= on_lap & wide
            hit_pass |= (s0 - PASS_LEAD_S < b) & (s1 > a) & near  # pass-time variant
        g["sector_yellow_on_lap"] = any_lap
        g["hit_lap"] = hit_lap
        g["hit_lap_wide"] = hit_lap_wide
        g["hit_pass"] = hit_pass
        g["n_marshal_sectors"] = n
        rows.append(g[["season", "race", "reason", "yellow_only", "reason_if_no_yellow", "sector_yellow_on_lap",
                       "hit_lap", "hit_lap_wide", "hit_pass", "n_marshal_sectors"]])

a = pd.concat(rows, ignore_index=True)
cand = (a["reason"] == "neutralised") & a["yellow_only"] & a["reason_if_no_yellow"].isna()
kept = a["reason"].isna()


def summary(g: pd.DataFrame) -> dict:
    c = (g["reason"] == "neutralised") & g["yellow_only"] & g["reason_if_no_yellow"].isna()
    k = g["reason"].isna()
    return {
        "passes": len(g),
        "neutralised_now": int((g["reason"] == "neutralised").sum()),
        "neutralised_yellow_only": int(((g["reason"] == "neutralised") & g["yellow_only"]).sum()),
        "yellow_only_other_reason_next": int(((g["reason"] == "neutralised") & g["yellow_only"] & g["reason_if_no_yellow"].notna()).sum()),
        "upper_bound_to_kept": int(c.sum()),
        "to_kept_no_sector_message_on_lap": int((c & ~g["sector_yellow_on_lap"]).sum()),
        "to_kept_sector_rule_k_k1": int((c & ~g["hit_lap"]).sum()),
        "stay_excluded_sector_rule_k_k1": int((c & g["hit_lap"]).sum()),
        "to_kept_sector_rule_wide_band": int((c & ~g["hit_lap_wide"]).sum()),
        "to_kept_pass_time_variant": int((c & ~g["hit_pass"]).sum()),
        "kept_now_would_be_excluded_k_k1": int((k & g["hit_lap"]).sum()),
        "kept_now_would_be_excluded_wide_band": int((k & g["hit_lap_wide"]).sum()),
        "races_no_marshal_sector_count": int(g.loc[g["n_marshal_sectors"] == 0, "race"].nunique()),
    }


out = pd.DataFrame([{"season": s, **summary(g)} for s, g in a.groupby("season")] + [{"season": "all", **summary(a)}])
out.to_csv(dst / "sector_yellow_measure.csv", index=False)
print(out.T.to_string())
