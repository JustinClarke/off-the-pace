"""Synthetic tests for WC-10e design A, the lap arm, the seal and the ledger. No real data is opened: the world is
made up, and file tests use temporary folders. These are not the registered SG1-SG7 checks (§17)."""

import errno

import numpy as np
import pandas as pd
import pytest

from tasks.wake_calibration import design_a as A
from tasks.wake_calibration import lap_arm as L
from tasks.wake_calibration import wc10_io as IO

BETA_T = np.array([0.12, 0.10, 0.08, 0.06, 0.04, 0.02, 0.01, 0.005])
BETA_V = np.array([3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.2, 0.1])
CLASS_OF = {"C1": "fast", "C2": "fast", "C3": "medium", "C4": "medium", "C5": "slow", "C6": "slow"}


def world(seed=3, races=("2022_1", "2022_2", "2022_3"), n_drivers=12, n_laps=40, noise=0.02, gamma=0.03):
    """Structure frame (wc10_io.load_structure columns) plus synthetic outcomes, with a planted dose-response."""
    rng = np.random.default_rng(seed)
    rows = []
    for r in races:
        season = int(r[:4])
        pit = {d: int(rng.integers(15, 26)) for d in range(n_drivers)}
        phi = {(c, l): -0.003 * l + rng.normal(0, 0.02) for c in CLASS_OF for l in range(1, n_laps + 1)}
        alpha = {}
        for d in range(n_drivers):
            g = rng.uniform(0.0, 6.0)
            for l in range(1, n_laps + 1):
                g = float(np.clip(g + rng.normal(0, 0.6), 0.05, 6.0))
                stint = 1 if l <= pit[d] else 2
                comp = "MEDIUM" if stint == 1 else "HARD"
                t = l - (0 if stint == 1 else pit[d]) + 2
                for c in CLASS_OF:
                    gap = max(0.01, g + rng.normal(0, 0.1))
                    free = gap >= 3.0
                    clear = bool(free and rng.random() < 0.5)
                    key = (d, stint, c)
                    alpha.setdefault(key, rng.normal(0, 0.3))
                    rows.append(dict(season=season, race_id=r, race=f"race_{r}", driver=f"D{d:02d}", lap=l,
                                     stint=float(stint), compound=comp, tyre_life=float(t), corner_id=c,
                                     corner_number=int(c[1]), corner_class=CLASS_OF[c], segment_basis="brake_onset",
                                     leader=f"D{(d - 1) % n_drivers:02d}", leader_lap=float(l),
                                     gap_s=np.nan if clear else gap, clear_ahead=clear,
                                     behind_1s=bool(rng.random() < 0.3), tag=None, reason=None,
                                     _alpha=alpha[key], _phi=phi[(c, l)]))
    f = pd.DataFrame(rows)
    prev = f[["season", "race_id", "driver", "lap", "corner_id", "gap_s", "clear_ahead", "reason"]].copy()
    prev["lap"] += 1
    prev = prev.rename(columns={"gap_s": "prev_lap_gap_s", "clear_ahead": "prev_lap_clear_ahead",
                                "reason": "prev_lap_reason"})
    f = f.merge(prev, on=["season", "race_id", "driver", "lap", "corner_id"], how="left")
    gap = f["gap_s"].to_numpy(float)
    b = A.E.gap_bin(np.where(np.isnan(gap), 9.0, gap))
    t = f["tyre_life"].to_numpy(float)
    gt = np.where(f["compound"] == "MEDIUM", 0.002 * t + 1e-4 * t * t, 0.001 * t + 5e-5 * t * t)
    eff_t = np.where(b >= 0, BETA_T[np.clip(b, 0, None)], 0.0)
    eff_v = np.where(b >= 0, BETA_V[np.clip(b, 0, None)], 0.0)
    base = 2.0 + f["_alpha"] + f["_phi"] + gt
    f["seg_time_s"] = base + gamma * f["behind_1s"] + eff_t + rng.normal(0, noise, len(f))
    f["min_speed_kph"] = 150 + 10 * (f["_alpha"] + f["_phi"] + gt) - 0.5 * f["behind_1s"] - eff_v + rng.normal(0, 0.5, len(f))
    f["exit_speed_kph"] = f["min_speed_kph"] + 60 + rng.normal(0, 0.5, len(f))
    return f.drop(columns=["_alpha", "_phi"])


def ys(p, f):
    return {o: f[o].reset_index(drop=True) for o in A.OUTCOMES}


@pytest.fixture(scope="module")
def fitted():
    f = world()
    p = A.prepare(f)
    m = A.fit_model(p, ys(p, f))
    return f, p, m


