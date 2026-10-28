"""Synthetic tests for the WC-03 / WC-04 contest (contest.py): §8a step 3 (amendment A4 ruling 3), the scored
set, the measured cost as a linear map, the halves and train laps, θ_now refit per draw, the 2025 rescoring
per draw, W1-W3, G5, G7 (A4 ruling 1) and the §9 verdict table. Every input is generated here; no bronze
file, warehouse or pass table on disk is read."""

import numpy as np
import pandas as pd
import pytest

from tasks.wake_calibration import contest as C
from tasks.wake_calibration import estimator as E
from tasks.wake_calibration.tests.test_estimator import TRUE_CURVE, _calendar, _race_passes

# ---------------------------------------------------------------- a synthetic world: passes + yardstick panel


def _age_bin(lap_in_stint: int) -> str:
    return ("a01_05", "b06_10", "c11_15", "d16_20", "e21_25", "f26_plus")[min((lap_in_stint - 1) // 5, 5)]


def world(seed=0, seasons=(2022, 2023, 2024), races_per_season=4, n_circuits=4, held=3, n_drivers=6,
          laps=range(2, 22), noise=0.05):
    """Fit races (circuit = slug prefix, so each circuit hosts several races), held-out 2025 races, prepared
    passes, and a yardstick panel whose residual = stint level + tyre age + the true measured cost (the
    registered curve applied by §7) + noise. Panel laps run 1..last, so lap 1 and the last lap have no pass
    row, as the builder makes them (A3)."""
    rng = np.random.default_rng(seed)
    races = [(s, f"c{(i + s) % n_circuits}x{s}r{i}") for s in seasons for i in range(races_per_season)]
    races += [(2025, f"c{i % n_circuits}x2025r{i}") for i in range(held)]
    cal = _calendar(races, circuit_of=lambda s, r: r.split("x")[0].upper())
    frame = pd.concat([_race_passes(s, r, rng, n_drivers=n_drivers, laps=laps, noise=noise) for s, r in races],
                      ignore_index=True)
    prepared = E.prepare_passes(frame, cal)
    # The class rule is tested in test_estimator.py. In this world the car ahead is redrawn at every corner, so
    # nearly every following pass is racecraft; held up / dirty air are assigned at random among following
    # passes with a measured reference instead, so both class curves have passes in every bin.
    judged = prepared["pass_class"].notna() & (prepared["ref_status"] == "measured")
    prepared.loc[judged, "pass_class"] = np.where(rng.random(int(judged.sum())) < 0.5, E.HELD_UP, E.DIRTY_AIR)
    keys = prepared[E.PASS_KEY].drop_duplicates().reset_index(drop=True)
    design = C.lap_design(keys, prepared)
    true_cost = design @ np.tile(TRUE_CURVE, (3, 1)).ravel()
    cost = dict(zip(map(tuple, keys.to_numpy()), true_cost))
    brk = prepared[prepared["segment_basis"] == E.BRAKING_BASIS]
    close = (brk["gap_s"] < 1.0).groupby([brk[k] for k in E.PASS_KEY]).mean()
    rows = []
    for (season, race_id, driver), _ in keys.groupby(["season", "race_id", "driver"]):
        level = {1: rng.normal(0, 0.5), 2: rng.normal(0, 0.5)}
        prev_share = 0.0
        for lap in range(1, max(laps) + 2):
            stint = 1 if lap < 14 else 2
            lis = lap if stint == 1 else lap - 13
            k = (season, race_id, driver, lap)
            share = float(close.get(k, rng.uniform(0, 0.3)))
            c = cost.get(k, 0.0)
            rows.append({
                "lap_id": f"{season}_{race_id}_{driver}_{lap}", "race_year": season, "race_id": race_id,
                "driver_id": driver, "lap_number": lap, "stint_id": f"{race_id}|{driver}|{stint}",
                "age_bin": _age_bin(lis), "partial_residual_s": level[stint] + 0.02 * lis + c + rng.normal(0, noise),
                "dirty_air_share_lap": share, "dirty_air_tax_s": float(np.clip(0.331 * prev_share, 0, 5)),
                "d_lag1": prev_share,
            })
            prev_share = share
    panel = pd.DataFrame(rows)
    return prepared, panel, cal, races


# ---------------------------------------------------------------- stint + tyre-age residual, weights (A4 4a)


def test_resid_stint_age_equals_two_way_demeaning():
    rng = np.random.default_rng(1)
    stint, age = rng.integers(0, 25, 400), rng.integers(0, 6, 400)
    y = rng.normal(size=(400, 2))
    assert np.allclose(C.resid_stint_age(y, stint, age), E.demean_two_way(y, stint, age), atol=1e-9)


def test_a4_weighted_equals_separate_copies():
    """A4 ruling 4a: a stint with frequency weight k = k copies of the stint, relabelled per copy. (Holds when
    the weight is constant within a stint; a race weight is, because stints are nested in races.)"""
    rng = np.random.default_rng(2)
    n = 300
    stint, age = rng.integers(0, 20, n), rng.integers(0, 6, n)
    y = rng.normal(size=n)
    w = rng.integers(0, 4, 20).astype(float)[stint]  # one weight per stint, as a race weight gives
    w[stint == 3] = 0.0
    copies = np.repeat(np.arange(n), w.astype(int))
    occ = np.concatenate([np.arange(int(k)) for k in w if k > 0])
    r_copy = C.resid_stint_age(y[copies], [f"{s}#{o}" for s, o in zip(stint[copies], occ)], age[copies])
    r_w = C.resid_stint_age(y, stint, age, w)
    assert np.allclose(r_w[copies], r_copy, atol=1e-9)
    assert np.isnan(r_w[w == 0]).all()


def test_theta_now_point_matches_estimator_and_recovers_the_slope():
    _, panel, _, _ = world(seed=3, races_per_season=2, n_drivers=4)
    fit = C.theta_fit_rows(panel)
    assert set(fit["race_year"]) <= {2022, 2023, 2024}
    assert C.theta_now_weighted(fit) == pytest.approx(E.fit_theta_now(panel), abs=1e-9)
    rng = np.random.default_rng(4)
    p = fit.copy()
    p["partial_residual_s"] = rng.normal(0, 0.1, len(p)) + 0.4 * p["dirty_air_share_lap"]
    assert C.theta_now_weighted(p) == pytest.approx(0.4, abs=0.05)


def test_theta_now_draws_use_the_draws_race_multiplicities_and_refuse_other_races():
    prepared, panel, _, _ = world(seed=5, races_per_season=2, n_drivers=4)
    fit = E.fit_passes(prepared)
    plan = E.resample_plan(sorted(fit["race_key"].unique()), E.race_circuits(fit), ["2025_x"], n_draws=3)
    pfit = C.theta_fit_rows(panel)
    th = C.theta_now_draws(pfit, plan)
    w = plan.race_weights()[0]
    races = list(plan.fit_races)
    copies = []
    for r, k in zip(races, w):
        for o in range(int(k)):
            g = pfit[pfit["race_id"] == r].copy()
            g["stint_id"] = g["stint_id"] + f"#{o}"
            copies.append(g)
    assert th[0] == pytest.approx(C.theta_now_weighted(pd.concat(copies)), abs=1e-9)
    with pytest.raises(E.EstimatorError):
        C.theta_now_draws(pfit[pfit["race_id"] != races[0]], plan)


def test_g1_v_theta_now_never_sees_the_held_out_season():
    _, panel, _, _ = world(seed=6, races_per_season=2, n_drivers=4)
    before = C.theta_now_weighted(C.theta_fit_rows(panel))
    panel.loc[panel["race_year"] == 2025, "partial_residual_s"] += 50 * panel["dirty_air_share_lap"]
    assert C.theta_now_weighted(C.theta_fit_rows(panel)) == before


# ---------------------------------------------------------------- §8a step 3 (A4 ruling 3) and the scored set


def test_a4_step3_label_is_the_registered_name():
    assert C.STEP3_REASON == "residual_beyond_5s" and C.STEP3_TRIM_S == 5.0


def _trim_panel(n_stints=10, laps=8, seed=7):
    rng = np.random.default_rng(seed)
    rows = [{"stint_id": f"s{s}", "age_bin": _age_bin(k + 1), "partial_residual_s": rng.normal(0, 0.2)}
            for s in range(n_stints) for k in range(laps)]
    return pd.DataFrame(rows)


def test_a4_step3_drops_laps_beyond_5s_once_on_kept_laps_only():
    p = _trim_panel()
    p.loc[5, "partial_residual_s"] = 20.0
    kept = pd.Series(True, index=p.index)
    kept.iloc[-3:] = False
    r = C.step3_trim_reason(p, kept)
    assert r.loc[5] == C.STEP3_REASON and r.drop(5).isna().all()
    p2 = p.copy()
    p2.loc[p.index[-3:], "partial_residual_s"] = 999.0  # a lap not kept at step 2 is not in the regression
    pd.testing.assert_series_equal(C.step3_trim_reason(p2, kept), r)


def test_a4_step3_threshold_is_strictly_greater_than_5s():
    p = pd.DataFrame({"stint_id": ["a"] * 2 + ["b"] * 2, "age_bin": ["x"] * 4,
                      "partial_residual_s": [5.0, -5.0, 0.0, 0.0]})
    # residuals: stint a mean 0 -> +-5.0 exactly; age bin is constant
    assert C.step3_trim_reason(p, pd.Series(True, index=p.index)).isna().all()
    p.loc[0, "partial_residual_s"], p.loc[1, "partial_residual_s"] = 5.02, -5.02
    assert C.step3_trim_reason(p, pd.Series(True, index=p.index)).notna().sum() == 2


def test_scored_set_runs_steps_1_to_5_in_order_and_counts_each_drop_once():
    prepared, panel, _, _ = world(seed=8, races_per_season=1, n_drivers=4)
    p25 = panel["race_year"] == 2025
    victim = panel.index[p25 & (panel["lap_number"] == 10)][0]
    panel.loc[victim, "partial_residual_s"] += 30.0
    panel.loc[panel.index[p25 & (panel["lap_number"] == 11)][0], "dirty_air_tax_s"] = np.nan
    s = C.scored_set(panel, prepared, theta_now_point=0.3)
    d = s.drops.set_index(["step", "reason"])["laps"]
    n_drivers_held = panel.loc[p25, ["race_id", "driver_id"]].drop_duplicates().shape[0]
    assert d[("step_1", "lap_1")] == n_drivers_held and d[("step_1", "last_lap")] == n_drivers_held
    assert d[("step_2", "flat_unknown")] == 1 and d[("step_3", C.STEP3_REASON)] == 1
    assert d.sum() + len(s.laps) == int(p25.sum())
    assert (s.laps["race_year"] == 2025).all()
    assert not s.laps["lap_id"].isin([panel.loc[victim, "lap_id"]]).any()


# ---------------------------------------------------------------- measured cost, halves, train laps


def test_lap_design_matches_lap_measured_cost():
    prepared, _, _, _ = world(seed=9, seasons=(2022,), races_per_season=1, held=0, n_drivers=4)
    keys = prepared[E.PASS_KEY].drop_duplicates().reset_index(drop=True).head(40)
    rng = np.random.default_rng(9)
    curve = np.sort(rng.uniform(0, 0.4, (3, E.N_BINS)), axis=1)[:, ::-1]
    lookup = {c: curve[i] for i, c in enumerate(E.CORNER_CLASSES)}
    got = C.lap_design(keys, prepared) @ curve.ravel()
    for i, k in enumerate(keys.itertuples(index=False, name=None)):
        lap = prepared[(prepared[E.PASS_KEY] == pd.Series(k, index=E.PASS_KEY)).all(axis=1)]
        assert got[i] == pytest.approx(E.lap_measured_cost(lap, lookup), abs=1e-12)


def _halves_passes(ref_measured, gaps, nca):
    n = len(gaps)
    return pd.DataFrame({
        "season": 2025, "race_id": "2025_a", "driver": "D0", "lap": 5, "segment_basis": E.BRAKING_BASIS,
        "reason": None, "reason_wc03": [E.NO_CAR_AHEAD if x else None for x in nca],
        "ref_status": ["measured" if m else "no_clean_reference" for m in ref_measured],
        "gap_s": [np.nan if x else g for g, x in zip(gaps, nca)], "corner_id": [str(i) for i in range(n)],
    })


def _lap():
    return pd.DataFrame({"season": [2025], "race_id": ["2025_a"], "driver": ["D0"], "lap": [5], "stint_id": ["s"]})


def test_lap_halves_clean_half_train_and_no_car_ahead_as_3s():
    h = C.lap_halves(_lap(), _halves_passes([True, True, False, False], [0.5, 0.6, 0.7, 0.8], [False] * 4))
    assert h["clean_reference"].iloc[0] and not h["train"].iloc[0]  # 2 of 4 measured: at least half
    h = C.lap_halves(_lap(), _halves_passes([True, False, False, False], [0.5, 0.6, 0.7, 0.8], [False] * 4))
    assert not h["clean_reference"].iloc[0] and h["train"].iloc[0]
    # no_car_ahead corners count as 3 s in the median: 0.5, 0.6, 3, 3 -> median 1.8, not a train lap
    h = C.lap_halves(_lap(), _halves_passes([False] * 4, [0.5, 0.6, 0, 0], [False, False, True, True]))
    assert not h["clean_reference"].iloc[0] and not h["train"].iloc[0]


def test_a4_a_lap_with_only_no_car_ahead_corners_is_clean_reference():
    h = C.lap_halves(_lap(), _halves_passes([False] * 3, [0, 0, 0], [True] * 3))
    assert h["clean_reference"].iloc[0] and not h["train"].iloc[0]


def test_mixed_stint_needs_two_clean_and_two_train_laps():
    laps = pd.DataFrame({"season": 2025, "race_id": "2025_a", "driver": "D0", "lap": [3, 4, 5, 6],
                         "stint_id": "s"})
    parts = []
    for lap, clean in zip([3, 4, 5, 6], [True, True, False, False]):
        p = _halves_passes([clean] * 3, [0.5, 0.5, 0.5], [False] * 3)
        parts.append(p.assign(lap=lap))
    h = C.lap_halves(laps, pd.concat(parts, ignore_index=True))
    assert h["mixed"].all()
    h = C.lap_halves(laps.iloc[:3], pd.concat(parts[:3], ignore_index=True))
    assert not h["mixed"].any()


# ---------------------------------------------------------------- §8b score and the contest bootstrap


def test_score_weighted_equals_copies_with_separate_stints():
    rng = np.random.default_rng(10)
    n = 200
    stint, age = rng.integers(0, 15, n), rng.integers(0, 6, n)
    y = rng.normal(size=n)
    x = {"flat": rng.uniform(0, .3, n), "now": rng.uniform(0, .3, n), "measured": rng.uniform(0, .3, n)}
    w = rng.integers(0, 3, 15).astype(float)[stint]  # constant within a stint, as a race weight gives
    masks = {"all": np.ones(n, bool), "half": np.arange(n) < 100}
    c = np.repeat(np.arange(n), w.astype(int))
    occ = np.concatenate([np.arange(int(k)) for k in w if k > 0])
    a = C.score(y, x, stint, age, masks, w)
    b = C.score(y[c], {k: v[c] for k, v in x.items()}, [f"{s}#{o}" for s, o in zip(stint[c], occ)], age[c],
                {k: m[c] for k, m in masks.items()})
    for s in masks:
        assert a[s]["r_flat"] == pytest.approx(b[s]["r_flat"], abs=1e-10)
        assert a[s]["r_now"] == pytest.approx(b[s]["r_now"], abs=1e-10)


def _fake_laps(n=300, races=6, seed=11):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "race_id": [f"2025_{i % races}" for i in range(n)], "stint_id": [f"2025_{i % races}|s{i % 7}" for i in range(n)],
        "age_bin": rng.integers(0, 6, n), "partial_residual_s": rng.normal(size=n),
        "dirty_air_share_lap": rng.uniform(0, 1, n), "x_flat": rng.uniform(0, 0.3, n),
        "clean_reference": rng.random(n) < 0.5, "train": rng.random(n) < 0.3, "mixed": rng.random(n) < 0.2,
    })


