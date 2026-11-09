"""int_lap_physical_ahead.py · intermediate · grain: one row per race lap (lap_id), on the int_stint_geometry spine.

MEASUREMENT ONLY. This model says how close each car was to the physical car ahead on track. It does not say
what that cost, and nothing here may be read as a time loss, a dirty-air penalty or a cause of a slow lap.
It does not read FastF1 DriverAhead or DistanceToDriverAhead (decision D2, experiment 13): the car ahead is
derived from X/Y positions only.

WHERE THE DEFINITION COMES FROM
  Experiment 18 (Study D) car-ahead builder, ported in experiment 26 (proposed_model/int_lap_physical_ahead.py)
  and checked on fresh races in experiments 27 and 28. The per-sample build below is that port with three
  changes, each listed here so the diff against the validated code is explicit:
    1. The X = Y = 0 placeholder guard is OFF by default (var physical_ahead_drop_zero_xy, default false).
       It is NOT validated: experiment 26 measured it exploratorily on Singapore 2019 only, and experiment 28
       (Abu Dhabi 2019) was inconclusive because that race did not show the defect. Turn it on only for a
       measured comparison, never silently. The value used is recorded per row in zero_xy_guard_on.
    2. The validated 'side_by_side' flag (nearest car < 10 m OR second-nearest within 15 m of it) is split
       in two: side_by_side = nearest car < 10 m (physically alongside); overlapping = second-nearest car
       within 15 m of the nearest (two cars ahead too close to order). Same rule, two labels.
    3. Per-sample time gap gap_s (seconds), described below, and the reduction to one row per lap.

PER SAMPLE (the follower's own 'pos' samples)
  Every other car's X/Y is linearly interpolated to the instant (bracket <= 1.0 s, no extrapolation) and
  projected onto the race's fastest clean lap polyline. The car ahead is the nearest car with forward arc
  distance in (0, 300 m], excluding cars in their pit window and cars parked on lap >= 2.
  Sample class, precedence top to bottom:
    unknown        follower in its pit window, parked, > 15 m off the polyline, or another car expected on
                   track has no position bracket within 1 s. Car ahead and gap are NULL. NEVER clear air.
    lap1           follower lap_number = 1 (Study D: 53-63% agreement; order not resolvable at the start).
    side_by_side   car ahead < 10 m.
    overlapping    second-nearest car within 15 m of the nearest.
    lapped         car ahead is on a different lap by unwrapped progress (lap offset != 0), either way.
    same_lap       a car ahead within 300 m on the same lap.
    clear          no car within 300 m ahead AND every expected car was located (a measured "nobody close").
  gap_s: the time the FOLLOWER took to reach the point where the car ahead was at that instant, read off the
  follower's own unwrapped progress vs session clock. This is the crossing-time gap of int_lap_proximity
  evaluated at the car ahead's position, so it needs no assumption about the car ahead's speed. Units:
  seconds. NULL if the follower never reaches that point (end of race, retirement) or takes > 30 s.

PER LAP (this model's rows), validity_class, precedence top to bottom:
    unknown          no position samples for the lap, or more than physical_ahead_unknown_max_share
                     (default 0.05) of its samples unknown. Pit in/out laps land here. Measured on Monza
                     2024: a 0.0 threshold made 286 of 1,008 laps unknown from one-sample 'car_missing'
                     gaps; at 0.05, 32. On a valid lap the gap/time columns cover its known samples only,
                     so time_within_1s_phys_s can undercount by at most that share.
    lap1             lap_number = 1.
    lapped           >= physical_ahead_min_class_samples (default 4, ~1 s) samples classed lapped.
    overlapping      >= that many samples classed overlapping.
    side_by_side     >= that many samples classed side_by_side.
    valid_same_lap   everything else: every sample known, and the car ahead (when one was within 300 m)
                     was on the same lap and orderable. Includes measured clear-air laps.
  Only valid_same_lap carries is_within_1s_of_car_ahead and the gap columns. Every other class has them NULL
  and must not be COALESCEd to "clear air" or to "following". The flag is FALSE only for a valid_same_lap
  lap whose minimum measured gap was >= 1 s (or that had no car within 300 m).

KNOWN LIMITS (not bugs to hide; see traffic_exposure_copy.md)
  * Agreement with int_lap_proximity's crossing-time car ahead is 96-99% on same-lap, non-lap-1,
    non-side-by-side samples (experiments 26, 27), not 100%.
  * Identity flips between consecutive samples are 0.18-0.42% of pairs in seven 2025 races and 0.64% in
    Canada 2025 (experiment 27), 0.66-0.83% in 2019 races (experiment 26). Canada's excess sits mostly in
    lapped and overlapping pairs (experiment 28). Carried per lap as n_ahead_flips / n_ahead_pairs.
  * Singapore 2019 has X = Y = 0 placeholder samples that shift progress by a lap; with the guard off its
    lapped share is ~35% (experiment 26). Those laps fall into 'lapped', which is excluded from every
    exposure figure, so the defect makes laps unusable rather than wrong. assert_physical_ahead_lapped_share
    warns on it.

Python because the build is a per-instant 20 x 20 interpolation and a nearest-neighbour projection, which has
no clean SQL form. One race at a time, ~5 s per race single-core (experiment 26).
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

W_M = 300.0             # car-ahead search window, metres of track
GAPMAX_S = 1.0          # max bracket for interpolating another car's position, s
OPEN_S = 120.0          # = var proximity_pit_window_open_s
OFFLINE_U = 150.0       # 15 m off the reference polyline, units of 1/10 m
STEP_U = 5.0            # polyline resampling step (0.5 m)
SIDE_BY_SIDE_M = 10.0
OVERLAP_M = 15.0
MAX_GAP_S = 30.0        # a follower taking longer than this to reach the car ahead's point is not "close"
CLOSE_S = 1.0
SAMPLE_CLASSES = ('unknown', 'lap1', 'side_by_side', 'overlapping', 'lapped', 'same_lap', 'clear')
LAP_CLASSES = ('valid_same_lap', 'lap1', 'side_by_side', 'lapped', 'overlapping', 'unknown')


def _pit_windows(laps):
    """Study D pit windows: stop windows plus pit-lane-start windows."""
    win = {}
    for d, g in laps.sort_values('LapNumber').groupby('Driver'):
        g = g.reset_index(drop=True)
        for _, r in g.iterrows():
            if pd.notna(r.PitInTime):
                nxt = g[g.LapNumber > r.LapNumber]
                nxt = nxt.iloc[0] if len(nxt) else None
                out = (nxt.PitOutTime / 1e9 if (nxt is not None and pd.notna(nxt.PitOutTime))
                       else r.PitInTime / 1e9 + OPEN_S)
                win.setdefault(d, []).append((r.PitInTime / 1e9, out))
            elif pd.notna(r.PitOutTime) and r.LapNumber == 1:
                win.setdefault(d, []).append((0.0, r.PitOutTime / 1e9))
    return win


def _inwin(drv, tt, win):
    m = np.zeros(len(tt), bool)
    for a, b in win.get(drv, []):
        m |= (tt >= a) & (tt <= b)
    return m


def _follower_time_gap(T, P, target):
    """Seconds until the follower's unwrapped progress P (vs clock T) first reaches `target`. NaN if never."""
    Pm = np.maximum.accumulate(P)
    k = np.searchsorted(Pm, target, side='left')
    ok = np.isfinite(target) & (k > 0) & (k < len(Pm))
    k1 = np.clip(k, 1, len(Pm) - 1); k0 = k1 - 1
    dp = Pm[k1] - Pm[k0]
    w = np.where(dp > 0, (target - Pm[k0]) / np.where(dp > 0, dp, 1), 0.0)
    t_reach = T[k0] + w * (T[k1] - T[k0])
    return np.where(ok, t_reach, np.nan)


