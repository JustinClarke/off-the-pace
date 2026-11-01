"""Synthetic tests for the WC-10e remainder: tyre carry-over (§9b), diagnostics X1-X15 (§12), per-lap scores (§13)
and the run tool (§0a, §13, BUILD-ORDER rule 8). No real data file is opened and no outcome column is read: every
world is invented, and file tests use temporary folders. These are not the registered SG1-SG7 checks (§17)."""

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tasks.wake_calibration import carryover as C
from tasks.wake_calibration import design_a as A
from tasks.wake_calibration import diagnostics as D
from tasks.wake_calibration import lap_arm as L
from tasks.wake_calibration import run_wc10 as R
from tasks.wake_calibration import wc10_io as IO

D_CHOICES = dict(x1_trim="registered_tau", modal_leader_tie="drop", fallback_negative_median="bin_0.3-0.5")


@pytest.fixture(autouse=True)
def _choices(monkeypatch):
    for k, v in D_CHOICES.items():
        monkeypatch.setitem(D.OPEN_CHOICES, k, v)


def _set_all():
    saved = dict(D.OPEN_CHOICES)
    D.OPEN_CHOICES.update(D_CHOICES)
    return saved


def _restore(saved):
    D.OPEN_CHOICES.clear()
    D.OPEN_CHOICES.update(saved)


@pytest.fixture(scope="module")
def world():
    saved = _set_all()
    inp = R.synthetic_world()
    p = A.prepare(inp.structure)
    y = {o: inp.y[o].reset_index(drop=True) for o in A.OUTCOMES}
    m = A.fit_model(p, y)
    lap = L.lap_frame(p, inp.lap_times)
    _restore(saved)
    return inp, p, y, m, lap


@pytest.fixture(scope="module")
def analysed():
    saved = _set_all()
    inp = R.synthetic_world()
    res = R.analyse(inp, R.synthetic_plan(12))
    _restore(saved)
    return res


# --------------------------------------------------------------------------- carry-over (§9b)


def _lap_rows(stint_laps, meds, race="2022_1", driver="D00", stint=1.0):
    n = len(stint_laps)
    return pd.DataFrame({"race_id": race, "driver": driver, "lap": stint_laps, "stint": stint, "compound": "MEDIUM",
                         "t": np.arange(n, dtype=float) + 2, "race_idx": A.RACE_INDEX[race],
                         "med": meds, "free_lap": [m >= 3.0 for m in meds], "following_lap": [m < 3.0 for m in meds],
                         "scored": True, L.STINT_KEY: f"{race}|{driver}|{stint}", "lap_time_s": 90.0})


def test_carry_frame_labels():
    # laps 1-10: free, close, close, free, free, close(1), free, [11 not scored -> absent], 12 close, 13 free
    laps = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13]
    meds = [3, .5, .5, 3, 3, .5, 3, 3, 3, 3, .5, 3]
    sc = C.carry_frame(_lap_rows(laps, [float(x) for x in meds]))
    s = sc.set_index("lap")
    assert list(s.loc[[2, 3, 6, 12], "episode_len"]) == [2, 2, 1, 1]
    assert s.loc[4, "C"] == 2 and s.loc[7, "C"] == 3 and s.loc[13, "C"] == 4 and s.loc[1, "C"] == 0
    assert s.loc[7, "C_ep1-2"] == 3 and s.loc[7, "C_ep3-4"] == 0
    # pre-trend: lap 1 is 1 lap before the episode at 2; laps 4 and 5 are 2 and 1 before the one at 6
    assert s.loc[1, "pi_1"] == 1 and s.loc[4, "pi_2"] == 1 and s.loc[5, "pi_1"] == 1
    assert s.loc[9, "pi_3"] == 1  # 12 - 9 = 3 (lap 11 is absent, so 12 starts a new episode)
    assert s.loc[13, ["pi_1", "pi_2", "pi_3"]].sum() == 0


def _carry_world(theta=0.05, seed=0, n_races=3, n_drivers=10, n_laps=40):
    rng = np.random.default_rng(seed)
    frames = []
    for r in A.RACES[:n_races]:
        phi = rng.normal(0, 0.2, n_laps + 1)
        for d in range(n_drivers):
            a = rng.normal(0, 0.5)
            close_run = set()
            for _ in range(3):
                s0 = int(rng.integers(2, n_laps - 6))
                close_run |= set(range(s0, s0 + int(rng.integers(1, 7))))
            laps = np.arange(1, n_laps + 1)
            meds = np.array([0.6 if l in close_run else 3.0 for l in laps])
            f = _lap_rows(laps, meds, race=r, driver=f"D{d:02d}")
            f["t"] = laps.astype(float)
            C_l = np.cumsum(meds < 1.0) - (meds < 1.0)
            f["lap_time_s"] = 90 + a + phi[laps] + 0.01 * laps + 0.0004 * laps ** 2 + theta * C_l \
                + rng.normal(0, 0.05, n_laps)
            frames.append(f)
    return pd.concat(frames, ignore_index=True)


