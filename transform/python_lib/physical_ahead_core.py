"""physical_ahead_core.py · shared pure-Python core of int_lap_physical_ahead and int_physical_ahead_pairs.

Moved verbatim from int_lap_physical_ahead.py; the model files keep only the dbt wiring. The text below is the
original model header, so "this model" means int_lap_physical_ahead, whose rows reduce_to_laps produces.
pairs_from_samples and read_race_inputs are the only additions (pair grain and the per-race bronze read).


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
  distance in (0, 300 m]. A car is "parked" on lap >= 2 when it moved < 5 m over a 10 s window. Parked cars are
  never on-track candidates: their unwrapped progress P is frozen while the follower keeps lapping, so the lap
  offset K of a parked car is a lap deficit (the follower is "lapping" a stopped car), which is arithmetically
  right but does not describe racing. Parked cars are handled apart from the candidates (changed 2026-11-20; before,
  they were dropped, so a follower behind a car stopped on the racing line came out 'clear', 0.25% of clear
  samples across all races):
    * parked ON the racing line (not in its pit window, <= 15 m from the polyline at that instant) is a real
      obstacle. It is recorded separately and, when it is the nearest car ahead, the sample is 'parked_ahead'
      (rule below). Its lap offset is never used. Evaluated per sample, so a retired car blocks only for the
      time it is actually on the line; once it is towed or pushed > 15 m off, it no longer counts.
    * parked OFF the line (> 15 m: gravel, garage, tow position) is still dropped. A car there is not in the
      follower's way, and a retired car can sit off the line for the rest of the race, so counting it would
      mark every lap that passes it.
  Cars in their pit window are NOT dropped (changed 2026-11-20; before, they were excluded
  like parked cars and a sample whose only car ahead was in the pits came out 'clear', 1.1% of clear samples
  across 188 races). They are held apart from the on-track candidates: if the nearest car ahead (over on-track
  cars and cars in their pit window) is in its pit window the sample is 'leader_in_pit'. A pit-window or on-line parked
  car that is farther than the nearest on-track car changes nothing. Neither ever makes a sample 'lapped',
  'overlapping' or 'side_by_side' (a car in the pit lane runs beside the main straight, so those labels would
  describe the pit lane, not racing); the pit-lane projection cannot give a meaningful lap offset, see
  below. Pit windows are PitInTime to the next lap row's PitOutTime, or PitInTime + 120 s when there is no exit
  time, plus (0, PitOutTime) for a pit-lane start on lap 1; this equals stg_pits.pit_in_time_s / pit_out_time_s
  on every stop (checked on all bronze races), so stg_pits was not made a dependency.
  Sample class, precedence top to bottom:
    unknown        follower in its pit window, parked, > 15 m off the polyline, or another car expected on
                   track has no position bracket within 1 s. Car ahead and gap are NULL. NEVER clear air.
    lap1           follower lap_number = 1 (Study D: 53-63% agreement; order not resolvable at the start).
    leader_in_pit  the nearest car ahead within 300 m is in its pit window. Not clear air (a car is there) and
                   not following (it is in the pit lane, not on the racing line); gap_m is the distance to it,
                   ahead_driver_id is that car, gap_s is NULL, so it is never in the close set (gap_s < 1 s).
    parked_ahead   the nearest car ahead within 300 m is parked on the racing line (see above), nearer than any
                   on-track car or pit-window car. Not clear air and not following: gap_m is the distance to it,
                   ahead_driver_id is that car, gap_s is NULL, so it is never in the close set (gap_s < 1 s). The
                   lap offset is not consulted, so a stopped car many laps "down" is not 'lapped'.
    side_by_side   car ahead < 10 m.
    overlapping    second-nearest car within 15 m of the nearest.
    lapped         car ahead is on a different lap by unwrapped progress (lap offset != 0), either way.
    same_lap       a car ahead within 300 m on the same lap.
    clear          no on-track car, no car in its pit window and no car parked on the racing line within 300 m
                   ahead (a car parked > 15 m off the line is still not counted, see above) AND every expected car was located (a measured
                   "nobody close").
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
    (parked_ahead)   NO lap rule yet: n_parked_ahead_samples is carried on every lap and such a lap stays
                     valid_same_lap, its parked_ahead time outside the close set. Whether many such samples
                     should make the lap 'unknown' (as for leader_in_pit) is an open owner decision.
    unknown          (second rule) >= that many samples classed leader_in_pit. The lap carries no LAP class of its
                     own: those >= 1 s were neither clear air nor following, so the lap's "never within 1 s" cannot
                     be claimed. unknown_reason_mode = 'leader_in_pit' tells it apart from an unmeasurable lap.
                     Fewer than that many leader_in_pit samples leave the lap valid_same_lap; the samples are still
                     counted in n_leader_in_pit_samples, and their time is outside the close set.
    valid_same_lap   everything else: every sample known, and the car ahead (when one was within 300 m)
                     was on the same lap and orderable. Includes measured clear-air laps.
  Only valid_same_lap carries is_within_1s_of_car_ahead and the gap columns. Every other class has them NULL
  and must not be COALESCEd to "clear air" or to "following". On a valid_same_lap lap the flag is TRUE when
  the minimum measured gap was < 1 s and FALSE otherwise. FALSE therefore also covers a lap with NO measured
  gap: no car within 300 m (clear air) or a car within 300 m whose gap_s was NULL (the follower never reached
  its point, or took > 30 s, which is "not close" by definition, MAX_GAP_S). It is never NULL on a valid lap:
  int_traffic_exposure_driver_race counts it as a boolean and assert_physical_ahead_unknown_never_clear_air
  requires it on every valid lap. Read gap_ahead_phys_s IS NULL to tell "no gap measured" from "gap >= 1 s".

KNOWN LIMITS (not bugs to hide; see traffic_exposure_copy.md)
  * Agreement with int_lap_proximity's crossing-time car ahead is 96-99% on same-lap, non-lap-1,
    non-side-by-side samples (experiments 26, 27), not 100%.
  * Identity flips between consecutive samples are 0.18-0.42% of pairs in seven 2025 races and 0.64% in
    Canada 2025 (experiment 27), 0.66-0.83% in 2019 races (experiment 26). Canada's excess sits mostly in
    lapped and overlapping pairs (experiment 28). Carried per lap as n_ahead_flips / n_ahead_pairs.
    The 2018-2019 rate is higher for two reasons (2026-11-21 diagnosis): pos samples are 0.30 s apart in 2018-2019
    against 0.22-0.24 s from 2020, and most flips sit in side_by_side / overlapping / lap1 / lapped samples, where
    the order of two cars is unresolvable by definition and the laps are already excluded. On valid_same_lap
    laps the rate is 0.04-0.06% in 2018-2019 (0.007-0.012% from 2020). Real data effect, not a logic fault.
  * 2018-2019 pos data starts every car with ~30 X = Y = 0 placeholder samples. Until 2026-11-21 the unwrapped
    progress P was anchored on a car's first sample, so a placeholder put about half the cars exactly one lap
    off in the four races where it landed wrong (Singapore 2018 / 2019, Monaco 2018 / 2019): lapped share
    25-42% and 34-54% of laps classed 'lapped'. P is now unwrapped over the real samples only, which gives the same
    laps as the (still unvalidated, still off) zero-XY guard on those races. The guard itself stays off.
    assert_physical_ahead_lapped_share stays as the check for this failure mode.
  * 2018 Australia and Bahrain have no race telemetry in bronze at all (the source returned nothing), so
    every lap of those two races is 'unknown' (no_position_samples) and track_length_m is NULL. 2021 Belgium
    is three laps behind the safety car (red flag, pit-lane restart), so 63% 'unknown' is the race itself.

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
SAMPLE_CLASSES = ('unknown', 'lap1', 'leader_in_pit', 'parked_ahead', 'side_by_side', 'overlapping', 'lapped', 'same_lap', 'clear')
LAP_CLASSES = ('valid_same_lap', 'lap1', 'side_by_side', 'lapped', 'overlapping', 'unknown')

# Reference-lap closure rule. The reference polyline is closed with one straight chord from its last sample to its
# first, so a lap whose trace does not close cuts a corner at the line. The reference is the fastest clean lap whose
# first-to-last-sample gap is under this many metres. Chosen from the gap of the fastest clean lap in all 188 races
# (X/Y are 1/10 m): median 21 m, 95th percentile 45 m, a continuous bulk to 55 m, then 70, 73, 93, 125 m (2020 Austria,
# whose 125 m gap read 88% of laps 'follower_offline'). 60 m sits in the break above the bulk. A race with no clean
# lap under it keeps the fastest clean lap (the earlier behaviour).
REFERENCE_MAX_CLOSURE_GAP_M = 60.0

REFERENCE_K = 5         # consensus reference: laps pooled (one per driver). Used only when reference_method = 'consensus'


def reference_candidates(laps, rule='legacy'):
    """Clean laps eligible to define the reference line, fastest first (ties broken by driver, lap: deterministic).
    'legacy' = the rule the model has always used (timed, not deleted, no pit in/out, lap >= 2, raw Compound not
    null) plus the HD22 manual exclusion when the staging flag is present (a no-op on current data).
    'stg_valid' = stg_laps.is_valid_lap (also needs is_accurate from 2019, no SC/VSC/red flag, not lap 1) and a
    normalised compound; needs the staging columns, so it raises when they are absent."""
    if rule == 'stg_valid':
        ok = laps[laps.is_stg_valid_lap.fillna(False).astype(bool) & laps.compound_clean.notna()
                  & laps.LapTime.notna()]
    else:
        ok = laps[laps.LapTime.notna() & (laps.Deleted != True) & laps.PitInTime.isna() & laps.PitOutTime.isna()  # noqa: E712
                  & (laps.LapNumber >= 2) & laps.Compound.notna()]
        if 'is_manual_excluded' in ok.columns:
            ok = ok[~ok.is_manual_excluded.fillna(False).astype(bool)]
    return ok.sort_values(['LapTime', 'Driver', 'LapNumber'], kind='stable')


def consensus_polyline(t, zero, cand, base_xy, k):
    """Pointwise median of the k fastest clean laps, one lap per driver, as an (n, 2) array on the fastest lap's
    own arc-length grid (so the start/finish origin is the fastest lap's). Each other lap is matched to the base
    lap by nearest point on a 0.5 m resampling of that lap, then X and Y are medianed per base point. A lap is
    skipped when it has < 50 position samples or its length differs from the base lap's by more than 5% (a
    clipped or doubled trace). Fewer than 3 usable laps -> the base lap alone (no consensus). Medians smooth
    lateral line differences between drivers and remove the influence of any one bad trace."""
    def dense(xy):
        xy2 = np.vstack([xy, xy[0]])
        c = np.r_[0, np.cumsum(np.hypot(*np.diff(xy2, axis=0).T))]
        gg = np.arange(0, c[-1], STEP_U)
        return np.c_[np.interp(gg, c, xy2[:, 0]), np.interp(gg, c, xy2[:, 1])], c[-1]
    base, Lb = dense(base_xy)
    got, seen = [base], set()
    first = cand.iloc[0]
    seen.add(first.Driver)
    for _, r in cand.iloc[1:].iterrows():
        if len(got) >= k:
            break
        if r.Driver in seen:
            continue
        o = t[(t.drv == r.Driver) & (t.lap == r.LapNumber) & ~zero].sort_values('T')
        if len(o) < 50:
            continue
        od, Lo = dense(o[['X', 'Y']].values)
        if abs(Lo - Lb) > 0.05 * Lb:
            continue
        _, ix = cKDTree(od).query(base)
        got.append(od[ix]); seen.add(r.Driver)
    if len(got) < 3:
        return base_xy
    return np.median(np.stack(got), axis=0)


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


def build_race_samples(tel, laps, drop_zero_xy=False, reference_method='single', reference_k=REFERENCE_K,
                       reference_rule='legacy'):
    """tel: 'pos' rows of one race (T s, drv, lap, X, Y) ordered by drv, T. laps: bronze laps of the race.
    Returns one row per follower sample with sample_class, ahead identity, gap_m, gap_s, dt_s, or None when the
    race has no clean reference lap to project onto (then every lap of the race is 'unknown').
    reference_method 'single' (default, the validated behaviour) projects onto the one fastest clean lap;
    'consensus' projects onto the pointwise median of up to reference_k clean laps (see consensus_polyline).
    reference_rule 'legacy' (default) or 'stg_valid' picks which laps count as clean (see reference_candidates)."""
    t = tel.reset_index(drop=True).copy()
    zero = ((t.X.values == 0) & (t.Y.values == 0)) if drop_zero_xy else np.zeros(len(t), bool)
    n_zero = int(((t.X.values == 0) & (t.Y.values == 0)).sum())
    drivers = sorted(t.drv.unique()); di = {d: i for i, d in enumerate(drivers)}; ND = len(drivers)
    t['di'] = t.drv.map(di)
    win = _pit_windows(laps)
    t['pit'] = False
    for d, g in t.groupby('drv'):
        t.loc[g.index, 'pit'] = _inwin(d, g['T'].values, win)

    cand = reference_candidates(laps, reference_rule)
    if cand.empty:
        return None   # no clean reference lap (e.g. 2021 Belgium, run behind the SC): race not measurable
    best, ref = cand.iloc[0], None
    for _, c_ in cand.iterrows():   # fastest clean lap whose trace closes to within REFERENCE_MAX_CLOSURE_GAP_M
        r_ = t[(t.drv == c_.Driver) & (t.lap == c_.LapNumber) & ~zero].sort_values('T')
        # a lap with no usable trace (< 50 samples) has no gap to test: it is picked as before and ends the race below
        if len(r_) < 50 or np.hypot(*(r_[['X', 'Y']].values[-1] - r_[['X', 'Y']].values[0])) / 10.0 < REFERENCE_MAX_CLOSURE_GAP_M:
            best, ref = c_, r_
            break
    if ref is None:   # no clean lap closes under the threshold: the fastest clean lap, as before
        ref = t[(t.drv == best.Driver) & (t.lap == best.LapNumber) & ~zero].sort_values('T')
    if len(ref) < 50:
        return None   # reference lap has no usable position trace
    xy = ref[['X', 'Y']].values
    if reference_method == 'consensus':
        xy = consensus_polyline(t, zero, cand, xy, reference_k)
    xy = np.vstack([xy, xy[0]])
    cs = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]; L = cs[-1]
    g = np.arange(0, L, STEP_U); gx = np.interp(g, cs, xy[:, 0]); gy = np.interp(g, cs, xy[:, 1])
    tree = cKDTree(np.c_[gx, gy])

    def proj(x, y):
        d, ix = tree.query(np.c_[x, y]); return g[ix], d

    full = t
    t = t[~zero].reset_index(drop=True)   # guard on: placeholder samples removed from every car's track
    t['s'], t['off'] = proj(t.X.values, t.Y.values)
    P = np.zeros(len(t))
    placeholder = (t.X.values == 0) & (t.Y.values == 0)   # empty when the guard is on (rows already removed)
    for _, gi in t.groupby('di').indices.items():
        # Unwrap over the real samples only. A car's first samples are X = Y = 0 placeholders in 2018-2019 pos data
        # (every car, ~30 samples of lap 1); anchoring on one put s0 at an arbitrary point, so the unwrapped progress
        # of about half the cars came out exactly one lap off and every pair with them read 'lapped' (Singapore 2018 /
        # 2019, Monaco 2018 and 2019). A placeholder row takes the progress of the real sample before it (the first
        # real sample for leading ones); its own projection is junk either way and is not used for the unwrap.
        s = t.s.values[gi]; good = ~placeholder[gi]
        if not good.any():
            good = np.ones(len(gi), bool)
        sg = s[good]; s0 = sg[0] - (L if sg[0] > L / 2 else 0)
        dd = np.diff(sg); dd = np.where(dd < -L / 2, dd + L, np.where(dd > L / 2, dd - L, dd))
        Pg = s0 + np.r_[0, np.cumsum(dd)]
        P[gi] = Pg[np.maximum(np.cumsum(good) - 1, 0)]
    t['P'] = P
    parked = np.zeros(len(t), bool)
    for _, gi in t.groupby('di').indices.items():
        T_ = t['T'].values[gi]; X_ = t.X.values[gi]; Y_ = t.Y.values[gi]
        lo = np.searchsorted(T_, T_ - 5.0); hi = np.searchsorted(T_, T_ + 5.0, 'right') - 1
        parked[gi] = (np.hypot(X_[hi] - X_[lo], Y_[hi] - Y_[lo]) < 50) & (t.lap.values[gi] >= 2)
    t['parked'] = parked

    idx_of = [np.where(t.di.values == i)[0] for i in range(ND)]
    A = {c: [t[c].values[ix].astype(float) for ix in idx_of] for c in ['T', 'X', 'Y', 'P', 'lap', 'pit', 'parked', 'off']}
    N = len(t)
    Fm = np.full((N, ND), np.inf, np.float32); Fp = np.full((N, ND), np.inf, np.float32)
    Fq = np.full((N, ND), np.inf, np.float32)   # parked on the racing line
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
            # a car in its pit window is no longer dropped: it is recorded here, separately from the eligible
            # candidates, and decides 'leader_in_pit' when it is the nearest car ahead (see the header)
            Fp[ri, j] = np.where(v & pj & (f > 0) & (f <= W_M), f, np.inf)
            # a car parked ON the racing line (not in its pit window) is an obstacle: recorded apart, never given a lap
            # offset (its P is frozen, so K would only count the laps the follower has gained on a stopped car)
            pkon = v & ~pj & (A['parked'][j][k0] > 0) & (A['off'][j][k0] <= OFFLINE_U) & (f > 0) & (f <= W_M)
            Fq[ri, j] = np.where(pkon, f, np.inf)
            K[ri, j] = np.where(v, np.round((Pj - Pi - np.mod(sj - si, L)) / L), np.nan)
    jbest = Fm.argmin(1); f1 = Fm.min(1).astype(float); has = np.isfinite(f1)
    f2 = np.sort(Fm, 1)[:, 1].astype(float) if ND > 1 else np.full(N, np.inf)
    rows = np.arange(N)
    kb = np.where(has, K[rows, jbest], np.nan)
    jp = Fp.argmin(1); fp1 = Fp.min(1).astype(float)
    jq = Fq.argmin(1); fq1 = Fq.min(1).astype(float)
    lip = np.isfinite(fp1) & (fp1 < f1) & (fp1 <= fq1)   # the nearest car ahead (on-track, pit-window or on-line parked) is in its pit window
    lpk = np.isfinite(fq1) & (fq1 < f1) & (fq1 < fp1)    # ... is parked on the racing line
    unknown = t.pit.values | t.parked.values | (t.off.values > OFFLINE_U) | (n_missing > 0)
    sbs = has & (f1 < SIDE_BY_SIDE_M)
    ovl = has & ~sbs & np.isfinite(f2) & (np.where(np.isfinite(f2), f2, 0.0) - np.where(has, f1, 0.0) < OVERLAP_M)
    cls = np.full(N, 'same_lap', dtype=object)
    cls[~has] = 'clear'
    cls[has & (kb != 0)] = 'lapped'
    cls[ovl] = 'overlapping'
    cls[sbs] = 'side_by_side'
    cls[lip] = 'leader_in_pit'   # overrides side_by_side / overlapping / lapped: those need an on-track car ahead
    cls[lpk] = 'parked_ahead'    # same: a parked car is an obstacle, not a lapped car (its lap offset is not used)
    cls[t.lap.values == 1] = 'lap1'
    cls[unknown] = 'unknown'
    reason = np.select([t.pit.values, t.parked.values, t.off.values > OFFLINE_U, n_missing > 0],
                       ['follower_pit', 'follower_parked', 'follower_offline', 'car_missing'], None)

    # follower-trajectory time gap (seconds) to the point where the car ahead is now
    gap_s = np.full(N, np.nan)
    for _, gi in t.groupby('di').indices.items():
        tgt = np.where(has[gi] & ~lip[gi] & ~lpk[gi], t.P.values[gi] + f1[gi] * 10.0, np.nan)
        reach = _follower_time_gap(t['T'].values[gi], t.P.values[gi], tgt)
        gap_s[gi] = reach - t['T'].values[gi]
    gap_s = np.where((gap_s >= 0) & (gap_s <= MAX_GAP_S), gap_s, np.nan)

    known = cls != 'unknown'
    ahead = np.where(has & known, np.array(drivers, dtype=object)[jbest], None)
    ahead = np.where(lip & known, np.array(drivers, dtype=object)[jp], ahead)
    ahead = np.where(lpk & known, np.array(drivers, dtype=object)[jq], ahead)
    # leader_in_pit / parked_ahead keep the metre gap to that car; gap_s stays NULL (never close)
    gap_m = np.where(lip, fp1, np.where(lpk, fq1, f1))
    out = pd.DataFrame(dict(
        driver_id=t.drv.values, lap_number=t.lap.values.astype(int), session_time_s=t['T'].values,
        sample_class=cls, unknown_reason=reason,
        ahead_driver_id=ahead,
        gap_m=np.where(known & (has | lip | lpk), gap_m, np.nan),
        gap_s=np.where(known & has & ~lip & ~lpk, gap_s, np.nan)))
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
    fa = out.ahead_driver_id.where(~out.sample_class.isin(['leader_in_pit', 'parked_ahead']))   # a pit / parked car's identity is not an ordering
    na = fa.groupby(out.driver_id).shift(-1)
    pair = fa.notna() & na.notna() & (nxt - out.session_time_s <= 1.0)
    out['flip_pair'] = pair
    out['flip'] = pair & (fa != na)
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
    lp = s.sample_class == 'lapped'
    s['dt_lapped_close'] = np.where(lp & (s.gap_s < CLOSE_S), s.dt_s, 0.0)
    s['gap_s_lapped'] = np.where(lp, s.gap_s, np.nan)
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
        lapped_seconds_within_1s=('dt_lapped_close', 'sum'),
        lapped_time_measured_s=('dt_known', 'sum'),
        lapped_gap_phys_min_s=('gap_s_lapped', 'min'),
        n_ahead_pairs=('flip_pair', 'sum'),
        n_ahead_flips=('flip', 'sum'),
    ).reset_index()
    unk = agg.n_unknown_samples / agg.n_samples
    m = min_class_samples
    lip_lap = agg.n_leader_in_pit_samples >= m
    agg['validity_class'] = np.select(
        [unk > unknown_max_share, agg.lap_number == 1, agg.n_lapped_samples >= m,
         agg.n_overlapping_samples >= m, agg.n_side_by_side_samples >= m, lip_lap],
        ['unknown', 'lap1', 'lapped', 'overlapping', 'side_by_side', 'unknown'], 'valid_same_lap')
    valid = agg.validity_class == 'valid_same_lap'
    # LAPPED TAG (added, headline unchanged): laps classed 'lapped' keep their own measurement. Populated on
    # validity_class = 'lapped' laps only, NULL elsewhere. lapped_seconds_within_1s = time the follower was
    # within 1 s behind a car that is on a different lap (class 'lapped' samples only; same_lap samples on the
    # same lap are not added); lapped_time_measured_s = the lap's known-sample time; lapped_gap_phys_min_s = the
    # smallest such gap. Never merged into the headline columns, which stay NULL on these laps.
    agg['is_lapped_lap'] = agg.validity_class == 'lapped'
    for c in ('lapped_seconds_within_1s', 'lapped_time_measured_s', 'lapped_gap_phys_min_s'):
        agg[c] = agg[c].where(agg.is_lapped_lap)
    agg['lapped_seconds_within_1s'] = agg.lapped_seconds_within_1s.round(4)
    agg['lapped_time_measured_s'] = agg.lapped_time_measured_s.round(4)
    for c in ('gap_ahead_phys_s', 'gap_ahead_phys_median_s', 'gap_ahead_phys_min_m',
              'time_within_1s_phys_s', 'time_measured_s'):
        agg[c] = agg[c].where(valid)
    agg['time_within_1s_phys_s'] = agg.time_within_1s_phys_s.round(4)
    agg['time_measured_s'] = agg.time_measured_s.round(4)
    # NaN gap (clear air, or gap unmeasured / > MAX_GAP_S) compares False on purpose: see the header, never NULL on a valid lap
    agg['is_within_1s_of_car_ahead'] = pd.Series(
        np.where(valid, agg.gap_ahead_phys_s.lt(CLOSE_S), None), dtype='boolean')
    # dominant unknown reason, for diagnosis only
    r = s[s.unknown_reason.notna()].groupby(['driver_id', 'lap_number']).unknown_reason.agg(
        lambda x: x.value_counts().index[0]).rename('unknown_reason_mode').reset_index()
    agg = agg.merge(amin, on=['driver_id', 'lap_number'], how='left')
    agg['gap_ahead_phys_min_driver_id'] = agg.gap_ahead_phys_min_driver_id.where(valid)
    agg = agg.merge(r, on=['driver_id', 'lap_number'], how='left')
    # a lap made 'unknown' only by the leader_in_pit rule says so (the follower's own samples were all known)
    agg.loc[lip_lap & (agg.validity_class == 'unknown') & ~(unk > unknown_max_share), 'unknown_reason_mode'] = 'leader_in_pit'
    return agg


def _as_bool(v):
    return str(v).strip().lower() in ('true', '1', 'yes')


def assert_lap_model_guard_matches(lap_guard_values, drop_zero_xy, model_name):
    """Config-consistency check for the pair models. They recompute the per-sample build, so they must use the
    same drop_zero_xy as int_lap_physical_ahead, which records its setting in zero_xy_guard_on on every row.
    Raises when the lap table was built with the other value. (reference_method / reference_k / reference_rule are
    not recorded in the lap table, so they cannot be checked here: they are a documented invariant only.)"""
    seen = {bool(x) for x in pd.Series(lap_guard_values).dropna().unique()}
    if seen and seen != {bool(drop_zero_xy)}:
        raise ValueError(f"{model_name}: drop_zero_xy={bool(drop_zero_xy)} but int_lap_physical_ahead was built with "
                         f"zero_xy_guard_on={sorted(seen)}; rebuild both with the same physical_ahead_* vars")



def read_race_inputs(tel_rel, laps_rel, rid):
    """The two frames build_race_samples needs for one race, read from the STAGING relations
    stg_physical_ahead_telemetry and stg_physical_ahead_laps (not from bronze: the cleaning rules live in
    staging). The frames are returned in the column names build_race_samples has always taken (telemetry
    T, drv, lap, X, Y, index; laps FastF1 names), so its code did not change. Either may be empty."""
    tel = (tel_rel.filter(f"race_id = '{rid}'")
           .project('session_time_s AS T, driver_id AS drv, lap_number AS lap, x AS X, y AS Y, sample_index AS "index"')
           .order('drv, T, "index"').df())
    laps = (laps_rel.filter(f"race_id = '{rid}'")
            .project('driver_id AS Driver, lap_number AS LapNumber, lap_time_ns AS LapTime, deleted AS Deleted, '
                     'compound_raw AS Compound, pit_in_time_ns AS PitInTime, pit_out_time_ns AS PitOutTime, '
                     'track_status AS TrackStatus, is_manual_excluded, is_stg_valid_lap, compound_clean')
            .df())
    return tel, laps


PAIR_COLS = ['follower_driver_id', 'leader_driver_id', 'lap_number', 'seconds_within_1s',
             'n_samples_within_1s', 'min_gap_s', 'median_gap_s']


def pairs_from_samples(s, sample_class='same_lap'):
    """Per-sample frame (build_race_samples output) -> one row per (follower, leader, lap_number) over the
    samples the lap model counts as close: sample_class == 'same_lap' and gap_s < CLOSE_S (the reduce_to_laps
    `close` definition), with a car ahead. seconds_within_1s sums the same dt_s, so summed over leaders it
    equals reduce_to_laps' dt_close per lap (before that model's 4 dp rounding and its validity gate).
    MEASUREMENT ONLY. No validity filtering here: that is the caller's flag, never a drop.
    sample_class='lapped' gives the lapped-traffic pairs (int_physical_ahead_pairs_lapped); default unchanged."""
    c = s[(s.sample_class == sample_class) & (s.gap_s < CLOSE_S) & s.ahead_driver_id.notna()]
    if c.empty:
        return pd.DataFrame({k: pd.Series(dtype='object' if k.endswith('driver_id') else 'float64')
                             for k in PAIR_COLS})
    g = c.groupby(['driver_id', 'ahead_driver_id', 'lap_number']).agg(
        seconds_within_1s=('dt_s', 'sum'), n_samples_within_1s=('dt_s', 'size'),
        min_gap_s=('gap_s', 'min'), median_gap_s=('gap_s', 'median')).reset_index()
    g['seconds_within_1s'] = g.seconds_within_1s.round(4)
    g = g.rename(columns={'driver_id': 'follower_driver_id', 'ahead_driver_id': 'leader_driver_id'})
    return g[PAIR_COLS]
