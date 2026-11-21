"""Documented sensitivity check (not a dbt test, not a retune): how the traffic-exposure headline moves with
int_lap_physical_ahead's unknown_max_share (var physical_ahead_unknown_max_share, default 0.05).

Why: 0.05 was tuned on ONE race (Monza 2024: a 0.0 threshold made 286 of 1,008 laps unknown, 0.05 made 32).
This script re-runs the per-sample build once per race and re-reduces it to laps at each threshold, then
rolls up exactly as int_traffic_exposure_driver_race / int_traffic_exposure_race do (pooled over measured
laps: valid_same_lap and not neutralised). It reports, per threshold, the pooled headline
(share_time_close_behind, bunching_share), the measured-lap share, the unknown-lap share, and across races the
largest and the count of races whose headline moves by more than --tol versus the 0.05 baseline.
It changes nothing: the default stays 0.05.

Inputs: bronze parquet (as check_physical_ahead_agreement.py) and, for the neutralised-lap flag, the warehouse
table int_lap_physical_ahead (is_neutralised_lap, the spine). If the warehouse lacks that table, pass
--no-spine: no lap is treated as neutralised, the lap count is the laps with samples, and the output is marked
NO_SPINE. That mode is a smoke test, not a publishable number.

Read-only: opens the warehouse with read_only=True and bronze parquet; writes nothing but the optional --out
JSON. usage (from transform/):
    ../.venv/bin/python scripts/check_unknown_share_sensitivity.py [--races 2024_16,2019_15]
        [--thresholds 0.02,0.05,0.10] [--tol 0.005] [--no-spine] [--out f.json]
"""
import argparse
import importlib.util
import json
import os