def test_carry_recovers_planted_theta_and_zero_pretrend():
    sc = C.carry_frame(_carry_world(theta=0.05))
    cf = C.fit_carry(sc)
    pt = C.carry_coefficients(cf)
    assert abs(pt["carry|main|theta_carry"] - 0.05) < 0.01
    for j in (1, 2, 3):
        assert abs(pt[f"carry|main|pi_{j}"]) < 0.05
    for n in C.TIER_NAMES:  # the plant does not depend on episode length
        assert abs(pt[f"carry|tier|{n}"] - 0.05) < 0.02
    plan = R.synthetic_plan(15, races=tuple(A.RACES[:3]))
    t = C.carry_table(cf, plan)
    row = t[(t["model"] == "main") & (t["term"] == "theta_carry")].iloc[0]
    assert row["lo95"] <= row["estimate_s"] <= row["hi95"] and row["draws"] == 15


def test_carry_bootstrap_weight_equals_literal_duplicate():
    lap = _carry_world(theta=0.02, n_races=2)
    cf = C.fit_carry(C.carry_frame(lap))
    w = np.zeros(A.N_RACES)
    w[A.RACE_INDEX[A.RACES[0]]], w[A.RACE_INDEX[A.RACES[1]]] = 2, 1
    a = C.carry_coefficients(cf, w)
    dup = lap[lap["race_id"] == A.RACES[0]].assign(race_id=A.RACES[5], race_idx=5)
    dup[L.STINT_KEY] = dup[L.STINT_KEY].str.replace(A.RACES[0], A.RACES[5])
    b = C.carry_coefficients(C.fit_carry(C.carry_frame(pd.concat([lap, dup], ignore_index=True))))
    for k in a:
        assert np.isclose(a[k], b[k], atol=1e-7, equal_nan=True), k


def test_carry_term_without_variation_is_dash_not_zero():
    lap = _carry_world(theta=0.0)
    lap["med"] = np.where(lap["med"] < 1.0, 2.0, lap["med"])  # no close lap anywhere
    lap["free_lap"] = lap["med"] >= 3.0
    cf = C.fit_carry(C.carry_frame(lap))
    pt = C.carry_coefficients(cf)
    assert np.isnan(pt["carry|main|theta_carry"])
    t = C.carry_table(cf, R.synthetic_plan(5, races=tuple(A.RACES[:3])))
    assert (t.loc[t["term"] == "theta_carry", "status"] == "—, not identified").all()


# --------------------------------------------------------------------------- diagnostics


def test_lap_step1_matches_lap_arm(world):
    _, _, _, _, lap = world
    arm = L.fit_lap_arm(lap)
    ls = D.lap_step1(lap)
    assert np.allclose(ls.tau, arm.tau, equal_nan=True) and np.array_equal(ls.valid, arm.valid)


def test_cap_coast():
    s, n = D.cap_coast(pd.Series([0.5, 10.0, 10.01, np.nan, 40.0]))
    assert n == 2 and np.isnan(s.iloc[2]) and s.iloc[1] == 10.0 and np.isnan(s.iloc[4])


def test_x14_washout_drops_free_passes_after_a_spell():
    p = pd.DataFrame({"group": ["g"] * 8, "lap": range(1, 9),
                      "gap_s": [4.0, 0.5, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0], "racecraft": [False] * 8})
    free = np.array([True, False, True, True, True, True, True, True])
    kept = D._x14_free(p, free)
    assert list(kept) == [True, False, False, False, False, True, True, True]


def test_diagnostics_cover_x1_to_x15(world):
    inp, p, y, m, lap = world
    ctx = D.build_context(m, y, inp.coast, inp.throttle, lap, inp.team, None)
    res = D.run_diagnostics(ctx, R.synthetic_plan(8))
    keys = set(res["stats"]["diagnostic"])
    want = {f"X{i}" for i in range(1, 16)} - {"X6"}  # X6 is a per-event table
    assert want <= keys, want - keys
    assert "x6" in res and res["x6_counts"]["events"] == 0
    assert res["stats"]["title"].str.startswith("DIAGNOSTIC").sum() == (res["stats"]["diagnostic"] != "X0").sum()
    assert res["n_draws"] == 8
    st = res["stats"].set_index("key")
    # the planted dose-response shows in X1 and X8; X1's near band carries its bracketed companion
    for k in A.CLASSES:
        assert abs(st.loc[f"X1|{k}|W8|near", "estimate"] - 0.07) < 0.02
        assert f"X1|{k}|W8|brk_near" in st.index and f"X3|{k}|shrinking|brk_near" in st.index
    assert set(res["x3_flags"]) == set(A.CLASSES)


def test_x1_trim_is_an_open_choice(world, monkeypatch):
    inp, p, y, m, lap = world
    ctx = D.build_context(m, y)
    monkeypatch.setitem(D.OPEN_CHOICES, "x1_trim", None)
    with pytest.raises(D.OpenChoiceError):
        D.diag_stats(ctx)


# --------------------------------------------------------------------------- owner rulings on the open choices


def test_ruled_values_and_preflight_passes():
    assert D.RULED_CHOICES == D_CHOICES
    assert D.OPEN_CHOICES == D.RULED_CHOICES  # the module ships with every choice ruled
    D.preflight()  # all eight ruled: passes


EIGHT = [("A", k) for k in A.RULED_CHOICES] + [("D", k) for k in D.RULED_CHOICES]


def test_eight_choices():
    assert len(EIGHT) == 8