def _fake_plan(n_draws, held):
    return E.resample_plan(["2022_a", "2022_b"], {"2022_a": "A", "2022_b": "B"}, held, n_draws=n_draws)


def test_g1_ii_identical_candidates_give_r_zero_in_the_point_and_every_draw():
    laps = _fake_laps()
    plan = _fake_plan(25, sorted(laps["race_id"].unique()))
    design = np.zeros((len(laps), 3 * E.N_BINS))
    laps["x_flat"] = 0.0
    res = C.run_contest(laps, design, np.zeros((3, E.N_BINS)), np.zeros((25, 3, E.N_BINS)), 0.0,
                        np.zeros(25), plan)
    for s in C.SETS:
        assert res.point[s]["r_flat"] == 0.0 and res.point[s]["r_now"] == 0.0
        assert (res.r_flat_draws[s] == 0.0).all() and (res.r_now_draws[s] == 0.0).all()


def test_contest_draws_rescore_the_drawn_held_out_races():
    laps = _fake_laps()
    held = sorted(laps["race_id"].unique())
    plan = _fake_plan(4, held)
    rng = np.random.default_rng(12)
    design = rng.uniform(0, 0.1, (len(laps), 3 * E.N_BINS))
    curves = rng.uniform(0, 0.3, (4, 3, E.N_BINS))
    thetas = rng.uniform(0.2, 0.5, 4)
    res = C.run_contest(laps, design, curves[0], curves, 0.3, thetas, plan)
    i = 2
    rows = np.concatenate([np.flatnonzero(laps["race_id"] == held[r]) for r in plan.held_idx[i]])
    occ = np.concatenate([np.full((laps["race_id"] == held[r]).sum(), j) for j, r in enumerate(plan.held_idx[i])])
    sub = laps.iloc[rows].reset_index(drop=True)
    x = {"none": np.zeros(len(sub)), "flat": sub["x_flat"].to_numpy(),
         "now": E.flat_now(sub["dirty_air_share_lap"].to_numpy(), thetas[i]),
         "measured": design[rows] @ curves[i].ravel()}
    direct = C.score(sub["partial_residual_s"].to_numpy(), x,
                     (sub["stint_id"] + "#" + pd.Series(occ).astype(str)).to_numpy(), sub["age_bin"].to_numpy(),
                     {"all": np.ones(len(sub), bool)})
    assert res.r_flat_draws["all"][i] == pytest.approx(direct["all"]["r_flat"], abs=1e-10)
    assert res.r_now_draws["all"][i] == pytest.approx(direct["all"]["r_now"], abs=1e-10)