def build_race_samples(tel, laps, drop_zero_xy=False):
    """tel: 'pos' rows of one race (T s, drv, lap, X, Y) ordered by drv, T. laps: bronze laps of the race.
    Returns one row per follower sample with sample_class, ahead identity, gap_m, gap_s, dt_s, or None when the
    race has no clean reference lap to project onto (then every lap of the race is 'unknown')."""
    t = tel.reset_index(drop=True).copy()
    zero = ((t.X.values == 0) & (t.Y.values == 0)) if drop_zero_xy else np.zeros(len(t), bool)
    n_zero = int(((t.X.values == 0) & (t.Y.values == 0)).sum())
    drivers = sorted(t.drv.unique()); di = {d: i for i, d in enumerate(drivers)}; ND = len(drivers)
    t['di'] = t.drv.map(di)
    win = _pit_windows(laps)
    t['pit'] = False
    for d, g in t.groupby('drv'):
        t.loc[g.index, 'pit'] = _inwin(d, g['T'].values, win)

    ok = laps[laps.LapTime.notna() & (laps.Deleted != True) & laps.PitInTime.isna() & laps.PitOutTime.isna()  # noqa: E712
              & (laps.LapNumber >= 2) & laps.Compound.notna()]
    if ok.empty:
        return None   # no clean reference lap (e.g. 2021 Belgium, run behind the SC): race not measurable
    best = ok.sort_values('LapTime').iloc[0]
    ref = t[(t.drv == best.Driver) & (t.lap == best.LapNumber) & ~zero].sort_values('T')
    if len(ref) < 50:
        return None   # reference lap has no usable position trace
    xy = ref[['X', 'Y']].values; xy = np.vstack([xy, xy[0]])
    cs = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]; L = cs[-1]
    g = np.arange(0, L, STEP_U); gx = np.interp(g, cs, xy[:, 0]); gy = np.interp(g, cs, xy[:, 1])
    tree = cKDTree(np.c_[gx, gy])

    def proj(x, y):
        d, ix = tree.query(np.c_[x, y]); return g[ix], d

    full = t
    t = t[~zero].reset_index(drop=True)   # guard on: placeholder samples removed from every car's track
    t['s'], t['off'] = proj(t.X.values, t.Y.values)
    P = np.zeros(len(t))
    for _, gi in t.groupby('di').indices.items():
        s = t.s.values[gi]; s0 = s[0] - (L if s[0] > L / 2 else 0)
        dd = np.diff(s); dd = np.where(dd < -L / 2, dd + L, np.where(dd > L / 2, dd - L, dd))
        P[gi] = s0 + np.r_[0, np.cumsum(dd)]
    t['P'] = P
    parked = np.zeros(len(t), bool)
    for _, gi in t.groupby('di').indices.items():
        T_ = t['T'].values[gi]; X_ = t.X.values[gi]; Y_ = t.Y.values[gi]
        lo = np.searchsorted(T_, T_ - 5.0); hi = np.searchsorted(T_, T_ + 5.0, 'right') - 1
        parked[gi] = (np.hypot(X_[hi] - X_[lo], Y_[hi] - Y_[lo]) < 50) & (t.lap.values[gi] >= 2)
    t['parked'] = parked

    idx_of = [np.where(t.di.values == i)[0] for i in range(ND)]
    A = {c: [t[c].values[ix].astype(float) for ix in idx_of] for c in ['T', 'X', 'Y', 'P', 'lap', 'pit', 'parked']}
    N = len(t)
    Fm = np.full((N, ND), np.inf, np.float32)
    K = np.full((N, ND), np.nan, np.float32); n_missing = np.zeros(N, np.int16)
    for i in range(ND):
        ri = idx_of[i]
        if len(ri) == 0:
            continue
        ti = A['T'][i]; si = t.s.values[ri]; Pi = t.P.values[ri]
        for j in range(ND):
            if i == j or len(idx_of[j]) == 0:
                continue
            tj = A['T'][j]
            k = np.searchsorted(tj, ti)
            v = (k > 0) & (k < len(tj))
            k0 = np.clip(k - 1, 0, len(tj) - 1); k1 = np.clip(k, 0, len(tj) - 1)
            span = tj[k1] - tj[k0]; v &= span <= GAPMAX_S
            n_missing[ri] += ((ti >= tj[0]) & (ti <= tj[-1]) & ~_inwin(drivers[j], ti, win) & ~v).astype(np.int16)
            w = np.where(span > 0, (ti - tj[k0]) / np.where(span > 0, span, 1), 0.0)
            xj = A['X'][j][k0] * (1 - w) + A['X'][j][k1] * w
            yj = A['Y'][j][k0] * (1 - w) + A['Y'][j][k1] * w
            Pj = A['P'][j][k0] * (1 - w) + A['P'][j][k1] * w
            sj, _ = proj(xj, yj)
            f = np.mod(sj - si, L) / 10.0
            pj = (A['pit'][j][k0] > 0) | (A['pit'][j][k1] > 0)
            elig = v & ~pj & ~(A['parked'][j][k0] > 0) & (f > 0) & (f <= W_M)
            Fm[ri, j] = np.where(elig, f, np.inf)
            K[ri, j] = np.where(v, np.round((Pj - Pi - np.mod(sj - si, L)) / L), np.nan)
    jbest = Fm.argmin(1); f1 = Fm.min(1).astype(float); has = np.isfinite(f1)
    f2 = np.sort(Fm, 1)[:, 1].astype(float) if ND > 1 else np.full(N, np.inf)
    rows = np.arange(N)
    kb = np.where(has, K[rows, jbest], np.nan)
    unknown = t.pit.values | t.parked.values | (t.off.values > OFFLINE_U) | (n_missing > 0)
    sbs = has & (f1 < SIDE_BY_SIDE_M)
    ovl = has & ~sbs & np.isfinite(f2) & (np.where(np.isfinite(f2), f2, 0.0) - np.where(has, f1, 0.0) < OVERLAP_M)
    cls = np.full(N, 'same_lap', dtype=object)
    cls[~has] = 'clear'
    cls[has & (kb != 0)] = 'lapped'
    cls[ovl] = 'overlapping'
    cls[sbs] = 'side_by_side'
    cls[t.lap.values == 1] = 'lap1'
    cls[unknown] = 'unknown'
    reason = np.select([t.pit.values, t.parked.values, t.off.values > OFFLINE_U, n_missing > 0],
                       ['follower_pit', 'follower_parked', 'follower_offline', 'car_missing'], None)

    # follower-trajectory time gap (seconds) to the point where the car ahead is now
    gap_s = np.full(N, np.nan)
    for _, gi in t.groupby('di').indices.items():
        tgt = np.where(has[gi], t.P.values[gi] + f1[gi] * 10.0, np.nan)
        reach = _follower_time_gap(t['T'].values[gi], t.P.values[gi], tgt)
        gap_s[gi] = reach - t['T'].values[gi]
    gap_s = np.where((gap_s >= 0) & (gap_s <= MAX_GAP_S), gap_s, np.nan)

    known = cls != 'unknown'
    ahead = np.where(has & known, np.array(drivers, dtype=object)[jbest], None)
    out = pd.DataFrame(dict(
        driver_id=t.drv.values, lap_number=t.lap.values.astype(int), session_time_s=t['T'].values,
        sample_class=cls, unknown_reason=reason,
        ahead_driver_id=ahead,
        gap_m=np.where(known & has, f1, np.nan),
        gap_s=np.where(known & has, gap_s, np.nan)))
    if drop_zero_xy and zero.any():   # placeholder rows kept as rows, always unknown
        z = full[zero]
        out = pd.concat([out, pd.DataFrame(dict(
            driver_id=z.drv.values, lap_number=z.lap.values.astype(int), session_time_s=z['T'].values,
            sample_class='unknown', unknown_reason='zero_xy_placeholder'))], ignore_index=True)
    out = out.sort_values(['driver_id', 'session_time_s'], kind='stable').reset_index(drop=True)
    # time the follower spent at each sample, clamped so a feed gap cannot dominate a lap
    nxt = out.groupby('driver_id').session_time_s.shift(-1)
    out['dt_s'] = (nxt - out.session_time_s).clip(lower=0.0, upper=GAPMAX_S).fillna(0.0)
    # identity flips between consecutive samples <= 1 s apart, both with a car ahead (exp 26 P4 definition)
    na = out.groupby('driver_id').ahead_driver_id.shift(-1)
    pair = out.ahead_driver_id.notna() & na.notna() & (nxt - out.session_time_s <= 1.0)
    out['flip_pair'] = pair
    out['flip'] = pair & (out.ahead_driver_id != na)
    out.attrs['track_length_m'] = L / 10.0
    out.attrs['n_zero_xy_samples'] = n_zero
    return out