# --------------------------------------------------------------------------- seal and ledger


def test_seal_refuses_2024_and_2025_before_opening(tmp_path):
    for s in (2024, 2025, 2021):
        with pytest.raises(IO.SealError):
            IO.check_seasons([2022, s])
    with pytest.raises(IO.SealError):  # SealError, not FileNotFoundError: refused before any open
        IO.guard_path(tmp_path / "pass_table_2024.parquet")
    with pytest.raises(IO.SealError):
        IO.guard_path(tmp_path / "laps" / "season=2025" / "race=x" / "a.parquet")
    with pytest.raises(IO.SealError):
        IO.guard_path(tmp_path / "no_season.parquet")
    with pytest.raises(IO.SealError):
        IO.load_structure(tmp_path, tmp_path, seasons=(2022, 2024))
    led = IO.Ledger(tmp_path / "ev")
    with pytest.raises(IO.SealError):
        IO.load_outcomes(led, tmp_path, tmp_path, tmp_path, seasons=(2025,))
    assert IO.guard_path(tmp_path / "pass_table_2023.parquet").name == "pass_table_2023.parquet"


def test_structure_loader_refuses_outcome_columns():
    with pytest.raises(IO.LedgerError):
        IO._refuse_guarded(["season", "seg_time_s"])
    with pytest.raises(IO.LedgerError):
        IO._refuse_guarded(["seg_end_t"])
    assert not set(IO.PASS_STRUCTURE_COLUMNS) & IO.GUARDED_COLUMNS
    assert not set(IO.SIDECAR_STRUCTURE_COLUMNS) & IO.GUARDED_COLUMNS


def test_ledger_order_and_outcome_decoded(tmp_path):
    led = IO.Ledger(tmp_path)
    led.begin("first", code="c1", inputs="i1")
    with pytest.raises(IO.LedgerError):
        led.run_start()  # no gate yet
    with pytest.raises(IO.LedgerError):
        IO.load_outcomes(led, tmp_path, tmp_path, tmp_path)
    led.gate(True, ["check 1: PASS"])
    with pytest.raises(IO.LedgerError):
        led.require_run_start()
    led.run_start()
    led.outcome_decoded("seg_time_s", "x/pass_table_2022.parquet")
    led.outcome_decoded("min_speed_kph", "x/pass_table_2022.parquet")
    text = led.path.read_text()
    assert text.count(IO.EV_DECODED) == 1
    cur = led.current()
    assert cur.decoded and not cur.written and cur.state == "RUNNING"
    led.outcome_written("SUMMARY.md")
    assert led.current().state == "COMPLETED"
    with pytest.raises(IO.RestartRefused):
        led.begin("again", code="c1", inputs="i1")


def test_restart_rules(tmp_path):
    led = IO.Ledger(tmp_path / "a")
    led.begin("s1", "c", "i")
    led.gate(False, ["check 2: FAIL"])
    assert led.current().state == "FAILED_RESTARTABLE"
    led.begin("s2 after gate fix", "c2", "i")  # nothing decoded: restartable, even with changed code
    led.gate(True, [])
    led.run_start()
    led.outcome_decoded("seg_time_s", "p")
    # killed by a signal, no EXIT line: restart only with identical code and inputs and an exit status > 128
    with pytest.raises(IO.RestartRefused):
        led.begin("s3", "c2", "i")
    with pytest.raises(IO.RestartRefused):
        led.begin("s3", "c3", "i", prior_exit_status=137)
    led2 = IO.Ledger(tmp_path / "b")
    led2.begin("s1", "c", "i")
    led2.gate(True, [])
    led2.run_start()
    led2.outcome_decoded("seg_time_s", "p")
    led2.begin("s2", "c", "i", prior_exit_status=137)
    assert led2.current().number == 2


def test_guarded_main_writes_type_file_line_only(tmp_path, capsys):
    led = IO.Ledger(tmp_path)
    led.begin("s", "c", "i")

    def boom():
        raise ValueError("secret 0.1234 outcome value")

    assert IO.guarded_main(boom, led) == 1
    err = capsys.readouterr().err
    text = led.path.read_text()
    assert "ValueError" in err and "secret" not in err and "0.1234" not in text and "secret" not in text
    assert IO.is_infrastructure_cause(exc=OSError(errno.ENOSPC, "x"))
    assert IO.is_infrastructure_cause(exit_status=137)
    assert not IO.is_infrastructure_cause(exc=ValueError())