@pytest.mark.parametrize("mod,name", EIGHT)
def test_preflight_refuses_run_start_if_any_choice_is_none(monkeypatch, mod, name):
    monkeypatch.setitem((A if mod == "A" else D).OPEN_CHOICES, name, None)
    with pytest.raises((A.OpenChoicesUnset, D.OpenChoiceError), match="RUN START refused") as e:
        D.preflight()
    assert name in str(e.value)


def test_ruling1_x1_trim_registered_tau(world):
    inp, p, y, m, lap = world
    ctx = D.build_context(m, y)
    out = D.diag_stats(ctx)
    cd = D.class_draws(m)
    for k, cm in m.classes.items():
        _, _, ok = ctx.x1[(k, 8)]
        wr = cd[k].wr
        # registered_tau: X1 uses exactly the passes that entered beta (and have >= 2 free passes in the window)
        want = float((wr * (cd[k].keep[D.TIME] & ok & np.isin(cm.ft["bin"].to_numpy(), A.NEAR_BINS))).sum())
        assert out[f"X1|{k}|W8|n_near"] == want


@pytest.mark.parametrize("bad", ["own_tau", "registered", "", "REGISTERED_TAU"])
def test_x1_trim_unknown_value_is_rejected(world, monkeypatch, bad):
    inp, p, y, m, lap = world
    ctx = D.build_context(m, y)
    monkeypatch.setitem(D.OPEN_CHOICES, "x1_trim", bad)
    with pytest.raises(D.OpenChoiceError, match="rejected"):
        D.diag_stats(ctx)
    with pytest.raises(D.OpenChoiceError, match="differ from the owner's ruling"):
        D.preflight()


def test_x1_trim_unknown_value_refused_by_cli(tmp_path):
    rc = R.main(["--mode", "synthetic", "--out", str(tmp_path / "s"), "--draws", "4",
                 "--assume-choices", "x1_trim=own_tau"])
    assert rc == 2 and not (tmp_path / "s").exists()


def test_coverage_floor_blanks_x5(world):
    inp, p, y, m, lap = world
    thr = inp.throttle.copy()
    thr.iloc[: int(len(thr) * 0.5)] = np.nan
    ctx = D.build_context(m, y, inp.coast, thr)
    res = D.run_diagnostics(ctx, R.synthetic_plan(4))
    cov = res["coverage"].set_index(["outcome", "class"])
    low = [k for k in A.CLASSES if cov.loc[(D.THROTTLE, k), "coverage"] < 0.70]
    assert low
    st = res["stats"]
    rows = st[st["key"].str.startswith(f"X5|{low[0]}|{D.THROTTLE}|") & (st["status"] != "count")]
    assert len(rows) and rows["estimate"].isna().all() and (rows["status"] == "—, coverage < 0.70").all()


def _release_frame(gap_L2=3.0, tie=False):
    """One driver D1 behind D0; D0 pits on lap 3 (pit_lap_leader on D1's lap-3 rows); D1 free-ish on lap 4."""
    rows = []
    for lap, gaps, reason in ((2, [0.5, 0.6, 0.7], None), (3, [0.8, 0.9, 1.0], "pit_lap_leader"),
                              (4, [gap_L2] * 3, None)):
        for c, g in zip(("C1", "C2", "C3"), gaps):
            leader = {"C1": "D0", "C2": "D9", "C3": "D8"}[c] if (tie and lap == 2) else "D0"
            rows.append(dict(season=2022, race_id="2022_1", driver="D1", lap=lap, stint=1.0, corner_id=c,
                             segment_basis="brake_onset", gap_s=g, clear_ahead=False, tag=None, reason=reason,
                             leader=leader))
    return pd.DataFrame(rows)


def test_release_events_recount():
    # L+2 at exactly 3.0 s: free under >= 3, mostly free under > 3 (median >= 3); both are accepted states
    p = _release_frame(gap_L2=3.0)
    r = D.release_events(p, {2022: 1})
    bs = r.by_season.set_index("season")
    assert bs.loc[2022, "matched_free_ge3"] == 1 and bs.loc[2022, "matched_free_gt3"] == 1
    assert r.reproduced and len(r.events) == 1
    assert not D.release_events(p, {2022: 5}).reproduced
    assert len(D.release_events(_release_frame(gap_L2=2.0)).events) == 0  # L+2 neither free nor mostly free


def test_release_modal_tie_is_an_open_choice(monkeypatch):
    p = _release_frame(tie=True)
    monkeypatch.setitem(D.OPEN_CHOICES, "modal_leader_tie", None)
    with pytest.raises(D.OpenChoiceError):
        D.release_events(p)
    monkeypatch.setitem(D.OPEN_CHOICES, "modal_leader_tie", "any")  # not the ruling: rejected
    with pytest.raises(D.OpenChoiceError, match="rejected"):
        D.release_events(p)


def test_ruling2_modal_tie_dropped_counted_and_recount_required():
    p = _release_frame(tie=True)
    r = D.release_events(p)
    assert len(r.events) == 0 and r.ties == 1  # a tied modal leader is not an X6 event; the tie is counted
    # the untied lap is still an event, so the expected recount reproduces it
    both = pd.concat([p, _release_frame().assign(driver="D2")], ignore_index=True)
    r2 = D.release_events(both, {2022: 1})
    assert r2.reproduced and len(r2.events) == 1 and r2.ties == 1
    # the recount must reproduce (here: 2 expected, 1 found after dropping the tie), or X6 refuses to report
    r3 = D.release_events(both, {2022: 2})
    assert not r3.reproduced
    ctx = D.Context(model=None, y={}, release=r3)
    t, counts = D.x6_table(ctx)
    assert t.empty and counts["status"].startswith("—, recount does not reproduce")
    assert counts["modal_ties_dropped"] == 1


