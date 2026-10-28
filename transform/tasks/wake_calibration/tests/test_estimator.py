"""Synthetic tests for the WC-03 estimator, including gate G1 (pre-registration §12a). No bronze data, no
warehouse and no pass table on disk is read: every input is generated here.

G1 parts, as numbered in §12a:
  (i)    recovery and interval coverage            test_g1_i_*
  (ii)   R = 0 for identical candidates            test_g1_ii_*
  (iii)  lap-total weights                         test_g1_iii_*
  (iv)   pit-stop event builder                    test_g1_iv_*
  (v)    no held-out row in any fit                test_g1_v_*
  (vi)   class rule, exactly one class             test_g1_vi_*
  (vii)  NULL flat or same-lap share -> unscored   test_g1_vii_*
  (viii) timing of one full draw                   test_g1_viii_*
"""

import time

import numpy as np
import pandas as pd
import pytest

from tasks.wake_calibration import build_pass_table as bpt
from tasks.wake_calibration import estimator as E

TRUE_CURVE = np.array([0.30, 0.22, 0.16, 0.11, 0.07, 0.04, 0.02, 0.01])  # non-increasing, one value per bin


# ---------------------------------------------------------------- synthetic pass table


def _race_passes(season: int, race: str, rng, n_drivers=8, laps=range(2, 26), n_corners=6, curve=TRUE_CURVE,
                 classes=("slow", "medium", "fast"), noise=0.05) -> pd.DataFrame:
    """One race of pass rows in the builder's columns. Corner k (1..n) is braking; corner n+1 is flat-out.
    Each driver follows a random car at a random gap or runs in clear air; the corner loss is curve(gap)."""
    rows = []
    drivers = [f"D{i}" for i in range(n_drivers)]
    base = {c: 3.0 + 0.4 * c for c in range(1, n_corners + 2)}
    for lap in laps:
        for d in drivers:
            for c in range(1, n_corners + 2):
                braking = c <= n_corners
                clear = rng.random() < 0.35
                gap = np.nan if clear else float(rng.uniform(0.0, 4.5))
                leader = None if clear else str(rng.choice([x for x in drivers if x != d]))
                cls = classes[(c - 1) % len(classes)]
                loss = curve[E.gap_bin(np.array([gap]))[0]] if (np.isfinite(gap) and gap < 3.0) else 0.0
                t0 = 1000.0 + 90.0 * lap + 12.0 * c
                seg = base[c] + loss + rng.normal(0.0, noise)
                rows.append({
                    "season": season, "race_id": f"{season}_{race}", "race": race, "driver": d, "lap": lap,
                    "stint": 1.0 if lap < 14 else 2.0, "compound": "MEDIUM" if lap < 14 else "HARD",
                    "corner_id": str(c), "corner_number": c, "corner_class": cls,
                    "segment_basis": "brake_onset" if braking else "fixed_before_apex",
                    "seg_start_t": t0, "seg_end_t": t0 + seg, "seg_time_s": seg,
                    "leader": leader, "leader_lap": np.nan if clear else float(lap), "gap_s": gap,
                    "clear_ahead": clear, "behind_1s": bool(rng.random() < 0.1), "tag": None, "reason": None,
                })
    frame = pd.DataFrame(rows)
    return bpt.references(frame)


def _calendar(races: list[tuple[int, str]], circuit_of=None) -> dict:
    circuit_of = circuit_of or (lambda s, r: r.upper())
    return {(s, r): (circuit_of(s, r), pd.Timestamp(f"{s}-06-01")) for s, r in races}


def _prepared(races: list[tuple[int, str]], seed=0, **kw) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frame = pd.concat([_race_passes(s, r, rng, **kw) for s, r in races], ignore_index=True)
    return E.prepare_passes(frame, _calendar(races))


def _plan(fit: pd.DataFrame, n_draws: int, held=("2025_x",), seed: int = E.SEED,
          method: str = E.BOOTSTRAP_ADOPTED) -> E.BootstrapPlan:
    """The bootstrap plan over the fit set's races; adopted method (circuit then race, amendment A1) unless
    the race-level comparison is asked for."""
    races = sorted(fit["race_key"].unique())
    return E.resample_plan(races, E.race_circuits(fit), list(held), n_draws=n_draws, seed=seed, method=method)


# ---------------------------------------------------------------- per-pass measures


def test_no_car_ahead_reason_only_where_the_builder_left_none():
    t = pd.DataFrame({"reason": [None, None, "pit_lap", None], "clear_ahead": [True, False, True, True]})
    assert E.wc03_reason(t).tolist() == ["no_car_ahead", None, None, "no_car_ahead"]


def test_circuit_of_uses_the_calendar_and_refuses_unknown_races():
    t = pd.DataFrame({"season": [2022, 2023], "race": ["monaco_grand_prix", "sakhir_grand_prix"]})
    cal = {(2022, "monaco_grand_prix"): ("Monaco", None), (2023, "sakhir_grand_prix"): ("Sakhir (outer)", None)}
    assert E.circuit_of(t, cal).tolist() == ["Monaco", "Sakhir (outer)"]
    with pytest.raises(E.EstimatorError):
        E.circuit_of(t, {(2022, "monaco_grand_prix"): ("Monaco", None)})


def _spread_table() -> pd.DataFrame:
    rows = []
    for lap, seg in zip(range(10, 19), [10.0, 10.2, 10.1, 10.9, 10.3, 10.0, 10.4, 10.2, 12.0]):
        rows.append(dict(season=2023, race_id="2023_1", driver="A", corner_id="3", stint=1.0, compound="SOFT",
                         lap=lap, seg_time_s=seg, reason=None, tag=None, clear_ahead=True, gap_s=np.nan,
                         behind_1s=False))
    return bpt.references(pd.DataFrame(rows))


def test_reference_spread_is_the_mad_of_the_builders_donors():
    t = _spread_table()
    spread = E.reference_spread(t)
    row = t.index[t["lap"] == 14][0]
    donors = t.loc[(t["lap"] - 14).abs().between(1, 4), "seg_time_s"].to_numpy()  # laps 10-13 and 15-18
    med = np.median(donors)
    assert t.loc[row, "ref_time_s"] == pytest.approx(med)
    assert spread[row] == pytest.approx(np.median(np.abs(donors - med)))


def test_reference_spread_floor_and_undefined_without_a_measured_reference():
    t = _spread_table()
    t["seg_time_s"] = 10.0
    t = bpt.references(t.drop(columns=["clean", "ref_n", "ref_time_s", "ref_status", "delta_time_s"]))
    t.loc[t["lap"] == 12, ["ref_status", "ref_time_s"]] = ["no_clean_reference", np.nan]
    spread = E.reference_spread(t)
    assert (spread[t["lap"] != 12] == E.SPREAD_FLOOR_S).all()
    assert np.isnan(spread[t["lap"] == 12]).all()


def test_reference_spread_refuses_a_reference_it_cannot_reproduce():
    t = _spread_table()
    t.loc[t["lap"] == 14, "ref_time_s"] += 0.5
    with pytest.raises(E.EstimatorError):
        E.reference_spread(t)


def test_leader_time_is_the_car_aheads_own_segment_on_its_lap():
    t = pd.DataFrame({
        "season": 2024, "race_id": "2024_5", "driver": ["A", "B", "B", "C"], "lap": [10, 10, 9, 10],
        "corner_id": "4", "seg_time_s": [5.0, 5.5, 6.5, 7.0],
        "leader": ["B", None, "A", "Z"], "leader_lap": [9.0, np.nan, 9.0, 10.0],
    })
    out = E.leader_time(t)
    assert out[0] == 6.5  # B on lap 9
    assert np.isnan(out[1]) and np.isnan(out[2]) and np.isnan(out[3])  # no leader / A has no lap 9 / Z unknown


def _rc_table(leaders_by_lap: dict[int, list], gaps=None) -> pd.DataFrame:
    rows = []
    for lap, leaders in leaders_by_lap.items():
        for c, lead in enumerate(leaders, start=1):
            rows.append(dict(season=2023, race_id="2023_1", driver="F", lap=lap, corner_id=str(c), corner_number=c,
                             segment_basis="brake_onset", leader=lead, gap_s=1.0))
    t = pd.DataFrame(rows)
    if gaps:
        for (lap, c), g in gaps.items():
            t.loc[(t["lap"] == lap) & (t["corner_number"] == c), "gap_s"] = g
    return t