# --------------------------------------------------------------------------- solver, structure, recovery


def test_solver_recovers_exact_fit():
    rng = np.random.default_rng(0)
    n = 3000
    a = rng.integers(0, 40, n)
    f = rng.integers(0, 30, n)
    t = rng.uniform(1, 30, n)
    quad = (a % 2).astype(int) * 2  # cells 0 (quad only) and 2 (lin 1 + quad 2)
    lin = np.where(quad == 2, 1, -1)
    th = np.array([0.0005, 0.01, -0.0003])
    y = rng.normal(0, 1, 40)[a] + rng.normal(0, 1, 30)[f] + np.where(lin >= 0, th[1] * t, 0) + th[quad] * t * t
    sol = A.solve_fe(y, a, f, lin, quad, t, 3, np.zeros(n, int))
    assert np.abs(sol.resid).max() < 1e-7
    assert np.allclose(sol.theta[:, 0], th, atol=1e-7)


def test_theta_layout_reference_and_thin():
    p = pd.DataFrame({"race_id": ["r"] * 9, "compound": ["H"] * 4 + ["M"] * 4 + ["S"],
                      "driver": list("abcd") + list("abcd") + ["a"]})
    lay = A.theta_layout(p, np.ones(9, bool))
    tab = lay.table.set_index("compound")
    assert tab.loc["H", "lin"] == -1  # tie 4-4 goes to the name first bytewise
    assert tab.loc["M", "lin"] >= 0
    assert tab.loc["S", "lin"] == -1 and tab.loc["S", "quad"] == tab.loc["H", "quad"]  # thin -> reference curve


def test_gap_change_order():
    p = pd.DataFrame({"gap_s": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], "prev_lap_gap_s": [np.nan, np.nan, 0.8, 0.3, 0.55, 4.0],
                      "prev_lap_clear_ahead": [True, None, False, False, False, False],
                      "prev_lap_reason": [None, None, None, None, None, "pit_lap"]})
    assert list(A.gap_change(p)) == ["arrived_from_free", "unknown", "shrinking", "growing", "steady", "unknown"]


def test_design_a_recovers_planted_dose_response(fitted):
    f, p, m = fitted
    pt = A.draw_stats(m)
    for k in A.CLASSES:
        beta = pt[f"{k}|seg_time_s|all|beta"]
        assert np.nanmax(np.abs(beta[1:] - BETA_T[1:])) < 0.015, (k, beta)
        assert abs(pt[f"{k}|seg_time_s|all|near"] - BETA_T[2:4].mean()) < 0.01
        assert abs(pt[f"{k}|min_speed_kph|all|near"] - BETA_V[2:4].mean()) < 0.4
        assert abs(pt[f"{k}|gamma|seg_time_s"] - 0.03) < 0.01
        assert abs(pt[f"{k}|S3|B"]) < 0.01  # no drift planted
        # bracketed estimate agrees with the full one when nothing drifts
        brk, n = pt[f"{k}|seg_time_s|brk|beta"], pt[f"{k}|seg_time_s|brk|n"]
        ok = n >= 15
        assert ok.sum() >= 2 and np.max(np.abs(brk[ok] - BETA_T[ok])) < 0.03, (k, brk, n)


def test_every_following_pass_has_exactly_one_class(fitted):
    f, p, m = fitted
    pt = A.draw_stats(m)
    for k, cm in m.classes.items():
        lab = cm.cls.labels(pt[f"{k}|gamma|seg_time_s"], pt[f"{k}|sigma"])
        assert len(lab) == len(cm.ft) and set(lab) <= {A.HELD_UP, A.DIRTY_AIR, A.UNKNOWN, A.RACECRAFT}


def test_null_outcome_never_filled(fitted):
    f, p, _ = fitted
    y = ys(p, f)
    y["min_speed_kph"] = y["min_speed_kph"].copy()
    y["min_speed_kph"].iloc[::7] = np.nan
    m = A.fit_model(p, y)
    for k, cm in m.classes.items():
        ef = cm.eff["min_speed_kph"]
        isnull = np.isnan(y["min_speed_kph"].to_numpy()[ef.rows])
        assert not (ef.valid & isnull).any()
        assert ef.drops["outcome_null"] > 0


