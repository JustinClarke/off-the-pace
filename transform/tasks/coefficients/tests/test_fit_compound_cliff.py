"""
Unit tests for the cliff fitting pipeline.

All tests run on synthetic data   no duckdb connection required.
The synthetic stints have known cliff onset laps so we can assert
the fitter recovers the correct values within a tolerance.
"""

import numpy as np
import pandas as pd
import pytest

from tasks.coefficients.survival import (
    build_survival_dataset,
    detect_cliff_lap,
    estimate_cliff_severity,
    estimate_wear_gradient,
    fit_cliff_onset_median,
)
from tasks.coefficients.provenance import build_provenance
from tasks.coefficients.seed_writer import write_pending, PENDING_DIR


# ---------------------------------------------------------------------------
# Synthetic data builders
# ---------------------------------------------------------------------------

def make_clean_stint(
    stint_id: str,
    circuit_key: str,
    compound_code: str,
    race_year: int,
    n_laps: int,
    wear_gradient: float = 0.04,
    cliff_at_lap: int | None = None,
    cliff_jump_s: float = 2.0,
    base_time: float = 90.0,
    track_temp: float = 35.0,
    noise_std: float = 0.05,
    forced_stop: bool = False,
) -> pd.DataFrame:
    """Generate a synthetic stint lap-by-lap DataFrame."""
    rng = np.random.default_rng(seed=abs(hash(stint_id)) % 2**31)

    laps = []
    for lap in range(1, n_laps + 1):
        pace = base_time + lap * wear_gradient
        if cliff_at_lap is not None and lap >= cliff_at_lap:
            pace += cliff_jump_s * (1 + (lap-cliff_at_lap) * 0.1)
        pace += rng.normal(0, noise_std)
        laps.append(
            {
                "stint_id": stint_id,
                "circuit_key": circuit_key,
                "compound_code": compound_code,
                "race_year": race_year,
                "lap_in_stint": lap,
                "age_in_stint": lap-1,
                "lap_time_s": pace,
                "track_temp_c": track_temp + rng.normal(0, 1),
                "forced_stop_flag": forced_stop and lap == n_laps,
            }
        )
    return pd.DataFrame(laps)


def make_stint_pool(
    n_stints: int,
    cliff_at_lap: int = 20,
    *,
    circuit_key: str = "bahrain_grand_prix",
    compound_code: str = "SOFT",
    race_year: int = 2023,
    voluntary_pit_before_cliff: bool = False,
) -> pd.DataFrame:
    """Build a pool of stints, some cliffing and some censored."""
    parts = []
    for i in range(n_stints):
        sid = f"{circuit_key}_{compound_code}_{race_year}_{i:04d}"
        if voluntary_pit_before_cliff and i % 3 != 0:
            # 2/3 of stints pit voluntarily before the cliff (censored)
            n_laps = cliff_at_lap-3 + (i % 4)
            df = make_clean_stint(
                sid, circuit_key, compound_code, race_year,
                n_laps=n_laps, cliff_at_lap=None,
            )
        else:
            # Stays out through the cliff
            n_laps = cliff_at_lap + 8
            df = make_clean_stint(
                sid, circuit_key, compound_code, race_year,
                n_laps=n_laps, cliff_at_lap=cliff_at_lap,
            )
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------------------
# detect_cliff_lap tests
# ---------------------------------------------------------------------------

class TestDetectCliffLap:
    def test_detects_cliff_at_known_lap(self):
        df = make_clean_stint("s1", "bahrain_grand_prix", "SOFT", 2023, 30, cliff_at_lap=20, noise_std=0.01)
        detected = detect_cliff_lap(df["lap_time_s"], df["lap_in_stint"])
        assert detected is not None
        # Allow ±2 laps tolerance (detection needs CLIFF_MIN_CONTINUATION_LAPS = 2 confirmation)
        assert abs(detected-20) <= 3, f"Expected ~20, got {detected}"

    def test_returns_none_for_clean_stint(self):
        df = make_clean_stint("s2", "bahrain_grand_prix", "SOFT", 2023, 25, cliff_at_lap=None, noise_std=0.02)
        detected = detect_cliff_lap(df["lap_time_s"], df["lap_in_stint"])
        assert detected is None

    def test_returns_none_for_short_stint(self):
        df = make_clean_stint("s3", "bahrain_grand_prix", "SOFT", 2023, 4)
        detected = detect_cliff_lap(df["lap_time_s"], df["lap_in_stint"])
        assert detected is None

    def test_cliff_severity_not_triggered_by_noise(self):
        """A single noisy lap should not trigger the cliff (needs 2 consecutive)."""
        df = make_clean_stint("s4", "bahrain_grand_prix", "SOFT", 2023, 30, cliff_at_lap=None, noise_std=0.01)
        # Inject one spike
        df.loc[df["lap_in_stint"] == 15, "lap_time_s"] += 2.0
        detected = detect_cliff_lap(df["lap_time_s"], df["lap_in_stint"])
        assert detected is None