def test_racecraft_leader_change_within_three_braking_corners_across_the_line():
    # 8 braking corners per lap. On lap 11 the car ahead changes from A to B at corner 2.
    t = _rc_table({10: ["A"] * 8, 11: ["A", "B", "B", "B", "B", "B", "B", "B"], 12: ["B"] * 8})
    rc = E.racecraft(t).to_numpy().reshape(3, 8)
    # Corner 1 of lap 11 (A) and lap-11 corners 2-4 (B, within 3 of the A at lap-11 c1) flag; lap 10 c6-c8 are
    # within 3 corners of lap-11 c2 (B) across the line: c6 is 4 away (no), c7 is 3 away (yes), c8 is 2 away (yes).
    assert rc[1].tolist() == [True, True, True, True, False, False, False, False]
    assert rc[0].tolist() == [False] * 6 + [True, True]
    assert not rc[2].any()


def test_racecraft_negative_gap_and_missing_leader_is_not_a_change():
    t = _rc_table({10: ["A", None, "A", "A", "A", "A"]}, gaps={(10, 5): -0.2})
    assert E.racecraft(t).tolist() == [False, False, False, False, True, False]


def test_gap_bins_are_lower_inclusive_upper_exclusive():
    gaps = np.array([0.0, 0.2999, 0.3, 0.75, 1.0, 2.9999, 3.0, -0.1, np.nan])
    assert E.gap_bin(gaps).tolist() == [0, 0, 1, 3, 4, 7, -1, -1, -1]
    assert E.GAP_EDGES.tolist() == [0.0, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]


# ---------------------------------------------------------------- G1 (vi): one class per following pass


def test_g1_vi_every_following_pass_gets_exactly_one_class():
    p = _prepared([(2023, "a_gp"), (2023, "b_gp")], seed=3)
    gap = p["gap_s"].to_numpy(dtype=float)
    following = (p["segment_basis"] == "brake_onset") & np.isfinite(gap) & (gap < 3.0)
    with_ref = following & (p["ref_status"] == "measured")
    assert with_ref.sum() > 500 and (following & ~with_ref).sum() > 50
    member = np.column_stack([(p["pass_class"] == c).to_numpy() for c in E.PASS_CLASSES])
    assert (member[following.to_numpy()].sum(1) == 1).all()  # with or without a reference (§5)
    assert p.loc[~following, "pass_class"].isna().all()  # not following: no class
    assert {E.RACECRAFT, E.HELD_UP, E.DIRTY_AIR} <= set(p.loc[with_ref, "pass_class"])
    assert E.NO_REFERENCE in set(p.loc[following & ~with_ref, "pass_class"])
    assert E.NO_REFERENCE not in set(p.loc[with_ref, "pass_class"])


def test_g1_vi_class_priority_and_the_held_up_boundary():
    base = dict(segment_basis="brake_onset", gap_s=1.0, racecraft=False, leader_time_s=10.0, ref_time_s=9.0,
                ref_spread_s=0.5)
    cases = [
        ({}, E.DIRTY_AIR),  # 10.0 == 9.0 + 2 x 0.5: not slower -> dirty air (N3 closes the gap)
        ({"leader_time_s": 10.0001}, E.HELD_UP),
        ({"leader_time_s": 8.0}, E.DIRTY_AIR),
        ({"leader_time_s": np.nan}, E.NO_LEADER_TIME),
        ({"racecraft": True, "leader_time_s": np.nan}, E.RACECRAFT),  # racecraft first
        ({"racecraft": True, "leader_time_s": 12.0}, E.RACECRAFT),
        ({"gap_s": -0.3, "racecraft": True}, E.RACECRAFT),
        ({"gap_s": 3.0}, None),  # not following
        ({"segment_basis": "fixed_before_apex"}, None),
    ]
    t = pd.DataFrame([{**base, **c} for c, _ in cases])
    assert E.pass_class(t).tolist() == [want for _, want in cases]


def test_g1_vi_a_following_pass_without_a_reference_is_no_reference():
    # Review item Q5: an explicit report-only class, after racecraft and no_leader_time in the order.
    base = dict(segment_basis="brake_onset", gap_s=1.0, racecraft=False, leader_time_s=10.0,
                ref_time_s=np.nan, ref_spread_s=np.nan)
    t = pd.DataFrame([base, {**base, "racecraft": True}, {**base, "leader_time_s": np.nan},
                      {**base, "ref_time_s": 9.0}])  # reference but no spread: still no_reference
    assert E.pass_class(t).tolist() == [E.NO_REFERENCE, E.RACECRAFT, E.NO_LEADER_TIME, E.NO_REFERENCE]


def test_no_reference_passes_never_enter_a_fit():
    p = _prepared([(2023, "a_gp"), (2023, "b_gp")], seed=3)
    assert (p["pass_class"] == E.NO_REFERENCE).any()
    assert not (E.fit_passes(p)["pass_class"] == E.NO_REFERENCE).any()


# ---------------------------------------------------------------- amendment A2: the fifth class, no_reference


def test_a2_five_classes_in_the_amended_order():
    assert E.PASS_CLASSES == ("racecraft", "no_leader_time", "no_reference", "held_up", "dirty_air")


def test_a2_no_reference_is_checked_before_held_up_and_dirty_air():
    # A car ahead far slower (would be held_up) or faster (would be dirty_air) than any reference: without
    # a measured reference the pass is no_reference either way.
    base = dict(segment_basis="brake_onset", gap_s=1.0, racecraft=False, ref_time_s=np.nan, ref_spread_s=np.nan)
    t = pd.DataFrame([{**base, "leader_time_s": 99.0}, {**base, "leader_time_s": 0.1},
                      {**base, "leader_time_s": 99.0, "ref_spread_s": 0.5}])  # spread but no ref time
    assert E.pass_class(t).tolist() == [E.NO_REFERENCE] * 3


def test_a2_no_reference_is_exactly_the_unmeasured_passes_past_steps_1_and_2():
    # (3) fires iff ref_status != measured, for a following pass that is not racecraft and has a leader
    # time; a pass with a measured reference keeps held_up or dirty_air (no registered class is moved).
    p = _prepared([(2023, "a_gp"), (2023, "b_gp")], seed=3)
    reach3 = p["pass_class"].notna() & ~p["racecraft"] & np.isfinite(p["leader_time_s"].to_numpy(dtype=float))
    measured = p["ref_status"] == "measured"
    assert ((p["pass_class"] == E.NO_REFERENCE) == (reach3 & ~measured)).all()
    assert p.loc[reach3 & measured, "pass_class"].isin([E.HELD_UP, E.DIRTY_AIR]).all()
    assert (reach3 & ~measured).sum() > 0 and (reach3 & measured).sum() > 0


def test_a2_no_reference_is_in_no_section_6_fit_set_main_or_class_curve():
    p = _prepared([(2023, "a_gp"), (2023, "b_gp")], seed=3)
    fit = E.fit_passes(p)
    assert (p["pass_class"] == E.NO_REFERENCE).any()
    for subset in (fit, fit[fit["pass_class"] == E.HELD_UP], fit[fit["pass_class"] == E.DIRTY_AIR]):
        assert not (subset["pass_class"] == E.NO_REFERENCE).any()
        assert (subset["ref_status"] == "measured").all()


def test_a2_no_reference_counts_per_season_and_corner_class():
    p = _prepared([(2023, "a_gp"), (2024, "b_gp")], seed=3)
    c = E.no_reference_counts(p)
    assert set(map(tuple, c[["season", "corner_class"]].to_numpy())) == {
        (s, k) for s in (2023, 2024) for k in E.CORNER_CLASSES}
    for _, row in c.iterrows():
        g = p[(p["season"] == row["season"]) & (p["corner_class"] == row["corner_class"])]
        assert row["following_braking_passes"] == g["pass_class"].notna().sum()
        assert row["no_reference_passes"] == (g["pass_class"] == E.NO_REFERENCE).sum()
    assert c["no_reference_passes"].sum() == (p["pass_class"] == E.NO_REFERENCE).sum()
    assert np.allclose(c["no_reference_share"], c["no_reference_passes"] / c["following_braking_passes"])


# ---------------------------------------------------------------- fit set and G1 (v): no held-out row in a fit


def test_fit_passes_apply_every_section_6_filter():
    p = _prepared([(2022, "a_gp"), (2025, "z_gp")], seed=1)
    p.loc[p.index[:40], "tag"] = "yielding"
    p["yielding"] = E.is_yielding(p["tag"])
    p.loc[p.index[40:80], "delta_time_s"] = 2.5
    fit = E.fit_passes(p, "main")
    assert set(fit["season"]) == {2022}
    assert (fit["segment_basis"] == "brake_onset").all() and fit["reason"].isna().all()
    assert fit["reason_wc03"].isna().all() and (fit["ref_status"] == "measured").all()
    assert not fit["yielding"].any() and (fit["delta_time_s"].abs() <= 2.0).all()
    assert fit["gap_s"].between(0.0, 3.0, inclusive="left").all()
    assert not set(p.index[:80]) & set(fit.index)


