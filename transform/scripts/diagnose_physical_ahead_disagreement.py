"""Read-only diagnostic: one lap where int_lap_physical_ahead and int_lap_proximity name different cars ahead at
the lap's minimum gap, both gaps under 1 s. At the physical model's minimum-gap sample and at int_lap_proximity's
minimum-gap crossing time, lists every other car's interpolated position, straight-line distance, the forward
arc distance on the reference line (what the model ranks by), and a reference-line-FREE time gap: how long the
follower's own trace takes to reach the point where that car is now. Mirrors the core's per-sample projection;
nothing is written.
usage (from transform/):
    ../.venv/bin/python scripts/diagnose_physical_ahead_disagreement.py WAREHOUSE.duckdb RACE_ID DRIVER LAP
"""
import os
import sys

import duckdb
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'python_lib'))
import physical_ahead_core as core  # noqa: E402
from physical_ahead_stage_inmem import open_staging  # noqa: E402


def interp(tj, vj, t):
    return np.interp(t, tj, vj)


def table(tel, win, drv, lap, t, L, tree, g, drivers, fol, label):
    """Rows for every other car at session time t."""
    fx, fy = interp(fol['T'].values, fol.X.values, t), interp(fol['T'].values, fol.Y.values, t)
    _, ix = tree.query([[fx, fy]]); sf = g[ix[0]]
    # follower heading from +-0.5 s
    hx = interp(fol['T'].values, fol.X.values, t + 0.5) - interp(fol['T'].values, fol.X.values, t - 0.5)
    hy = interp(fol['T'].values, fol.Y.values, t + 0.5) - interp(fol['T'].values, fol.Y.values, t - 0.5)
    speed = np.hypot(hx, hy) / 10.0   # m/s (units are 1/10 m, window 1 s)
    rows = []
    for d in drivers:
        if d == drv:
            continue
        o = tel[tel.drv == d]
        tj = o['T'].values
        if len(tj) == 0 or t < tj[0] or t > tj[-1]:
            continue
        k = np.searchsorted(tj, t)
        if k == 0 or k >= len(tj):
            continue
        span = tj[k] - tj[k - 1]
        xj, yj = interp(tj, o.X.values, t), interp(tj, o.Y.values, t)
        _, ixj = tree.query([[xj, yj]]); sj = g[ixj[0]]
        f = ((sj - sf) % L) / 10.0
        dist = np.hypot(xj - fx, yj - fy) / 10.0
        ahead_dot = (xj - fx) * hx + (yj - fy) * hy > 0
        # reference-line-free gap: when does the follower's own trace come nearest to (xj, yj), searching its
        # samples from t to t + 30 s
        m = (fol['T'].values >= t) & (fol['T'].values <= t + 30.0)
        if m.any():
            dd = np.hypot(fol.X.values[m] - xj, fol.Y.values[m] - yj)
            jmin = int(np.argmin(dd)); own_gap = fol['T'].values[m][jmin] - t; own_miss = dd[jmin] / 10.0
        else:
            own_gap, own_miss = np.nan, np.nan
        inpit = bool(core._inwin(d, np.array([t]), win)[0])
        rows.append(dict(car=d, euclid_m=round(dist, 1), ahead_by_heading=bool(ahead_dot),
                         fwd_arc_m=round(f, 1), in_300m_window=bool(0 < f <= core.W_M),
                         own_trace_gap_s=round(own_gap, 2), own_trace_miss_m=round(own_miss, 1),
                         bracket_s=round(span, 2), in_pit_window=inpit))
    df = pd.DataFrame(rows).sort_values('euclid_m')
    print(f'\n--- {label}: session time {t:.2f} s, follower {drv} lap {lap}, follower speed {speed * 3.6:.0f} km/h ---')
    print(df.head(6).to_string(index=False))
    return df


def main(wh, rid, drv, lap):
    lap = int(lap)
    w = duckdb.connect(wh, read_only=True)
    lid = f'{rid.split("_")[0]}_{rid}_{drv}_{lap}'
    p = w.sql(f"SELECT * FROM int_lap_physical_ahead WHERE lap_id = '{lid}'").df().iloc[0]
    x = w.sql(f"SELECT * FROM int_lap_proximity WHERE lap_id = '{lid}'").df().iloc[0]
    print(f'{lid}: physical min gap {p.gap_ahead_phys_s:.3f} s behind {p.gap_ahead_phys_min_driver_id}; '
          f'proximity min gap {x.gap_ahead_min_s:.3f} s behind {x.gap_ahead_min_driver_id} at crossing {x.gap_ahead_min_crossing_s}')
    c = open_staging(4)
    tel, laps = core.read_race_inputs(c.sql('SELECT * FROM stg_physical_ahead_telemetry'),
                                      c.sql('SELECT * FROM stg_physical_ahead_laps'), rid)
    s = core.build_race_samples(tel, laps)
    L = s.attrs['track_length_m'] * 10.0
    # rebuild the reference polyline exactly as the core does (single, legacy rule)
    best = core.reference_candidates(laps, 'legacy').iloc[0]
    ref = tel[(tel.drv == best.Driver) & (tel.lap == best.LapNumber)].sort_values('T')
    xy = ref[['X', 'Y']].values; xy = np.vstack([xy, xy[0]])
    cs = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]
    g = np.arange(0, cs[-1], core.STEP_U)
    tree = cKDTree(np.c_[np.interp(g, cs, xy[:, 0]), np.interp(g, cs, xy[:, 1])])
    print(f'reference lap {best.Driver} lap {int(best.LapNumber)} ({best.LapTime / 1e9:.3f} s), length {cs[-1] / 10:.0f} m')
    win = core._pit_windows(laps)
    drivers = sorted(tel.drv.unique())
    fol = tel[tel.drv == drv].sort_values('T')
    sl = s[(s.driver_id == drv) & (s.lap_number == lap)]
    print('sample classes this lap:', sl.sample_class.value_counts().to_dict(),
          '| samples under 1 s with each car ahead:',
          sl[(sl.sample_class == 'same_lap') & (sl.gap_s < 1)].ahead_driver_id.value_counts().to_dict())
    v = sl[sl.sample_class == 'same_lap'].sort_values('gap_s').iloc[0]
    print(f'physical min-gap sample: t={v.session_time_s:.2f}, gap_s={v.gap_s:.3f}, gap_m={v.gap_m:.1f}, ahead={v.ahead_driver_id}')
    table(tel, win, drv, lap, v.session_time_s, L, tree, g, drivers, fol, 'AT PHYSICAL MIN-GAP SAMPLE')
    tx = float(x.gap_ahead_min_crossing_s)
    near = sl.iloc[(sl.session_time_s - tx).abs().argsort()[:1]].iloc[0]
    print(f'physical sample nearest the proximity crossing: t={near.session_time_s:.2f} class={near.sample_class} '
          f'ahead={near.ahead_driver_id} gap_s={near.gap_s} gap_m={near.gap_m}')
    table(tel, win, drv, lap, tx, L, tree, g, drivers, fol, 'AT PROXIMITY MIN-GAP CROSSING TIME')
    # follower-lap neighbours: the proximity crossing is the FOLLOWER'S bin entry; list the proximity car's ahead-gap too
    for who in (x.gap_ahead_min_driver_id, p.gap_ahead_phys_min_driver_id):
        sub = sl[sl.ahead_driver_id == who]
        print(f'physical samples with {who} as car ahead on this lap: {len(sub)}; classes {sub.sample_class.value_counts().to_dict()}')


if __name__ == '__main__':
    main(*sys.argv[1:5])