def reduce_to_laps(s, unknown_max_share=0.05, min_class_samples=4):
    """Per-sample frame -> one row per (driver_id, lap_number)."""
    s = s.copy()
    for c in SAMPLE_CLASSES:
        s['n_' + c] = (s.sample_class == c).astype(int)
    s['close'] = (s.sample_class == 'same_lap') & (s.gap_s < CLOSE_S)
    s['dt_close'] = np.where(s.close, s.dt_s, 0.0)
    s['dt_known'] = np.where(s.sample_class != 'unknown', s.dt_s, 0.0)
    s['gap_s_valid'] = np.where(s.sample_class == 'same_lap', s.gap_s, np.nan)
    s['gap_m_valid'] = np.where(s.sample_class == 'same_lap', s.gap_m, np.nan)
    # identity of the car ahead at the lap's minimum valid gap (diagnostic; for the int_lap_proximity agreement test)
    v = s[s.gap_s_valid.notna()].sort_values(['driver_id', 'lap_number', 'gap_s_valid', 'session_time_s'], kind='stable')
    amin = v.groupby(['driver_id', 'lap_number'], as_index=False).first()[['driver_id', 'lap_number', 'ahead_driver_id']]
    amin = amin.rename(columns={'ahead_driver_id': 'gap_ahead_phys_min_driver_id'})
    agg = s.groupby(['driver_id', 'lap_number']).agg(
        n_samples=('sample_class', 'size'),
        **{f'n_{c}_samples': ('n_' + c, 'sum') for c in SAMPLE_CLASSES},
        gap_ahead_phys_s=('gap_s_valid', 'min'),
        gap_ahead_phys_median_s=('gap_s_valid', 'median'),
        gap_ahead_phys_min_m=('gap_m_valid', 'min'),
        time_within_1s_phys_s=('dt_close', 'sum'),
        time_measured_s=('dt_known', 'sum'),
        n_ahead_pairs=('flip_pair', 'sum'),
        n_ahead_flips=('flip', 'sum'),
    ).reset_index()
    unk = agg.n_unknown_samples / agg.n_samples
    m = min_class_samples
    agg['validity_class'] = np.select(
        [unk > unknown_max_share, agg.lap_number == 1, agg.n_lapped_samples >= m,
         agg.n_overlapping_samples >= m, agg.n_side_by_side_samples >= m],
        ['unknown', 'lap1', 'lapped', 'overlapping', 'side_by_side'], 'valid_same_lap')
    valid = agg.validity_class == 'valid_same_lap'
    for c in ('gap_ahead_phys_s', 'gap_ahead_phys_median_s', 'gap_ahead_phys_min_m',
              'time_within_1s_phys_s', 'time_measured_s'):
        agg[c] = agg[c].where(valid)
    agg['time_within_1s_phys_s'] = agg.time_within_1s_phys_s.round(4)
    agg['time_measured_s'] = agg.time_measured_s.round(4)
    agg['is_within_1s_of_car_ahead'] = pd.Series(
        np.where(valid, agg.gap_ahead_phys_s.lt(CLOSE_S), None), dtype='boolean')
    # dominant unknown reason, for diagnosis only
    r = s[s.unknown_reason.notna()].groupby(['driver_id', 'lap_number']).unknown_reason.agg(
        lambda x: x.value_counts().index[0]).rename('unknown_reason_mode').reset_index()
    agg = agg.merge(amin, on=['driver_id', 'lap_number'], how='left')
    agg['gap_ahead_phys_min_driver_id'] = agg.gap_ahead_phys_min_driver_id.where(valid)
    return agg.merge(r, on=['driver_id', 'lap_number'], how='left')


