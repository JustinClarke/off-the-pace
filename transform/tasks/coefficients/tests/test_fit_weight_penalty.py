"""
Unit tests for the per-circuit weight-penalty calibration.

All tests run on synthetic first-stint lap panels   no duckdb connection.
The synthetic laps have a known pace-improvement slope so we can assert the
fitter recovers a plausible weight_penalty_factor and respects the prior
guardrails (insufficient data, deviation-too-large → retain prior).
"""

import numpy as np
import pandas as pd

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