def _assert_draw_equal(a, b):
    for k in A.CLASSES:
        assert np.isclose(a[f"{k}|gamma|seg_time_s"], b[f"{k}|gamma|seg_time_s"], atol=1e-8)
        assert np.isclose(a[f"{k}|sigma"], b[f"{k}|sigma"], atol=1e-8)
        for o in A.OUTCOMES:
            for s in ("all", "one", "brk", "dirty_air", "held_up", "brk_dirty", "one_dirty"):
                assert np.allclose(a[f"{k}|{o}|{s}|beta"], b[f"{k}|{o}|{s}|beta"], atol=1e-7, equal_nan=True)
                assert np.allclose(a[f"{k}|{o}|{s}|n"], b[f"{k}|{o}|{s}|n"], atol=1e-9)
        assert np.isclose(a[f"{k}|S3|B"], b[f"{k}|S3|B"], atol=1e-8, equal_nan=True)
        for sw in ("S2pace", "S2aero"):
            for part in ("D", "beta_brk", "std_one", "n_brk"):
                assert np.isclose(a[f"{k}|{sw}|{part}"], b[f"{k}|{sw}|{part}"], atol=1e-7, equal_nan=True)
        assert a[f"{k}|class_counts"] == pytest.approx(b[f"{k}|class_counts"])
    assert np.isclose(a["aero|fast-slow|D"], b["aero|fast-slow|D"], atol=1e-7, equal_nan=True)


def test_bootstrap_reweighting_equals_literal_refit_circuit_copies_and_duplicate_races():
    """SG4 evidence (ruling 5). One draw: Sakhir drawn twice, copy 1 picks 2022_1 twice (a race drawn twice within
    one copy) and copy 2 picks 2022_1 and 2023_1; Jeddah once, picking 2022_2 twice. Weights 2022_1: 3, 2023_1: 1,
    2022_2: 2. The reweighted point fit must equal a literal refit on the replicated data in which every entry is
    a separate copy (relabelled as an unused Appendix A race), sigma's degrees of freedom included."""
    f = world(seed=5, races=("2022_1", "2023_1", "2022_2"), n_drivers=10, n_laps=30)
    p = A.prepare(f)
    m = A.fit_model(p, ys(p, f))
    extra = {"2022_1": ("2022_3", "2022_4"), "2022_2": ("2022_5",)}  # entries beyond the first, as separate copies
    parts = [f] + [f[f["race_id"] == r].assign(race_id=new, season=int(new[:4]), race=f"race_{new}")
                   for r, news in extra.items() for new in news]
    lit = pd.concat(parts, ignore_index=True)
    pl = A.prepare(lit)
    ml = A.fit_model(pl, ys(pl, lit))
    w = np.zeros(A.N_RACES)
    for r, n in (("2022_1", 3), ("2023_1", 1), ("2022_2", 2)):
        w[A.RACE_INDEX[r]] = n
    a, b = A.draw_stats(m, w), A.draw_stats(ml)
    _assert_draw_equal(a, b)
    # duplicate races alone (no circuit copy): Jeddah's 2022_2 twice within one copy, Sakhir's races once each
    lit2 = pd.concat([f, f[f["race_id"] == "2022_2"].assign(race_id="2022_5", race="race_2022_5")],
                     ignore_index=True)
    pl2 = A.prepare(lit2)
    w2 = np.zeros(A.N_RACES)
    for r, n in (("2022_1", 1), ("2023_1", 1), ("2022_2", 2)):
        w2[A.RACE_INDEX[r]] = n
    _assert_draw_equal(A.draw_stats(m, w2), A.draw_stats(A.fit_model(pl2, ys(pl2, lit2))))
    # sigma counts the duplicated race's parameters per entry: not the "once per copy" reading
    s1 = m.classes["fast"].step1[A.TIME]
    g = s1.gamma(w2)
    rss = float(w2 @ (s1.syy - 2 * g * s1.sxy + g * g * s1.sxx))
    once = np.sqrt(rss / (float(w2 @ s1.n_r) - (float((w2 > 0) @ s1.p_r) + 1.0)))
    assert A.draw_stats(m, w2)["fast|sigma"] > once


def test_bootstrap_plan_is_fixed_and_follows_appendix_a():
    assert len(A.CIRCUITS) == 24 and A.N_RACES == 43
    assert A.CIRCUITS[-3:] == ["São Paulo", "Yas Island", "Zandvoort"]
    p1, p2 = A.bootstrap_plan(20), A.bootstrap_plan(20)
    assert np.array_equal(p1.weights, p2.weights)
    rng = np.random.default_rng(A.SEED)
    first = rng.integers(0, 24, 24)
    assert p1.weights[0].sum() == sum(len(A.APPENDIX_A[A.CIRCUITS[c]]) for c in first)
    assert np.array_equal(p1.copies, p1.weights)  # ruling 5: every entry is a copy
    assert (p1.weights > 0).sum(axis=1).min() > 0 and (p1.weights >= 2).any()  # duplicates occur in the plan