# ---------------------------------------------------------------- W1-W3, G5, G7, verdict


def _res(r_flat_all, r_now_all, train_point, train_draws):
    B = len(r_flat_all)
    point = {s: {"r_flat": 0.01, "r_now": 0.01} for s in C.SETS}
    point[C.SET_TRAIN]["r_flat"] = train_point
    rf = {s: np.full(B, 0.01) for s in C.SETS}
    rn = {s: np.full(B, 0.01) for s in C.SETS}
    rf[C.SET_ALL], rn[C.SET_ALL], rf[C.SET_TRAIN] = np.asarray(r_flat_all), np.asarray(r_now_all), np.asarray(train_draws)
    return C.ContestResult(point=point, r_flat_draws=rf, r_now_draws=rn, theta_point=0.3, theta_draws=np.zeros(B))


def test_w1_needs_both_lower_ends_at_least_half_a_percent():
    good = np.linspace(0.006, 0.02, 1000)
    assert C.w1(_res(good, good, 0.0, good)).passed
    assert not C.w1(_res(good, good - 0.002, 0.0, good)).passed  # beats flat, not flat-now: W1 fails (N5)
    bad = good.copy()
    bad[0] = np.nan
    assert C.w1(_res(bad, good, 0.0, good)).passed is None


def test_w2_point_at_least_zero_and_lower_end_at_least_minus_half_a_percent():
    d = np.linspace(-0.004, 0.01, 1000)
    assert C.w2(_res(d, d, 0.0, d)).passed
    assert not C.w2(_res(d, d, -0.0001, d)).passed
    assert not C.w2(_res(d, d, 0.01, d - 0.01)).passed


