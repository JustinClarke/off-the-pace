"""int_lap_physical_ahead.py · intermediate · grain: one row per race lap (lap_id), on the int_stint_geometry spine.

MEASUREMENT ONLY. This model says how close each car was to the physical car ahead on track. It does not say
what that cost, and nothing here may be read as a time loss, a dirty-air penalty or a cause of a slow lap.

The definitions (car-ahead build, sample classes, validity_class precedence, known limits, the unvalidated
X = Y = 0 guard) and all of the computation live in transform/python_lib/physical_ahead_core.py, shared with
int_physical_ahead_pairs. This file is only the dbt wiring: config, the int_stint_geometry spine, the race loop
and the join. Read the core module's docstring for what any column means.

Import path: dbt-duckdb appends the profile's module_paths (profiles.yml, 'python_lib') to sys.path, so the
plain import below works under dbt. The fallback loads the file by path for scripts that load this model by
file path (check_physical_ahead_agreement.py, check_unknown_share_sensitivity.py).
"""
import importlib.util
import os
import sys

import numpy as np
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

# Re-exported so existing scripts that load this file by path keep working unchanged.
W_M, GAPMAX_S, OPEN_S, OFFLINE_U, STEP_U = core.W_M, core.GAPMAX_S, core.OPEN_S, core.OFFLINE_U, core.STEP_U
SIDE_BY_SIDE_M, OVERLAP_M, MAX_GAP_S, CLOSE_S = core.SIDE_BY_SIDE_M, core.OVERLAP_M, core.MAX_GAP_S, core.CLOSE_S
SAMPLE_CLASSES, LAP_CLASSES = core.SAMPLE_CLASSES, core.LAP_CLASSES
_pit_windows, _inwin, _follower_time_gap = core._pit_windows, core._inwin, core._follower_time_gap
build_race_samples, reduce_to_laps, _as_bool = core.build_race_samples, core.reduce_to_laps, core._as_bool
read_race_inputs = core.read_race_inputs


def model(dbt, session):
    dbt.config(materialized='table')
    # dbt parses dbt.config.get() statically, so each key is read with a literal name
    def cfg(v, default):
        return default if v is None or str(v).strip() in ('', 'None') else v
    drop_zero_xy = _as_bool(cfg(dbt.config.get('drop_zero_xy'), False))   # NOT validated; default off (core header)
    unknown_max_share = float(cfg(dbt.config.get('unknown_max_share'), 0.05))
    min_class_samples = int(float(cfg(dbt.config.get('min_class_samples'), 4)))
    # reference line: 'single' (default, validated) or 'consensus' (median of reference_k laps, see the core)
    reference_method = str(cfg(dbt.config.get('reference_method'), 'single'))
    reference_k = int(float(cfg(dbt.config.get('reference_k'), core.REFERENCE_K)))
    reference_rule = str(cfg(dbt.config.get('reference_rule'), 'legacy'))

    spine = dbt.ref('int_stint_geometry').project(
        'lap_id, race_year, race_id, driver_id, lap_number, '
        '(is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap) AS is_neutralised_lap').df()
    tel_rel = dbt.ref('stg_physical_ahead_telemetry')   # cleaning rules live in staging, not in this file
    laps_rel = dbt.ref('stg_physical_ahead_laps')
    parts, no_ref = [], []
    for rid in sorted(spine.race_id.unique()):
        tel, laps = read_race_inputs(tel_rel, laps_rel, rid)
        if tel.empty or laps.empty:
            continue   # no telemetry: every spine lap of the race comes out 'unknown' below
        smp = build_race_samples(tel, laps, drop_zero_xy=drop_zero_xy, reference_method=reference_method,
                                 reference_k=reference_k, reference_rule=reference_rule)
        if smp is None:
            no_ref.append(rid)
            continue   # every spine lap of the race comes out 'unknown' (reason no_reference_lap)
        lp = reduce_to_laps(smp, unknown_max_share, min_class_samples)
        lp.insert(0, 'race_id', rid)
        lp['track_length_m'] = smp.attrs['track_length_m']
        lp['n_zero_xy_samples_race'] = smp.attrs['n_zero_xy_samples']
        parts.append(lp)
    laps_out = pd.concat(parts, ignore_index=True)
    out = spine.merge(laps_out, on=['race_id', 'driver_id', 'lap_number'], how='left')
    # spine laps with no position samples at all: unknown, never clear air
    no_data = out.n_samples.isna()
    out.loc[no_data, 'validity_class'] = 'unknown'
    out.loc[no_data, 'unknown_reason_mode'] = np.where(
        out.loc[no_data, 'race_id'].isin(no_ref), 'no_reference_lap', 'no_position_samples')
    out.loc[no_data, 'n_samples'] = 0
    out['zero_xy_guard_on'] = drop_zero_xy
    out['is_lapped_lap'] = (out.validity_class == 'lapped')
    out = out.rename(columns={'race_year': 'season'})
    count_cols = ['n_samples'] + [f'n_{c}_samples' for c in SAMPLE_CLASSES] + ['n_ahead_pairs', 'n_ahead_flips']
    for c in count_cols:
        out[c] = out[c].fillna(0).astype('int64')
    cols = ['lap_id', 'race_id', 'season', 'driver_id', 'lap_number', 'validity_class', 'is_within_1s_of_car_ahead',
            'gap_ahead_phys_s', 'gap_ahead_phys_median_s', 'gap_ahead_phys_min_m', 'gap_ahead_phys_min_driver_id',
            'time_within_1s_phys_s',
            'time_measured_s', 'is_neutralised_lap'] + count_cols + [
            'unknown_reason_mode', 'track_length_m', 'n_zero_xy_samples_race', 'zero_xy_guard_on',
            'is_lapped_lap', 'lapped_seconds_within_1s', 'lapped_time_measured_s', 'lapped_gap_phys_min_s']
    return out[cols].sort_values(['race_id', 'driver_id', 'lap_number'], kind='stable').reset_index(drop=True)