# --------------------------------------------------------------------------- owner rulings and the preflight


def test_preflight_refuses_run_start_while_a_choice_is_open(tmp_path, monkeypatch):
    A.preflight()  # ruled values: passes
    led = IO.Ledger(tmp_path)
    led.begin("s", "c", "i")
    led.gate(True, [])
    for bad in (None, "keep"):
        monkeypatch.setitem(A.OPEN_CHOICES, "undefined_draws", bad)
        with pytest.raises(A.OpenChoicesUnset):
            A.preflight()
        with pytest.raises(IO.PreflightError, match="undefined_draws"):
            led.run_start()
        assert IO.EV_RUN_START not in led.path.read_text() and not led.current().run_start
    monkeypatch.setitem(A.OPEN_CHOICES, "undefined_draws", "propagate")
    led.run_start()
    assert led.current().run_start


def test_ruling1_racecraft_free_passes_dropped_and_counted(fitted, monkeypatch):
    f, p, _ = fitted
    y = f["seg_time_s"].reset_index(drop=True)
    q = p.copy()
    idx = q.index[q["free"]][:25]
    q.loc[idx, "racecraft"] = True
    monkeypatch.setitem(A.OPEN_CHOICES, "racecraft_free_passes", None)  # behaviour is the ruling, not a lookup
    fs = A.free_set(q, y, A.TIME)
    assert not fs[idx].any()
    assert A.racecraft_free_dropped(q, y) == int(q["racecraft"][q["free"]].sum()) >= 25
    m = A.fit_model(q, ys(q, f))
    assert m.racecraft_free_dropped[A.TIME] >= 25
    assert not m.st.free_time[idx].any()


def test_ruling2_empty_alpha_bar_corner_skipped_then_n_rule(fitted):
    """Fast class = C1, C2. In 2022_1 only one driver keeps free HARD passes at C2, so alpha-bar at (2022_1, HARD,
    C2) is empty once his stint is excluded: C2 is skipped for his C1 passes, N_F = 0 < 2, and the pass is unknown."""
    f, p, _ = fitted
    hard_c2 = p[p["free"] & (p["race_id"] == "2022_1") & (p["corner_id"] == "C2") & (p["compound"] == "HARD")]
    fol_c1 = p[p["following"] & (p["race_id"] == "2022_1") & (p["corner_id"] == "C1") & (p["compound"] == "HARD")]
    keep = fol_c1[fol_c1["driver"].isin(hard_c2["driver"])]["driver"].value_counts().index[0]
    q = p.copy()
    q.loc[hard_c2.index[hard_c2["driver"] != keep], "free"] = False
    m = A.fit_model(q, ys(q, f))
    cm = m.classes["fast"]
    assert cm.cls.skipped_corners > 0
    own = ((cm.ft["race_id"] == "2022_1") & (cm.ft["driver"] == keep) & (cm.ft["compound"] == "HARD")
           & (cm.ft["corner_id"] == "C1")).to_numpy()
    reasons = set(cm.cls.unknown_reason[own])
    assert own.any() and not cm.cls.known[own].any()
    assert "N_F<2" in reasons and reasons <= {"racecraft", "leader_not_eligible", "N_F<2"}


def test_ruling3_disconnected_prediction_dropped_and_counted(fitted):
    ok = np.array([True, True, True, True, False])
    ca = np.array([0.0, 1.0, 2.0, 3.0, 0.0])
    cp = np.array([0.0, 2.0, -1.0, 3.0, 9.0])  # row 1 other component, row 2 cells span components
    assert list(A._component_check(ok, ca, cp)) == [True, False, False, True, False]
    _, _, m = fitted
    for cm in m.classes.values():
        for ef in cm.eff.values():
            assert "disconnected" in ef.drops and ef.drops["disconnected"] >= 0
    f, p, _ = fitted
    arm = L.fit_lap_arm(L.lap_frame(p, lap_times_from(f)))
    assert "disconnected" in arm.drops


