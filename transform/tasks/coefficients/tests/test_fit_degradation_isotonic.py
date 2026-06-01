"""
Unit tests for the isotonic tyre-degradation fit + modulation coefficients.

All pure functions are tested on synthetic envelopes/panels   no duckdb.
Asserts: isotonic base is monotone (p50 non-decreasing, p10≤p50≤p90), the
dirty-air gate respects N_AIR_MIN / sign / clamp, and the temp penalty uses
the per-compound headroom table.
"""

import numpy as np
import pandas as pd

from tasks.coefficients.fit_degradation_isotonic import (
    fit_cell_isotonic,
    fit_isotonic_base,
    compute_dirty_air_mult,
    compute_temp_penalty,
    COMPOUND_HEADROOM_C,
    TEMP_PENALTY,
    DIRTY_AIR_MULT_MAX,
    N_AIR_MIN,
    N_FLOOR,
)


def make_cell(
    circuit_id="bahrain", era="post2022", compound="HARD",
    n_laps=25, *, noisy=False, n_obs=50, seed=0,
):
    """A single-cell envelope with a noisy-but-rising p50."""
    rng = np.random.default_rng(seed)
    rows = []
    for lap in range(1, n_laps + 1):
        base = 0.05 * lap
        jitter = rng.normal(0, 0.3) if noisy else 0.0
        p50 = base + jitter
        rows.append({
            "circuit_id": circuit_id, "era": era, "compound": compound,
            "lap_in_stint": lap, "n_observations": n_obs,
            "obs_deg_from_fresh_p10_s": p50 - 0.4,
            "obs_deg_from_fresh_p50_s": p50,
            "obs_deg_from_fresh_p90_s": p50 + 0.4,
        })
    return pd.DataFrame(rows)


class TestFitCellIsotonic:
    def test_p50_is_monotone(self):
        fitted = fit_cell_isotonic(make_cell(noisy=True, seed=3))
        diffs = fitted["p50_mono"].diff().dropna()
        assert (diffs >= -1e-9).all(), "p50 must be non-decreasing"

    def test_quantiles_ordered(self):
        fitted = fit_cell_isotonic(make_cell(noisy=True, seed=4))
        assert (fitted["p10_mono"] <= fitted["p50_mono"] + 1e-9).all()
        assert (fitted["p50_mono"] <= fitted["p90_mono"] + 1e-9).all()

    def test_thin_cell_below_floor_falls_back(self):
        # Only 1 lap above N_FLOOR → fewer than 2 → raw fallback path.
        cell = make_cell(n_laps=2)
        cell.loc[cell["lap_in_stint"] == 1, "n_observations"] = N_FLOOR - 1
        fitted = fit_cell_isotonic(cell)
        assert len(fitted) == 2  # still one row per lap, quantiles sorted


class TestFitIsotonicBase:
    def test_covers_all_cells_and_renames(self):
        env = pd.concat([
            make_cell(compound="HARD", seed=1),
            make_cell(compound="MEDIUM", seed=2),
        ], ignore_index=True)
        base = fit_isotonic_base(env)
        assert "obs_deg_from_fresh_p50_mono_s" in base.columns
        assert set(base["compound"]) == {"HARD", "MEDIUM"}


class TestComputeDirtyAirMult:
    def _iso_base(self):
        return fit_isotonic_base(make_cell(compound="HARD", n_laps=25, seed=5))

    def test_gate_passes_positive_contrast(self):
        iso = self._iso_base()
        air = pd.DataFrame([{
            "circuit_id": "bahrain", "era": "post2022", "compound": "HARD",
            "mean_deg_dirty": 0.30, "mean_deg_clean": 0.0,
            "n_dirty": N_AIR_MIN + 5, "n_clean": N_AIR_MIN + 5,
        }])
        out = compute_dirty_air_mult(air, iso)
        mult = out["dirty_air_deg_mult"].iloc[0]
        assert 1.0 < mult <= DIRTY_AIR_MULT_MAX

    def test_gate_fails_negative_contrast(self):
        iso = self._iso_base()
        air = pd.DataFrame([{
            "circuit_id": "bahrain", "era": "post2022", "compound": "HARD",
            "mean_deg_dirty": -0.1, "mean_deg_clean": 0.0,
            "n_dirty": N_AIR_MIN + 5, "n_clean": N_AIR_MIN + 5,
        }])
        out = compute_dirty_air_mult(air, iso)
        assert out["dirty_air_deg_mult"].iloc[0] == 1.0

    def test_gate_fails_thin_sample(self):
        iso = self._iso_base()
        air = pd.DataFrame([{
            "circuit_id": "bahrain", "era": "post2022", "compound": "HARD",
            "mean_deg_dirty": 0.30, "mean_deg_clean": 0.0,
            "n_dirty": N_AIR_MIN - 1, "n_clean": N_AIR_MIN + 5,
        }])
        out = compute_dirty_air_mult(air, iso)
        assert out["dirty_air_deg_mult"].iloc[0] == 1.0

    def test_clamped_to_max(self):
        iso = self._iso_base()
        air = pd.DataFrame([{
            "circuit_id": "bahrain", "era": "post2022", "compound": "HARD",
            "mean_deg_dirty": 10.0, "mean_deg_clean": 0.0,
            "n_dirty": N_AIR_MIN + 5, "n_clean": N_AIR_MIN + 5,
        }])
        out = compute_dirty_air_mult(air, iso)
        assert out["dirty_air_deg_mult"].iloc[0] == DIRTY_AIR_MULT_MAX


class TestComputeTempPenalty:
    def test_uses_compound_headroom_table(self):
        env = pd.concat([
            make_cell(compound="HARD"),
            make_cell(compound="SOFT"),
        ], ignore_index=True)
        out = compute_temp_penalty(env)
        by_compound = out.set_index("compound")["temp_headroom_c"]
        assert by_compound["HARD"] == COMPOUND_HEADROOM_C["HARD"]
        assert by_compound["SOFT"] == COMPOUND_HEADROOM_C["SOFT"]
        # Softs overheat sooner → smaller headroom.
        assert by_compound["SOFT"] < by_compound["HARD"]
        assert (out["temp_penalty_s_per_deg"] == TEMP_PENALTY).all()

    def test_unknown_compound_uses_fallback(self):
        env = make_cell(compound="EXOTIC")
        out = compute_temp_penalty(env)
        assert out["temp_headroom_c"].iloc[0] == COMPOUND_HEADROOM_C["_all"]