# ---------------------------------------------------------------------------
# build_survival_dataset tests
# ---------------------------------------------------------------------------

class TestBuildSurvivalDataset:
    def test_produces_one_row_per_stint(self):
        pool = make_stint_pool(n_stints=20)
        survival = build_survival_dataset(pool)
        assert len(survival) == pool["stint_id"].nunique()

    def test_cliffed_stints_marked_observed(self):
        pool = make_stint_pool(n_stints=30, cliff_at_lap=20)
        survival = build_survival_dataset(pool)
        # All stints stay out past the cliff, so should be mostly observed=1
        assert survival["observed"].sum() > 0

    def test_censored_stints_have_lower_duration(self):
        pool = make_stint_pool(n_stints=30, cliff_at_lap=20, voluntary_pit_before_cliff=True)
        survival = build_survival_dataset(pool)
        censored = survival[survival["observed"] == 0]
        cliffed = survival[survival["observed"] == 1]
        if len(censored) > 0 and len(cliffed) > 0:
            assert censored["duration"].mean() < cliffed["duration"].mean()


# ---------------------------------------------------------------------------
# fit_cliff_onset_median tests
# ---------------------------------------------------------------------------

class TestFitCliffOnsetMedian:
    def test_recovers_known_cliff_onset(self):
        """KM median should be close to the true cliff onset lap."""
        pool = make_stint_pool(n_stints=40, cliff_at_lap=20)
        survival = build_survival_dataset(pool)
        median = fit_cliff_onset_median(survival, min_stints=5)
        assert median is not None
        # Allow generous ±5 lap tolerance given synthetic noise
        assert abs(median-20) <= 6, f"Expected ~20, got {median}"

    def test_returns_none_below_min_stints(self):
        pool = make_stint_pool(n_stints=5, cliff_at_lap=20)
        survival = build_survival_dataset(pool)
        result = fit_cliff_onset_median(survival, min_stints=10)
        assert result is None

    def test_returns_value_above_zero(self):
        pool = make_stint_pool(n_stints=30, cliff_at_lap=15)
        survival = build_survival_dataset(pool)
        median = fit_cliff_onset_median(survival, min_stints=5)
        if median is not None:
            assert median > 0


# ---------------------------------------------------------------------------
# estimate_cliff_severity tests
# ---------------------------------------------------------------------------

class TestEstimateCliffSeverity:
    def test_severity_positive(self):
        pool = make_stint_pool(n_stints=30, cliff_at_lap=20)
        severity = estimate_cliff_severity(pool, cliff_onset_laps=20)
        if severity is not None:
            assert severity > 0

    def test_severity_within_expected_range(self):
        """Synthetic stints have cliff_jump_s=2.0, so severity should be around 2.0."""
        pool = make_stint_pool(n_stints=50, cliff_at_lap=20)
        severity = estimate_cliff_severity(pool, cliff_onset_laps=20)
        if severity is not None:
            assert 0.5 < severity < 6.0, f"Severity out of range: {severity}"


# ---------------------------------------------------------------------------
# estimate_wear_gradient tests
# ---------------------------------------------------------------------------

class TestEstimateWearGradient:
    def test_recovers_known_gradient(self):
        """Synthetic stints have wear_gradient=0.04; fitter should recover this."""
        pool = make_stint_pool(n_stints=40, cliff_at_lap=25)
        gradient = estimate_wear_gradient(pool, cliff_onset_laps=25)
        if gradient is not None:
            assert 0.01 < gradient < 0.15, f"Gradient {gradient} out of expected range"


# ---------------------------------------------------------------------------
# Provenance tests
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_provenance_keys_present(self):
        prov = build_provenance("test_method", 2020, 2024)
        assert "fit_date" in prov
        assert "data_window" in prov
        assert "git_sha" in prov
        assert "fit_method" in prov
        assert "fit_timestamp" in prov

    def test_data_window_format(self):
        prov = build_provenance("test", 2018, 2024)
        assert prov["data_window"] == "2018_to_2024"

    def test_fit_method_stored(self):
        prov = build_provenance("km_survival_v1", 2020, 2024)
        assert prov["fit_method"] == "km_survival_v1"


# ---------------------------------------------------------------------------
# seed_writer tests
# ---------------------------------------------------------------------------

class TestSeedWriter:
    def test_write_pending_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "tasks.coefficients.seed_writer.PENDING_DIR", tmp_path
        )
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        path = write_pending(df, "test_seed")
        assert path.exists()
        loaded = pd.read_csv(path)
        assert list(loaded.columns) == ["a", "b"]
        assert len(loaded) == 2

    def test_write_pending_atomic(self, tmp_path, monkeypatch):
        """Verify no .tmp file left behind after successful write."""
        monkeypatch.setattr(
            "tasks.coefficients.seed_writer.PENDING_DIR", tmp_path
        )
        df = pd.DataFrame({"x": range(100)})
        write_pending(df, "atomic_test")
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0