def test_ruling2_tie_count_printed_in_summary(analysed):
    assert "modal-leader ties dropped (not events, ruling modal_leader_tie = drop): " in analysed.summary


# --------------------------------------------------------------------------- per-lap scores (§13 item 7)


def _score_world():
    """Race with 3 braking corners; laps: 1 score lap (one corner at 0.1 s), 2 missing a corner, 3 yielding,
    4 racecraft corner (gap < 0) allowed, 5 overlapping-free but interval missing."""
    rows = []
    for lap in range(1, 6):
        for c, num, k in (("C1", 1, "fast"), ("C2", 2, "medium"), ("C3", 3, "slow")):
            if lap == 2 and c == "C3":
                continue
            gap = 0.1 if c == "C1" else 5.0
            if lap == 4 and c == "C2":
                gap = -0.2
            rows.append(dict(row=len(rows), race_id="2022_1", driver="D1", lap=lap, stint=1.0, corner_id=c,
                             corner_number=num, corner_class=k, segment_basis="brake_onset", gap_s=gap,
                             clear_ahead=False, tag="yielding" if (lap == 3 and c == "C2") else None,
                             eligible=not (lap == 4 and c == "C2"), racecraft=(lap == 4 and c == "C2"),
                             extrapolated=False))
    p = pd.DataFrame(rows)
    start = p["lap"] * 100.0 + p["corner_number"] * 10.0
    end = start + 2.0
    end[(p["lap"] == 5) & (p["corner_id"] == "C3")] = np.nan
    return p, start.to_numpy(), end.to_numpy()


def test_score_lap_rules_and_pricing():
    p, s, e = _score_world()
    sf = D.score_frame(p, s, e)
    assert sorted(sf.laps["lap"]) == [1, 4, 5]
    c = sf.corners.set_index(["lap", "corner_id"])
    assert c.loc[(1, "C1"), "price_bin"] == 1  # 0-0.3 s priced at 0.3-0.5 s
    assert c.loc[(4, "C2"), "price_bin"] == 1  # racecraft gap < 0 at 0.3-0.5 s
    assert c.loc[(1, "C3"), "price_bin"] == -1  # free corner gives 0
    assert not sf.laps.set_index("lap").loc[5, "weights_ok"]


def test_scores_unavailable_is_dash_with_reason_never_zero(world):
    inp, p, y, m, lap = world
    plan = R.synthetic_plan(6)
    pt, dr = A.draw_stats(m), A.run_draws(m, plan)
    sf = D.score_frame(p, inp.seg_start, inp.seg_end)
    t = D.per_lap_scores(sf, m, pt, dr, "NEITHER", "—")
    assert t["S_pace"].isna().all() and (t["S_pace_reason"] == "switch: NEITHER (no pace level)").all()
    assert t["S_aero"].isna().all() and t["S_aero_reason"].str.startswith("switch: aero").all()
    t2 = D.per_lap_scores(sf, m, pt, dr, "DESIGN A", "proposed")
    fol = t2[t2["following_lap"] & (t2["S_pace_reason"] == "")]
    assert len(fol) and (fol["S_pace"] > 0).mean() > 0.9
    assert (fol["S_pace_p10"] <= fol["S_pace_p90"]).all()
    assert t2.loc[~t2["following_lap"], "S_pace"].fillna(0).eq(0).all()


def test_fallback_negative_median_is_an_open_choice(world, monkeypatch):
    inp, p, y, m, lap = world
    sf = D.score_frame(p, inp.seg_start, inp.seg_end)
    sf.laps.loc[sf.laps.index[0], "med_gap"] = -0.1
    arm = L.fit_lap_arm(lap)
    lp = L.lap_stats(arm)
    monkeypatch.setitem(D.OPEN_CHOICES, "fallback_negative_median", None)
    with pytest.raises(D.OpenChoiceError):
        D._pace_values(sf, {}, "FALLBACK (lap level, pace only)", lp)
    monkeypatch.setitem(D.OPEN_CHOICES, "fallback_negative_median", "unavailable")  # not the ruling
    with pytest.raises(D.OpenChoiceError, match="rejected"):
        D._pace_values(sf, {}, "FALLBACK (lap level, pace only)", lp)


def test_ruling3_fallback_negative_median_priced_at_bin_03_05(world):
    inp, p, y, m, lap = world
    sf = D.score_frame(p, inp.seg_start, inp.seg_end)
    i_neg, i_b0, i_b1, i_nan = sf.laps.index[:4]
    sf.laps.loc[i_neg, "med_gap"] = -0.1  # negative median -> 0.3-0.5 s bin
    sf.laps.loc[i_b0, "med_gap"] = 0.1  # 0-0.3 s bin -> also priced at the 0.3-0.5 s value
    sf.laps.loc[i_b1, "med_gap"] = 0.4
    sf.laps.loc[i_nan, "med_gap"] = np.nan  # no median: stays undefined, not priced
    beta = np.arange(1.0, A.N_BINS + 1.0)  # distinct per bin
    v = D._pace_values(sf, {}, "FALLBACK (lap level, pace only)", {"lap|beta": beta})
    assert v[i_neg] == beta[1] and v[i_b0] == beta[1] and v[i_b1] == beta[1]
    assert np.isnan(v[i_nan])