def test_ruling4_undefined_draws_propagate():
    draws = [{"x": float(v)} for v in np.linspace(0.1, 1.0, 50)]
    assert np.isfinite(A.interval(draws, "x")).all()
    draws[7]["x"] = np.nan
    lo, hi = A.interval(draws, "x")
    assert np.isnan(lo) and np.isnan(hi)  # not the percentiles of the 49 defined draws
    v, info = A.s2_verdict([0.0] * 49 + [np.nan], 0.1, 10_000, A.S2_PACE_FLOOR)
    assert v == A.INCONCLUSIVE and np.isnan(info["lo90"])
    assert A.s2_verdict([0.0] * 50, 0.1, 10_000, A.S2_PACE_FLOOR)[0] == A.AGREE
    base = {f"{k}|{A.TIME}|all|{s}": 0.05 for k in A.CLASSES for s in ("near", "far")}
    base.update({f"{k}|S2pace|D": 0.0 for k in A.CLASSES}, **{"aero|fast-slow|D": 0.0})
    ds = [dict(base) for _ in range(10)]
    ds[2]["medium|seg_time_s|all|far"] = np.nan
    ds[3]["slow|S2pace|D"] = np.nan
    ds[3]["aero|fast-slow|D"] = np.nan
    ds[4]["fast|S2pace|D"] = np.nan
    lap = [{"lap|near": 0.1}] * 9 + [{"lap|near": np.nan}]
    u = A.switch_undefined_counts(ds, lap)
    assert u == {"S1": 1, "S2 pace": 2, "S2 aero": 1, "F1": 1}
    assert not L.f1_verdict(lap, {"medium": True, "slow": True})
    ok = {k: True for k in A.CLASSES}
    _, _, line = A.go_no_go(ok, {k: A.AGREE for k in A.CLASSES}, A.AGREE, ok, True, undefined=u)
    assert "| undefined draws S1 1, S2 pace 2, S2 aero 1, F1 1" in line


def test_switch_and_go_no_go(fitted):
    f, p, m = fitted
    plan = A.bootstrap_plan(30)
    # only 3 races in the world: draws without them leave statistics undefined, so restrict the plan's races
    keep = np.array([A.RACE_INDEX[r] for r in ("2022_1", "2022_2", "2022_3")])
    W = np.zeros_like(plan.weights)
    rng = np.random.default_rng(1)
    for i in range(W.shape[0]):
        np.add.at(W[i], keep[rng.integers(0, 3, 3)], 1)
    plan = A.Plan(weights=W)
    draws = A.run_draws(m, plan)
    pt = A.draw_stats(m)
    s1 = A.s1_verdicts(pt, draws)
    s3 = A.s3_verdicts(pt)
    s2p = {k: v[0] for k, v in A.s2_pace(pt, draws).items()}
    s2a, _ = A.s2_aero(pt, draws)
    lap = L.lap_frame(p, lap_times_from(f))
    arm = L.fit_lap_arm(lap)
    ld = L.lap_draws(arm, plan)
    f1 = L.f1_verdict(ld, s3)
    u = A.switch_undefined_counts(draws, ld)
    v, aero, line = A.go_no_go(s1, s2p, s2a, s3, f1, undefined=u)
    assert line.startswith("GO/NO-GO: ") and "| S1 " in line and "| S3 " in line and "| undefined draws S1 " in line
    assert u["S1"] == 0
    assert all(s1.values()) and all(s3.values())


def lap_times_from(f):
    t = f.groupby(["race_id", "driver", "lap"])["seg_time_s"].sum().rename("lap_time_s").reset_index()
    t["lap_time_s"] += 60.0
    return t


def test_lap_arm_recovers_sign(fitted):
    f, p, _ = fitted
    arm = L.fit_lap_arm(L.lap_frame(p, lap_times_from(f)))
    st = L.lap_stats(arm)
    assert np.isfinite(st["lap|near"]) and st["lap|near"] > 0
    assert arm.drops["following_laps"] > 0


def test_go_no_go_table():
    ok = {k: True for k in A.CLASSES}
    u = {"S1": 0, "S2 pace": 0, "S2 aero": 0, "F1": 0}
    agree = {"fast": A.INCONCLUSIVE, "medium": A.AGREE, "slow": A.AGREE}
    v, aero, line = A.go_no_go(ok, agree, A.INCONCLUSIVE, ok, True, undefined=u)
    assert v == "DESIGN A" and aero == "proposed" and "fast-corner bracketed check inconclusive" in line
    assert "| undefined draws S1 0, S2 pace 0, S2 aero 0, F1 0" in line
    v, aero, _ = A.go_no_go(ok, {**agree, "fast": A.DISAGREE}, A.AGREE, ok, True, undefined=u)
    assert v.startswith("FALLBACK") and aero == "—"
    v, _, _ = A.go_no_go(ok, {**agree, "slow": A.INCONCLUSIVE}, A.AGREE, ok, False, undefined=u)
    assert v == "NEITHER"
    v, aero, line = A.go_no_go(ok, {k: A.INCONCLUSIVE for k in A.CLASSES}, A.DISAGREE, ok, False, s2_unpowered=True,
                               undefined=u)
    assert v == "DESIGN A" and aero == "—" and "S2 unpowered" in line


