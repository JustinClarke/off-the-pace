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


# DA-03F slow-corner follow-up (synthetic only): venue rule, blocking cut, verdict, lock.

def _races(rows):
    return pd.DataFrame(rows, columns=["race_id", "venue", "race_year"])


def test_venue_of_track_maps_one_off_events_to_their_venue():
    assert fm.venue_of_track("styrian_grand_prix") == "austria"
    assert fm.venue_of_track("austrian_grand_prix") == "austria"
    assert fm.venue_of_track("70th_anniversary_grand_prix") == "britain"
    assert fm.venue_of_track("british_grand_prix") == "britain"
    assert fm.venue_of_track("sakhir_grand_prix") == "bahrain"
    assert fm.venue_of_track("monaco_grand_prix") == "monaco_grand_prix"  # unlisted
    assert {fm.venue_of_track(t) for t in fm.VENUE_OF_TRACK} >= fm.FOLLOWUP_EXPECTED_VENUES


def test_venue_rule_keeps_full_venues_with_all_races_and_drops_a_missing_season():
    full = [(f"{y}_1", "austria", y) for y in fm.FOLLOWUP_SEASONS]
    extra = [("2020_2", "austria", 2020), ("2021_8", "austria", 2021)]  # Styrian
    gap = [(f"{y}_5", "monaco", y) for y in fm.FOLLOWUP_SEASONS if y != 2020]
    kept = fm.followup_venue_races(_races(full + extra + gap))
    assert set(kept["venue"]) == {"austria"}
    assert set(kept["race_id"]) == {r for r, _, _ in full + extra}
    assert len(kept) == 10


def test_followup_race_table_uses_race_to_track_and_refuses_unmapped_races():
    panel = pd.DataFrame({"race_id": ["2020_1", "2020_2", "2020_9"],
                          "race_year": [2020, 2020, 2020],
                          "corner_class": ["low", "high", "low"]})
    tracks = pd.DataFrame({"race_id": ["2020_1", "2020_2", "2020_9"],
                           "track_id": ["austrian_grand_prix", "styrian_grand_prix",
                                        "tuscan_grand_prix"]})
    t = fm.followup_race_table(panel, tracks)
    # 2020_9 is a P3 exception race: not a p3-sample race
    assert t.set_index("race_id")["venue"].to_dict() == {"2020_1": "austria",
                                                         "2020_2": "austria"}
    with pytest.raises(ValueError, match="no race_to_track row"):
        fm.followup_race_table(panel, tracks.iloc[:1])


def test_blocking_cut_keeps_only_ahead_at_or_quicker_than_median():
    d = pd.DataFrame({"ahead_y_s": [-0.2, 0.0, 0.01, 0.3],
                      "gap_band": ["0_lt0.5", "5_gt3_reference", "0_lt0.5", "4_2to3"],
                      "corner_class": ["low", "high", "low", "flat"]})
    assert fm.blocking_cut_mask(d).tolist() == [True, True, False, False]
    assert fm.apply_blocking_cut(d)["ahead_y_s"].tolist() == [-0.2, 0.0]


def test_blocking_cut_raises_on_a_missing_proxy():
    d = pd.DataFrame({"ahead_y_s": [-0.2, np.nan, 0.1]})
    with pytest.raises(fm.FollowupProxyMissing, match="1 valid rows"):
        fm.blocking_cut_mask(d)
    with pytest.raises(fm.FollowupProxyMissing):
        fm.apply_blocking_cut(d)


# One synthetic (D, lo, hi, T) per class, T = 0.03.
_CLS_NUMS = {"S": (0.10, 0.05, 0.15, 0.03),   # lo > 0 and D >= T
             "R": (0.00, -0.02, 0.02, 0.03),  # hi < T (not below 0)
             "N": (0.03, -0.01, 0.07, 0.03)}  # neither


def _sample(cls):
    D, lo, hi, T = _CLS_NUMS[cls]
    return {"D_s": D, "ci_low_s": lo, "ci_high_s": hi, "T_s": T}


def test_followup_sample_class_numbers():
    for cls, nums in _CLS_NUMS.items():
        assert fm.followup_sample_class(*nums) == cls
    # D >= T but lower bound not above 0: N; lower bound above 0 but D < T: N
    assert fm.followup_sample_class(0.05, -0.001, 0.10, 0.03) == "N"
    assert fm.followup_sample_class(0.02, 0.01, 0.04, 0.03) == "N"


@pytest.mark.parametrize("pattern", [(a, b, c) for a in "SRN" for b in "SRN" for c in "SRN"])
def test_followup_verdict_all_27_patterns_give_exactly_one_verdict(pattern):
    v = fm.followup_verdict(dict(zip(fm.FOLLOWUP_SAMPLES, map(_sample, pattern))))
    assert v["verdict"] in fm.FOLLOWUP_VERDICTS
    assert v["classes"] == dict(zip(fm.FOLLOWUP_SAMPLES, pattern))
    expected = ("PASS" if pattern == ("S", "S", "S") else
                "REFUTED" if "R" in pattern else "INCONCLUSIVE")
    assert v["verdict"] == expected
    # exactly one of the three rules holds for each pattern
    holds = [pattern == ("S", "S", "S"), "R" in pattern,
             "R" not in pattern and "N" in pattern]
    assert sum(holds) == 1
    assert v["label"] is None  # the R numbers here have an upper bound >= 0