def test_ruling6_s_aero_unweighted_literal_formula(world):
    inp, p, y, m, lap = world
    pt = A.draw_stats(m)
    sf = D.score_frame(p, inp.seg_start, inp.seg_end)
    a = D._aero_values(sf, m, pt)
    sf.corners["w"] = sf.corners["w"] * 7.0  # w_k must not enter S_aero
    b = D._aero_values(sf, m, pt)
    assert np.array_equal(a, b, equal_nan=True)
    import inspect
    assert "§13 item 7" in inspect.getsource(D._aero_values)


# --------------------------------------------------------------------------- the run tool


def test_analyse_outputs_and_summary(analysed):
    res = analysed
    lines = res.summary.splitlines()
    assert lines[0].startswith("GO/NO-GO: ") and lines[1] == R.LINE2 and lines[2] == R.LINE3
    assert R.SYNTHETIC_LINE in lines[3]
    assert R.DD_WC2 in res.summary and R.DD_WC18 in res.summary and R.MULTIPLE_TESTING in res.summary
    for name in ("curves", "near_far", "aero_contrasts", "switch_S1", "switch_S2", "switch_S3", "switch_F1",
                 "lap_arm", "tyre_carry", "per_lap_scores", "DIAGNOSTIC_X1-X15", "support_S2_cells",
                 "support_phi_by_race"):
        assert name in res.tables, name
    nf = res.tables["near_far"]
    assert {"brk_near", "brk_far"} <= set(nf.columns)  # §8a mandatory companion
    assert {"brk_estimate"} <= set(res.tables["aero_contrasts"].columns)
    assert res.n_intervals > 0 and f"Intervals reported: {res.n_intervals}." in res.summary


def test_ruling5_line2_word_for_word(analysed):
    assert R.LINE2 == "Exploratory, discovery data (2022-23), in-sample, not confirmed."
    assert analysed.summary.splitlines()[1] == R.LINE2


def test_banned_words_absent(analysed, tmp_path):
    R.write_outputs(analysed, tmp_path)
    for f in tmp_path.iterdir():
        if f.suffix in (".md", ".csv"):
            lines = f.read_text().splitlines()
            # exactly LINE2 (line 2 of SUMMARY.md) is exempt; every other line is checked
            if f.name == "SUMMARY.md":
                assert lines[1] == R.LINE2 and lines.count(R.LINE2) == 1
                lines = lines[:1] + lines[2:]
            text = "\n".join(lines).lower()
            assert "significant" not in text and "proves" not in text, f.name
            assert "confirmed" not in text, f.name


def test_ruling4_output_location():
    assert R.DEFAULT_ARTIFACTS == IO.WC / "_artifacts" / "WC-10" / "discovery"
    assert R.build_parser().parse_args(["--mode", "real"]).artifacts_dir == R.DEFAULT_ARTIFACTS
    assert "_artifacts/WC-10/discovery/" in R.__doc__


def test_write_outputs_sha256sums(analysed, tmp_path):
    hashes = R.write_outputs(analysed, tmp_path / "o")
    sums = (tmp_path / "o" / "SHA256SUMS").read_text().splitlines()
    assert len(sums) == len(hashes) and "SUMMARY.md" in hashes
    for line in sums:
        h, n = line.split("  ", 1)
        assert R.sha256_file(tmp_path / "o" / n) == h


def test_cli_synthetic_end_to_end(tmp_path, capsys):
    out = tmp_path / "syn"
    rc = R.main(["--mode", "synthetic", "--out", str(out), "--draws", "6"])
    assert rc == 0 and (out / "SYNTHETIC").is_file() and (out / "SHA256SUMS").is_file()
    assert (out / "SUMMARY.md").read_text().startswith("GO/NO-GO: ")


def test_cli_synthetic_refuses_real_folders(tmp_path):
    assert R.main(["--mode", "synthetic", "--out", str(R.DEFAULT_ARTIFACTS / "x")]) == 2
    assert R.main(["--mode", "synthetic", "--out", str(R.EVIDENCE_ROOT / "x")]) == 2


def test_real_mode_refused_without_run_start(tmp_path):
    ev, art = tmp_path / "ev", tmp_path / "art"
    rc = R.main(["--mode", "real", "--evidence-dir", str(ev), "--artifacts-dir", str(art)])
    assert rc == 2 and not ev.exists() and not art.exists()
    rc = R.main(["--mode", "real", "--run-start", "--draws", "5", "--evidence-dir", str(ev),
                 "--artifacts-dir", str(art)])
    assert rc == 2 and not ev.exists()
    art.mkdir()
    (art / "old.csv").write_text("x")
    rc = R.main(["--mode", "real", "--run-start", "--evidence-dir", str(ev), "--artifacts-dir", str(art)])
    assert rc == 2 and not ev.exists()


def _no_read(*a, **k):
    raise AssertionError("nothing may be read")