# --------------------------------------------------------------------------- amendment B2 (tyre_life) and B1 label


def test_b1_label_duplicate_race_in_copy_is_copy(monkeypatch):
    """B1 D(2) names the value "copy"; the old code label "separate_copy" is no longer accepted."""
    assert A.RULED_CHOICES["duplicate_race_in_copy"] == "copy" == A.OPEN_CHOICES["duplicate_race_in_copy"]
    A.preflight()
    monkeypatch.setitem(A.OPEN_CHOICES, "duplicate_race_in_copy", "separate_copy")
    with pytest.raises(A.OpenChoicesUnset, match="duplicate_race_in_copy"):
        A.preflight()


def test_b2_ruling1_tyre_life_required_for_step1(fitted):
    """B2 (1): a free pass without tyre_life never enters step 1; (2) it is counted, racecraft first."""
    f, p, _ = fitted
    y = f["seg_time_s"].reset_index(drop=True)
    q = p.copy()
    idx = q.index[q["free"] & ~q["racecraft"]][:40]
    q.loc[idx, "t"] = np.nan
    rc = q.index[q["free"] & ~q["racecraft"]][40:45]
    q.loc[rc, ["t", "racecraft"]] = [np.nan, True]  # racecraft and no tyre_life: counted under ruling 1 only
    fs = A.free_set(q, y, A.TIME)
    assert not fs[idx].any() and not fs[rc].any()
    assert A.tyre_life_free_dropped(q, y) == 40
    assert A.racecraft_free_dropped(q, y) == int((q["free"] & q["racecraft"]).sum())


def _nan_t_world():
    """The synthetic world with, in race 2022_1, stint 2 of the three drivers with the most free stint-2 passes on
    compound UNKNOWN (3 drivers: an estimated theta cell) and every pass of the third one's stint 2 with tyre_life
    missing (free and following rows)."""
    f = world()
    s2 = (f["race_id"] == "2022_1") & (f["stint"] == 2.0)
    free = f["clear_ahead"].fillna(False).astype(bool) | (f["gap_s"] >= 3.0)
    top = f[s2 & free].groupby("driver").size().sort_values(ascending=False).index[:3]  # 3 drivers with free passes
    unk = s2 & f["driver"].isin(top)
    f.loc[unk, "compound"] = "UNKNOWN"
    nan_t = s2 & (f["driver"] == top[2])
    f.loc[nan_t, "tyre_life"] = np.nan
    return f, nan_t.to_numpy()


def test_b2_nan_tyre_life_free_rows_fit_converges_counted_and_layout_after_drop():
    """B2 (1)-(3) on a synthetic structure with NaN-tyre_life free rows in a race: the fit converges, the rows are
    counted under tyre_life_missing, and the theta layout is computed after the drop (UNKNOWN flips from estimated
    to the reference curve; two parameters fewer per class)."""
    f, nan_t = _nan_t_world()
    p = A.prepare(f)
    y = ys(p, f)
    assert (nan_t & p["free"].to_numpy()).sum() > 0 and (nan_t & p["following"].to_numpy()).sum() > 0
    m = A.fit_model(p, y)  # before B2 this raised EstimatorError (no convergence in 10,000 sweeps)
    for k, cm in m.classes.items():
        for o, s1 in cm.step1.items():
            assert s1.sweeps < A.MAX_SWEEPS and np.isfinite(s1.ry).all()
    # counted: free passes per outcome; following passes per class, under their own reason
    free_nan = nan_t & p["free"].to_numpy() & ~p["racecraft"].to_numpy()
    for o in A.OUTCOMES:
        assert m.tyre_life_free_dropped[o] == int((free_nan & np.isfinite(y[o].to_numpy())).sum()) > 0
    assert not m.st.free_time[nan_t].any()
    fol_nan = int((nan_t & p["following"].to_numpy()).sum())
    for o in A.OUTCOMES:
        assert sum(cm.eff[o].drops[A.TYRE_LIFE_MISSING] for cm in m.classes.values()) == fol_nan
    for cm in m.classes.values():
        rows = cm.ft["row"].to_numpy()
        assert not cm.eff[A.TIME].valid[nan_t[rows]].any()
        reasons = set(cm.cls.unknown_reason[nan_t[rows]])
        assert reasons <= {A.TYRE_LIFE_MISSING, "racecraft"}
    # layout after the drop
    free_before = p["free"].to_numpy() & ~p["racecraft"].to_numpy()
    for k in A.CLASSES:
        cmask = (p["corner_class"] == k).to_numpy()
        before = A.theta_layout(p, free_before, class_mask=cmask).table.set_index(["race_id", "compound"])
        after = m.st.theta[k]
        tab = after.table.set_index(["race_id", "compound"])
        assert before.loc[("2022_1", "UNKNOWN"), "lin"] >= 0  # 3 drivers before the drop: estimated
        assert tab.loc[("2022_1", "UNKNOWN"), "lin"] == -1  # 2 drivers after: the reference curve
        assert tab.loc[("2022_1", "UNKNOWN"), "quad"] == after.default_quad["2022_1"]
        assert after.n_params == A.theta_layout(p, free_before, class_mask=cmask).n_params - 2