def test_followup_verdict_reversed_label_and_not_run_paths():
    rev = {"D_s": -0.10, "ci_low_s": -0.15, "ci_high_s": -0.05, "T_s": 0.03}
    v = fm.followup_verdict({"pooled": _sample("S"), "pre2022": rev,
                             "post2022": _sample("N")})
    assert v["verdict"] == "REFUTED" and v["label"] == "reversed"
    ok = {n: _sample("S") for n in fm.FOLLOWUP_SAMPLES}
    for bad in (None, {"not_run": "no low corner rows"}, {"not_run": "crash: X"},
                {**_sample("S"), "D_s": float("nan")}, {"D_s": 0.1}):
        v = fm.followup_verdict({**ok, "post2022": bad})
        assert v["verdict"] == "NOT_RUN" and v["reason"].startswith("post2022"), bad
    assert fm.followup_verdict({"pooled": ok["pooled"]})["verdict"] == "NOT_RUN"


def test_followup_d_is_low_minus_high_with_the_interval_flipped():
    p3 = {"contrasts": {"high_minus_low": {"beta_s": -0.1, "se_s": 0.01,
                                           "ci_low_s": -0.12, "ci_high_s": -0.08}}}
    d = fm.followup_d(p3)
    assert d["D_s"] == pytest.approx(0.1)
    assert (d["ci_low_s"], d["ci_high_s"]) == pytest.approx((0.08, 0.12))
    assert fm.followup_d({"contrasts": {}}) is None and fm.followup_d(None) is None


def _followup_panel(class_lt1, dropped_venue=True):
    """Two venues held in every season 2018-2025 (one race each per season), plus a
    venue missing 2020. Races are make_panel races relabelled by year."""
    n = 16 + (2 if dropped_venue else 0)
    p = make_panel(n_races=n, class_lt1=class_lt1, seed=21)
    ids = sorted(p["race_id"].unique(), key=lambda r: int(r.split("_")[1]))
    years, tracks = {}, {}
    for i, r in enumerate(ids[:16]):
        years[r] = fm.FOLLOWUP_SEASONS[i % 8]
        tracks[r] = "austrian_grand_prix" if i < 8 else "spanish_grand_prix"
    for r, y in zip(ids[16:], (2019, 2023)):
        years[r], tracks[r] = y, "monaco_grand_prix"
    p = p.assign(race_year=p["race_id"].map(years))
    rt = pd.DataFrame({"race_id": list(tracks), "track_id": list(tracks.values())})
    return p, rt


def test_run_followup_panel_end_to_end_on_a_planted_slow_corner_loss():
    p, rt = _followup_panel({**MECH, "low": 0.25, "high": 0.02})
    out = fm.run_followup_panel(p, rt, expected_venues=frozenset({"austria", "spain"}))
    assert out["venues"] == ["austria", "spain"] and len(out["races"]) == 16
    assert out["rows_after_cut"] == int(((p["ahead_y_s"] <= 0)
                                         & p["race_id"].isin(out["races"])).sum())
    for n in fm.FOLLOWUP_SAMPLES:
        s = out["by_sample"][n]
        assert s["D_s"] == pytest.approx(0.23, abs=0.04), n
        assert s["T_s"] == pytest.approx(abs(s["beta_lt1"]["beta_s"]) / 3)
        # the registered specs ran unchanged on the restricted sample
        assert "dr_cc" in s["p3_spec"]["formula"]
        assert s["n_races"] == (16 if n == "pooled" else 8)
    assert out["followup_verdict"]["verdict"] == "PASS"
    # the registered venue list does not match this synthetic sample: NOT_RUN
    v = fm.run_followup_panel(p, rt)["followup_verdict"]
    assert v["verdict"] == "NOT_RUN" and "venue rule kept" in v["reason"]


def test_run_followup_panel_not_run_on_missing_proxy_or_missing_slow_rows():
    p, rt = _followup_panel(MECH, dropped_venue=False)
    bad = p.copy()
    bad.loc[bad.index[0], "ahead_y_s"] = np.nan
    v = fm.run_followup_panel(bad, rt, expected_venues=None)["followup_verdict"]
    assert v["verdict"] == "NOT_RUN" and v["reason"].startswith("missing proxy")
    no_low = p[p["corner_class"] != "low"]
    out = fm.run_followup_panel(no_low, rt, expected_venues=None)
    assert out["followup_verdict"]["verdict"] == "NOT_RUN"
    assert out["by_sample"]["pooled"] == {"not_run": "no low corner rows"}


def _write_followup_log(path, sha, **extra):
    items = [{"id": fm.PREREG_LOG_ITEM, "prereg_sha256": "f" * 64},
             {"id": fm.FOLLOWUP_LOG_ITEM, **({"prereg_sha256": sha} if sha else {}),
              **extra}]
    path.write_text(json.dumps({"items": items, "history": []}))