B2_FAKE = "ab" * 32  # stands in for the B2 hash in tests (B2 is not committed yet)


def _sg_record(path, checks=None, b2=B2_FAKE, **extra):
    import json
    rec = {"checks": checks if checks is not None else {c: "PASS" for c in IO.SG_CHECKS}, "b2_sha256": b2, **extra}
    path.write_text(json.dumps(rec))
    return path


@pytest.fixture
def prereq(tmp_path, monkeypatch):
    """CLI arguments that satisfy check_prerequisites, with the git lookup stubbed (B1 and B2 'committed')."""
    monkeypatch.setattr(R, "committed_sha256", {IO.B1_PATH: IO.B1_SHA256, IO.B2_PATH: B2_FAKE}.get)
    rec = _sg_record(tmp_path / "sg_pass.json")
    return ["--b1-sha256", IO.B1_SHA256, "--b2-sha256", B2_FAKE, "--sg-record", str(rec)]


def test_real_mode_gate_failure_is_restartable_and_reads_nothing(tmp_path, monkeypatch, prereq):
    for name in ("load_structure", "load_lap_structure", "load_outcomes"):
        monkeypatch.setattr(IO, name, _no_read)
    monkeypatch.setattr(R, "calendar_2022_23", _no_read)
    ev, art = tmp_path / "ev", tmp_path / "art"
    rc = R.main(["--mode", "real", "--run-start", "--evidence-dir", str(ev), "--artifacts-dir", str(art)] + prereq,
                gate_fn=lambda: (False, ["check 1 pass table: FAIL"]))
    assert rc == 1
    led = IO.Ledger(ev)
    cur = led.current()
    assert cur.gate is False and not cur.run_start and not cur.decoded and cur.state == "FAILED_RESTARTABLE"
    assert "AssertionError" not in led.path.read_text()
    assert not art.exists()
    # restartable: a second start is allowed
    assert R.main(["--mode", "real", "--run-start", "--evidence-dir", str(ev), "--artifacts-dir", str(art)] + prereq,
                  gate_fn=lambda: (False, ["check 1 pass table: FAIL"])) == 1
    assert len(led.starts()) == 2


def _stub_real(monkeypatch, analyse):
    calls = []
    syn = R.synthetic_world()
    monkeypatch.setattr(IO, "load_structure", lambda *a, **k: (calls.append("structure"), syn.structure)[1])
    monkeypatch.setattr(IO, "load_lap_structure", lambda *a, **k: (calls.append("laps"), syn.team)[1])
    monkeypatch.setattr(R, "calendar_2022_23", lambda *a, **k: calls.append("calendar") or {})
    monkeypatch.setattr(A, "check_appendix_a", lambda *a, **k: calls.append("appendix"))
    monkeypatch.setattr(R, "read_release_expected", lambda *a, **k: None)

    def fake_outcomes(ledger, *a, **k):
        ledger.require_run_start()  # refuses unless gate PASS and RUN START
        calls.append("outcomes")
        ledger.outcome_decoded("seg_time_s", "x/pass_table_2022.parquet")
        return {}

    monkeypatch.setattr(IO, "load_outcomes", fake_outcomes)
    monkeypatch.setattr(R, "assemble_inputs", lambda *a, **k: syn)
    monkeypatch.setattr(R, "analyse", analyse)
    return calls


def test_real_mode_order_gate_runstart_decode_written(tmp_path, monkeypatch, prereq):
    res = R.Results(tables={"t": pd.DataFrame({"a": [1.0]})}, summary="GO/NO-GO: X\n", n_intervals=0,
                    verdict="X", line="GO/NO-GO: X")
    calls = _stub_real(monkeypatch, lambda *a, **k: res)
    ev, art = tmp_path / "ev", tmp_path / "art"
    rc = R.main(["--mode", "real", "--run-start", "--evidence-dir", str(ev), "--artifacts-dir", str(art)] + prereq,
                gate_fn=lambda: (True, ["check 1 pass table: PASS"]))
    assert rc == 0
    assert calls == ["structure", "calendar", "appendix", "laps", "outcomes"]
    events = [ln.split("  ")[1] for ln in (ev / "PROVENANCE.txt").read_text().splitlines()]
    order = [e for e in events if e in ("START", "GATE", "RUN START", "OUTCOME DECODED", "OUTCOME-DERIVED WRITTEN",
                                        "OUTPUT", "EXIT")]
    assert order[:5] == ["START", "GATE", "RUN START", "OUTCOME DECODED", "OUTCOME-DERIVED WRITTEN"]
    assert order[-1] == "EXIT" and "OUTPUT" in order
    rs = [ln for ln in (ev / "PROVENANCE.txt").read_text().splitlines() if ln.split("  ")[1] == "RUN START"][0]
    assert f"b1_sha256={IO.B1_SHA256}" in rs and f"b2_sha256={B2_FAKE}" in rs and "sg_record_sha256=" in rs
    assert (art / "SHA256SUMS").is_file() and IO.Ledger(ev).current().state == "COMPLETED"
    # one run: a second start is refused
    assert R.main(["--mode", "real", "--run-start", "--evidence-dir", str(ev),
                   "--artifacts-dir", str(tmp_path / "art2")] + prereq, gate_fn=lambda: (True, [])) == 1


