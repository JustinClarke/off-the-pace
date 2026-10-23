"""DA-01 settle, item 2. Does the MultiViewer marshal-sector layout fit the
race-control sector yellows?

For each race in three groups:
  T  = 2018 races where the API served the 2019 layout (test)
  C1 = 2018 races where the API served the 2018 layout (control)
  C2 = 2019 races at the same circuits as T, 2019 layout (control)
do:
  1. Build a reference track polyline from the race's own position channel
     (stg_telemetry_position view): median x/y and median speed per 0.002
     relative_distance bin, OnTrack samples outside pit windows.
  2. Project each marshal-sector marker (trackPosition x/y) onto that polyline:
     rd_k and the off-track distance of the marker (position units, 1/10 m).
  3. For each race-control sector YELLOW / DOUBLE YELLOW message, convert its
     UTC Time to session time (laps: lap-1 LapStartDate vs LapStartTime), and
     find the slowest car on track in [t-20 s, t+3 s] (speed / bin median
     speed, OnTrack, outside pit window +-5 s). Skip messages when the field
     is slow (median ratio < 0.7: SC/VSC/red). A message is matched when the
     slowest car's ratio < 0.5.
  4. Predict the marshal sector from that car's relative_distance under two
     conventions (marker = sector start; marker = nearest) and compare with
     the race-control sector number: exact and within +-1.
Read-only: dev is ATTACHed READ_ONLY from the scratch copy. Run with cwd =
repo transform/ so the views' relative bronze paths resolve.
Usage: python 08_ms_layout_fit.py <settle_dir> <da01_scratch_dir>
"""
import csv
import json
import os
import sys

import duckdb
import numpy as np
import pandas as pd

S, D1 = sys.argv[1], sys.argv[2]
con = duckdb.connect()
con.execute("SET threads TO 10")
con.execute(f"ATTACH '{S}/dev.duckdb' AS dev (READ_ONLY)")

served = list(csv.DictReader(open(os.path.join(D1, "out", "07c_served_year_by_race_2018_2020.csv"))))
T = [r for r in served if r["race_year"] == "2018" and r["same_year"] == "False"]
C1 = [r for r in served if r["race_year"] == "2018" and r["same_year"] == "True"]
t_keys = {r["circuit_key"] for r in T}
C2 = [r for r in served if r["race_year"] == "2019" and r["circuit_key"] in t_keys]
groups = [("T_2018_on_2019_layout", T), ("C1_2018_on_2018_layout", C1), ("C2_2019_on_2019_layout", C2)]

msg_rows, race_rows, marker_rows = [], [], []

