"""int_physical_ahead_pairs_lapped.py · intermediate · grain: one row per (race_id, follower driver_id, leader
driver_id, lap_number) for which the follower spent at least one position sample under 1 s behind a car on a
DIFFERENT lap (sample_class = 'lapped'), on laps the lap model classes as 'lapped' (is_lapped_lap).

MEASUREMENT ONLY. Separate from int_physical_ahead_pairs, which holds same_lap pairs and is not changed by this
model. This table is lapped traffic only: pair_class = 'lapped_traffic' on every row. Seconds here are never added
to int_physical_ahead_pairs or to time_within_1s_phys_s. Not wired to any page.

Same per-sample build and pair helper as int_physical_ahead_pairs (physical_ahead_core.pairs_from_samples, with
sample_class='lapped'), same reference config. Summed over leaders, seconds_within_1s equals
int_lap_physical_ahead.lapped_seconds_within_1s for the lap (both rounded to 4 dp). Only laps with
is_lapped_lap = TRUE in int_lap_physical_ahead are kept; non-lapped laps are not in this table.
"""
import importlib.util
import os
import sys

import pandas as pd

try:
    import physical_ahead_core as core
except ImportError:
    _here = os.path.dirname(os.path.abspath(globals().get('__file__', os.path.join(os.getcwd(), 'x'))))
    for _p in (os.path.join(_here, '..', '..', 'python_lib'), os.path.join(os.getcwd(), 'python_lib'),
               os.path.join(os.getcwd(), 'transform', 'python_lib')):
        _f = os.path.join(_p, 'physical_ahead_core.py')
        if os.path.exists(_f):
            _spec = importlib.util.spec_from_file_location('physical_ahead_core', _f)
            core = importlib.util.module_from_spec(_spec)
            sys.modules['physical_ahead_core'] = core
            _spec.loader.exec_module(core)
            break
    else:
        raise

OUT_COLS = ['race_id', 'season', 'follower_driver_id', 'leader_driver_id', 'lap_number', 'pair_class',
            'seconds_within_1s', 'n_samples_within_1s', 'min_gap_s', 'median_gap_s', 'validity_class',
            'zero_xy_guard_on']


def model(dbt, session):
    dbt.config(materialized='table')
    v = dbt.config.get('drop_zero_xy')
    drop_zero_xy = core._as_bool(False if v is None or str(v).strip() in ('', 'None') else v)
    def cfg(v, default):
        return default if v is None or str(v).strip() in ('', 'None') else v
    reference_method = str(cfg(dbt.config.get('reference_method'), 'single'))   # must match int_lap_physical_ahead
    reference_k = int(float(cfg(dbt.config.get('reference_k'), core.REFERENCE_K)))
    reference_rule = str(cfg(dbt.config.get('reference_rule'), 'legacy'))

    laps = dbt.ref('int_lap_physical_ahead').project(
        'race_id, season, driver_id, lap_number, validity_class, is_lapped_lap, zero_xy_guard_on').df()
    core.assert_lap_model_guard_matches(laps.zero_xy_guard_on, drop_zero_xy, 'int_physical_ahead_pairs_lapped')
    laps = laps.drop(columns='zero_xy_guard_on')
    lapped_laps = laps[laps.is_lapped_lap.astype(bool)]
    tel_rel = dbt.ref('stg_physical_ahead_telemetry')
    laps_rel = dbt.ref('stg_physical_ahead_laps')
    parts = []
    for rid in sorted(lapped_laps.race_id.unique()):
        tel, bronze_laps = core.read_race_inputs(tel_rel, laps_rel, rid)
        if tel.empty or bronze_laps.empty:
            continue
        smp = core.build_race_samples(tel, bronze_laps, drop_zero_xy=drop_zero_xy, reference_method=reference_method,
                                      reference_k=reference_k, reference_rule=reference_rule)
        if smp is None:
            continue
        pr = core.pairs_from_samples(smp, sample_class='lapped')
        pr.insert(0, 'race_id', rid)
        parts.append(pr)
    if not parts:
        out = pd.DataFrame({c: pd.Series(dtype='object') for c in OUT_COLS})
    else:
        out = pd.concat(parts, ignore_index=True)
        lap_flag = lapped_laps.rename(columns={'driver_id': 'follower_driver_id'})
        # inner join = the lapped filter, applied at the end
        out = out.merge(lap_flag.drop(columns=['season', 'is_lapped_lap']),
                        on=['race_id', 'follower_driver_id', 'lap_number'], how='inner')
        out['season'] = out.race_id.map(laps.groupby('race_id').season.first())
        out['pair_class'] = 'lapped_traffic'
        out['zero_xy_guard_on'] = drop_zero_xy
    out['n_samples_within_1s'] = out.n_samples_within_1s.astype('int64')
    return out[OUT_COLS].sort_values(
        ['race_id', 'follower_driver_id', 'leader_driver_id', 'lap_number'], kind='stable').reset_index(drop=True)
