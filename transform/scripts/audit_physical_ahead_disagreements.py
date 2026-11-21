"""Read-only audit: on laps where int_lap_physical_ahead and int_lap_proximity name different cars ahead at the lap
minimum (both minima < 1 s, valid, non-neutralised), who is right? Judged WITHOUT either model's machinery, from the
follower's own X/Y trace: for a claim 'car C was G seconds ahead at session time t', take C's interpolated position at t
and find when the follower's own trace comes nearest to that point within the next 30 s (own-trace gap). A claim is
SUPPORTED when that point is reached (miss <= 25 m) and own-trace gap is within TOL s of G. Proximity's claim is tested at
its crossing time; the physical claim at its minimum-gap sample. Samples a few laps per race. Nothing is written.
usage (from transform/):
    ../.venv/bin/python scripts/audit_physical_ahead_disagreements.py WAREHOUSE.duckdb OUT.csv [--races 2025_4,2025_5] [--per-race 12]
"""
import argparse
import os
import sys

import duckdb
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'python_lib'))
import physical_ahead_core as core  # noqa: E402
from physical_ahead_stage_inmem import open_staging  # noqa: E402

TOL = 0.30     # s; one position sample is ~0.2-0.3 s apart, so +-0.3 s is the resolution of either method
MISS_M = 25.0


def own_gap(trace, T, X, Y, car_xy, t):
    m = (T >= t) & (T <= t + 30.0)
    if not m.any():
        return np.nan, np.nan
    dd = np.hypot(X[m] - car_xy[0], Y[m] - car_xy[1])
    j = int(np.argmin(dd))
    return T[m][j] - t, dd[j] / 10.0


def car_at(tel_d, t):
    tj = tel_d['T'].values
    if len(tj) == 0 or t < tj[0] or t > tj[-1]:
        return None
    return np.interp(t, tj, tel_d.X.values), np.interp(t, tj, tel_d.Y.values)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('warehouse'); ap.add_argument('out')
    ap.add_argument('--races', default='2025_4,2025_5,2025_7,2025_10,2025_15')
    ap.add_argument('--per-race', type=int, default=12)
    a = ap.parse_args()
    w = duckdb.connect(a.warehouse, read_only=True)
    c = open_staging(4)
    rows = []
    for rid in a.races.split(','):
        d = w.sql(f"""SELECT p.lap_id, p.driver_id, p.lap_number, p.gap_ahead_phys_s pg, p.gap_ahead_phys_min_driver_id pcar,
                     x.gap_ahead_min_s xg, x.gap_ahead_min_driver_id xcar, x.gap_ahead_min_crossing_s xt
                     FROM int_lap_physical_ahead p JOIN int_lap_proximity x USING (lap_id)
                     WHERE p.race_id = '{rid}' AND p.validity_class = 'valid_same_lap' AND NOT p.is_neutralised_lap
                     AND p.gap_ahead_phys_s < 1 AND x.gap_ahead_min_s < 1
                     AND p.gap_ahead_phys_min_driver_id <> x.gap_ahead_min_driver_id""").df()
        d = d.sample(min(a.per_race, len(d)), random_state=1)
        tel, laps = core.read_race_inputs(c.sql('SELECT * FROM stg_physical_ahead_telemetry'),
                                          c.sql('SELECT * FROM stg_physical_ahead_laps'), rid)
        s = core.build_race_samples(tel, laps)
        by = {k: g.sort_values('T') for k, g in tel.groupby('drv')}
        for r in d.itertuples():
            fol = by[r.driver_id]
            T, X, Y = fol['T'].values, fol.X.values, fol.Y.values
            sl = s[(s.driver_id == r.driver_id) & (s.lap_number == r.lap_number) & (s.sample_class == 'same_lap')]
            if sl.empty:
                continue
            v = sl.sort_values('gap_s').iloc[0]
            out = dict(race_id=rid, lap_id=r.lap_id, phys_car=r.pcar, phys_gap_s=round(r.pg, 3), prox_car=r.xcar,
                       prox_gap_s=r.xg)
            for tag, car, g, t in (('phys', r.pcar, r.pg, v.session_time_s), ('prox', r.xcar, r.xg, r.xt)):
                xy = car_at(by[car], t)
                og, miss = own_gap(fol, T, X, Y, xy, t) if xy else (np.nan, np.nan)
                out[f'{tag}_own_gap_s'] = round(og, 2) if np.isfinite(og) else np.nan
                out[f'{tag}_miss_m'] = round(miss, 1) if np.isfinite(miss) else np.nan
                out[f'{tag}_supported'] = bool(np.isfinite(og) and miss <= MISS_M and abs(og - g) <= TOL)
                out[f'{tag}_car_ahead_at_all'] = bool(np.isfinite(og) and miss <= MISS_M and og > 0.05)
            rows.append(out)
    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)
    pd.set_option('display.width', 250)
    print(df.to_string(index=False))
    n = len(df)
    print(f'\nlaps audited {n}')
    for tag in ('phys', 'prox'):
        print(f'{tag}: claim supported by follower own trace (reached within {MISS_M:.0f} m and gap within {TOL} s): '
              f'{int(df[tag + "_supported"].sum())}/{n}; car actually ahead at all: {int(df[tag + "_car_ahead_at_all"].sum())}/{n}')


if __name__ == '__main__':
    main()