def test_g1_v_no_held_out_row_reaches_a_fit():
    p = _prepared([(2022, "a_gp"), (2025, "z_gp"), (2021, "y_gp"), (2019, "x_gp")], seed=2)
    assert set(E.fit_passes(p, "main")["season"]) == {2022}
    assert set(E.fit_passes(p, "older")["season"]) == {2019}
    with pytest.raises(E.LeakageError):
        E.assert_no_leak(p[p["season"].isin([2022, 2025])], "main")
    with pytest.raises(E.LeakageError):
        E.assert_no_leak(p[p["season"].isin([2019, 2021])], "older")
    with pytest.raises(E.LeakageError):
        E.assert_no_leak(p[p["season"] == 2019], "main")  # an older season in the main fit
    with pytest.raises(E.LeakageError):
        E.resample_plan(["2022_a", "2025_z"], {"2022_a": "A", "2025_z": "Z"}, ["2025_z"], n_draws=2)


def test_g1_v_theta_now_ignores_held_out_laps():
    panel = _panel(np.random.default_rng(4), theta=0.4)
    theta = E.fit_theta_now(panel)
    poisoned = panel.copy()
    held = poisoned["race_year"] == 2025
    poisoned.loc[held, "partial_residual_s"] = poisoned.loc[held, "dirty_air_share_lap"] * 50.0
    assert E.fit_theta_now(poisoned) == theta


def test_g1_v_curve_ignores_held_out_passes():
    races = [(2022, "a_gp"), (2023, "b_gp"), (2024, "c_gp"), (2025, "z_gp")]
    p = _prepared(races, seed=5)
    fit_races = sorted(p.loc[p["season"] < 2025, "race_key"].unique())
    before = E.fit_curves(E.fit_passes(p), fit_races)
    p.loc[p["season"] == 2025, "delta_time_s"] = 1.9
    after = E.fit_curves(E.fit_passes(p), fit_races)
    pd.testing.assert_frame_equal(before, after)


# ---------------------------------------------------------------- the REML curve


def _sim_passes(rng, curve=TRUE_CURVE, n_races=68, n_circuits=23, n_corners=8, per_cell=30,
                sd_circuit=0.0, sd_corner=0.0, sd_race=0.03, sd_noise=0.15) -> pd.DataFrame:
    """Fit passes for one corner class drawn from the registered model (§6) plus a race shock: loss = curve(bin)
    + circuit effect + corner effect + race shock + noise. Race r runs at circuit r mod n_circuits, so with 23
    circuits each circuit hosts about 3 races, as 2022-2024 does."""
    race = np.repeat(np.arange(n_races), n_corners * per_cell)
    circuit = race % n_circuits
    corner = circuit * n_corners + np.tile(np.repeat(np.arange(n_corners), per_cell), n_races)
    a = rng.normal(0.0, sd_circuit, n_circuits)
    b = rng.normal(0.0, sd_corner, n_circuits * n_corners)
    u = rng.normal(0.0, sd_race, n_races)
    b_idx = E.gap_bin(rng.uniform(0.0, 3.0, len(race)))
    y = curve[b_idx] + a[circuit] + b[corner] + u[race] + rng.normal(0.0, sd_noise, len(race))
    return pd.DataFrame({"race_key": [f"r{r:02d}" for r in race], "circuit": [f"c{c:02d}" for c in circuit],
                         "corner_key": [f"k{k:03d}" for k in corner], "gap_bin": b_idx, "delta_time_s": y,
                         "corner_class": "medium"})


def test_reml_matches_statsmodels_mixedlm():
    sm = pytest.importorskip("statsmodels.formula.api")
    df = _sim_passes(np.random.default_rng(11), n_races=16, n_circuits=8, n_corners=4, per_cell=40,
                     sd_circuit=0.08, sd_corner=0.05, sd_race=0.0)
    fit = E.reml_fit(*E.draw_stats(E.corner_stats(df)))
    df["bin"] = df["gap_bin"].astype(str)
    ref = sm.mixedlm("delta_time_s ~ 0 + C(bin)", df, groups="circuit", re_formula="1",
                     vc_formula={"corner": "0 + C(corner_key)"}).fit(reml=True)
    assert np.abs(ref.fe_params.to_numpy() - fit.beta).max() < 1e-6
    assert np.abs(ref.bse_fe.to_numpy() - np.sqrt(fit.var_beta)).max() < 1e-5
    assert fit.sigma2 == pytest.approx(ref.scale, rel=1e-5)
    assert fit.var_corner == pytest.approx(float(ref.vcomp[0]), rel=1e-3)


def test_reml_refuses_an_empty_bin():
    df = _sim_passes(np.random.default_rng(1), n_races=4, n_circuits=2, n_corners=2, per_cell=50)
    df = df[df["gap_bin"] != 5]
    with pytest.raises(E.EmptyBinError):
        E.reml_fit(*E.draw_stats(E.corner_stats(df)))


def test_pava_is_non_increasing_weighted_and_leaves_a_monotone_input_alone():
    y = np.array([0.3, 0.2, 0.25, 0.1, 0.12, 0.0, 0.01, -0.02])
    w = np.array([1.0, 1.0, 3.0, 1.0, 1.0, 2.0, 2.0, 1.0])
    out = E.pava_nonincreasing(y, w)
    assert (np.diff(out) <= 1e-15).all()
    assert out[1] == out[2] == pytest.approx((0.2 * 1 + 0.25 * 3) / 4)
    assert out[5] == out[6] == pytest.approx(0.005)
    assert np.array_equal(E.pava_nonincreasing(TRUE_CURVE, np.ones(8)), TRUE_CURVE)
    with pytest.raises(E.EstimatorError):
        E.pava_nonincreasing(y, np.zeros(8))


def test_g1_i_recovers_a_known_non_increasing_curve_end_to_end():
    races = [(s, f"r{i}_gp") for s in (2022, 2023, 2024) for i in range(6)]
    p = _prepared(races, seed=8, noise=0.03)
    fit = E.fit_passes(p)
    table = E.fit_curves(fit, sorted(fit["race_key"].unique()))
    for cls, g in table.groupby("corner_class"):
        est = g.sort_values("bin")["estimate_s"].to_numpy()
        assert (np.diff(est) <= 1e-12).all()
        assert np.abs(est - TRUE_CURVE).max() < 0.02, cls


def _coverage(design: dict, method: str = E.BOOTSTRAP_ADOPTED, n_sims: int = 200, n_draws: int = 200,
              seed: int = 0) -> np.ndarray:
    """Share of simulations whose 95 % percentile interval (whole chain refit per draw, REML then PAVA)
    covers the true value, per bin. The bootstrap is the adopted circuit-then-race resample (amendment A1)
    unless `method` asks for the race-level comparison.

    CLARIFICATION (§12a G1 i), pending owner confirmation: "its 95 % intervals cover the true values in at
    least 90 % of 200 simulations" is read per bin, so every one of the 8 bins must reach 0.90 on its own;
    a pooled share over all bins could pass with one bin badly under-covered. The registration does not say
    per bin or pooled. The simulation design (the variance components and races per circuit passed in
    `design`) is not fixed by the registration either."""
    rng = np.random.default_rng(seed)
    hits = np.zeros(E.N_BINS)
    for s in range(n_sims):
        df = _sim_passes(rng, **design)
        plan = _plan(df, n_draws, held=("held_out",), seed=seed + s, method=method)
        draws = E.bootstrap_curves(df, plan, classes=("medium",))[:, 0]
        lo, hi = E.percentile_interval(draws)
        hits += (lo <= TRUE_CURVE) & (TRUE_CURVE <= hi)
    return hits / n_sims


def test_g1_i_interval_coverage_race_shocks_only():
    """200 simulations x 200 draws (§12a G1 i), adopted circuit-then-race bootstrap. Design: no circuit or
    corner effect; a race shock and noise."""
    cover = _coverage({"sd_circuit": 0.0, "sd_corner": 0.0, "sd_race": 0.03})
    print("G1(i) coverage, race shocks only, adopted circuit-then-race bootstrap, per bin:",
          np.round(cover, 3).tolist(), "hits of 200:", np.round(cover * 200).astype(int).tolist())
    assert (cover >= 0.90).all(), cover