for gname, races in groups:
    for r in races:
        rid, slug, year, key = r["race_id"], r["race_slug"], int(r["race_year"]), r["circuit_key"]
        lay = json.load(open(os.path.join(D1, "dl", f"c{key}_{year}.json")))
        ms = sorted(lay.get("marshalSectors") or [], key=lambda m: m["number"])
        n_ms = len(ms)
        tel = con.sql(f"""
            SELECT driver_id, lap_number, session_time_s AS t, relative_distance AS rd,
                   pos_x AS x, pos_y AS y, speed_kph AS v, track_status AS st
            FROM dev.main.stg_telemetry_position WHERE race_id = '{rid}'
              AND pos_x IS NOT NULL AND relative_distance IS NOT NULL""").df()
        base = {"group": gname, "race_id": rid, "race_slug": slug, "layout_year": lay.get("year"), "n_ms": n_ms}
        if tel.empty:
            race_rows.append({**base, "telemetry": False})
            continue
        pits = con.sql(f"""SELECT driver_id, pit_in_time_s - 5 AS a,
                COALESCE(pit_out_time_s, pit_in_time_s + 120) + 5 AS b
                FROM dev.main.stg_pits WHERE race_id = '{rid}' AND pit_in_time_s IS NOT NULL""").df()
        tel["in_pit"] = False
        for p in pits.itertuples():
            m = (tel.driver_id == p.driver_id) & (tel.t >= p.a) & (tel.t <= p.b)
            tel.loc[m, "in_pit"] = True
        tel["bin"] = np.minimum((tel.rd.clip(0, 0.99999) * 500).astype(int), 499)
        ok = (tel.st == "OnTrack") & ~tel.in_pit & (tel.lap_number >= 2)
        ref = tel[ok].groupby("bin").agg(x=("x", "median"), y=("y", "median"), v=("v", "median")).reindex(range(500))
        ref = ref.interpolate(limit_direction="both")
        tel["ratio"] = tel.v / ref.v.values[tel.bin.values]

        # marshal markers onto the polyline
        rx, ry = ref.x.values, ref.y.values
        mk_rd, mk_off = [], []
        for m in ms:
            d = np.hypot(rx - m["trackPosition"]["x"], ry - m["trackPosition"]["y"])
            i = int(np.argmin(d))
            mk_rd.append((i + 0.5) / 500)
            mk_off.append(float(d[i]))
            marker_rows.append({**base, "number": m["number"], "rd": round((i + 0.5) / 500, 4), "off_track_units": round(float(d[i]), 1)})
        mk_rd = np.array(mk_rd)
        # ordering: markers in number order should advance around the lap (circular)
        steps = np.diff(np.r_[mk_rd, mk_rd[0]]) % 1.0 if n_ms else np.array([])
        in_order = int(np.sum(steps < 0.5)) if n_ms else 0  # forward step (wrap counted once)
        wraps = int(np.sum(np.diff(mk_rd) < 0)) if n_ms else 0

        # session-time offset
        laps = con.sql(f"""SELECT MIN(LapStartTime) AS lst, MIN(LapStartDate) AS lsd
            FROM read_parquet('../data/bronze/laps/season={year}/race={slug}/*.parquet') WHERE LapNumber = 1""").df()
        lst = pd.to_timedelta(laps.lst[0]).total_seconds() if not pd.api.types.is_number(laps.lst[0]) else laps.lst[0] / 1e9
        off = lst - pd.Timestamp(laps.lsd[0]).timestamp()
        rc = con.sql(f"""SELECT Time, Flag, CAST(Sector AS INTEGER) AS sector, Lap
            FROM read_parquet('../data/bronze/race_control/season={year}/race={slug}/*.parquet', union_by_name = true)
            WHERE Scope = 'Sector' AND Flag IN ('YELLOW', 'DOUBLE YELLOW') ORDER BY Time""").df()
        race_rows.append({**base, "telemetry": True, "marker_median_off_units": round(float(np.median(mk_off)), 1) if n_ms else "",
                          "marker_max_off_units": round(float(np.max(mk_off)), 1) if n_ms else "",
                          "markers_in_number_order": f"{n_ms - wraps + (1 if wraps else 0)}/{n_ms}" if n_ms else "",
                          "order_wraps": wraps, "rc_sector_yellows": len(rc),
                          "rc_max_sector": int(rc.sector.max()) if len(rc) else ""})
        for m in rc.itertuples():
            t = pd.Timestamp(m.Time).timestamp() + off
            w = tel[(tel.t >= t - 20) & (tel.t <= t + 3)]
            field = w[(w.st == "OnTrack") & ~w.in_pit]
            rec = {**base, "t_session": round(t, 1), "lap": m.Lap, "flag": m.Flag, "rc_sector": m.sector}
            if field.empty or field.ratio.median() < 0.7:
                rec["status"] = "field_slow_or_empty"
                msg_rows.append(rec)
                continue
            # prefer a car that was at racing speed shortly before (a fresh
            # incident) over one parked long ago; fall back to the slowest car
            mins = field.sort_values("ratio").groupby("driver_id").head(1)
            prev = tel[(tel.t >= t - 90) & (tel.t < t - 20) & (tel.st == "OnTrack") & ~tel.in_pit]
            fresh = set(prev[prev.ratio > 0.7].driver_id)
            slow = mins[mins.ratio < 0.5]
            pick = slow[slow.driver_id.isin(fresh)]
            cand = (pick if len(pick) else mins).iloc[0]
            # position from x/y projected on the polyline (relative_distance
            # is unreliable for stopped/retired cars)
            dxy = np.hypot(rx - cand.x, ry - cand.y)
            ixy = int(np.argmin(dxy))
            rd_xy = (ixy + 0.5) / 500
            rec.update({"slow_driver": cand.driver_id, "min_ratio": round(float(cand.ratio), 3),
                        "fresh": cand.driver_id in fresh, "n_slow_cars": len(slow),
                        "slow_rd_channel": round(float(cand.rd), 4), "slow_rd": round(rd_xy, 4),
                        "slow_off_track_units": round(float(dxy[ixy]), 1)})
            if cand.ratio >= 0.5:
                rec["status"] = "no_slow_car"
                msg_rows.append(rec)
                continue
            rd = rd_xy
            k_start = int(ms[int(np.argmax(np.where(mk_rd <= rd, mk_rd, -1)))]["number"]) if np.any(mk_rd <= rd) else int(ms[int(np.argmax(mk_rd))]["number"])
            cd = np.abs((mk_rd - rd + 0.5) % 1.0 - 0.5)
            k_near = int(ms[int(np.argmin(cd))]["number"])
            def circ(a, b):
                dd = abs(a - b) % n_ms
                return min(dd, n_ms - dd)
            rec.update({"status": "matched", "pred_start": k_start, "pred_nearest": k_near,
                        "d_start": circ(k_start, m.sector), "d_nearest": circ(k_near, m.sector)})
            msg_rows.append(rec)
        print(gname, rid, slug, "n_ms", n_ms, "rc", len(rc), flush=True)