def test_b2_lap_arm_nan_tyre_life_laps_counted_not_silent():
    """B2 for the lap arm: free laps without tyre_life leave step 1, following laps without it are counted under
    tyre_life_missing (before B2 they vanished through isfinite(tau)); the layout is after the drop."""
    f, nan_t = _nan_t_world()
    p = A.prepare(f)
    lap = L.lap_frame(p, lap_times_from(f))
    arm = L.fit_lap_arm(lap)
    sc = lap[lap["scored"]]
    tn = ~np.isfinite(sc["t"].to_numpy(float))
    assert arm.drops[A.TYRE_LIFE_MISSING] == int((tn & sc["following_lap"].to_numpy()).sum())
    assert arm.drops[A.TYRE_LIFE_MISSING + "_free"] == int((tn & sc["free_lap"].to_numpy()).sum()) > 0
    assert arm.sweeps < A.MAX_SWEEPS
    d = arm.drops
    accounted = (d[A.TYRE_LIFE_MISSING] + d["not_supported"] + d["phi_unsupported"] + d["other_undefined"]
                 + d["disconnected"] + d["trimmed"] + int(arm.valid.sum()))
    assert accounted == d["following_laps"]  # every following lap is valid or carries a named reason
    lay = A.theta_layout(sc.reset_index(drop=True), L.lap_free(sc.reset_index(drop=True)))
    assert lay.table.set_index(["race_id", "compound"]).loc[("2022_1", "UNKNOWN"), "lin"] == -1


@pytest.mark.skipif(not (IO.DEFAULT_PASS_DIR / "pass_table_2022.parquet").is_file()
                    or not (IO.DEFAULT_SIDECAR_DIR / "sidecar_2022.parquet").is_file(),
                    reason="2022-23 structure artifacts not present")
def test_b2_real_structure_all_43_races_step1_converges():
    """Structure columns only (load_structure refuses every outcome column); y and lap times are FAKE finite
    constants. After B2 every corner class's step 1 and the lap arm converge over all 43 races, and the lap-arm
    layout has 149 parameters (2022_11 UNKNOWN on the reference curve; 151 before the drop)."""
    s = IO.load_structure()
    assert not set(s.columns) & IO.GUARDED_COLUMNS
    p = A.prepare(s)
    y = pd.Series(np.zeros(len(p)))
    st = A.structure_sets(p, y)
    races = set()
    for k in A.CLASSES:
        s1 = A.fit_step1(p, y, A.TIME, k, st, st.free_time)
        assert s1.sweeps < A.MAX_SWEEPS
        races |= set(np.flatnonzero(s1.n_r > 0))
        assert st.theta[k].table.set_index(["race_id", "compound"]).loc[("2022_11", "UNKNOWN"), "lin"] == -1
    assert races == set(range(A.N_RACES)) and A.N_RACES == 43
    lt = p[["race_id", "driver", "lap"]].drop_duplicates().assign(lap_time_s=0.0)
    lap = L.lap_frame(p, lt)
    arm = L.fit_lap_arm(lap)
    assert arm.sweeps < A.MAX_SWEEPS and arm.lap["race_id"].nunique() == 43
    sc = lap[lap["scored"]].reset_index(drop=True)
    assert A.theta_layout(sc, sc["free_lap"].to_numpy()).n_params == 151
    lay = A.theta_layout(sc, L.lap_free(sc))
    assert lay.n_params == 149
    assert lay.table.set_index(["race_id", "compound"]).loc[("2022_11", "UNKNOWN"), "lin"] == -1
    assert arm.drops[A.TYRE_LIFE_MISSING] == 78 and arm.drops[A.TYRE_LIFE_MISSING + "_free"] == 57