def test_g1_i_interval_coverage_registered_model():
    """200 simulations x 200 draws (§12a G1 i), adopted circuit-then-race bootstrap (amendment A1). Design:
    the registered model's own circuit and corner random effects, and a race shock; about 3 races per circuit,
    as in 2022-2024. The simulation is the registered model, unchanged; the 90 % bar is unchanged.

    History: under the registered race-level resample (now the comparison only) this design gave 0.595-0.645
    per bin and failed (2026-10-28/29); that failure is why amendment A1 exists."""
    cover = _coverage({"sd_circuit": 0.05, "sd_corner": 0.05, "sd_race": 0.03})
    print("G1(i) coverage, registered model, adopted circuit-then-race bootstrap, per bin:",
          np.round(cover, 3).tolist(), "hits of 200:", np.round(cover * 200).astype(int).tolist())
    assert (cover >= 0.90).all(), cover


def test_the_adopted_bootstrap_is_circuit_then_race():
    assert E.BOOTSTRAP_ADOPTED == "circuit" and E.BOOTSTRAP_COMPARISON == "race"
    plan = E.resample_plan(["a", "b"], {"a": "X", "b": "Y"}, ["z"], n_draws=2)
    assert plan.method == E.BOOTSTRAP_ADOPTED
    with pytest.raises(E.EstimatorError):
        E.resample_plan(["a"], {"a": "X"}, ["z"], n_draws=2, method="stint")
    with pytest.raises(E.EstimatorError):
        E.resample_plan(["a", "b"], {"a": "X"}, ["z"], n_draws=2)  # a fit race with no circuit


def test_resample_plan_is_fixed_by_the_seed_and_sorted_race_lists():
    circ = {"a": "X", "b": "X", "c": "Y"}  # circuit X hosts races a and b, circuit Y hosts c
    a = E.resample_plan(["b", "a", "c"], circ, ["y", "x"], n_draws=5)
    b = E.resample_plan(["c", "a", "b"], circ, ["x", "y"], n_draws=5)
    assert a.fit_races == ["a", "b", "c"] and a.circuits == ["X", "Y"] and a.race_circuit.tolist() == [0, 0, 1]
    assert all(np.array_equal(p[0], q[0]) and np.array_equal(p[1], q[1]) for p, q in zip(a.fit_draws, b.fit_draws))
    assert np.array_equal(a.held_idx, b.held_idx) and a.n_draws == 5
    # Draw order (adopted): circuits, then each picked circuit's races in pick order, then held-out races.
    rng = np.random.default_rng(E.SEED)
    races_of = {0: np.array([0, 1]), 1: np.array([2])}
    want_r, want_g = [], []
    for j, c in enumerate(rng.integers(0, 2, 2)):
        own = races_of[int(c)]
        want_r.append(own[rng.integers(0, len(own), len(own))])
        want_g.append(np.full(len(own), j))
    assert np.array_equal(a.fit_draws[0][0], np.concatenate(want_r))
    assert np.array_equal(a.fit_draws[0][1], np.concatenate(want_g))
    assert np.array_equal(a.held_idx[0], rng.integers(0, 2, 2))
    # The race-level comparison: one race draw per draw, each race in its own circuit's group.
    r = E.resample_plan(["b", "a", "c"], circ, ["y", "x"], n_draws=5, method=E.BOOTSTRAP_COMPARISON)
    rng = np.random.default_rng(E.SEED)
    first = rng.integers(0, 3, 3)
    assert np.array_equal(r.fit_draws[0][0], first)
    assert np.array_equal(r.fit_draws[0][1], np.array([0, 0, 1])[first])  # each race's own circuit
    assert np.array_equal(r.held_idx[0], rng.integers(0, 2, 2))
    assert E.N_BOOT == 1000 and E.SEED == 20261027 and E.CI_PERCENTILES == (2.5, 97.5)


def _relabelled(df: pd.DataFrame, races: list[str], draw: list[tuple[str, int]]) -> pd.DataFrame:
    """The passes of a draw written out by hand: each (race, copy) appended, its circuit and corners renamed
    by copy so that copies are distinct random-effect groups."""
    parts = []
    for race, copy in draw:
        p = df[df["race_key"] == race].copy()
        p["circuit"] = p["circuit"] + f"#{copy}"
        p["corner_key"] = p["corner_key"] + f"#{copy}"
        parts.append(p)
    return pd.concat(parts, ignore_index=True)


def _one_draw_plan(base: E.BootstrapPlan, races: list[int], groups: list[int]) -> E.BootstrapPlan:
    import dataclasses
    return dataclasses.replace(base, fit_draws=((np.array(races), np.array(groups)),), held_idx=base.held_idx[:1])


def test_a_circuit_drawn_twice_is_two_circuit_and_corner_groups():
    df = _sim_passes(np.random.default_rng(2), n_races=6, n_circuits=3, n_corners=3, per_cell=40,
                     sd_circuit=0.05, sd_corner=0.05)
    races = sorted(df["race_key"].unique())  # r00 and r03 are at circuit c00
    base = _plan(df, 1)
    stats = E.corner_stats(df, races)
    # Circuit c00 drawn twice (copies 0 and 1), each copy drawing r00 and r03; copy 2 is c01 with r01 twice.
    plan = _one_draw_plan(base, [0, 3, 0, 3, 1, 1], [0, 0, 1, 1, 2, 2])
    count, total, sq, circuit = E.plan_draw_stats(stats, plan, 0)
    assert len(count) == 9 and len(set(circuit.tolist())) == 3  # 3 copies x 3 corners, 3 circuit groups
    by_hand = _relabelled(df, races, [("r00", 0), ("r03", 0), ("r00", 1), ("r03", 1), ("r01", 2), ("r01", 2)])
    ref = E.draw_stats(E.corner_stats(by_hand))
    assert np.allclose(np.sort(count.sum(1)), np.sort(ref[0].sum(1)))
    assert np.allclose(count.sum(0), ref[0].sum(0)) and np.allclose(total.sum(0), ref[1].sum(0))
    assert sq.sum() == pytest.approx(ref[2].sum())
    want, _ = E.fit_curve_from_stats(*ref)
    got, _ = E.fit_curve_from_stats(count, total, sq, circuit)
    assert np.allclose(got, want, atol=1e-6)
    # The same draw with both c00 copies merged into one group is a different fit (the copies matter).
    merged = _one_draw_plan(base, [0, 3, 0, 3, 1, 1], [0, 0, 0, 0, 2, 2])
    assert len(E.plan_draw_stats(stats, merged, 0)[0]) == 6


def test_the_race_level_comparison_is_frequency_weights_in_the_races_own_groups():
    df = _sim_passes(np.random.default_rng(2), n_races=6, n_circuits=3, n_corners=3, per_cell=40,
                     sd_circuit=0.05, sd_corner=0.05)
    races = sorted(df["race_key"].unique())
    stats = E.corner_stats(df, races)
    plan = _plan(df, 5, method=E.BOOTSTRAP_COMPARISON)
    w = plan.race_weights()
    for i in range(5):
        if (E.draw_stats(stats, w[i])[0].sum(0) <= 0).any():
            continue
        got, _ = E.fit_curve_from_stats(*E.plan_draw_stats(stats, plan, i))
        want, _ = E.fit_curve_from_stats(*E.draw_stats(stats, w[i]))
        assert np.allclose(got, want, atol=1e-6)


def test_a_fit_pass_at_a_circuit_other_than_the_plans_is_refused():
    df = _sim_passes(np.random.default_rng(2), n_races=6, n_circuits=3, n_corners=3, per_cell=20)
    races = sorted(df["race_key"].unique())
    wrong = {r: "c00" for r in races}
    plan = E.resample_plan(races, wrong, ["held_out"], n_draws=2)
    with pytest.raises(E.EstimatorError):
        E.bootstrap_curves(df, plan, classes=("medium",))
    with pytest.raises(E.EstimatorError):
        E.race_circuits(df.assign(circuit=np.where(np.arange(len(df)) % 2 == 0, "c00", "c01")))


def test_a_race_drawn_twice_counts_twice():
    df = _sim_passes(np.random.default_rng(2), n_races=6, n_circuits=3, n_corners=3, per_cell=40)
    races = sorted(df["race_key"].unique())
    stats = E.corner_stats(df, races)
    weight = np.array([2, 0, 1, 1, 1, 1])
    count, total, _, _ = E.draw_stats(stats, weight)
    doubled = pd.concat([df, df[df["race_key"] == races[0]]])
    doubled = doubled[doubled["race_key"] != races[1]]
    ref_count, ref_total, _, _ = E.draw_stats(E.corner_stats(doubled, races))
    assert np.allclose(count, ref_count) and np.allclose(total, ref_total)


def test_curve_with_intervals_table():
    races = [(s, f"r{i}_gp") for s in (2022, 2023, 2024) for i in range(3)]
    p = _prepared(races, seed=9)
    fit = E.fit_passes(p)
    table, draws = E.curve_with_intervals(fit, _plan(fit, 20))
    assert draws.shape == (20, 3, 8) and len(table) == 24
    assert (table["bootstrap_method"] == E.BOOTSTRAP_ADOPTED).all()
    assert (table["ci_lower_s"] <= table["ci_upper_s"]).all()
    assert (np.diff(draws, axis=2) <= 1e-12).all()  # every draw is non-increasing
    assert (table["status"] == E.CURVE_OK).all() and (table["empty_bin_draws"] == 0).all()
    assert E.main_curve_verdict_line(table) is None


