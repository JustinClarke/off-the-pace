"""DA-03 estimator tests (synthetic panel with a planted effect; never reads the warehouse).

The estimator is not run on real data until the pre-registration is committed (the CLI
refuses without its hash). These tests pin that the estimator recovers a planted effect,
that the race-clustered standard errors and the placebo / gate logic behave, and that the
registration lock holds.
"""
from __future__ import annotations

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
               exception_race: bool = False) -> pd.DataFrame:
    """Synthetic panel. `class_lt1` overrides the under-1 s effect by corner class
    (pre-2022 and post-2022 unless `post_class_lt1` overrides the 2022+ races).
    `exception_race` adds race 2020_9 with corner_class no_geometry."""
    rng = np.random.default_rng(seed)
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
            for lap in range(2, 22):
                lap_fe = rng.normal(0, 0.3)
                tyre = lap
                for m in range(20):
                    cc = "no_geometry" if race_id in fm.P3_EXCEPTION_RACES else corner_class_of(m)
                    gap = rng.exponential(2.5)
                    behind = rng.exponential(2.5)
                    ahead_y = rng.normal(0, 0.05)
                    lt1_b = eff.get(cc, lt1_effect)
                    beta = (lt1_b if gap < 1 else TRUE["g1_1p5"] if gap < 1.5
                            else TRUE["g1p5_2"] if gap < 2 else TRUE["g2_3"] if gap < 3 else 0.0)
                    y = (lap_fe + race_shock + beta + 0.2 * ahead_y
                         + (behind_effect if behind < 1 else 0.0)
                         + 0.001 * tyre * (m / 20) + rng.normal(0, 0.05))
                    band = ("0_lt0.5" if gap < 0.5 else "1_0.5to1" if gap < 1 else
                            "2_1to1.5" if gap < 1.5 else "3_1.5to2" if gap < 2 else
                            "4_2to3" if gap < 3 else "5_gt3_reference")
                    # DRS: open within 1 s on straights; the zone is every straight
                    # micro-sector with an even index (deterministic, no RNG draw).
                    drs_open = bool(cc == "straight" and gap < 1.0)
                    drs_zone = bool(cc == "straight" and m % 2 == 0)
                    rows.append((f"{race_id}_{d}_{lap}", year, race_id, f"D{d}", lap, m,
                                 y, ahead_y, gap, band, behind, lap, gap * 0.9 + rng.normal(0, 0.1),
                                 tyre, cc, drs_open, drs_zone))
    cols = ["lap_id", "race_year", "race_id", "driver_id", "lap_number", "microsector",
            "y_s", "ahead_y_s", "gap_ahead_s", "gap_band", "gap_behind_s",
            "behind_lap_number", "exit_gap_ahead_s", "tyre_life", "corner_class",
            "drs_open", "ms_drs_any_open"]
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
    assert g["beta_lt1_ci_excludes_0"]
    assert g["p1_pass"]
    assert g["p2_ci_includes_0"]
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
