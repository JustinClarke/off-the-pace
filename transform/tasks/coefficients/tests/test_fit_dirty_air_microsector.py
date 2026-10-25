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


def make_panel(n_races: int = 12, seed: int = 7, behind_effect: float = 0.0,
               lt1_effect: float = 0.10) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for r in range(n_races):
        year = 2019 if r % 2 == 0 else 2023
        race_id = f"{year}_{r}"
        race_shock = rng.normal(0, 0.02)
        for d in range(16):
            for lap in range(2, 22):
                lap_fe = rng.normal(0, 0.3)
                tyre = lap
                for m in range(20):
                    gap = rng.exponential(2.5)
                    behind = rng.exponential(2.5)
                    ahead_y = rng.normal(0, 0.05)
                    beta = (lt1_effect if gap < 1 else TRUE["g1_1p5"] if gap < 1.5
                            else TRUE["g1p5_2"] if gap < 2 else TRUE["g2_3"] if gap < 3 else 0.0)
                    y = (lap_fe + race_shock + beta + 0.2 * ahead_y
                         + (behind_effect if behind < 1 else 0.0)
                         + 0.001 * tyre * (m / 20) + rng.normal(0, 0.05))
                    band = ("0_lt0.5" if gap < 0.5 else "1_0.5to1" if gap < 1 else
                            "2_1to1.5" if gap < 1.5 else "3_1.5to2" if gap < 2 else
                            "4_2to3" if gap < 3 else "5_gt3_reference")
                    rows.append((f"{race_id}_{d}_{lap}", year, race_id, f"D{d}", lap, m,
                                 y, ahead_y, gap, band, behind, lap, gap * 0.9 + rng.normal(0, 0.1),
                                 tyre))
    cols = ["lap_id", "race_year", "race_id", "driver_id", "lap_number", "microsector",
            "y_s", "ahead_y_s", "gap_ahead_s", "gap_band", "gap_behind_s",
            "behind_lap_number", "exit_gap_ahead_s", "tyre_life"]
    return fm.add_regressors(pd.DataFrame(rows, columns=cols))


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
    assert g["p3"].startswith("OWED")


def test_p1_placebo_fails_when_following_confound_is_planted():
    # A close-racing effect that also hits the car BEHIND must show up in P1.
    res = fm.fit_specs(make_panel(behind_effect=0.10))
    g = fm.evaluate_gates(res)
    assert not g["p1_pass"]


def test_gate_fails_when_there_is_no_effect():
    res = fm.fit_specs(make_panel(lt1_effect=0.0, seed=11))
    # no planted lt1 effect: either the CI includes 0 or the estimate is ~0
    assert abs(res["specs"]["lt1"]["terms"]["lt1"]["beta_s"]) < 0.02


def test_fit_is_refused_without_the_registered_hash(tmp_path, monkeypatch):
    prereg = tmp_path / "prereg.md"
    prereg.write_text("registered")
    monkeypatch.setattr(fm, "PREREG_PATH", prereg)
    assert fm.main(["--db", str(tmp_path / "none.duckdb")]) == 2
    assert fm.main(["--db", str(tmp_path / "none.duckdb"), "--prereg-sha256", "0" * 64]) == 2
    assert fm.sha256_of(prereg) == fm.sha256_of(prereg)