def test_real_mode_exception_writes_type_file_line_only(tmp_path, monkeypatch, capsys, prereq):
    def boom(*a, **k):
        raise ValueError("secret 1.2345 outcome value")

    _stub_real(monkeypatch, boom)
    ev, art = tmp_path / "ev", tmp_path / "art"
    rc = R.main(["--mode", "real", "--run-start", "--evidence-dir", str(ev), "--artifacts-dir", str(art)] + prereq,
                gate_fn=lambda: (True, []))
    assert rc == 1
    text = (ev / "PROVENANCE.txt").read_text()
    err = capsys.readouterr().err
    assert "ValueError" in text and "secret" not in text and "1.2345" not in text and "secret" not in err
    cur = IO.Ledger(ev).current()
    assert cur.decoded and not cur.written and cur.state == "RUNNING" and not art.exists()


def test_calendar_opens_2022_23_schedule_only(tmp_path):
    for s in (2022, 2023, 2024):
        d = tmp_path / "schedule" / f"season={s}"
        d.mkdir(parents=True)
        pq.write_table(pa.table({"EventName": ["Bahrain Grand Prix"], "Location": ["Sakhir"],
                                 "EventDate": [pd.Timestamp(f"{s}-03-01")], "season": [s]}), d / "schedule.parquet")
    led = IO.Ledger(tmp_path / "ev")
    led.begin("t", "c", "i")
    cal = R.calendar_2022_23(tmp_path, led)
    assert set(cal) == {(2022, "bahrain_grand_prix"), (2023, "bahrain_grand_prix")}
    text = led.path.read_text()
    assert "season=2024" not in text and text.count("OPENED") == 2


def test_assemble_inputs_caps_coast_and_aligns():
    s = pd.DataFrame({"season": [2022, 2022], "race_id": ["2022_1"] * 2, "driver": ["A", "B"], "lap": [2, 2],
                      "corner_id": ["C1", "C1"]})
    key = IO.SIDECAR_KEY
    out = {"pass": s[key].iloc[::-1].assign(seg_start_t=[1.0, 2.0], seg_end_t=[3.0, 4.0], seg_time_s=[2.0, 2.1],
                                           min_speed_kph=[100.0, 101.0]),
           "sidecar": s[key].assign(exit_speed_kph=[150.0, 151.0], coast_time_s=[12.0, 1.0],
                                    partial_throttle_share=[0.1, 0.2]),
           "laps": pd.DataFrame({"race_id": ["2022_1"], "driver": ["A"], "lap": [2], "lap_time_s": [90.0]})}
    inp = R.assemble_inputs(s, out, None, None)
    assert list(inp.y["seg_time_s"]) == [2.1, 2.0] and inp.coast_capped == 1 and np.isnan(inp.coast.iloc[0])


# --------------------------------------------------------------------------- W14 and amendment B2 in the outputs


def _w14_cases(tmp_path):
    good = {c: "PASS" for c in IO.SG_CHECKS}
    ok_rec = _sg_record(tmp_path / "ok.json")
    return {
        "no b1": ["--b2-sha256", B2_FAKE, "--sg-record", str(ok_rec)],
        "wrong b1": ["--b1-sha256", "cd" * 32, "--b2-sha256", B2_FAKE, "--sg-record", str(ok_rec)],
        "no b2": ["--b1-sha256", IO.B1_SHA256, "--sg-record", str(ok_rec)],
        "b2 not committed": ["--b1-sha256", IO.B1_SHA256, "--b2-sha256", "ef" * 32, "--sg-record", str(ok_rec)],
        "no sg record": ["--b1-sha256", IO.B1_SHA256, "--b2-sha256", B2_FAKE],
        "sg record missing file": ["--b1-sha256", IO.B1_SHA256, "--b2-sha256", B2_FAKE, "--sg-record",
                                   str(tmp_path / "absent.json")],
        "sg fail": ["--b1-sha256", IO.B1_SHA256, "--b2-sha256", B2_FAKE, "--sg-record",
                    str(_sg_record(tmp_path / "f.json", checks={**good, "SG3": "FAIL"}))],
        "sg incomplete": ["--b1-sha256", IO.B1_SHA256, "--b2-sha256", B2_FAKE, "--sg-record",
                          str(_sg_record(tmp_path / "i.json", checks={c: "PASS" for c in IO.SG_CHECKS[:6]}))],
        "sg pre-fix": ["--b1-sha256", IO.B1_SHA256, "--b2-sha256", B2_FAKE, "--sg-record",
                       str(_sg_record(tmp_path / "pf.json", pre_fix=True))],
        "sg other b2": ["--b1-sha256", IO.B1_SHA256, "--b2-sha256", B2_FAKE, "--sg-record",
                        str(_sg_record(tmp_path / "ob.json", b2="12" * 32))],
    }


@pytest.mark.parametrize("case", ["no b1", "wrong b1", "no b2", "b2 not committed", "no sg record",
                                  "sg record missing file", "sg fail", "sg incomplete", "sg pre-fix", "sg other b2"])