def test_followup_lock_needs_the_da03f_hash_and_no_recorded_run(prereg_repo):
    repo, prereg, log = prereg_repo
    _git(repo, "add", "wi/prereg.md")
    _git(repo, "commit", "-q", "-m", "prereg")
    sha = fm.sha256_of(prereg)
    _write_followup_log(log, sha)
    assert fm.followup_lock_errors(prereg, log) == []
    # the DA-02P lock is unchanged: it reads DA-02P, whose hash differs
    assert any("DA-02P.prereg_sha256" in e for e in fm.prereg_lock_errors(prereg, log))
    _write_followup_log(log, None)
    assert fm.followup_lock_errors(prereg, log) == [
        "build log item DA-03F records no prereg_sha256"]
    _write_followup_log(log, "0" * 64)
    assert any("DA-03F.prereg_sha256" in e for e in fm.followup_lock_errors(prereg, log))
    _write_followup_log(log, sha, run_recorded=True)
    errs = fm.followup_lock_errors(prereg, log)
    assert len(errs) == 1 and "already records a run" in errs[0]
    log.write_text(json.dumps({"items": [{"id": "DA-03F", "prereg_sha256": sha}],
                               "history": [{"run_recorded": "DA-03F"}]}))
    assert any("already records a run" in e for e in fm.followup_lock_errors(prereg, log))


def test_da02p_lock_ignores_the_followup_item(prereg_repo):
    repo, prereg, log = prereg_repo
    _git(repo, "add", "wi/prereg.md")
    _git(repo, "commit", "-q", "-m", "prereg")
    sha = fm.sha256_of(prereg)
    log.write_text(json.dumps({"items": [
        {"id": fm.PREREG_LOG_ITEM, "prereg_sha256": sha},
        {"id": fm.FOLLOWUP_LOG_ITEM, "prereg_sha256": "0" * 64, "run_recorded": True}]}))
    assert fm.PREREG_LOG_ITEM == "DA-02P"
    assert fm.prereg_lock_errors(prereg, log) == []
    assert fm.prereg_lock_errors(prereg, log, log_item=fm.PREREG_LOG_ITEM) == []


def test_followup_cli_refuses_without_the_matching_hash(tmp_path, monkeypatch):
    prereg = tmp_path / "DA-03F-preregistration.md"
    prereg.write_text("follow-up registered")
    monkeypatch.setattr(fm, "FOLLOWUP_PREREG_PATH", prereg)
    monkeypatch.setattr(fm, "followup_lock_errors", lambda *a: [])
    monkeypatch.setattr(fm, "run_followup", lambda db: pytest.fail("ran without hash"))
    monkeypatch.setattr(fm, "run", lambda db: pytest.fail("DA-03 fit ran in follow-up mode"))
    assert fm.main(["--followup"]) == 2
    assert fm.main(["--followup", "--prereg-sha256", "0" * 64]) == 2
    # the DA-03 file's hash is not the follow-up's
    assert fm.main(["--followup", "--prereg-sha256", fm.sha256_of(fm.PREREG_PATH)]) == 2


def test_followup_cli_refuses_when_locked_errors_and_runs_when_locked(
        tmp_path, monkeypatch, capsys):
    prereg = tmp_path / "DA-03F-preregistration.md"
    prereg.write_text("follow-up registered")
    sha = fm.sha256_of(prereg)
    monkeypatch.setattr(fm, "FOLLOWUP_PREREG_PATH", prereg)
    monkeypatch.setattr(fm, "run", lambda db: pytest.fail("DA-03 fit ran in follow-up mode"))
    monkeypatch.setattr(fm, "followup_lock_errors",
                        lambda *a: ["build log item DA-03F already records a run"])
    monkeypatch.setattr(fm, "run_followup", lambda db: pytest.fail("ran after a run"))
    assert fm.main(["--followup", "--prereg-sha256", sha]) == 2
    assert fm.main(["--followup", "--check-prereg-lock"]) == 2
    monkeypatch.setattr(fm, "followup_lock_errors", lambda *a: [])
    monkeypatch.setattr(fm, "run_followup", lambda db: {
        "followup_verdict": {"verdict": "INCONCLUSIVE", "label": None, "reason": None}})
    out = tmp_path / "f.json"
    assert fm.main(["--followup", "--prereg-sha256", sha, "--out", str(out)]) == 0
    assert "DA-03F VERDICT: INCONCLUSIVE" in capsys.readouterr().err
    assert json.loads(out.read_text())["prereg_sha256"] == sha
    monkeypatch.setattr(fm, "run_followup", lambda db: {
        "followup_verdict": {"verdict": "NOT_RUN", "label": None, "reason": "crash"}})
    assert fm.main(["--followup", "--prereg-sha256", sha, "--out", str(out)]) == 3


def test_followup_cli_without_its_prereg_file_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(fm, "FOLLOWUP_PREREG_PATH", tmp_path / "absent.md")
    assert fm.main(["--followup", "--prereg-sha256", "0" * 64]) == 2
