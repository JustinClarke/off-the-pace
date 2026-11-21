"""Read-only comparison: single fastest-lap reference vs consensus reference (median of k laps) for the
physical-ahead measurement. For each race it builds the per-sample frame both ways from the staging contract
(bronze parquet, no warehouse writes), reduces to laps, and computes the headline the exposure model reports:
share_time_close_behind = sum(time_within_1s_phys_s) / sum(time_measured_s) over valid_same_lap, non-neutralised
laps (neutralised flag from int_stint_geometry of a read-only warehouse). Also reports, per race, whether the
reference lap changes under rule 'stg_valid', the track length under each method, and the 'single' result vs
the warehouse's int_traffic_exposure_race (a cross-check that this script reproduces the model).
usage (from transform/):
    ../.venv/bin/python scripts/check_physical_ahead_reference_consensus.py WAREHOUSE.duckdb OUT.csv [--k 5] [--seasons 2018-2025] [--procs 6]
"""
import argparse
import os
import sys
from multiprocessing import Pool

import duckdb
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'python_lib'))
import physical_ahead_core as core  # noqa: E402
from physical_ahead_stage_inmem import open_staging  # noqa: E402

_ctx = {}


def headline(lp, neut):
    d = lp.merge(neut, on=['driver_id', 'lap_number'], how='inner')
    m = d[(d.validity_class == 'valid_same_lap') & ~d.is_neutralised_lap]
    num, den = m.time_within_1s_phys_s.sum(), m.time_measured_s.sum()
    return dict(n_measured=len(m), share=(num / den if den else np.nan),
                bunching=(m.is_within_1s_of_car_ahead.astype(float).sum() / len(m) if len(m) else np.nan))


def one(args):
    rid, k, neut = args
    if 'c' not in _ctx:
        _ctx['c'] = open_staging(2)
    c = _ctx['c']
    tel, laps = core.read_race_inputs(c.sql('SELECT * FROM stg_physical_ahead_telemetry'),
                                      c.sql('SELECT * FROM stg_physical_ahead_laps'), rid)
    out = dict(race_id=rid)
    if tel.empty or laps.empty:
        return out
    cand_s = core.reference_candidates(laps, 'legacy')
    cand_v = core.reference_candidates(laps, 'stg_valid')
    out['ref_legacy'] = f'{cand_s.iloc[0].Driver}:{int(cand_s.iloc[0].LapNumber)}' if len(cand_s) else None
    out['ref_stg_valid'] = f'{cand_v.iloc[0].Driver}:{int(cand_v.iloc[0].LapNumber)}' if len(cand_v) else None
    for name, kw in (('single', dict()), ('consensus', dict(reference_method='consensus', reference_k=k))):
        s = core.build_race_samples(tel.copy(), laps.copy(), **kw)
        if s is None:
            out[f'{name}_share'] = np.nan
            continue
        lp = core.reduce_to_laps(s)
        h = headline(lp, neut)
        out.update({f'{name}_{a}': b for a, b in h.items()})
        out[f'{name}_L'] = s.attrs['track_length_m']
        out[f'{name}_lapped_laps'] = int((lp.validity_class == 'lapped').sum())
        out[f'{name}_unknown_laps'] = int((lp.validity_class == 'unknown').sum())
        out[f'{name}_valid_laps'] = int((lp.validity_class == 'valid_same_lap').sum())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('warehouse'); ap.add_argument('out')
    ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--seasons', default='2018-2025')
    ap.add_argument('--procs', type=int, default=6)
    ap.add_argument('--races', default='')
    a = ap.parse_args()
    y0, y1 = (int(x) for x in a.seasons.split('-'))
    w = duckdb.connect(a.warehouse, read_only=True)
    sp = w.sql(f"""SELECT race_id, race_year, driver_id, lap_number,
                  (is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap) AS is_neutralised_lap
                  FROM int_stint_geometry WHERE race_year BETWEEN {y0} AND {y1}""").df()
    ref = w.sql('SELECT race_id, share_time_close_behind AS model_share FROM int_traffic_exposure_race').df()
    races = sorted(sp.race_id.unique())
    if a.races:
        races = [r for r in races if r in a.races.split(',')]
    jobs = [(r, a.k, sp[sp.race_id == r][['driver_id', 'lap_number', 'is_neutralised_lap']]) for r in races]
    with Pool(a.procs) as p:
        rows = []
        for i, r in enumerate(p.imap_unordered(one, jobs)):
            rows.append(r)
            if i % 10 == 0:
                print(f'{i + 1}/{len(jobs)} done', flush=True)
    df = pd.DataFrame(rows).merge(ref, on='race_id', how='left').sort_values('race_id')
    df['d_share'] = df.consensus_share - df.single_share
    df.to_csv(a.out, index=False)
    print('wrote', a.out, len(df))


if __name__ == '__main__':
    main()