def _as_bool(v):
    return str(v).strip().lower() in ('true', '1', 'yes')


def model(dbt, session):
    dbt.config(materialized='table')
    # dbt parses dbt.config.get() statically, so each key is read with a literal name
    def cfg(v, default):
        return default if v is None or str(v).strip() in ('', 'None') else v
    drop_zero_xy = _as_bool(cfg(dbt.config.get('drop_zero_xy'), False))   # NOT validated; default off (header)
    unknown_max_share = float(cfg(dbt.config.get('unknown_max_share'), 0.05))
    min_class_samples = int(float(cfg(dbt.config.get('min_class_samples'), 4)))

    spine = dbt.ref('int_stint_geometry').project(
        'lap_id, race_year, race_id, driver_id, lap_number, '
        '(is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap) AS is_neutralised_lap').df()
    tel_rel = dbt.source('bronze_f1', 'raw_telemetry')
    laps_rel = dbt.source('bronze_f1', 'raw_laps')
    parts, no_ref = [], []
    for rid in sorted(spine.race_id.unique()):
        tel = (tel_rel.filter(f"Source = 'pos' AND race_id = '{rid}'")
               .project('SessionTime / 1e9 AS T, driver_id AS drv, CAST(lap_number AS INTEGER) AS lap, X, Y, "index"')
               .order('drv, T, "index"').df())
        laps = laps_rel.filter(f"race_id = '{rid}'").df()
        if tel.empty or laps.empty:
            continue   # no telemetry: every spine lap of the race comes out 'unknown' below
        smp = build_race_samples(tel, laps, drop_zero_xy=drop_zero_xy)
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
    out = out.rename(columns={'race_year': 'season'})
    count_cols = ['n_samples'] + [f'n_{c}_samples' for c in SAMPLE_CLASSES] + ['n_ahead_pairs', 'n_ahead_flips']
    for c in count_cols:
        out[c] = out[c].fillna(0).astype('int64')
    cols = ['lap_id', 'race_id', 'season', 'driver_id', 'lap_number', 'validity_class', 'is_within_1s_of_car_ahead',
            'gap_ahead_phys_s', 'gap_ahead_phys_median_s', 'gap_ahead_phys_min_m', 'gap_ahead_phys_min_driver_id',
            'time_within_1s_phys_s',
            'time_measured_s', 'is_neutralised_lap'] + count_cols + [
            'unknown_reason_mode', 'track_length_m', 'n_zero_xy_samples_race', 'zero_xy_guard_on']
    return out[cols].sort_values(['race_id', 'driver_id', 'lap_number'], kind='stable').reset_index(drop=True)