def test_p1_and_p2_rules():
    pt = np.tile(TRUE_CURVE, (3, 1))
    draws = pt[None] + np.random.default_rng(13).normal(0, 0.005, (200, 3, E.N_BINS))
    assert C.p1(pt, draws).passed
    bad = pt.copy()
    bad[1, 6:] = -0.05  # far band below zero by more than 25 % of near
    assert not C.p1(bad, draws).passed
    assert C.p2(pt, draws).passed  # fast = slow: interval straddles 0
    rev = draws.copy()
    rev[:, 2, 2:4] -= 0.1  # fast clearly below slow
    assert not C.p2(pt, rev).passed


def _curve_table(status_by_class):
    rows = []
    for cls in E.CORNER_CLASSES:
        st = status_by_class.get(cls, E.CURVE_OK)
        for b in range(E.N_BINS):
            rows.append({"corner_class": cls, "bin": b, "status": st,
                         "point_empty_bins": "" if st == E.CURVE_OK else "5",
                         "empty_bin_draws": 0 if st == E.CURVE_OK else 1000, "n_draws": 1000})
    return pd.DataFrame(rows)


def test_a4_g7_main_curve_any_class_and_dirty_air_fast_or_slow():
    ok = _curve_table({})
    assert C.g7_curve_identified(ok, ok).passed
    assert not C.g7_curve_identified(_curve_table({"medium": E.CURVE_NO_VERDICT}), ok).passed
    assert C.g7_curve_identified(ok, _curve_table({"medium": E.CURVE_NOT_ESTIMABLE})).passed
    assert not C.g7_curve_identified(ok, _curve_table({"fast": E.CURVE_NOT_ESTIMABLE})).passed
    assert not C.g7_curve_identified(ok, _curve_table({"slow": E.CURVE_NOT_ESTIMABLE})).passed


