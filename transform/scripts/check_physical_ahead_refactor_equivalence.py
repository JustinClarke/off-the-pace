"""Read-only check: the physical-ahead refactor (core moved to python_lib/physical_ahead_core.py) changed no
behaviour. Builds a small synthetic race (5 cars on a circle, one pit stop, one lapped car, two cars running
~0.5 s apart), runs the OLD code (int_lap_physical_ahead.py as committed at --old-ref, default HEAD) and the NEW
code (the working-tree model file, which imports the shared core), and asserts the per-sample frame, the per-lap
frame and the frame attrs are identical. It also checks the new pair table is consistent with the lap frame
(summed per follower-lap it equals time_within_1s_phys_s within the lap model's 4 dp rounding).

Writes nothing. Uses `git show <ref>:<path>` (read-only). If the ref already holds the refactored file, pass
--old-file with a copy of the pre-refactor model. usage (from transform/):
    ../.venv/bin/python scripts/check_physical_ahead_refactor_equivalence.py [--old-ref HEAD | --old-file f.py]
"""
import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL_REL = 'transform/models/intermediate/int_lap_physical_ahead.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def synthetic_race():
    """Circle of 5000 m (coordinates in 1/10 m). Each car: (speed m/s, start offset m behind the grid line)."""
    circ_u = 50000.0
    r = circ_u / (2 * np.pi)
    cars = {'AAA': (80.0, 0.0), 'BBB': (80.0, -40.0),    # BBB runs 40 m = 0.5 s behind AAA
            'CCC': (78.0, -900.0), 'DDD': (76.0, -1800.0), 'EEE': (60.0, -2500.0)}   # EEE is lapped
    rng = np.random.default_rng(7)
    rows, laps = [], []
    t_end = 330.0
    for d, (v, off) in cars.items():
        t = np.arange(0.0, t_end, 0.25) + rng.uniform(0, 0.05, int(np.ceil(t_end / 0.25)))
        dist = v * t + off
        lap = np.floor(dist / 5000.0).astype(int) + 1
        lap = np.clip(lap, 1, None)
        th = 2 * np.pi * (dist % 5000.0) / 5000.0
        tel = pd.DataFrame(dict(T=t, drv=d, lap=lap, X=r * np.cos(th), Y=r * np.sin(th)))
        tel['index'] = np.arange(len(tel))
        rows.append(tel)
        for ln in sorted(tel.lap.unique()):
            sub = tel[tel.lap == ln]
            lt = (sub['T'].max() - sub['T'].min()) * 1e9
            laps.append(dict(Driver=d, LapNumber=ln, LapTime=lt, Deleted=False, Compound='MEDIUM',
                             PitInTime=np.nan, PitOutTime=np.nan))
    laps = pd.DataFrame(laps)
    # one pit stop: DDD in on lap 2, out on lap 3
    di = laps.index[(laps.Driver == 'DDD') & (laps.LapNumber == 2)][0]
    laps.loc[di, 'PitInTime'] = 150.0e9
    do = laps.index[(laps.Driver == 'DDD') & (laps.LapNumber == 3)][0]
    laps.loc[do, 'PitOutTime'] = 175.0e9
    return pd.concat(rows, ignore_index=True).sort_values(['drv', 'T', 'index']).reset_index(drop=True), laps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old-ref', default='HEAD')
    ap.add_argument('--old-file', default='')
    a = ap.parse_args()
    if a.old_file:
        old_path = a.old_file
    else:
        src = subprocess.run(['git', 'show', f'{a.old_ref}:{MODEL_REL}'], capture_output=True, text=True,
                             check=True, cwd=ROOT).stdout
        if 'physical_ahead_core' in src:
            sys.exit('old-ref already holds the refactored model; pass --old-file with the pre-refactor copy')
        old_path = os.path.join(tempfile.mkdtemp(), 'old_int_lap_physical_ahead.py')
        with open(old_path, 'w') as f:
            f.write(src)
    old = load(old_path, 'old_lap_physical_ahead')
    new = load(os.path.join(ROOT, 'models', 'intermediate', 'int_lap_physical_ahead.py'), 'new_lap_physical_ahead')
    assert hasattr(new, 'core'), 'new model should import the shared core'

    tel, laps = synthetic_race()
    for guard in (False, True):
        so = old.build_race_samples(tel.copy(), laps.copy(), drop_zero_xy=guard)
        sn = new.build_race_samples(tel.copy(), laps.copy(), drop_zero_xy=guard)
        assert so is not None and sn is not None
        pd.testing.assert_frame_equal(so, sn, check_exact=True)
        assert so.attrs == sn.attrs, (so.attrs, sn.attrs)
        for kw in ({}, dict(unknown_max_share=0.0, min_class_samples=1)):
            lo = old.reduce_to_laps(so, **kw)
            ln_ = new.reduce_to_laps(sn, **kw)
            pd.testing.assert_frame_equal(lo, ln_, check_exact=True)
    cls = so.sample_class.value_counts().to_dict()
    n_close = int(((so.sample_class == 'same_lap') & (so.gap_s < 1.0)).sum())
    print('sample classes:', cls, '| close samples:', n_close)
    assert cls.get('same_lap', 0) > 0 and n_close > 0, 'synthetic input must exercise the close-follow path'
    assert (old.W_M, old.GAPMAX_S, old.CLOSE_S, old.OPEN_S) == (new.W_M, new.GAPMAX_S, new.CLOSE_S, new.OPEN_S)
    for name in ('SAMPLE_CLASSES', 'LAP_CLASSES'):
        assert getattr(old, name) == getattr(new, name)
    print('OK sample frame, lap frame and constants identical (guard off and on; default and strict thresholds)')

    # pair table consistency with the lap frame (guard off, defaults)
    s = new.build_race_samples(tel.copy(), laps.copy())
    lap = new.reduce_to_laps(s)
    pr = new.core.pairs_from_samples(s)
    per = pr.groupby(['follower_driver_id', 'lap_number']).seconds_within_1s.sum().rename('pair_s').reset_index()
    j = lap.merge(per, left_on=['driver_id', 'lap_number'], right_on=['follower_driver_id', 'lap_number'], how='left')
    raw = s.assign(c=np.where((s.sample_class == 'same_lap') & (s.gap_s < 1.0), s.dt_s, 0.0)) \
        .groupby(['driver_id', 'lap_number']).c.sum().rename('raw_close_s').reset_index()
    j = j.merge(raw, on=['driver_id', 'lap_number'])
    assert (j.pair_s.fillna(0) - j.raw_close_s).abs().max() < 1e-3, 'pairs do not sum to the lap close time'
    v = j[j.validity_class == 'valid_same_lap']
    assert ((v.pair_s.fillna(0) - v.time_within_1s_phys_s).abs() < 1e-3).all()
    assert (pr.seconds_within_1s >= 0).all() and (pr.min_gap_s < 1.0).all()
    print(f'OK pair table: {len(pr)} pair-lap rows, sums match lap close time to < 1e-3 s; '
          f'pairs: {sorted(set(zip(pr.follower_driver_id, pr.leader_driver_id)))}')


if __name__ == '__main__':
    main()