import duckdb
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location(
    'int_lap_physical_ahead', os.path.join(ROOT, 'models', 'intermediate', 'int_lap_physical_ahead.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

BASE = 0.05   # the shipped default; deltas are measured against it


def rollup(lp, n_laps):
    """lp: reduce_to_laps frame with is_neutralised_lap. Returns the race-level headline at one threshold."""
    meas = lp[(lp.validity_class == 'valid_same_lap') & ~lp.is_neutralised_lap]
    tm = float(meas.time_measured_s.sum())
    return dict(
        n_laps=int(n_laps), n_measured=int(len(meas)),
        share_laps_measured=len(meas) / n_laps if n_laps else None,
        share_laps_unknown=float((lp.validity_class == 'unknown').sum()) / n_laps if n_laps else None,
        share_time_close_behind=float(meas.time_within_1s_phys_s.sum()) / tm if tm > 0 else None,
        bunching_share=float(meas.is_within_1s_of_car_ahead.astype(bool).sum()) / len(meas) if len(meas) else None,
        _close_s=float(meas.time_within_1s_phys_s.sum()), _meas_s=tm,
        _bunch=int(meas.is_within_1s_of_car_ahead.astype(bool).sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--warehouse', default=os.path.join(ROOT, '..', 'data', 'dev.duckdb'))
    ap.add_argument('--bronze', default=os.path.join(ROOT, '..', 'data', 'bronze'))
    ap.add_argument('--races', default='')
    ap.add_argument('--thresholds', default='0.02,0.05,0.10')
    ap.add_argument('--min-class-samples', type=int, default=4)
    ap.add_argument('--tol', type=float, default=0.005, help='abs change in a headline share counted as moving')
    ap.add_argument('--no-spine', action='store_true')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    ths = [float(x) for x in a.thresholds.split(',')]
    if BASE not in ths:
        ths = sorted(ths + [BASE])
    laps_glob = os.path.join(a.bronze, 'laps', '*', '*', '*.parquet')
    tel_glob = os.path.join(a.bronze, 'telemetry', '*', '*', '*.parquet')
    spine = None
    if not a.no_spine:
        wh = duckdb.connect(a.warehouse, read_only=True)
        spine = wh.sql('SELECT race_id, driver_id, lap_number, is_neutralised_lap FROM int_lap_physical_ahead').df()
    races = a.races.split(',') if a.races else (
        sorted(spine.race_id.unique()) if spine is not None else [])
    if not races:
        raise SystemExit('no races: pass --races or build int_lap_physical_ahead')
    per = {}
    for rid in races:
        tel = duckdb.sql(f"""SELECT SessionTime / 1e9 AS T, driver_id AS drv, CAST(lap_number AS INTEGER) AS lap,
                X, Y, "index" FROM '{tel_glob}' WHERE Source = 'pos' AND race_id = '{rid}'
            ORDER BY drv, T, "index" """).df()
        laps = duckdb.sql(f"SELECT * FROM '{laps_glob}' WHERE race_id = '{rid}'").df()
        smp = m.build_race_samples(tel, laps) if len(tel) and len(laps) else None
        if smp is None:
            per[rid] = None; print(rid, 'not_measurable', flush=True); continue
        sp = spine[spine.race_id == rid][['driver_id', 'lap_number', 'is_neutralised_lap']] if spine is not None else None
        per[rid] = {}
        for t in ths:
            lp = m.reduce_to_laps(smp, t, a.min_class_samples)
            if sp is not None:
                lp = lp.merge(sp, on=['driver_id', 'lap_number'], how='left')
                lp['is_neutralised_lap'] = lp.is_neutralised_lap.fillna(False).astype(bool)
                n = len(sp)   # spine laps without samples are 'unknown' in the model: they stay in the denominator
            else:
                lp['is_neutralised_lap'] = False
                n = len(lp)
            per[rid][t] = rollup(lp, n)
        print(rid, {t: round(v['share_time_close_behind'], 4) if v['share_time_close_behind'] is not None else None
                    for t, v in per[rid].items()}, flush=True)
    ok = {r: v for r, v in per.items() if v}
    summary = dict(spine='NO_SPINE (smoke test, not publishable)' if a.no_spine else 'int_lap_physical_ahead',
                   baseline=BASE, tol=a.tol, races_measured=len(ok), by_threshold={})
    for t in ths:
        tot = lambda k: sum(v[t][k] for v in ok.values())  # noqa: E731
        d_close, d_bunch, d_meas = [], [], []
        for r, v in ok.items():
            b, x = v[BASE], v[t]
            if b['share_time_close_behind'] is not None and x['share_time_close_behind'] is not None:
                d_close.append(x['share_time_close_behind'] - b['share_time_close_behind'])
            if b['bunching_share'] is not None and x['bunching_share'] is not None:
                d_bunch.append(x['bunching_share'] - b['bunching_share'])
            d_meas.append(x['share_laps_measured'] - b['share_laps_measured'])
        summary['by_threshold'][str(t)] = dict(
            pooled_share_time_close_behind=tot('_close_s') / tot('_meas_s') if tot('_meas_s') else None,
            pooled_bunching_share=tot('_bunch') / tot('n_measured') if tot('n_measured') else None,
            pooled_share_laps_measured=tot('n_measured') / tot('n_laps'),
            pooled_share_laps_unknown=sum(v[t]['share_laps_unknown'] * v[t]['n_laps'] for v in ok.values()) / tot('n_laps'),
            max_abs_delta_close=max((abs(x) for x in d_close), default=None),
            max_abs_delta_bunching=max((abs(x) for x in d_bunch), default=None),
            races_close_moved_gt_tol=sum(abs(x) > a.tol for x in d_close),
            races_bunching_moved_gt_tol=sum(abs(x) > a.tol for x in d_bunch),
            max_abs_delta_measured_share=max((abs(x) for x in d_meas), default=None))
    print(json.dumps(summary, indent=1))
    if a.out:
        clean = {r: ({str(t): {k: x for k, x in v.items() if not k.startswith('_')} for t, v in vs.items()} if vs else None)
                 for r, vs in per.items()}
        json.dump(dict(summary=summary, races=clean), open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