def test_verdict_table_is_read_top_to_bottom():
    t, f, u = C.Check("x", True, "", ""), C.Check("x", False, "", ""), C.Check("x", None, "", "", "why")
    assert C.verdict([t], t, t, t)[0] == C.REPLACE
    assert C.verdict([t], t, f, t)[0] == C.KEEP_AND_SHOW
    assert C.verdict([t], f, t, t)[0] == C.KEEP_AND_STOP
    assert C.verdict([t], f, f, f)[0] == C.KEEP_AND_STOP
    assert C.verdict([t], t, t, f)[0] == C.KEEP_AND_STOP
    assert C.verdict([t], t, f, f)[0] == C.KEEP_AND_STOP
    assert C.verdict([f], t, t, t)[0] == C.NO_VERDICT
    assert C.verdict([t], t, u, t)[0] == C.NO_VERDICT
    assert C.verdict([t], None, None, None)[0] == C.NO_VERDICT


def test_g5_minimums():
    n = 2400
    laps = pd.DataFrame({"race_id": [f"r{i % 24}" for i in range(n)], "clean_reference": (np.arange(n) // 24) % 2 == 0,
                         "train": (np.arange(n) // 24) % 2 == 1, "mixed": False})
    assert C.g5_minimums(None, laps, 68, 24).passed
    assert not C.g5_minimums(None, laps, 59, 24).passed
    assert not C.g5_minimums(None, laps, 68, 19).passed
    laps["train"] = False
    assert not C.g5_minimums(None, laps, 68, 24).passed


# ---------------------------------------------------------------- the whole chain, end to end


def test_run_era_end_to_end_on_synthetic_data():
    prepared, panel, _, _ = world(seed=14, races_per_season=3, n_drivers=6)
    held = sorted(panel.loc[panel["race_year"] == 2025, "race_id"].unique())
    res = C.run_era(prepared, panel, held, n_draws=8)
    assert res.contest is not None and res.scored is not None
    assert (res.main_table["status"] == E.CURVE_OK).all()
    # the panel's residual carries the true measured cost: measured beats the flat penalty and flat-now
    assert res.contest.point[C.SET_ALL]["r_flat"] > 0.1 and res.contest.point[C.SET_ALL]["r_now"] > 0.0
    assert len(res.contest.theta_draws) == 8 and np.isfinite(res.contest.theta_draws).all()
    # tiny synthetic world: G5 minimums are short, so the verdict is no verdict, and it says why
    assert res.verdict_code == C.NO_VERDICT and "G5" in res.verdict_line
    text = C.scorecard(res)
    assert text.splitlines()[0] == res.verdict_line and text.splitlines()[2] == C.WITHIN_STINT_LINE
    assert "0.0000 (" not in text


def test_run_era_stops_at_g7_before_the_contest():
    prepared, panel, _, _ = world(seed=15, races_per_season=2, n_drivers=4)
    prepared = prepared[~((prepared["corner_class"] == "fast") & (prepared["gap_bin"] == 7))]
    held = sorted(panel.loc[panel["race_year"] == 2025, "race_id"].unique())
    res = C.run_era(prepared, panel, held, n_draws=3)
    assert res.contest is None and res.verdict_code == C.NO_VERDICT and "G7" in res.verdict_line


def test_unavailable_is_a_dash_with_a_reason_never_zero():
    assert C.fmt(np.nan, reason="no laps") == "— (no laps)"
    assert C.UNAVAILABLE == "—"
    assert C.DD_WC2_DISCLAIMER == ("Normalised from other compounds, based on stints from other drivers or the "
                                   "general performance of the tyres after removing other factors.")


def test_g1_viii_timing_of_the_theta_now_refit_and_rescoring_per_draw():
    """G1 (viii), the part test_estimator's timing leaves out: one draw's θ_now refit (about 51,000 panel laps,
    the 2022-2024 share of 135,841) and 2025 rescoring (about 17,000 laps, 4 candidates, 5 sets)."""
    import time
    rng = np.random.default_rng(22)
    n_fit, n_held = 51_000, 17_000
    fit = pd.DataFrame({"race_id": [f"r{i % 68}" for i in range(n_fit)],
                        "stint_id": [f"r{i % 68}|s{i % 1400}" for i in range(n_fit)],
                        "age_bin": rng.integers(0, 6, n_fit), "dirty_air_share_lap": rng.uniform(0, 1, n_fit),
                        "partial_residual_s": rng.normal(size=n_fit)})
    w = rng.integers(0, 3, 68).astype(float)[pd.factorize(fit["race_id"])[0]]
    laps = _fake_laps(n=n_held, races=24, seed=23)
    laps["stint_id"] = laps["race_id"] + "|" + pd.Series(np.arange(n_held) % 30).astype(str)
    design = rng.uniform(0, 0.05, (n_held, 3 * E.N_BINS))
    hw = rng.integers(0, 3, 24).astype(float)[pd.factorize(laps["race_id"])[0]]
    masks = C.set_masks(laps)
    t0 = time.perf_counter()
    th = C.theta_now_weighted(fit, w)
    x = {"none": np.zeros(n_held), "flat": laps["x_flat"].to_numpy(),
         "now": E.flat_now(laps["dirty_air_share_lap"].to_numpy(), th),
         "measured": design @ np.tile(TRUE_CURVE, (3, 1)).ravel()}
    C.score(laps["partial_residual_s"].to_numpy(), x, laps["stint_id"].to_numpy(), laps["age_bin"].to_numpy(),
            masks, hw)
    secs = time.perf_counter() - t0
    print(f"G1(viii): θ_now refit + 2025 rescoring, one draw {secs:.3f} s; x {E.N_BOOT} ~ {secs * E.N_BOOT / 60:.1f} min")
    assert secs < 30.0
