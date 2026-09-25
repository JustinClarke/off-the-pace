"""
Unit tests for the per-circuit weight-penalty calibration.

All tests run on synthetic first-stint lap panels. The synthetic laps have a
known pace-improvement slope so we can assert the fitter recovers a plausible
weight_penalty_factor and respects the prior guardrails (insufficient data,
deviation-too-large → retain prior). The F55 tests at the end run run_fit
against a throwaway synthetic warehouse file -- no real warehouse needed.
"""

import duckdb
import numpy as np
import pandas as pd
import pytest

from tasks.coefficients import fit_weight_penalty as W
from tasks.coefficients.fit_weight_penalty import (
    calibrate_circuit,
    MIN_CALIBRATION_LAPS,
    PRIOR_DEVIATION_THRESHOLD,
)


def make_first_stint_panel(
    circuit_key: str,
    n_laps: int,
    *,
    slope_s_per_lap: float = -0.05,
    base_residual: float = 0.0,
    noise_std: float = 0.01,
    seed: int = 0,
) -> pd.DataFrame:
    """Synthetic first-stint laps with pace_residual = lap_time - expected_compound.

    lap_time falls by ~slope_s_per_lap per lap (fuel burn-off → faster);
    expected_compound_pace_s is held at 0 so pace_residual == lap_time.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for lap in range(1, n_laps + 1):
        lt = base_residual + lap * slope_s_per_lap + rng.normal(0, noise_std)
        rows.append({
            "circuit_key": circuit_key,
            "lap_number": lap,
            "lap_time_s": lt,
            "expected_compound_pace_s": 0.0,
        })
    return pd.DataFrame(rows)


class TestCalibrateCircuit:
    def test_recovers_positive_factor(self):
        df = make_first_stint_panel("bahrain_grand_prix", n_laps=80, slope_s_per_lap=-0.05)
        # fuel_rate 1.6 kg/lap → wpf ≈ 0.05/1.6 ≈ 0.031
        out = calibrate_circuit(df, "bahrain_grand_prix", prior_wpf=0.030, fuel_rate=1.6)
        assert out["calibration_source"] == "first_stint_regression"
        assert out["weight_penalty_factor"] > 0
        assert out["calibration_flag"] == "OK"

    def test_insufficient_data_retains_prior(self):
        df = make_first_stint_panel("monaco", n_laps=MIN_CALIBRATION_LAPS - 1)
        out = calibrate_circuit(df, "monaco", prior_wpf=0.025, fuel_rate=1.6)
        assert out["calibration_flag"] == "INSUFFICIENT_DATA"
        assert out["weight_penalty_factor"] == 0.025
        assert out["calibration_source"] == "prior_insufficient_data"

    def test_large_deviation_flags_and_retains_prior(self):
        # Steep slope → measured wpf far from a tiny prior → REVIEW_REQUIRED.
        df = make_first_stint_panel("spa", n_laps=80, slope_s_per_lap=-0.20)
        out = calibrate_circuit(df, "spa", prior_wpf=0.010, fuel_rate=1.6)
        assert out["calibration_delta_pct"] / 100 > PRIOR_DEVIATION_THRESHOLD
        assert out["calibration_flag"] == "REVIEW_REQUIRED"
        # Adopts the prior, not the noisy measured value.
        assert out["weight_penalty_factor"] == 0.010

    def test_factor_has_floor(self):
        # Flat/positive slope → measured would be ≤ 0, but is floored at 0.005.
        df = make_first_stint_panel("flat", n_laps=80, slope_s_per_lap=0.0, noise_std=0.0)
        out = calibrate_circuit(df, "flat", prior_wpf=0.005, fuel_rate=1.6)
        assert out["measured_weight_penalty_factor"] >= 0.005


# ---------------------------------------------------------------------------
# F55 (WI-13): the slope is divided by the burn the fuel model applies
# ---------------------------------------------------------------------------

SPAIN = "spanish_grand_prix"
SEED_RATE = 1.9          # circuit_reference's hand-set constant for Spain
# int_lap_fuel_state's rate is the season's FIA limit over the scheduled laps
RATE = {2018: 105 / 66, 2024: 110 / 66, 2025: 110 / 55}
FUEL_SLOPE = -0.06       # s/lap of pace gained as the fuel burns, noise-free


def _warehouse(path, *, unpriced_lap: str | None = None) -> None:
    """Spain in three seasons, 5 drivers x 5 clean first-stint laps a race, plus a
    Monaco row in circuit_reference with no laps at all. Round 10 each season, so
    the fitter's race_to_track join resolves; stg_laps.circuit_key is the race id,
    as it is in the real staging model."""
    laps = []
    for season in RATE:
        race = f"{season}_10"
        for drv in ("AAA", "BBB", "CCC", "DDD", "EEE"):
            for lap in range(1, 6):
                laps.append({
                    "lap_id": f"{race}_{drv}_{lap}", "stint_id": f"{race}_{drv}_1",
                    "race_year": season, "race_id": race, "circuit_key": race,
                    "driver_id": drv, "lap_number": lap, "lap_in_stint": lap,
                    "age_in_stint": lap, "stint_number": 1, "compound": "MEDIUM",
                    "lap_time_s": 80.0 + FUEL_SLOPE * lap,
                    "fuel_consumption_rate_kg_per_lap": RATE[season],
                })
    laps = pd.DataFrame(laps)
    fuel = laps.loc[laps["lap_id"] != unpriced_lap, ["lap_id", "fuel_consumption_rate_kg_per_lap"]]
    circuit_reference = pd.DataFrame({
        "circuit_key": [SPAIN, "monaco_grand_prix"],
        "weight_penalty_factor": [0.035, 0.025],
        "fuel_consumption_rate_kg_per_lap": [SEED_RATE, 1.6],
    })
    con = duckdb.connect(str(path))
    con.register("laps_df", laps)
    con.register("fuel_df", fuel)
    con.register("ref_df", circuit_reference)
    con.execute("""
        CREATE TABLE int_stint_geometry AS
            SELECT stint_id, lap_id, lap_in_stint, age_in_stint, stint_number FROM laps_df;
        CREATE TABLE stg_laps AS
            SELECT lap_id, circuit_key, race_year, race_id, driver_id, compound, lap_number,
                   lap_time_s, TRUE AS is_valid_lap, FALSE AS is_safety_car_lap,
                   FALSE AS is_vsc_lap, FALSE AS is_pit_lap
            FROM laps_df;
        CREATE TABLE stg_weather (lap_id VARCHAR, rainfall_flag BOOLEAN, track_temp_c DOUBLE);
        CREATE TABLE int_compound_cliff_predicted AS
            SELECT lap_id, 0.0 AS expected_compound_pace_s FROM laps_df;
        CREATE TABLE race_to_track AS
            SELECT DISTINCT race_id, 'spanish_grand_prix' AS track_id FROM laps_df;
        CREATE TABLE int_lap_fuel_state AS SELECT * FROM fuel_df;
        CREATE TABLE circuit_reference AS SELECT * FROM ref_df;
    """)
    con.close()


@pytest.fixture
def fit(tmp_path, monkeypatch):
    """run_fit against a synthetic warehouse, recording the rate each call receives."""
    seen = {}
    real = W.calibrate_circuit

    def spy(lap_df, circuit_key, prior_wpf, fuel_rate):
        seen[circuit_key] = fuel_rate
        return real(lap_df, circuit_key, prior_wpf, fuel_rate)

    def run(seasons, circuits=None, **warehouse):
        db = tmp_path / "warehouse.duckdb"
        _warehouse(db, **warehouse)
        monkeypatch.setattr(W, "DB_PATH", db)
        monkeypatch.setattr(W, "calibrate_circuit", spy)
        return W.run_fit(seasons=seasons, circuits=circuits).set_index("circuit_key"), seen

    return run


class TestBurnRateIsTheFuelModels:
    def test_rate_passed_is_the_fuel_models_mean_for_the_circuit(self, fit):
        out, seen = fit(seasons=[2018, 2024])
        # int_lap_fuel_state's mean rate for Spain over the fitted seasons' laps
        model_rate = (RATE[2018] + RATE[2024]) / 2          # 1.6288 kg/lap
        assert seen[SPAIN] == pytest.approx(model_rate)
        # the seed constant is what the fitter used to divide by -- 17% high here
        assert seen[SPAIN] != pytest.approx(SEED_RATE, rel=0.01)
        # ...and the factor is the fuel slope over that burn: s/lap / (kg/lap) = s/kg
        assert out.loc[SPAIN, "measured_weight_penalty_factor"] == pytest.approx(
            -FUEL_SLOPE / model_rate, abs=1e-5)

    def test_only_the_fitted_seasons_laps_set_the_rate(self, fit):
        _, seen = fit(seasons=[2024, 2025])
        assert seen[SPAIN] == pytest.approx((RATE[2024] + RATE[2025]) / 2)

    def test_a_circuit_without_laps_keeps_its_prior_without_a_rate(self, fit):
        out, _ = fit(seasons=[2018, 2024])
        assert out.loc["monaco_grand_prix", "calibration_flag"] == "INSUFFICIENT_DATA"
        assert out.loc["monaco_grand_prix", "weight_penalty_factor"] == 0.025

    def test_an_unpriced_calibration_lap_stops_the_fit(self, fit):
        with pytest.raises(ValueError, match="no int_lap_fuel_state rate"):
            fit(seasons=[2018, 2024], unpriced_lap="2024_10_AAA_3")

    def test_calibrate_refuses_a_missing_rate(self):
        df = make_first_stint_panel("x", n_laps=80)
        with pytest.raises(ValueError, match="burn rate"):
            calibrate_circuit(df, "x", prior_wpf=0.03, fuel_rate=float("nan"))
