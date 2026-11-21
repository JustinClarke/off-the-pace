"""Read-only check: moving the physical-ahead Python onto the staging views (stg_physical_ahead_laps /
stg_physical_ahead_telemetry) changed no existing output. Compares a BASELINE warehouse (built from the old code
that read bronze directly) with a NEW warehouse (built from the staging path), table by table, on every column
the baseline table has: rows sorted by the table key, strings / booleans / ints exactly equal, floats within 1e-9,
NULL positions equal. Columns only the new table has (the lapped tag) are listed, not compared.
Also asserts, in the NEW lap table, that the lapped columns are populated on validity_class = 'lapped' laps only.
Opens both files read-only; writes nothing. usage (from transform/):
    ../.venv/bin/python scripts/check_physical_ahead_staging_equivalence.py BASELINE.duckdb NEW.duckdb
"""
import sys

import duckdb
import numpy as np

KEYS = {
    'int_lap_physical_ahead': ['race_id', 'driver_id', 'lap_number'],
    'int_physical_ahead_pairs': ['race_id', 'follower_driver_id', 'leader_driver_id', 'lap_number'],
    'int_physical_ahead_pair_race': ['race_id', 'follower_driver_id', 'leader_driver_id'],
    'int_traffic_exposure_driver_race': ['race_id', 'driver_id'],
    'int_traffic_exposure_race': ['race_id'],
}
TOL = 1e-9


def main(a, b):
    ca = duckdb.connect(a, read_only=True)
    cb = duckdb.connect(b, read_only=True)
    ok_all = True
    for t, key in KEYS.items():
        da = ca.sql(f'SELECT * FROM {t}').df().sort_values(key, kind='stable').reset_index(drop=True)
        db = cb.sql(f'SELECT * FROM {t}').df().sort_values(key, kind='stable').reset_index(drop=True)
        bad, n_float = [], 0
        if len(da) != len(db):
            bad.append(f'row count {len(da)} vs {len(db)}')
        else:
            for c in da.columns:
                if c not in db.columns:
                    bad.append(f'{c}: missing in new')
                    continue
                x, y = da[c], db[c]
                if x.isna().tolist() != y.isna().tolist():
                    bad.append(f'{c}: NULL pattern differs ({int((x.isna() != y.isna()).sum())} rows)')
                    continue
                m = x.notna().values
                if x.dtype.kind == 'f' or y.dtype.kind == 'f':
                    n_float += 1
                    d = np.abs(x[m].astype(float).values - y[m].astype(float).values)
                    if d.size and d.max() > TOL:
                        bad.append(f'{c}: max abs diff {d.max():.3g}')
                elif not (x[m].astype(object).values == y[m].astype(object).values).all():
                    bad.append(f'{c}: values differ')
        new_only = [c for c in db.columns if c not in da.columns]
        print(f'{t}: rows {len(da)} vs {len(db)}, {len(da.columns)} baseline columns ({n_float} float) '
              f'-> {"IDENTICAL" if not bad else "DIFFERS"}; new-only columns: {new_only}')
        for m_ in bad:
            print('    ', m_)
        ok_all &= not bad
    lap = cb.sql('SELECT * FROM int_lap_physical_ahead').df()
    lp = lap[lap.validity_class == 'lapped']
    chk = {
        'is_lapped_lap == (validity_class = lapped)': bool((lap.is_lapped_lap == (lap.validity_class == 'lapped')).all()),
        'lapped columns NULL off lapped laps': bool(lap[~lap.is_lapped_lap][
            ['lapped_seconds_within_1s', 'lapped_time_measured_s', 'lapped_gap_phys_min_s']].isna().all().all()),
        'lapped_time_measured_s populated on lapped laps': bool(lp.lapped_time_measured_s.notna().mean() > 0.99),
        'lapped_seconds_within_1s <= lapped_time_measured_s': bool(
            (lp.lapped_seconds_within_1s <= lp.lapped_time_measured_s + 1e-9).all()),
        'headline gap columns still NULL on lapped laps': bool(lp[['gap_ahead_phys_s', 'time_within_1s_phys_s',
                                                                    'time_measured_s']].isna().all().all()),
    }
    print(f'lapped laps: {len(lp)} of {len(lap)}; with lapped_seconds_within_1s > 0: '
          f'{int((lp.lapped_seconds_within_1s > 0).sum())}; sum lapped_seconds_within_1s '
          f'{lp.lapped_seconds_within_1s.sum():.1f} s of {lp.lapped_time_measured_s.sum():.1f} s measured')
    for k, v in chk.items():
        print(f'  {"PASS" if v else "FAIL"}  {k}')
        ok_all &= v
    print('RESULT:', 'ALL EQUIVALENT' if ok_all else 'FAILED')
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
