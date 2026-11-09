"""Counts only: kept fixed_before_apex passes that follow a car within the existing 3 s clean threshold, and how
many of those have the follower's DRS open (codes 10, 12, 14) anywhere in the outcome segment."""
import glob, sys
import numpy as np, pandas as pd, pyarrow.parquet as pq
src = sys.argv[1]; B = "/Users/justin/github/off-the-pace/data/bronze"
OPEN = {10, 12, 14}
rows = []
for p in sorted(glob.glob(f"{src}/pass_table_*.parquet")):
    t = pd.read_parquet(p, columns=["season", "race", "driver", "segment_basis", "reason", "gap_s", "clear_ahead",
                                    "seg_start_t", "seg_end_t", "corner_class"])
    t = t[t.reason.isna()]
    for (s, r), g in t.groupby(["season", "race"]):
        tel = pq.read_table(f"{B}/telemetry/season={s}/race={r}/telemetry.parquet", columns=["driver_id", "SessionTime", "DRS"]).to_pandas()
        tel["t"] = tel.SessionTime.dt.total_seconds(); tel["open"] = tel.DRS.isin(OPEN)
        g = g.copy(); g["drs_open"] = False
        for d, gd in g.groupby("driver"):
            td = tel[tel.driver_id == d].sort_values("t")
            ct = np.concatenate([[0], np.cumsum(td.open.to_numpy())]); tt = td.t.to_numpy()
            i0 = np.searchsorted(tt, gd.seg_start_t.to_numpy()); i1 = np.searchsorted(tt, gd.seg_end_t.to_numpy(), side="right")
            g.loc[gd.index, "drs_open"] = (ct[i1] - ct[i0]) > 0
        g["following"] = (~g.clear_ahead) & (g.gap_s < 3.0)
        rows.append(g.groupby(["season", "segment_basis", "following", "drs_open"]).size().rename("passes").reset_index())
out = pd.concat(rows).groupby(["segment_basis", "following", "drs_open"]).passes.sum().reset_index()
print(out.to_string()); out.to_csv(sys.argv[2], index=False)