out = os.path.join(S, "out")
for name, rows in [("08_ms_fit_messages", msg_rows), ("08_ms_fit_races", race_rows), ("08_ms_markers", marker_rows)]:
    keys = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    with open(os.path.join(out, name + ".csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

m = pd.DataFrame(msg_rows)
mm = m[m.status == "matched"]
summ = []
for g, x in m.groupby("group"):
    y = mm[mm.group == g]
    summ.append({"group": g, "races": x.race_id.nunique(), "yellow_msgs": len(x),
                 "matched": len(y), "field_slow": int((x.status == "field_slow_or_empty").sum()),
                 "no_slow_car": int((x.status == "no_slow_car").sum()),
                 "start_exact": round((y.d_start == 0).mean(), 3), "start_within1": round((y.d_start <= 1).mean(), 3),
                 "nearest_exact": round((y.d_nearest == 0).mean(), 3), "nearest_within1": round((y.d_nearest <= 1).mean(), 3),
                 "start_median_dist": float(y.d_start.median()) if len(y) else None,
                 "start_far_ge3": int((y.d_start >= 3).sum())})
for sub, cond in [("fresh_only", mm.fresh == True), ("fresh_single_slow_car", (mm.fresh == True) & (mm.n_slow_cars == 1))]:
    for g, y in mm[cond].groupby("group"):
        summ.append({"group": g + "|" + sub, "matched": len(y),
                     "start_exact": round((y.d_start == 0).mean(), 3), "start_within1": round((y.d_start <= 1).mean(), 3),
                     "nearest_exact": round((y.d_nearest == 0).mean(), 3), "nearest_within1": round((y.d_nearest <= 1).mean(), 3),
                     "start_median_dist": float(y.d_start.median()), "start_far_ge3": int((y.d_start >= 3).sum())})
pd.DataFrame(summ).to_csv(os.path.join(out, "08_ms_fit_summary_by_group.csv"), index=False)
per_race = mm.groupby(["group", "race_id", "race_slug"]).agg(
    matched=("rc_sector", "size"), start_exact=("d_start", lambda s: round((s == 0).mean(), 3)),
    start_within1=("d_start", lambda s: round((s <= 1).mean(), 3)),
    nearest_exact=("d_nearest", lambda s: round((s == 0).mean(), 3)),
    nearest_within1=("d_nearest", lambda s: round((s <= 1).mean(), 3))).reset_index()
per_race.to_csv(os.path.join(out, "08_ms_fit_summary_by_race.csv"), index=False)
print(pd.DataFrame(summ).to_string())
print(per_race.to_string())
print(pd.DataFrame(race_rows).to_string())
