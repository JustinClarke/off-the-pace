"""DA-03 estimator tests (synthetic panel with a planted effect; never reads the warehouse).

The estimator is not run on real data until the pre-registration is committed (the CLI
refuses without its hash). These tests pin that the estimator recovers a planted effect,
that the race-clustered standard errors and the placebo / gate logic behave, and that the
registration lock holds.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from tasks.coefficients import fit_dirty_air_microsector as fm

TRUE = {"lt1": 0.10, "g1_1p5": 0.05, "g1p5_2": 0.03, "g2_3": 0.01}


def corner_class_of(m: int) -> str:
    """Fixed synthetic map: micro-sector m gets one of the seven P3 classes."""
    return fm.P3_CLASSES[m % len(fm.P3_CLASSES)]


def make_panel(n_races: int = 12, seed: int = 7, behind_effect: float = 0.0,
               lt1_effect: float = 0.10, class_lt1: dict | None = None,
               post_class_lt1: dict | None = None,
               exception_race: bool = False, band_effects: dict | None = None,
               gap_floor_s: float = 0.0, entry_timing_noise_s: float = 0.0) -> pd.DataFrame:
    """Synthetic panel. `class_lt1` overrides the under-1 s effect by corner class
    (pre-2022 and post-2022 unless `post_class_lt1` overrides the 2022+ races).
    `exception_race` adds race 2020_9 with corner_class no_geometry.

    The true gap persists along the lap (a car close at boundary k - 1 is mostly still
    close at k), and lag_gap_ahead_s carries the recorded gap at k - 1 (NaN at the
    first boundary of each driver's race, as for lap 1 in the real panel).
    `entry_timing_noise_s` plants the shared-crossing error: each boundary crossing
    of the driver is recorded with an error e_k, so the recorded gap at k is
    true + e_k and the recorded micro-sector time is true - e_k + e_{k+1}."""
    rng = np.random.default_rng(seed)
    effects = TRUE if band_effects is None else band_effects
    rows = []
    races = [(2019 if r % 2 == 0 else 2023, f"{2019 if r % 2 == 0 else 2023}_{r}")
             for r in range(n_races)]
    if exception_race:
        races.append((2020, "2020_9"))
    for year, race_id in races:
        race_shock = rng.normal(0, 0.02)
        eff = (post_class_lt1 if (year >= fm.ERA_BREAK and post_class_lt1 is not None)
               else class_lt1) or {}
        for d in range(16):
            true_gap, prev_gap = None, np.nan
            e_next = rng.normal(0, entry_timing_noise_s) if entry_timing_noise_s else 0.0
            for lap in range(2, 22):
                lap_fe = rng.normal(0, 0.3)
                tyre = lap
                for m in range(20):
                    cc = "no_geometry" if race_id in fm.P3_EXCEPTION_RACES else corner_class_of(m)
                    if true_gap is None or rng.random() > 0.8:
                        true_gap = gap_floor_s + rng.exponential(2.5)
                    else:
                        true_gap = max(gap_floor_s, abs(true_gap + rng.normal(0, 0.2)))
                    e_k = e_next
                    e_next = rng.normal(0, entry_timing_noise_s) if entry_timing_noise_s else 0.0
                    gap = max(true_gap + e_k, 0.001)
                    behind = rng.exponential(2.5)
                    ahead_y = rng.normal(0, 0.05)
                    lt1_b = eff.get(cc, lt1_effect)
                    beta = (lt1_b if true_gap < 1 else effects["g1_1p5"] if true_gap < 1.5
                            else effects["g1p5_2"] if true_gap < 2
                            else effects["g2_3"] if true_gap < 3 else 0.0)
                    y = (lap_fe + race_shock + beta + 0.2 * ahead_y
                         + (behind_effect if behind < 1 else 0.0)
                         + 0.001 * tyre * (m / 20) + rng.normal(0, 0.05)
                         - e_k + e_next)
                    band = ("0_lt0.5" if gap < 0.5 else "1_0.5to1" if gap < 1 else
                            "2_1to1.5" if gap < 1.5 else "3_1.5to2" if gap < 2 else
                            "4_2to3" if gap < 3 else "5_gt3_reference")
                    # DRS: open within 1 s on straights; the zone is every straight
                    # micro-sector with an even index (deterministic, no RNG draw).
                    drs_open = bool(cc == "straight" and gap < 1.0)
                    drs_zone = bool(cc == "straight" and m % 2 == 0)
                    rows.append((f"{race_id}_{d}_{lap}", year, race_id, f"D{d}", lap, m,
                                 y, ahead_y, gap, band, behind, lap, gap * 0.9 + rng.normal(0, 0.1),
                                 tyre, cc, drs_open, drs_zone, prev_gap))
                    prev_gap = gap
    cols = ["lap_id", "race_year", "race_id", "driver_id", "lap_number", "microsector",
            "y_s", "ahead_y_s", "gap_ahead_s", "gap_band", "gap_behind_s",
            "behind_lap_number", "exit_gap_ahead_s", "tyre_life", "corner_class",
            "drs_open", "ms_drs_any_open", "lag_gap_ahead_s"]
    return fm.add_regressors(pd.DataFrame(rows, columns=cols))


# Planted mechanism: fast-corner loss in high, a tow (gain) in flat kinks and on
# straights, small loss in slow corners.
MECH = {"high": 0.15, "flat": -0.10, "low": 0.02, "medium": 0.08, "straight": -0.05,
        "link": 0.05, "mixed": 0.10}


@pytest.fixture(scope="module")
def result():
    return fm.fit_specs(make_panel())


def test_recovers_planted_band_effects(result):
    t = result["specs"]["lt1"]["terms"]
    for k, true in TRUE.items():
        assert t[k]["beta_s"] == pytest.approx(true, abs=0.02), k


def test_clustered_se_is_finite_and_estimate_within_5_se_of_truth(result):
    t = result["specs"]["lt1"]["terms"]["lt1"]
    assert t["se_s"] > 0 and np.isfinite(t["se_s"])
    assert t["ci_low_s"] < t["beta_s"] < t["ci_high_s"]
    # the planted effect is recovered to within 5 clustered standard errors
    assert abs(t["beta_s"] - TRUE["lt1"]) < 5 * t["se_s"]
    assert result["n_races"] == 12


def test_gate_passes_with_planted_effect_and_null_placebos(result):
    g = fm.evaluate_gates(result)
    assert g["beta_lt1_positive_ci_excludes_0"]
    # the two-sided beta_lt1_ci_excludes_0 is retired (it passed a negative interval)
    assert "beta_lt1_ci_excludes_0" not in g
    assert g["lag_gap_pass"]
    assert g["p1_pass"]
    assert g["p2_ci_includes_0"]
    # registered P2 (option (b)): pooled interval narrow and the shift small
    assert g["p2_precision_pass"]
    # P3 is estimated, never OWED. With one effect in every class, (a) passes but
    # (b) high minus low cannot, so P3 does not pass.
    assert "OWED" not in str(g)
    assert g["p3_status"] == "RUN"
    assert g["p3_a_pass"] and not g["p3_b_pass"] and not g["p3_pass"]


def test_p1_placebo_fails_when_following_confound_is_planted():
    # A close-racing effect that also hits the car BEHIND must show up in P1.
    res = fm.fit_specs(make_panel(behind_effect=0.10))
    g = fm.evaluate_gates(res)
    assert not g["p1_pass"]


def test_gate_fails_when_there_is_no_effect():
    res = fm.fit_specs(make_panel(lt1_effect=0.0, seed=11))
    # no planted lt1 effect: either the CI includes 0 or the estimate is ~0
    assert abs(res["specs"]["lt1"]["terms"]["lt1"]["beta_s"]) < 0.02


@pytest.fixture(scope="module")
def mech_result():
    return fm.fit_specs(make_panel(class_lt1=MECH, exception_race=True))


def test_p3_high_recovers_only_the_fast_corner_loss(mech_result):
    t = mech_result["specs"]["p3"]["terms"]
    for c, true in MECH.items():
        assert t[f"lt1__{c}"]["beta_s"] == pytest.approx(true, abs=0.02), c
    # the flat tow does not leak into high: high is the planted loss, not a blend
    assert t["lt1__high"]["beta_s"] == pytest.approx(MECH["high"], abs=0.02)
    c = mech_result["specs"]["p3"]["contrasts"]
    assert c["high_minus_low"]["beta_s"] == pytest.approx(MECH["high"] - MECH["low"], abs=0.03)
    assert c["flat_minus_straight"]["beta_s"] == pytest.approx(
        MECH["flat"] - MECH["straight"], abs=0.03)
    g = fm.evaluate_gates(mech_result)
    assert g["p3_a_pass"] and g["p3_b_pass"] and g["p3_pass"]


def test_p3_report_only_blocks_are_present_and_not_gated(mech_result):
    rep = fm.evaluate_gates(mech_result)["p3_report_only"]
    assert rep["gated"] is False
    for k in ("beta_lt1_flat", "flat_minus_straight", "beta_lt1_straight",
              "high_minus_straight"):
        assert rep[k] is not None and "beta_s" in rep[k], k
    assert rep["order_high_ge_medium_ge_low"] is True


def test_p3_drops_the_exception_races_from_p3_only(mech_result):
    p3 = mech_result["specs"]["p3"]
    assert p3["rows_dropped_exception_races"] == 16 * 20 * 20
    assert "no_geometry" not in p3["rows_by_class"]
    assert p3["n_races"] == 12 and mech_result["n_races"] == 13
    assert mech_result["specs"]["lt1"]["n_obs"] == p3["rows"] + p3["rows_dropped_exception_races"]
    assert "dr_cc" in p3["formula"] and "tyre__high" in p3["formula"]
    assert "C(micro)" not in p3["formula"]


@pytest.mark.parametrize("flat", [-0.40, 0.0, 0.40])
def test_flat_cannot_change_the_p3_verdict(flat):
    # Fast-corner loss planted: P3 passes whatever the flat class does.
    g = fm.evaluate_gates(fm.fit_specs(make_panel(class_lt1={**MECH, "flat": flat})))
    assert g["p3_pass"], flat
    # No fast-corner loss (high = low): P3 fails, and a big flat loss cannot rescue it.
    g = fm.evaluate_gates(fm.fit_specs(
        make_panel(class_lt1={**MECH, "high": MECH["low"], "flat": flat}, seed=3)))
    assert not g["p3_b_pass"] and not g["p3_pass"], flat


def test_p3_verdict_is_pooled_and_per_era():
    # The fast-corner loss holds pre-2022 only; post-2022 high has no loss at all.
    out = fm.run_panel(make_panel(class_lt1=MECH,
                                  post_class_lt1={**MECH, "high": 0.0}))
    by = out["p3_verdict"]["by_sample"]
    assert set(by) == {"pooled", "pre2022", "post2022"}
    assert by["pooled"] and by["pre2022"] and not by["post2022"]
    assert out["p3_verdict"]["pass"] is False
    for e in ("pre2022", "post2022"):
        assert out["eras"][e]["specs"]["p3"]["n_races"] == 6


def test_drs_specs_are_reported_and_cannot_move_p3(mech_result):
    s = mech_result["specs"]
    assert s["drs_closed"]["gated"] is False and s["drs_location"]["gated"] is False
    assert s["drs_closed"]["rows"] < mech_result["n_rows"]
    assert s["drs_location"]["rows"] < mech_result["n_rows"]
    g = fm.evaluate_gates(mech_result)
    assert set(g["drs_report_only"]) == {"drs_closed", "drs_location"}
    # P3 verdict is identical with the DRS specs removed
    stripped = {**mech_result, "specs": {k: v for k, v in s.items()
                                         if k not in ("drs_closed", "drs_location")}}
    g2 = fm.evaluate_gates(stripped)
    assert g2["p3_pass"] == g["p3_pass"]


def test_fit_is_refused_without_the_registered_hash(tmp_path, monkeypatch):
    prereg = tmp_path / "prereg.md"
    prereg.write_text("registered")
    monkeypatch.setattr(fm, "PREREG_PATH", prereg)
    assert fm.main(["--db", str(tmp_path / "none.duckdb")]) == 2
    assert fm.main(["--db", str(tmp_path / "none.duckdb"), "--prereg-sha256", "0" * 64]) == 2
    assert fm.sha256_of(prereg) == fm.sha256_of(prereg)


# Overall gate verdict: one mechanical PASS/FAIL across gates 1-5, pooled and per era.

@pytest.fixture(scope="module")
def mech_run():
    # 24 races (12 per era): with 6 races per era the synthetic P2 interval is wider
    # than the registered 0.008 s, so P2 would fail by imprecision in each era.
    return fm.run_panel(make_panel(n_races=24, class_lt1=MECH))


def test_gate_verdict_passes_when_every_registered_gate_passes(mech_run):
    v = mech_run["gate_verdict"]
    assert v["verdict"] == "PASS" and v["pass"] is True and v["failed"] == []
    expected = {f"{n}__{s}" for n, _ in fm.GATE_CHECKS
                for s in ("pooled", "pre2022", "post2022")} | {"no_sign_flip_by_era"}
    assert set(v["checks"]) == expected


def test_gate_verdict_fails_on_p3_in_one_era_only():
    out = fm.run_panel(make_panel(class_lt1=MECH, post_class_lt1={**MECH, "high": 0.0}))
    v = out["gate_verdict"]
    assert v["verdict"] == "FAIL" and "p3__post2022" in v["failed"]


def test_gate_verdict_fails_on_p1_confound():
    v = fm.run_panel(make_panel(class_lt1=MECH, behind_effect=0.10))["gate_verdict"]
    assert v["verdict"] == "FAIL" and any(k.startswith("p1__") for k in v["failed"])


def test_gate_verdict_fails_on_sign_flip_and_negative_beta():
    flip = {c: -0.10 for c in fm.P3_CLASSES}
    v = fm.run_panel(make_panel(class_lt1=MECH, post_class_lt1=flip))["gate_verdict"]
    assert v["verdict"] == "FAIL"
    assert "no_sign_flip_by_era" in v["failed"]
    # a negative interval excluding 0 is not a pass of gate 1
    assert "beta_lt1_positive__post2022" in v["failed"]


def test_gate_verdict_counts_a_missing_spec_as_fail(mech_run):
    stripped = {**mech_run, "pooled": {**mech_run["pooled"],
                                       "gates": {k: v for k, v in mech_run["pooled"]["gates"].items()
                                                 if k != "p2_precision_pass"}}}
    v = fm.gate_verdict(stripped)
    assert v["verdict"] == "FAIL" and v["failed"] == ["p2__pooled"]


def test_cli_prints_the_verdict_with_the_registered_hash(tmp_path, monkeypatch, capsys, mech_run):
    prereg = tmp_path / "prereg.md"
    prereg.write_text("registered")
    monkeypatch.setattr(fm, "PREREG_PATH", prereg)
    monkeypatch.setattr(fm, "prereg_lock_errors", lambda *a: [])
    monkeypatch.setattr(fm, "run", lambda db: dict(mech_run))
    out = tmp_path / "fit.json"
    assert fm.main(["--prereg-sha256", fm.sha256_of(prereg), "--out", str(out)]) == 0
    assert "DA-03 GATE VERDICT: PASS" in capsys.readouterr().err
    written = json.loads(out.read_text())
    assert written["gate_verdict"]["verdict"] == "PASS"
    assert written["prereg_sha256"] == fm.sha256_of(prereg)


# Lagged-gap check (DA-02P amendment, owner ruling 1 option (a)): the gap at boundary
# k - 1 shares no crossing with y (boundaries k and k + 1).

def test_lag_gap_is_a_separate_spec_and_the_primary_is_unchanged(result):
    lag, lt1 = result["specs"]["lag_gap"], result["specs"]["lt1"]
    assert set(lag["terms"]) == set(fm.LAG_BANDS) | {"ahead_y_s"}
    assert not set(fm.LT1_BANDS) & set(lag["terms"])
    # the primary keeps every row; lag_gap drops only the rows with no lagged gap
    # (the first boundary of each of 12 x 16 driver-races)
    assert lt1["n_obs"] == result["n_rows"]
    assert lag["rows"] == result["n_rows"] - 12 * 16
    # a persistent planted effect shows through the lagged gap, attenuated
    assert 0 < lag["terms"]["lag_lt1"]["beta_s"] < lt1["terms"]["lt1"]["beta_s"]


def test_entry_crossing_noise_passes_gate_1_but_not_the_lag_check():
    # No true effect at all and no true gap under 1 s. Only the shared entry-crossing
    # error puts rows under 1 s, and the same error makes y slower there.
    res = fm.fit_specs(make_panel(lt1_effect=0.0, band_effects=dict.fromkeys(TRUE, 0.0),
                                  gap_floor_s=1.05, entry_timing_noise_s=0.10, seed=5))
    g = fm.evaluate_gates(res)
    assert g["beta_lt1_positive_ci_excludes_0"]
    assert not g["lag_gap_pass"]
    lag = res["specs"]["lag_gap"]["terms"]["lag_lt1"]
    assert lag["ci_low_s"] <= 0 <= lag["ci_high_s"]


def test_gate_verdict_fails_on_the_lag_check_alone(mech_run):
    stripped = {**mech_run, "pooled": {**mech_run["pooled"],
                                       "gates": {**mech_run["pooled"]["gates"],
                                                 "lag_gap_pass": False}}}
    v = fm.gate_verdict(stripped)
    assert v["verdict"] == "FAIL" and v["failed"] == ["lag_gap__pooled"]


def test_load_panel_lags_the_gap_from_the_valid_boundary_directly_before(tmp_path):
    import duckdb

    db = tmp_path / "w.duckdb"
    con = duckdb.connect(str(db))
    # (driver, lap, microsector, gap_ahead_s, invalid_reason); 3 micro-sectors per lap
    rows = [("A", 1, 2, 0.4, "lap1"), ("A", 2, 0, 0.5, None), ("A", 2, 1, 0.6, None),
            ("A", 2, 2, 0.7, "wide_bracket"), ("A", 3, 0, 0.8, None),
            ("A", 3, 2, 0.9, None),  # A has no lap 3 micro-sector 1 row
            ("B", 2, 0, 1.2, None), ("B", 2, 1, 1.3, None), ("B", 2, 2, 1.4, None),
            ("B", 3, 0, 1.5, None)]
    con.execute("""CREATE TABLE int_microsector_proximity (
        microsector_id VARCHAR, lap_id VARCHAR, race_year INT, race_id VARCHAR,
        driver_id VARCHAR, lap_number INT, microsector INT, y_s DOUBLE, ahead_y_s DOUBLE,
        gap_ahead_s DOUBLE, gap_band VARCHAR, gap_behind_s DOUBLE, behind_lap_number INT,
        exit_gap_ahead_s DOUBLE, drs_open BOOLEAN, invalid_reason VARCHAR)""")
    for drv, lap, m, gap, why in rows:
        con.execute("INSERT INTO int_microsector_proximity VALUES "
                    "(?, ?, 2019, '2019_1', ?, ?, ?, 0.0, 0.0, ?, NULL, NULL, NULL, NULL, "
                    "FALSE, ?)",
                    [f"{drv}_{lap}_{m}", f"{drv}_{lap}", drv, lap, m, gap, why])
    con.execute("CREATE TABLE stg_laps (lap_id VARCHAR, tyre_life DOUBLE)")
    con.execute("CREATE TABLE int_microsector_corner_class (race_year INT, race_id VARCHAR,"
                " microsector INT, corner_class VARCHAR)")
    con.close()
    got = fm.load_panel(db).set_index("microsector_id")["lag_gap_ahead_s"]
    expected = {"A_2_0": None,   # m - 1 is a lap-1 row (invalid)
                "A_2_1": 0.5,
                "A_3_0": None,   # m - 1 (lap 2, micro-sector 2) is invalid
                "A_3_2": None,   # the row before is not boundary k - 1
                "B_2_0": None,   # no row before
                "B_2_1": 1.2, "B_2_2": 1.3,
                "B_3_0": 1.4}    # across the lap line
    assert set(got.index) == set(expected)
    for k, v in expected.items():
        assert (pd.isna(got[k]) if v is None else got[k] == pytest.approx(v)), k


# Registration lock: committed at HEAD, unchanged, and the hash recorded in the log.

def _git(repo, *a):
    import subprocess

    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c",
                    "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *a],
                   check=True, capture_output=True)


def _write_log(path, sha):
    item = {"id": fm.PREREG_LOG_ITEM, **({"prereg_sha256": sha} if sha else {})}
    path.write_text(json.dumps({"items": [{"id": "OTHER"}, item]}))


@pytest.fixture
def prereg_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "wi").mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "README").write_text("x\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-q", "-m", "init")
    prereg = repo / "wi" / "prereg.md"
    prereg.write_text("registered\n")
    return repo, prereg, tmp_path / "build-log.json"


def test_prereg_lock_needs_a_commit_and_the_logged_hash(prereg_repo):
    repo, prereg, log = prereg_repo
    sha = fm.sha256_of(prereg)
    _write_log(log, sha)
    errs = fm.prereg_lock_errors(prereg, log)
    assert len(errs) == 1 and "not committed at HEAD" in errs[0]
    _git(repo, "add", "wi/prereg.md")
    assert any("not committed" in e for e in fm.prereg_lock_errors(prereg, log))  # staged only
    _git(repo, "commit", "-q", "-m", "prereg")
    assert fm.prereg_lock_errors(prereg, log) == []
    _write_log(log, None)
    assert fm.prereg_lock_errors(prereg, log) == [
        f"build log item {fm.PREREG_LOG_ITEM} records no prereg_sha256"]
    _write_log(log, "0" * 64)
    errs = fm.prereg_lock_errors(prereg, log)
    assert len(errs) == 1 and "does not match" in errs[0]


def test_prereg_lock_fails_on_an_edit_after_the_commit(prereg_repo):
    repo, prereg, log = prereg_repo
    _git(repo, "add", "wi/prereg.md")
    _git(repo, "commit", "-q", "-m", "prereg")
    prereg.write_text("registered, then edited\n")
    _write_log(log, fm.sha256_of(prereg))  # even with the new hash logged
    errs = fm.prereg_lock_errors(prereg, log)
    assert len(errs) == 1 and "differs from its committed version" in errs[0]


def test_fit_is_refused_when_the_prereg_is_not_locked(tmp_path, monkeypatch, capsys):
    prereg = tmp_path / "prereg.md"  # not in a git work tree, no log
    prereg.write_text("registered")
    monkeypatch.setattr(fm, "PREREG_PATH", prereg)
    monkeypatch.setattr(fm, "BUILD_LOG_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(fm, "run", lambda db: pytest.fail("fit ran on an unlocked prereg"))
    assert fm.main(["--prereg-sha256", fm.sha256_of(prereg)]) == 2
    assert fm.main(["--check-prereg-lock"]) == 2


def test_check_prereg_lock_flag_reports_a_locked_file(prereg_repo, monkeypatch, capsys):
    repo, prereg, log = prereg_repo
    _git(repo, "add", "wi/prereg.md")
    _git(repo, "commit", "-q", "-m", "prereg")
    _write_log(log, fm.sha256_of(prereg))
    monkeypatch.setattr(fm, "PREREG_PATH", prereg)
    monkeypatch.setattr(fm, "BUILD_LOG_PATH", log)
    assert fm.main(["--check-prereg-lock"]) == 0
    assert capsys.readouterr().out.strip() == f"LOCKED {fm.sha256_of(prereg)}"


def _term(beta, lo, hi):
    return {"beta_s": beta, "ci_low_s": lo, "ci_high_s": hi}


def test_p2_option_b_numbers_are_set_and_gated_option_a_is_not():
    assert fm.P2_MAX_CI_WIDTH_S == 0.008
    assert fm.P2_MAX_SHARE_OF_BETA == pytest.approx(1 / 3)
    assert fm.GATE1_MIN_SHARE_OF_LAP_FIGURE is None
    assert fm.GATE1_LAP_FIGURE_S is None
    assert list(fm.GATE_CHECKS) == [
        ("beta_lt1_positive", "beta_lt1_positive_ci_excludes_0"), ("p1", "p1_pass"),
        ("p2", "p2_precision_pass"), ("p3", "p3_pass"), ("lag_gap", "lag_gap_pass")]
    assert fm.gate1_minimum_effect_check(_term(0.05, 0.03, 0.07)) is None


def test_p2_precision_check_passes_when_narrow_and_small():
    lt1 = _term(0.03, 0.02, 0.04)
    # width 0.006 s <= 0.008 s; |0.004| < 0.03 / 3 = 0.01; it excludes 0 and still passes
    assert fm.p2_precision_check(_term(0.004, 0.001, 0.007), lt1) is True
    assert fm.p2_precision_check(_term(-0.001, -0.004, 0.002), lt1) is True


def test_p2_precision_check_fails_when_interval_wider_than_0_008_s():
    lt1 = _term(0.03, 0.02, 0.04)
    # width 0.010 s > 0.008 s: includes 0 and the shift is ~0, but it is imprecise
    assert fm.p2_precision_check(_term(0.0, -0.005, 0.005), lt1) is False
    assert fm.p2_precision_check(None, lt1) is False


def test_p2_precision_check_fails_when_shift_exceeds_a_third_of_beta():
    lt1 = _term(0.03, 0.02, 0.04)
    # narrow (0.006 s) but |0.011| >= 0.03 / 3, either sign
    assert fm.p2_precision_check(_term(0.011, 0.008, 0.014), lt1) is False
    assert fm.p2_precision_check(_term(-0.011, -0.014, -0.008), lt1) is False
    # a missing beta(lt1) cannot be a pass
    assert fm.p2_precision_check(_term(0.001, -0.002, 0.004), None) is False


def test_gate_verdict_fails_p2_by_imprecision_on_a_small_panel():
    # 6 synthetic races per era: P2 ~0 and includes 0, but the era intervals are wider
    # than 0.008 s, so P2 fails there and passes pooled.
    out = fm.run_panel(make_panel(class_lt1=MECH))
    v = out["gate_verdict"]
    assert v["verdict"] == "FAIL"
    assert {"p2__pre2022", "p2__post2022"} <= set(v["failed"])
    assert "p2__pooled" not in v["failed"]
    for e in ("pre2022", "post2022"):
        g = out["eras"][e]["gates"]
        assert g["p2_ci_includes_0"] and g["p2_ci_width_s"] > fm.P2_MAX_CI_WIDTH_S


def test_gate1_minimum_effect_check_option_a():
    lt1 = _term(0.05, 0.03, 0.07)
    # per micro-sector bar = share x lap figure / 20 micro-sectors
    assert fm.gate1_minimum_effect_check(lt1, lap_figure_s=0.4, min_share=0.5,
                                         n_microsectors=20) is True    # 0.05 > 0.01
    assert fm.gate1_minimum_effect_check(lt1, lap_figure_s=4.0, min_share=0.5,
                                         n_microsectors=20) is False   # 0.05 < 0.10
    assert fm.gate1_minimum_effect_check(None, lap_figure_s=0.4, min_share=0.5) is False


def test_p2_precision_check_option_b():
    lt1 = _term(0.05, 0.03, 0.07)
    # (b1) width cap only
    assert fm.p2_precision_check(_term(0.0, -0.01, 0.01), lt1, max_ci_width_s=0.03) is True
    assert fm.p2_precision_check(_term(0.0, -0.05, 0.05), lt1, max_ci_width_s=0.03) is False
    # (b2) size relative to beta(lt1) only: a small, significant shift can pass
    assert fm.p2_precision_check(_term(0.004, 0.002, 0.006), lt1,
                                 max_share_of_beta=1 / 3) is True
    assert fm.p2_precision_check(_term(0.03, 0.02, 0.04), lt1,
                                 max_share_of_beta=1 / 3) is False
    # both set: both must hold
    assert fm.p2_precision_check(_term(0.004, -0.04, 0.048), lt1, max_ci_width_s=0.03,
                                 max_share_of_beta=1 / 3) is False
    # a missing spec is a FAIL, never a pass
    assert fm.p2_precision_check(None, lt1, max_ci_width_s=0.03) is False