def test_w14_real_mode_refuses_without_b1_b2_and_sg_pass_record(tmp_path, monkeypatch, capsys, case):
    """W14: real mode refuses (exit 2, no ledger, nothing read) unless the B1 and B2 hashes match the committed
    files and an SG1-SG7 pass record made under this B2 exists."""
    monkeypatch.setattr(R, "committed_sha256", {IO.B1_PATH: IO.B1_SHA256, IO.B2_PATH: B2_FAKE}.get)
    for name in ("load_structure", "load_lap_structure", "load_outcomes"):
        monkeypatch.setattr(IO, name, _no_read)
    monkeypatch.setattr(R, "calendar_2022_23", _no_read)
    ev, art = tmp_path / "ev", tmp_path / "art"
    rc = R.main(["--mode", "real", "--run-start", "--evidence-dir", str(ev), "--artifacts-dir", str(art)]
                + _w14_cases(tmp_path)[case], gate_fn=_no_read)
    assert rc == 2 and not ev.exists() and not art.exists()
    assert "REFUSED" in capsys.readouterr().err


def test_w14_recorded_b2_hash_must_match(tmp_path, monkeypatch, prereq):
    monkeypatch.setattr(IO, "B2_SHA256", "99" * 32)
    ev = tmp_path / "ev"
    rc = R.main(["--mode", "real", "--run-start", "--evidence-dir", str(ev), "--artifacts-dir", str(tmp_path / "a")]
                + prereq, gate_fn=_no_read)
    assert rc == 2 and not ev.exists()


def test_w14_committed_b1_hash_read_from_git():
    """B1 as committed at HEAD hashes to the recorded value (git show; read-only)."""
    h = R.committed_sha256(IO.B1_PATH)
    if h is None:
        pytest.skip("git or the committed B1 is not available")
    assert h == IO.B1_SHA256


def _nan_t_inputs():
    inp = R.synthetic_world()
    s = inp.structure
    m = (s["race_id"] == "2022_2") & (s["stint"] == 2.0) & s["driver"].isin(["D03", "D07"])
    s.loc[m, "tyre_life"] = np.nan
    return inp, m.to_numpy()


@pytest.fixture(scope="module")
def analysed_nan():
    saved = _set_all()
    inp, m = _nan_t_inputs()
    res = R.analyse(inp, R.synthetic_plan(6))
    _restore(saved)
    return inp, m, res


def test_b2_counts_in_outputs_and_ledger(analysed_nan, tmp_path, monkeypatch, prereq):
    """B2 (2): tyre_life_missing rows are counted in the outputs (support_rulings, lap-arm drops, carry-over
    counts, support table) and in the ledger's rulings line; the run still completes."""
    inp, m, res = analysed_nan
    p = A.prepare(inp.structure)
    rl = res.tables["support_rulings"]
    b2 = rl[rl["ruling"].str.startswith("B2")]
    free_n = int((m & p["free"].to_numpy() & ~p["racecraft"].to_numpy()).sum())
    fol_n = int((m & p["following"].to_numpy()).sum())
    got_free = b2[b2["ruling"] == "B2 tyre_life_missing free passes (step 1)"].set_index("outcome")["count"]
    assert got_free[A.TIME] == free_n > 0
    got_fol = b2[(b2["ruling"] == "B2 tyre_life_missing following passes") & (b2["outcome"] == A.TIME)]
    assert int(got_fol["count"].sum()) == fol_n > 0
    lapd = res.tables["lap_arm_drops"].iloc[0]
    assert lapd[A.TYRE_LIFE_MISSING + "_free"] > 0 and A.TYRE_LIFE_MISSING in lapd.index
    assert res.tables["tyre_carry_counts"].iloc[0]["free_laps_tyre_life_missing"] > 0
    assert int(res.tables["support_class_bin_W"][A.TYRE_LIFE_MISSING].sum()) == fol_n
    assert np.isfinite(res.tables["support_exposure_by_bin"]["mean_signed_tyre_age_distance"].dropna()).all()
    # the ledger's rulings line carries the B2 counts
    _stub_real(monkeypatch, lambda *a, **k: res)
    ev, art = tmp_path / "ev", tmp_path / "art"
    rc = R.main(["--mode", "real", "--run-start", "--evidence-dir", str(ev), "--artifacts-dir", str(art)] + prereq,
                gate_fn=lambda: (True, []))
    assert rc == 0
    line = [ln for ln in (ev / "PROVENANCE.txt").read_text().splitlines() if "  INFO  rulings" in ln][0]
    assert f"[B2 tyre_life_missing free passes (step 1)|all|{A.TIME}]={free_n}" in line
    assert "B2 tyre_life_missing following laps (lap arm)" in line


def test_b2_diagnostics_lap_step1_matches_lap_arm_with_nan_tyre_life():
    saved = _set_all()
    try:
        inp, _ = _nan_t_inputs()
        p = A.prepare(inp.structure)
        lap = L.lap_frame(p, inp.lap_times)
        arm = L.fit_lap_arm(lap)
        ls = D.lap_step1(lap)
        assert np.allclose(ls.tau, arm.tau, equal_nan=True) and np.array_equal(ls.valid, arm.valid)
        sc = C.carry_frame(lap)
        assert not sc.loc[~np.isfinite(sc["t"].to_numpy(float)), "carry_fit"].any()
        cf = C.fit_carry(sc)
        assert cf.counts["free_laps_tyre_life_missing"] == int(
            (sc["free_lap"] & ~np.isfinite(sc["t"].to_numpy(float))).sum()) > 0
    finally:
        _restore(saved)
