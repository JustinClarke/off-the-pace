"""DA-01 settle, item 2b. Signed sector offset (predicted marker-start sector
of the slow car minus race-control sector, circular) per group and race, and
marker-layout stability across years at the T circuits.
Usage: python -I 08b_offset_summary.py <settle_dir> <da01_scratch_dir>"""
import json
import os
import sys

import numpy as np
import pandas as pd

S, D1 = sys.argv[1], sys.argv[2]
out = os.path.join(S, "out")
m = pd.read_csv(os.path.join(out, "08_ms_fit_messages.csv"))
m = m[m.status == "matched"].copy()


def signed(r):
    d = (r.pred_start - r.rc_sector) % r.n_ms
    return d if d <= r.n_ms / 2 else d - r.n_ms


m["offset"] = m.apply(signed, axis=1).astype(int)
m.to_csv(os.path.join(out, "08b_ms_fit_messages_with_offset.csv"), index=False)


def summ(x):
    o = x.offset
    return pd.Series({"matched": len(o), "median_offset": float(o.median()),
                      "share_0_to_3": round(o.between(0, 3).mean(), 3),
                      "share_neg1_to_3": round(o.between(-1, 3).mean(), 3),
                      "share_abs_ge5": round((o.abs() >= 5).mean(), 3),
                      "race_iqr_offset_median": None})


rows = []
for g, x in m.groupby("group"):
    s = summ(x)
    iqr = x.groupby("race_id").offset.agg(lambda o: np.subtract(*np.percentile(o, [75, 25])))
    s["race_iqr_offset_median"] = float(iqr.median())
    rows.append({"group": g, **s.to_dict()})
pd.DataFrame(rows).to_csv(os.path.join(out, "08b_offset_by_group.csv"), index=False)
per_race = m.groupby(["group", "race_id", "race_slug"]).apply(summ, include_groups=False).reset_index()
per_race["offsets"] = m.groupby(["group", "race_id", "race_slug"]).offset.agg(lambda o: " ".join(map(str, o))).values
per_race.drop(columns="race_iqr_offset_median").to_csv(os.path.join(out, "08b_offset_by_race.csv"), index=False)
print(pd.DataFrame(rows).to_string())
print(per_race.drop(columns="race_iqr_offset_median").to_string())

# layout stability: for each T circuit compare the served 2019 layout with
# the 2020-2025 payloads (served year, count, max marker shift in units)
keys = {"10": "Melbourne", "63": "Sakhir", "144": "Baku", "15": "Catalunya", "22": "Monte Carlo",
        "23": "Montreal", "28": "Paul Ricard", "19": "Spielberg", "2": "Silverstone", "34": "Hockenheim"}
st = []
for k, name in keys.items():
    base = json.load(open(os.path.join(D1, "dl", f"c{k}_2019.json")))
    bm = {m_["number"]: m_["trackPosition"] for m_ in base["marshalSectors"]}
    for y in range(2018, 2026):
        p = os.path.join(D1, "dl", f"c{k}_{y}.json")
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            continue
        try:
            d = json.load(open(p))
        except ValueError:
            continue
        ms = {m_["number"]: m_["trackPosition"] for m_ in d.get("marshalSectors") or []}
        common = set(ms) & set(bm)
        shift = max((np.hypot(ms[n]["x"] - bm[n]["x"], ms[n]["y"] - bm[n]["y"]) for n in common), default=None)
        st.append({"circuit_key": k, "circuit": name, "requested_year": y, "served_year": d.get("year"),
                   "n_ms": len(ms), "n_ms_2019": len(bm),
                   "max_marker_shift_vs_2019_units": round(float(shift), 1) if shift is not None else ""})
pd.DataFrame(st).to_csv(os.path.join(out, "08b_layout_stability_T_circuits.csv"), index=False)
print(pd.DataFrame(st).to_string())
