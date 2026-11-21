"""int_physical_ahead_pairs.py · intermediate · grain: one row per (race_id, follower driver_id, leader driver_id,
lap_number) for which the follower spent at least one position sample under 1 s behind that leader.

MEASUREMENT ONLY. This model says how long one car was within 1 s behind a named other car. It does not say what
that cost, and nothing here may be read as a time loss, a dirty-air penalty or a cause of a slow lap. Not wired
to any page.

Same definitions as int_lap_physical_ahead (transform/python_lib/physical_ahead_core.py): a sample counts when
sample_class = 'same_lap' and gap_s < 1.0, and carries the sample's dt_s. Summed over leaders, seconds_within_1s
therefore equals int_lap_physical_ahead.time_within_1s_phys_s for the lap (that column is rounded to 4 dp and NULL
on non-valid laps; the pair rows are kept). The per-sample build is recomputed here (about 5 s per race) because
the lap model reduces away the leader identity; it uses the same drop_zero_xy setting, so the two models agree.

REQUIRED INVARIANT: drop_zero_xy, reference_method, reference_k and reference_rule (the physical_ahead_* vars,
mirrored in this model's config in _physical_ahead.yml) must be identical in int_lap_physical_ahead,
int_physical_ahead_pairs and int_physical_ahead_pairs_lapped, or the pair seconds stop summing to the lap
model's time_within_1s_phys_s. Enforced at run time for drop_zero_xy only (core.assert_lap_model_guard_matches
compares it with the lap table's zero_xy_guard_on and raises). The three reference_* settings are NOT recorded in
the lap table, so nothing enforces them beyond assert_physical_ahead_pairs_sum_matches_lap, which fails when
they drift enough to change the seconds. Always build the three models in one invocation with the same vars.

Rows on non-valid laps are KEPT and flagged: validity_class is copied from int_lap_physical_ahead for the lap.
Filter to validity_class = 'valid_same_lap' before using a pair figure; a lap that is not valid is never clear
air and never evidence of following. A pair-lap with no row had no sample under 1 s for that pair, which on a
valid lap is a measurement and on any other lap is not. The lap's validity comes from the lap model; a lap with
no row there (telemetry lap outside the spine) is labelled 'unknown'.

Known limits: the car-ahead agreement, identity-flip and unvalidated zero-XY-guard limits of
int_lap_physical_ahead apply unchanged and pair-wise. A flip between two close cars splits one stretch of
following across two pairs. The 1 s threshold is a measurement bucket, not a validated effect size.
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

OUT_COLS = ['race_id', 'season', 'follower_driver_id', 'leader_driver_id', 'lap_number', 'seconds_within_1s',
            'n_samples_within_1s', 'min_gap_s', 'median_gap_s', 'validity_class', 'zero_xy_guard_on']


def model(dbt, session):
    dbt.config(materialized='table')
    # dbt parses dbt.config.get() statically, so the key is read with a literal name
    v = dbt.config.get('drop_zero_xy')
    drop_zero_xy = core._as_bool(False if v is None or str(v).strip() in ('', 'None') else v)
    def cfg(v, default):
        return default if v is None or str(v).strip() in ('', 'None') else v
    reference_method = str(cfg(dbt.config.get('reference_method'), 'single'))   # must match int_lap_physical_ahead
    reference_k = int(float(cfg(dbt.config.get('reference_k'), core.REFERENCE_K)))
    reference_rule = str(cfg(dbt.config.get('reference_rule'), 'legacy'))

    laps = dbt.ref('int_lap_physical_ahead').project(
        'race_id, season, driver_id, lap_number, validity_class, zero_xy_guard_on').df()
    core.assert_lap_model_guard_matches(laps.zero_xy_guard_on, drop_zero_xy, 'int_physical_ahead_pairs')
    laps = laps.drop(columns='zero_xy_guard_on')
    tel_rel = dbt.ref('stg_physical_ahead_telemetry')
    laps_rel = dbt.ref('stg_physical_ahead_laps')
    parts = []
    for rid in sorted(laps.race_id.unique()):
        tel, bronze_laps = core.read_race_inputs(tel_rel, laps_rel, rid)
        if tel.empty or bronze_laps.empty:
            continue
        smp = core.build_race_samples(tel, bronze_laps, drop_zero_xy=drop_zero_xy, reference_method=reference_method,
                                      reference_k=reference_k, reference_rule=reference_rule)
        if smp is None:
            continue
        pr = core.pairs_from_samples(smp)
        pr.insert(0, 'race_id', rid)
        parts.append(pr)
    if not parts:
        out = pd.DataFrame({c: pd.Series(dtype='object') for c in OUT_COLS})
    else:
        out = pd.concat(parts, ignore_index=True)
        lap_flag = laps.rename(columns={'driver_id': 'follower_driver_id'})
        out = out.merge(lap_flag.drop(columns='season'), on=['race_id', 'follower_driver_id', 'lap_number'],
                        how='left')
        out['season'] = out.race_id.map(laps.groupby('race_id').season.first())
        # a pair-lap the lap model has no row for is never treated as valid
        out['validity_class'] = out.validity_class.fillna('unknown')
        out['zero_xy_guard_on'] = drop_zero_xy
    out['n_samples_within_1s'] = out.n_samples_within_1s.astype('int64')
    return out[OUT_COLS].sort_values(
        ['race_id', 'follower_driver_id', 'leader_driver_id', 'lap_number'], kind='stable').reset_index(drop=True)