# ---------------------------------------------------------------- empty gap bins (review item Q6)


def _three_class_fit(seed=30, n_races=12, n_circuits=4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    parts = []
    for c, cls in enumerate(E.CORNER_CLASSES):
        df = _sim_passes(rng, n_races=n_races, n_circuits=n_circuits, n_corners=3, per_cell=30,
                         sd_circuit=0.03, sd_corner=0.03).assign(corner_class=cls)
        df["corner_key"] = df["corner_key"] + f"_{c}"
        parts.append(df)
    fit = pd.concat(parts, ignore_index=True)
    fit["pass_class"] = np.where(rng.random(len(fit)) < 0.4, E.HELD_UP, E.DIRTY_AIR)
    fit["under_attack"] = rng.random(len(fit)) < 0.2
    return fit


def test_main_curve_empty_bin_in_the_point_fit_is_no_verdict_and_nothing_raises():
    fit = _three_class_fit()
    fit = fit[~((fit["corner_class"] == "fast") & (fit["gap_bin"] == 5))]
    table, draws = E.curve_with_intervals(fit, _plan(fit, 15), role="main")
    fast = table["corner_class"] == "fast"
    assert (table.loc[fast, "status"] == E.CURVE_NO_VERDICT).all()
    assert table.loc[fast, ["estimate_s", "ci_lower_s", "ci_upper_s"]].isna().all().all()
    assert (table.loc[fast, "point_empty_bins"] == "5").all() and (table.loc[fast, "empty_bin_draws"] == 15).all()
    assert (table.loc[~fast, "status"] == E.CURVE_OK).all()  # the other classes are still fitted
    assert draws.shape == (15, 3, 8) and np.isnan(draws[:, 2]).all() and np.isfinite(draws[:, :2]).all()
    line = E.main_curve_verdict_line(table)
    assert line.startswith("No verdict:") and "fast: bins 5 have no fit pass" in line and "15 of 15" in line


def test_main_curve_empty_bin_in_some_draws_is_no_verdict_and_no_draw_is_skipped_or_redrawn():
    fit = _three_class_fit()
    races = sorted(fit["race_key"].unique())
    # Fast bin 5 survives in one race only, so every draw that misses that race has an empty bin.
    only = races[3]
    fit = fit[~((fit["corner_class"] == "fast") & (fit["gap_bin"] == 5) & (fit["race_key"] != only))]
    plan = _plan(fit, 40)
    missing = plan.race_weights()[:, races.index(only)] == 0
    assert 0 < missing.sum() < 40
    table, draws = E.curve_with_intervals(fit, plan, role="main")
    fast = table["corner_class"] == "fast"
    assert (table.loc[fast, "point_empty_bins"] == "").all()  # the point fit itself is fine
    assert (table.loc[fast, "empty_bin_draws"] == missing.sum()).all()
    assert (table.loc[fast, "status"] == E.CURVE_NO_VERDICT).all()
    assert table.loc[fast, ["estimate_s", "ci_lower_s", "ci_upper_s"]].isna().all().all()
    # Every draw kept its place in the fixed plan: empty draws are NaN, the rest are the fit of that draw.
    assert np.isnan(draws[missing, 2]).all() and np.isfinite(draws[~missing, 2]).all()
    stats = E.corner_stats(fit[fit["corner_class"] == "fast"], races)
    i = int(np.flatnonzero(~missing)[0])
    refit, _ = E.fit_curve_from_stats(*E.plan_draw_stats(stats, plan, i))
    assert np.allclose(draws[i, 2], refit, atol=1e-5)
    assert f"{missing.sum()} of 40 draws had an empty bin" in E.main_curve_verdict_line(table)


def test_a_warm_start_on_the_boundary_does_not_stop_a_draw_short_of_its_reml_optimum():
    # Regression (2026-10-28): the full-data fit puts the circuit variance on the lower bound; a draw
    # searched from that start alone stopped short. Warm-started and cold fits must reach the same optimum.
    fit = _three_class_fit()
    races = sorted(fit["race_key"].unique())
    only = races[3]
    fit = fit[~((fit["corner_class"] == "fast") & (fit["gap_bin"] == 5) & (fit["race_key"] != only))]
    stats = E.corner_stats(fit[fit["corner_class"] == "fast"], races)
    full = E.reml_fit(*E.draw_stats(stats))
    start = np.log(np.clip([full.var_circuit / full.sigma2, full.var_corner / full.sigma2], 1e-9, None))
    assert start[0] < -10  # the case this guards: a ratio on the boundary
    plan = _plan(fit, 10)
    for i in range(plan.n_draws):
        parts = E.plan_draw_stats(stats, plan, i)
        if (parts[0].sum(0) <= 0).any():
            continue
        warm, cold = E.reml_fit(*parts, start=start), E.reml_fit(*parts)
        assert np.allclose(warm.beta, cold.beta, atol=1e-5)


def test_class_curve_empty_bin_is_not_estimable_for_that_class_only():
    fit = _three_class_fit()
    fit = fit[~((fit["pass_class"] == E.HELD_UP) & (fit["corner_class"] == "slow") & (fit["gap_bin"] == 0))]
    plan = _plan(fit, 10)
    out = E.class_curves_with_intervals(fit, plan)
    held, _ = out[E.HELD_UP]
    slow = held["corner_class"] == "slow"
    assert (held.loc[slow, "status"] == E.CURVE_NOT_ESTIMABLE).all()
    assert held.loc[slow, "estimate_s"].isna().all()
    assert (held.loc[~slow, "status"] == E.CURVE_OK).all() and held.loc[~slow, "ci_lower_s"].notna().all()
    dirty, _ = out[E.DIRTY_AIR]
    assert (dirty["status"] == E.CURVE_OK).all() and (dirty["pass_class"] == E.DIRTY_AIR).all()
    # The main curve on the same passes is unaffected: other pass classes fill the bin.
    main, _ = E.curve_with_intervals(fit, plan, role="main")
    assert (main["status"] == E.CURVE_OK).all()


# ---------------------------------------------------------------- under attack (review item Q7)


def test_under_attack_difference_recovers_a_known_offset_and_uses_the_same_draws():
    fit = _three_class_fit(seed=31, n_races=20, n_circuits=5)
    # Flagged passes at slow corners, bin 2, lose 0.25 s more; everywhere else the flag does nothing.
    bump = (fit["under_attack"]) & (fit["corner_class"] == "slow") & (fit["gap_bin"] == 2)
    fit.loc[bump, "delta_time_s"] += 0.25
    races = sorted(fit["race_key"].unique())
    plan = _plan(fit, 200)
    t = E.under_attack_difference(fit, plan)
    assert len(t) == 24 and (t["status"] == E.CURVE_OK).all() and (t["n_draws"] == 200).all()
    cell = t[(t["corner_class"] == "slow") & (t["bin"] == 2)].iloc[0]
    assert cell["difference_s"] == pytest.approx(0.25, abs=0.06)
    assert cell["ci_lower_s"] > 0.0
    others = t.drop(cell.name)
    assert others["difference_s"].abs().max() < 0.06
    # Point values are plain pass means.
    sub = fit[(fit["corner_class"] == "fast") & (fit["gap_bin"] == 6)]
    want = sub.loc[sub["under_attack"], "delta_time_s"].mean() - sub.loc[~sub["under_attack"], "delta_time_s"].mean()
    assert t[(t["corner_class"] == "fast") & (t["bin"] == 6)]["difference_s"].iloc[0] == pytest.approx(want)
    # Draw 0 by hand: a race that enters k times (over all circuit copies) counts k times.
    first = plan.fit_draws[0][0]
    w = np.bincount(first, minlength=len(races))
    rw = sub["race_key"].map(dict(zip(races, w))).to_numpy(dtype=float)
    fl = sub["under_attack"].to_numpy()
    y = sub["delta_time_s"].to_numpy()
    d0 = np.average(y[fl], weights=rw[fl]) - np.average(y[~fl], weights=rw[~fl])
    one = E.under_attack_difference(fit, _plan(fit, 1))  # same seed: its one draw is draw 0 above
    assert np.array_equal(_plan(fit, 1).fit_draws[0][0], first)
    assert one[(one["corner_class"] == "fast") & (one["bin"] == 6)]["ci_lower_s"].iloc[0] == pytest.approx(d0)


def test_under_attack_difference_cell_without_flagged_passes_is_not_estimable():
    fit = _three_class_fit(seed=32)
    fit.loc[(fit["corner_class"] == "medium") & (fit["gap_bin"] == 7), "under_attack"] = False
    t = E.under_attack_difference(fit, _plan(fit, 20))
    cell = t[(t["corner_class"] == "medium") & (t["bin"] == 7)].iloc[0]
    assert cell["status"] == E.CURVE_NOT_ESTIMABLE and np.isnan(cell["difference_s"])
    assert cell["passes_under_attack"] == 0 and np.isnan(cell["ci_lower_s"])
    assert (t.drop(cell.name)["status"] == E.CURVE_OK).all()


# ---------------------------------------------------------------- G1 (iii): lap totals


def test_g1_iii_lap_weights_never_count_an_instant_twice():
    rng = np.random.default_rng(13)
    for _ in range(300):
        n = int(rng.integers(1, 9))
        start = np.sort(rng.uniform(0.0, 60.0, n))
        rng.shuffle(start)
        end = start + rng.uniform(0.5, 15.0, n)
        w = E.lap_weights(start, end, np.arange(n))
        assert ((w >= 0.0) & (w <= 1.0)).all()
        # Owned time adds up to the length of the union of the intervals...
        grid = np.linspace(start.min(), end.max(), 20001)
        covered = ((grid[:, None] >= start) & (grid[:, None] <= end)).any(1)
        union = covered.mean() * (end.max() - start.min())
        assert np.sum(w * (end - start)) == pytest.approx(union, rel=2e-3)
        # ...and each instant belongs to the first corner (by start) that covers it, exactly once.
        order = np.argsort(start, kind="stable")
        owned = np.zeros(n)
        first = np.full(len(grid), -1)
        for k in order[::-1]:
            first[(grid >= start[k]) & (grid <= end[k])] = k
        for k in range(n):
            owned[k] = (first == k).mean() * (end.max() - start.min())
        assert np.allclose(owned, w * (end - start), atol=0.01)


def test_g1_iii_lap_weights_overlap_example_and_step_5():
    w = E.lap_weights(np.array([0.0, 8.0, 9.0, 30.0]), np.array([10.0, 12.0, 11.0, 31.0]))
    assert w.tolist() == pytest.approx([1.0, 0.5, 0.0, 1.0])
    assert E.lap_weights(np.array([0.0, np.nan]), np.array([1.0, 2.0])) is None
    assert E.lap_weights(np.array([0.0, 2.0]), np.array([1.0, 2.0])) is None  # empty interval


def test_lap_measured_cost_applies_the_curve_rules():
    curve = {"slow": TRUE_CURVE, "fast": TRUE_CURVE * 2}
    lap = pd.DataFrame({
        "segment_basis": ["brake_onset"] * 4 + ["fixed_before_apex"],
        "seg_start_t": [0.0, 8.0, 20.0, 40.0, 50.0], "seg_end_t": [10.0, 12.0, 25.0, 45.0, 55.0],
        "corner_number": [1, 2, 3, 4, 5], "corner_class": ["slow", "fast", "slow", "fast", "fast"],
        "gap_s": [0.4, -0.1, 3.2, np.nan, 0.1], "reason_wc03": [None, None, None, "no_car_ahead", None],
    })
    # c1: bin 1 (0.22) x 1; c2: gap < 0 -> first fast bin (0.60) x 0.5; c3: >= 3 s -> 0; c4: no car -> 0.
    assert E.lap_measured_cost(lap, curve) == pytest.approx(0.22 + 0.5 * 0.60)
    bad = lap.copy()
    bad.loc[2, "seg_end_t"] = np.nan
    assert np.isnan(E.lap_measured_cost(bad, curve))


# ---------------------------------------------------------------- G1 (ii) and (vii): contest pieces


def _panel(rng, theta=0.4, n_stints=60, laps=12) -> pd.DataFrame:
    rows = []
    for s in range(n_stints):
        year = (2022, 2023, 2024, 2025)[s % 4]
        level = rng.normal(0.0, 0.5)
        for k in range(laps):
            share = float(rng.uniform(0.0, 1.0))
            age = min(k // 5, 5)
            rows.append({"race_year": year, "stint_id": f"s{s}", "age_bin": age,
                         "dirty_air_share_lap": share,
                         "partial_residual_s": level + 0.03 * age + theta * share + rng.normal(0.0, 0.1)})
    return pd.DataFrame(rows)


def test_demean_two_way_equals_least_squares_on_indicators():
    rng = np.random.default_rng(3)
    a = rng.integers(0, 7, 300)
    b = rng.integers(0, 4, 300)
    y = rng.normal(size=300)
    x = np.column_stack([np.eye(7)[a], np.eye(4)[b]])
    expected = y - x @ np.linalg.lstsq(x, y, rcond=None)[0]
    assert np.allclose(E.demean_two_way(y, a, b), expected, atol=1e-9)


def test_theta_now_recovers_the_slope_on_fit_seasons():
    assert E.fit_theta_now(_panel(np.random.default_rng(5), theta=0.4)) == pytest.approx(0.4, abs=0.03)


def test_g1_ii_identical_candidates_score_r_zero():
    rng = np.random.default_rng(6)
    n = 400
    stint = rng.integers(0, 30, n)
    age = rng.integers(0, 6, n)
    y = rng.normal(size=n)
    x = rng.uniform(0.0, 0.5, n)
    out = E.contest_scores(y, {"none": np.zeros(n), "flat": x, "now": x * 0.7, "measured": x}, stint, age)
    assert out["r_flat"].iloc[0] == 0.0
    out = E.contest_scores(y, {"flat": x, "now": x, "measured": x}, stint, age,
                           subsets={"all": np.ones(n, bool), "half": np.arange(n) < n // 2})
    assert (out["r_flat"] == 0.0).all() and (out["r_now"] == 0.0).all()


def test_contest_removes_stint_level_so_a_constant_cost_per_stint_scores_like_none():
    rng = np.random.default_rng(7)
    n = 300
    stint = rng.integers(0, 20, n)
    age = rng.integers(0, 6, n)
    y = rng.normal(size=n)
    per_stint = rng.uniform(0.0, 1.0, 20)[stint]
    out = E.contest_scores(y, {"flat": np.zeros(n), "measured": per_stint}, stint, age)
    assert out["r_flat"].iloc[0] == pytest.approx(0.0, abs=1e-12)


def test_g1_vii_unknown_flat_or_same_lap_share_leaves_the_lap_unscored():
    now = E.flat_now(np.array([0.5, np.nan, 20.0, -1.0]), 0.4)
    assert now[0] == pytest.approx(0.2) and np.isnan(now[1]) and now[2] == 5.0 and now[3] == 0.0
    p = _prepared([(2025, "z_gp")], seed=12, n_drivers=3, laps=range(5, 9))
    p["reason"] = None
    p["reason_wc03"] = np.where(p["clear_ahead"], "no_car_ahead", None)
    p["tag"] = None
    p["yielding"] = False
    laps = p[["season", "race_id", "driver", "lap"]].drop_duplicates().reset_index(drop=True)
    laps["x_flat"] = 0.1
    laps["x_now"] = 0.1
    laps.loc[0, "x_flat"] = np.nan
    laps.loc[1, "x_now"] = np.nan
    laps.loc[2, ["x_flat", "x_now"]] = np.nan
    reason = E.lap_drop_reason(laps, p)
    assert reason.tolist()[:3] == ["flat_unknown", "flat_now_unknown", "flat_unknown"]
    assert reason.iloc[3:].isna().all()
    with pytest.raises(E.EstimatorError):  # a NaN can never be scored as if it were 0
        E.contest_scores(np.zeros(3), {"flat": np.array([0.1, np.nan, 0.0]), "measured": np.zeros(3)},
                         np.array([0, 0, 1]), np.array([0, 1, 0]))


def test_lap_drop_reason_other_step_2_rules():
    p = _prepared([(2025, "z_gp")], seed=14, n_drivers=3, laps=range(5, 10))
    p["reason"] = None
    p["reason_wc03"] = np.where(p["clear_ahead"], "no_car_ahead", None)
    p["yielding"] = False
    laps = p[["season", "race_id", "driver", "lap"]].drop_duplicates().reset_index(drop=True)
    laps["x_flat"] = laps["x_now"] = 0.1
    key = lambda i: (p["driver"] == laps.loc[i, "driver"]) & (p["lap"] == laps.loc[i, "lap"])  # noqa: E731
    p.loc[key(0) & (p["corner_id"] == "2"), "reason"] = "yellow_sector"
    p.loc[key(1) & (p["corner_id"] == "7"), "yielding"] = True  # a flat-out pass still counts
    p.loc[key(2) & (p["corner_id"] == "3"), "seg_end_t"] = np.nan
    reason = E.lap_drop_reason(laps, p)
    assert reason.tolist()[:3] == ["corner_missing", "yielding", "no_segment_time"]
    assert reason.iloc[3:].isna().all()


# ---------------------------------------------------------------- amendment A3: §8a step 1 lap-level counting


def _a3_race(season=2023, last=25, gap_lap=10):
    """Pass rows on laps 2..last-1 (as the builder makes them: no lap 1, no last lap), minus D0's lap
    `gap_lap` (a mid-race telemetry gap). The panel has every lap 1..last for every driver, stint_id per
    driver and half-race."""
    p = _prepared([(season, "a_gp")], seed=21, n_drivers=3, laps=range(2, last))
    p = p[~((p["driver"] == "D0") & (p["lap"] == gap_lap))].reset_index(drop=True)
    panel = pd.DataFrame([
        {"race_year": season, "race_id": f"{season}_a_gp", "driver_id": d, "lap_number": lap,
         "stint_id": f"{d}_{1 if lap < 14 else 2}"}
        for d in ("D0", "D1", "D2") for lap in range(1, last + 1)])
    return p, panel


def test_a3_last_lap_counted_as_last_lap_and_in_no_fit_set():
    p, panel = _a3_race()
    before_p, before_fit = p.copy(), E.fit_passes(p).copy()
    r = E.lap_step1_reason(panel, p)
    assert (r[panel["lap_number"] == 25] == E.LAST_LAP).all()
    pd.testing.assert_frame_equal(p, before_p)  # no pass row and no reference changed
    pd.testing.assert_frame_equal(E.fit_passes(p), before_fit)  # no fit set changed
    assert not before_fit["lap"].isin([1, 25]).any()


def test_a3_lap_1_counted_as_lap_1_even_when_it_is_the_last_lap():
    p, panel = _a3_race()
    r = E.lap_step1_reason(panel, p)
    assert (r[panel["lap_number"] == 1] == E.LAP_1).all()
    only = pd.DataFrame([{"race_year": 2023, "race_id": "2023_a_gp", "driver_id": "D9", "lap_number": 1}])
    assert E.lap_step1_reason(only, p).tolist() == [E.LAP_1]  # lap_1 is checked before last_lap


def test_a3_mid_race_gap_counted_as_no_pass_rows_and_laps_with_passes_go_on():
    p, panel = _a3_race(gap_lap=10)
    r = E.lap_step1_reason(panel, p)
    gap = (panel["driver_id"] == "D0") & (panel["lap_number"] == 10)
    assert r[gap].tolist() == [E.NO_PASS_ROWS]
    assert r[panel["lap_number"].between(2, 24) & ~gap].isna().all()


def test_a3_last_lap_is_the_drivers_highest_panel_lap_in_that_race():
    p, panel = _a3_race()
    panel = panel[~((panel["driver_id"] == "D2") & (panel["lap_number"] > 20))]  # D2 stops after lap 20
    p = p[~((p["driver"] == "D2") & (p["lap"] == 20))]  # ...and the builder made no lap-20 rows for D2
    r = E.lap_step1_reason(panel, p)
    d2 = panel["driver_id"] == "D2"
    assert r[d2 & (panel["lap_number"] == 20)].tolist() == [E.LAST_LAP]
    assert (r[~d2 & (panel["lap_number"] == 20)].isna()).all()  # lap 20 has passes for the others


def test_a3_step_1_counts_add_up_to_panel_laps_with_no_pass_rows():
    p, panel = _a3_race()
    r = E.lap_step1_reason(panel, p)
    keys = p[["season", "race_id", "driver", "lap"]].drop_duplicates().rename(
        columns={"season": "race_year", "driver": "driver_id", "lap": "lap_number"})
    unjoined = int((panel.merge(keys, on=E.PANEL_KEY, how="left", indicator=True)["_merge"] == "left_only").sum())
    counts = E.lap_drop_counts({"step1": r})
    assert counts["reason"].tolist() == E.STEP1_DROP_REASONS
    assert counts.set_index("reason")["laps"].to_dict() == {"lap_1": 3, "last_lap": 3, "no_pass_rows": 1}
    assert counts["laps"].sum() == unjoined == r.notna().sum()


def test_a3_a_stint_left_with_one_lap_is_counted_at_step_4_not_step_1():
    p, panel = _a3_race()
    # D1's last stint is laps 24-25; lap 25 (the last lap) has no pass rows, so after step 1 the stint has 1 lap.
    panel.loc[(panel["driver_id"] == "D1") & (panel["lap_number"] >= 24), "stint_id"] = "D1_3"
    step1 = E.lap_step1_reason(panel, p)
    kept = step1.isna()  # steps 2-3 are taken to keep every joined lap here
    step4 = E.short_stint_reason(panel, kept)
    lap24 = (panel["driver_id"] == "D1") & (panel["lap_number"] == 24)
    lap25 = (panel["driver_id"] == "D1") & (panel["lap_number"] == 25)
    assert step1[lap24].isna().all() and step4[lap24].tolist() == [E.SHORT_STINT]
    assert step1[lap25].tolist() == [E.LAST_LAP]
    assert step4[lap25].isna().all()  # dropped at step 1, not counted again at step 4
    counts = E.lap_drop_counts({"step1": step1, "step4": step4})
    got = {(s, k): n for s, k, n in counts.itertuples(index=False)}
    assert got[("step4", E.SHORT_STINT)] == 1 and got[("step1", E.LAST_LAP)] == 3
    assert counts["laps"].sum() == (step1.notna() | step4.notna()).sum()  # every drop counted once


def test_a3_labels_go_by_position_even_for_a_lap_with_no_telemetry():
    """A3 decision record: a driver's last panel lap with no telemetry of its own is `last_lap`; a lap 1 with
    no telemetry is `lap_1`; any other lap with no pass row, telemetry or not, is `no_pass_rows`."""
    p, panel = _a3_race(gap_lap=10)
    # D1's telemetry stops after lap 23: laps 24 and 25 have no telemetry, so the builder (needing L-1 and
    # L+1) makes no pass rows for lap 24, nor for lap 23 (lap 24 missing). Lap 25 never had pass rows.
    p = p[~((p["driver"] == "D1") & (p["lap"] >= 23))]
    r = E.lap_step1_reason(panel, p)
    d1 = panel["driver_id"] == "D1"
    assert r[d1 & (panel["lap_number"] == 25)].tolist() == [E.LAST_LAP]  # no telemetry, still last_lap
    assert r[d1 & panel["lap_number"].isin([23, 24])].tolist() == [E.NO_PASS_ROWS] * 2  # 24: no telemetry
    assert r[d1 & (panel["lap_number"] == 1)].tolist() == [E.LAP_1]
    # D0's lap 10 (mid-race gap) stays no_pass_rows; D0 and D2 last laps stay last_lap.
    assert r[(panel["driver_id"] == "D0") & (panel["lap_number"] == 10)].tolist() == [E.NO_PASS_ROWS]
    assert (r[~d1 & (panel["lap_number"] == 25)] == E.LAST_LAP).all()
    counts = E.lap_drop_counts({"step1": r}).set_index("reason")["laps"].to_dict()
    assert counts == {"lap_1": 3, "last_lap": 3, "no_pass_rows": 3}


def test_a3_step_4_label_is_the_registered_name():
    assert E.SHORT_STINT == "stint_under_2_laps"


def test_a3_each_lap_counted_once_at_its_first_step():
    idx = pd.RangeIndex(4)
    s1 = pd.Series([E.LAST_LAP, None, None, None], index=idx, dtype=object)
    s2 = pd.Series(["flat_unknown", "flat_unknown", None, None], index=idx, dtype=object)
    counts = E.lap_drop_counts({"step1": s1, "step2": s2})
    got = {(s, k): n for s, k, n in counts.itertuples(index=False)}
    assert got == {("step1", "lap_1"): 0, ("step1", "last_lap"): 1, ("step1", "no_pass_rows"): 0,
                   ("step2", "flat_unknown"): 1}


def test_a3_step_1_refuses_duplicate_or_keyless_panel_rows():
    p, panel = _a3_race()
    with pytest.raises(E.EstimatorError):
        E.lap_step1_reason(pd.concat([panel, panel.iloc[:1]]), p)
    bad = panel.copy()
    bad.loc[0, "lap_number"] = np.nan
    with pytest.raises(E.EstimatorError):
        E.lap_step1_reason(bad, p)


# ---------------------------------------------------------------- G1 (iv): pit-stop events


def _pit_race(followers: dict[str, dict], big_l=20) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Car A pits in on lap L. Each follower runs behind A at the given gap on L-2, L-1 and clean otherwise.
    Its segment time is 10 s, plus `traffic` on L-2, L-1, plus `poison` on L+-1/L+-2 laps used as donors if
    the builder were wrong. Four braking corners."""
    rows, pits = [], []
    for f, spec in followers.items():
        for lap in range(big_l - 7, big_l + 8):
            pre = lap in (big_l - 2, big_l - 1)
            for c in range(1, 5):
                seg = 10.0 + (spec.get("traffic", 0.3) if pre else 0.0)
                if lap in (big_l + 1, big_l + 2):
                    seg += spec.get("post", 0.0)
                if lap == big_l:
                    seg += 5.0
                rows.append(dict(season=2023, race_id="2023_7", driver=f, lap=lap, stint=1.0, compound="HARD",
                                 corner_id=str(c), segment_basis="brake_onset", reason=None,
                                 leader="A" if pre else None,
                                 leader_lap=float(lap + spec.get("lap_offset", 0)) if pre else np.nan,
                                 gap_s=spec["gap"] if pre else np.nan, seg_time_s=seg,
                                 # Clean everywhere outside the traffic laps, including L-2..L+2 neighbours,
                                 # so a wrong donor window would change the reference.
                                 clean=not pre))
        for lap in spec.get("pit_laps", []):
            pits.append(dict(season=2023, race_id="2023_7", driver=f, lap=lap, pit_in=True, pit_out=False))
    pits.append(dict(season=2023, race_id="2023_7", driver="A", lap=big_l, pit_in=True, pit_out=False))
    pits.append(dict(season=2023, race_id="2023_7", driver="A", lap=big_l + 1, pit_in=False, pit_out=True))
    return pd.DataFrame(rows), pd.DataFrame(pits)


def test_g1_iv_each_stop_counted_once_closest_follower_kept():
    passes, pits = _pit_race({"F1": {"gap": 0.9}, "F2": {"gap": 0.6}, "F3": {"gap": 1.4}})
    events, drops = E.pit_stop_events(passes, pits)
    assert len(events) == 1
    assert events.iloc[0]["follower"] == "F2" and events.iloc[0]["pit_lap"] == 20
    assert events.iloc[0]["jump_s"] == pytest.approx(0.3) and events.iloc[0]["corners"] == 4
    assert drops["candidates"].sum() == 0


def test_g1_iv_different_lap_pairs_and_other_drops():
    passes, pits = _pit_race({
        "F1": {"gap": 0.8, "lap_offset": 1},  # car ahead a lap ahead: dropped
        "F2": {"gap": 1.6},  # not close
        "F3": {"gap": 0.5, "pit_laps": [22]},  # follower pits on L+2
    })
    events, drops = E.pit_stop_events(passes, pits)
    assert events.empty
    assert drops.set_index("reason")["candidates"].to_dict() == {
        "not_close": 1, "different_lap": 1, "follower_pits": 1, "leader_pits": 0, "no_outside_reference": 0}


def test_g1_iv_reference_never_comes_from_laps_l_minus_2_to_l_plus_2():
    # Laps L-1..L+2 are poisoned for use as donors (L itself +5 s, L+1/L+2 +0.7 s); the outside laps are 10 s.
    passes, pits = _pit_race({"F1": {"gap": 0.7, "post": 0.7}})
    g = passes[passes["driver"] == "F1"]
    ref = E.pit_outside_reference(g, 20)
    assert ref == {str(c): 10.0 for c in range(1, 5)}
    events, _ = E.pit_stop_events(passes, pits)
    assert events.iloc[0]["jump_s"] == pytest.approx(0.3 - 0.7)
    # Without clean passes outside the window there is no reference, even though L-2..L+2 are clean.
    g2 = passes.copy()
    outside = g2["lap"].isin([20 + d for d in E.PIT_REF_LAPS])
    g2.loc[outside, "clean"] = False
    g2.loc[g2["lap"].isin([21, 22, 20]), "clean"] = True
    events, drops = E.pit_stop_events(g2, pits)
    assert events.empty and drops.set_index("reason").loc["no_outside_reference", "candidates"] == 1


def test_g1_iv_every_braking_corner_whatever_its_reason():
    """§11 'every braking corner': a WC-01 exclusion reason does not take a pass out of the event test or the
    jump (owner instruction 2026-10-28). Reference donors stay clean passes only."""
    # (a) A whole pre-window lap carries a lap-level reason: the event still stands (it was not_close before).
    passes, pits = _pit_race({"F1": {"gap": 0.7}})
    passes.loc[passes["lap"] == 18, "reason"] = "neutralised"
    events, drops = E.pit_stop_events(passes, pits)
    assert len(events) == 1 and events.iloc[0]["follower"] == "F1" and drops["candidates"].sum() == 0
    assert events.iloc[0]["corners"] == 4

    # (b) One excluded corner on L-1 has a different car ahead: that breaks "same car ahead at every braking
    # corner" (it was ignored before, and the event kept).
    passes, pits = _pit_race({"F1": {"gap": 0.7}})
    row = (passes["lap"] == 19) & (passes["corner_id"] == "3")
    passes.loc[row, ["reason", "leader"]] = ["yellow_sector", "B"]
    events, drops = E.pit_stop_events(passes, pits)
    assert events.empty and drops.set_index("reason").loc["not_close", "candidates"] == 1

    # (c) Passes with a reason on L+1/L+2 enter the jump; a pass with no segment time does not.
    passes, pits = _pit_race({"F1": {"gap": 0.7, "post": 0.2}})
    passes.loc[passes["lap"] == 21, "reason"] = "yellow_sector"
    passes.loc[(passes["lap"] == 22) & (passes["corner_id"] == "4"), "seg_time_s"] = np.nan
    events, _ = E.pit_stop_events(passes, pits)
    assert events.iloc[0]["jump_s"] == pytest.approx(0.3 - 0.2) and events.iloc[0]["corners"] == 4

    # (d) Donors still need clean (reason NULL is part of clean): marking the outside laps with a reason and
    # not clean leaves no reference.
    passes, pits = _pit_race({"F1": {"gap": 0.7}})
    outside = passes["lap"].isin([20 + d for d in E.PIT_REF_LAPS])
    passes.loc[outside, ["reason", "clean"]] = ["wet", False]
    events, drops = E.pit_stop_events(passes, pits)
    assert events.empty and drops.set_index("reason").loc["no_outside_reference", "candidates"] == 1


# ---------------------------------------------------------------- G1 (viii): timing of one full draw


def test_g1_viii_timing_of_one_draw():
    """Times one bootstrap draw of the curve chain: the main curve and the held-up and dirty-air class curves,
    three corner classes each (9 REML fits and 9 PAVA steps), on a synthetic fit set of 400,000 passes over
    68 races (about the 2022-2024 share of the 1,071,162 measured passes in §2a, an upper bound).

    The θ_now refit and the 2025 rescoring per draw are timed in test_contest.py
    (test_g1_viii_timing_of_the_theta_now_refit_and_rescoring_per_draw)."""
    rng = np.random.default_rng(20)
    parts = []
    for c, cls in enumerate(E.CORNER_CLASSES):
        df = _sim_passes(rng, n_races=68, n_circuits=23, n_corners=5, per_cell=400, sd_circuit=0.05,
                         sd_corner=0.05).assign(corner_class=cls)
        df["corner_key"] = df["corner_key"] + f"_{c}"
        parts.append(df)
    fit = pd.concat(parts, ignore_index=True)
    fit["pass_class"] = np.where(rng.random(len(fit)) < 0.3, E.HELD_UP, E.DIRTY_AIR)
    assert 390_000 <= len(fit) <= 420_000
    races = sorted(fit["race_key"].unique())
    plan = _plan(fit, 1)  # adopted circuit-then-race plan (amendment A1)
    subsets = [fit, fit[fit["pass_class"] == E.HELD_UP], fit[fit["pass_class"] == E.DIRTY_AIR]]
    t0 = time.perf_counter()
    for sub in subsets:
        E.bootstrap_curves(sub, plan)
    one_draw_with_setup = time.perf_counter() - t0
    stats = [E.corner_stats(sub[sub["corner_class"] == cls], races) for sub in subsets for cls in E.CORNER_CLASSES]
    t0 = time.perf_counter()
    for s in stats:
        E.fit_curve_from_stats(*E.plan_draw_stats(s, plan, 0))
    one_draw = time.perf_counter() - t0
    print(f"G1(viii): one draw of the curve chain (circuit-then-race) {one_draw:.3f} s (cold start); with per-run setup "
          f"{one_draw_with_setup:.3f} s; x {E.N_BOOT} draws ~ {one_draw * E.N_BOOT / 60:.1f} min")
    assert one_draw < 60.0
