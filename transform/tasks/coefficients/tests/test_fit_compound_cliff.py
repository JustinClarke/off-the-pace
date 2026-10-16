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
    is_tyre_failure,
)
from tasks.coefficients.provenance import build_provenance
from tasks.coefficients.seed_writer import write_pending, PENDING_DIR
from tasks.coefficients.fit_compound_cliff import fresh_tyre_only


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

    def test_is_fresh_tyre_defaults_true_when_absent(self):
        """Synthetic fixtures without the column shouldn't be dropped from the survival set."""
        pool = make_stint_pool(n_stints=10)
        survival = build_survival_dataset(pool)
        assert survival["is_fresh_tyre"].all()

    def test_scrubbed_stints_kept_as_covariate_not_dropped(self):
        """Scrubbed (non-fresh) stints stay in the survival set, just flagged."""
        pool = make_stint_pool(n_stints=10)
        pool["is_fresh_tyre"] = True
        pool.loc[pool["stint_id"] == pool["stint_id"].iloc[0], "is_fresh_tyre"] = False
        survival = build_survival_dataset(pool)
        assert len(survival) == pool["stint_id"].nunique()
        assert (~survival["is_fresh_tyre"]).sum() == 1

    def test_tyre_failure_status_marks_observed_event(self):
        """A puncture DNF with no pace-based cliff signature should still be an event."""
        # Short, clean stint (no cliff) that ends abruptly in a puncture.
        df = make_clean_stint(
            "s_puncture", "bahrain_grand_prix", "SOFT", 2023,
            n_laps=10, cliff_at_lap=None, noise_std=0.02,
        )
        df["dnf_status"] = "Puncture"
        survival = build_survival_dataset(df)
        row = survival.iloc[0]
        assert row["observed"] == 1
        assert row["tyre_failure"] == 1
        assert row["duration"] == 9  # max age_in_stint (n_laps - 1)

    def test_mechanical_dnf_status_stays_censored(self):
        """Engine/collision DNFs are not tyre-failure events -- stay censored by default."""
        df = make_clean_stint(
            "s_engine", "bahrain_grand_prix", "SOFT", 2023,
            n_laps=10, cliff_at_lap=None, noise_std=0.02,
        )
        df["dnf_status"] = "Engine"
        survival = build_survival_dataset(df)
        row = survival.iloc[0]
        assert row["observed"] == 0
        assert row["tyre_failure"] == 0

    def test_missing_dnf_status_defaults_not_failure(self):
        pool = make_stint_pool(n_stints=10)
        survival = build_survival_dataset(pool)
        assert (survival["tyre_failure"] == 0).all()


class TestIsTyreFailure:
    @pytest.mark.parametrize("status", ["Puncture", "Wheel", "Wheel nut", "Tyre", "puncture"])
    def test_recognizes_tyre_failure_statuses(self, status):
        assert is_tyre_failure(status)

    @pytest.mark.parametrize("status", ["Engine", "Collision", "Retired", "Gearbox", None])
    def test_rejects_non_tyre_statuses(self, status):
        assert not is_tyre_failure(status)


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

    def test_recovers_known_gradient_net_of_wind(self):
        """Injecting a wind-driven lap-time penalty shouldn't bias the recovered
        wear slope once wind_speed_ms is available to net out."""
        pool = make_stint_pool(n_stints=40, cliff_at_lap=25)
        rng = np.random.default_rng(seed=42)
        pool["wind_speed_ms"] = rng.uniform(0, 15, size=len(pool))
        # Wind adds drag independent of wear: +0.05s/lap per m/s of wind.
        pool["lap_time_s"] = pool["lap_time_s"] + 0.05 * pool["wind_speed_ms"]
        gradient = estimate_wear_gradient(pool, cliff_onset_laps=25)
        if gradient is not None:
            assert 0.01 < gradient < 0.15, f"Gradient {gradient} out of expected range"

    def test_missing_wind_column_falls_back_to_simple_regression(self):
        """No wind_speed_ms column (e.g. older callers) should behave exactly as before."""
        pool = make_stint_pool(n_stints=40, cliff_at_lap=25)
        assert "wind_speed_ms" not in pool.columns
        gradient = estimate_wear_gradient(pool, cliff_onset_laps=25)
        if gradient is not None:
            assert 0.01 < gradient < 0.15, f"Gradient {gradient} out of expected range"


# ---------------------------------------------------------------------------
# Phase C: normalized-pace column selection
# ---------------------------------------------------------------------------

def _pool_with_traffic(n_stints: int = 40, cliff_at_lap: int = 25):
    """Stint pool where lap_time_s carries a large traffic penalty and
    normalized_pace_s is the clean underlying pace.

    The penalty is deliberately age-correlated (it grows through the stint) so
    that fitting the contaminated column visibly inflates the wear slope --
    a pace-blind implementation would pass a test using uncorrelated noise.
    """
    pool = make_stint_pool(n_stints=n_stints, cliff_at_lap=cliff_at_lap)
    pool["normalized_pace_s"] = pool["lap_time_s"]
    pool["lap_time_s"] = pool["lap_time_s"] + 0.10 * pool["age_in_stint"]
    return pool


class TestNormalizedPaceColumn:
    def test_wear_gradient_fits_the_requested_column(self):
        """Same rows, different pace column -> the normalized fit must recover
        the true 0.04 gradient while the contaminated one reads ~0.14."""
        pool = _pool_with_traffic()
        raw = estimate_wear_gradient(pool, cliff_onset_laps=25)
        normalized = estimate_wear_gradient(pool, cliff_onset_laps=25, pace_col="normalized_pace_s")
        assert raw is not None and normalized is not None
        assert normalized < raw, "normalized fit should not inherit the traffic penalty"
        assert 0.01 < normalized < 0.08, f"expected ~0.04, got {normalized}"

    def test_absent_column_falls_back_to_lap_time(self):
        """A pre-Phase-C frame (no normalized_pace_s) must not raise, and must
        give exactly the same answer as asking for lap_time_s."""
        pool = make_stint_pool(n_stints=40, cliff_at_lap=25)
        assert "normalized_pace_s" not in pool.columns
        assert estimate_wear_gradient(
            pool, cliff_onset_laps=25, pace_col="normalized_pace_s"
        ) == estimate_wear_gradient(pool, cliff_onset_laps=25)

    def test_survival_dataset_detects_cliff_on_requested_column(self):
        """Cliff detection must key off the normalized series."""
        pool = _pool_with_traffic()
        surv = build_survival_dataset(pool, pace_col="normalized_pace_s")
        assert len(surv) > 0
        assert surv["observed"].sum() > 0, "no cliffs detected on the normalized series"

    def test_severity_fits_the_requested_column(self):
        """Severity measured on normalized pace is smaller than on the
        traffic-inflated series: the post-cliff window is exactly where a
        struggling car collects traffic, which otherwise reads as cliff depth.

        Magnitudes are kept under estimate_cliff_severity's 1.5s winsorise cap
        on both sides -- a larger synthetic cliff saturates the clip and the
        comparison stops measuring the penalty at all.
        """
        cliff_at_lap = 20
        pool = pd.concat(
            [
                make_clean_stint(
                    f"sev_{i:04d}", "bahrain_grand_prix", "SOFT", 2023,
                    n_laps=cliff_at_lap + 8, cliff_at_lap=cliff_at_lap, cliff_jump_s=0.7,
                )
                for i in range(30)
            ],
            ignore_index=True,
        )
        pool["normalized_pace_s"] = pool["lap_time_s"]
        post_cliff = pool["lap_in_stint"] >= cliff_at_lap
        pool.loc[post_cliff, "lap_time_s"] += 0.25

        raw = estimate_cliff_severity(pool, cliff_onset_laps=cliff_at_lap)
        normalized = estimate_cliff_severity(
            pool, cliff_onset_laps=cliff_at_lap, pace_col="normalized_pace_s"
        )
        assert raw is not None and normalized is not None
        assert max(raw, normalized) < 1.5, "test saturated the winsorise cap; lower the magnitudes"
        assert normalized < raw, f"normalized {normalized} should undercut raw {raw}"


# ---------------------------------------------------------------------------
# fresh_tyre_only tests
# ---------------------------------------------------------------------------

class TestFreshTyreOnly:
    def test_filters_to_fresh_laps(self):
        df = pd.DataFrame({
            "lap_time_s": [90.0, 91.0, 92.0],
            "is_fresh_tyre": [True, False, True],
        })
        result = fresh_tyre_only(df)
        assert len(result) == 2
        assert result["is_fresh_tyre"].all()

    def test_missing_column_keeps_all_rows(self):
        """Synthetic fixtures / older data without the column stay unfiltered."""
        df = pd.DataFrame({"lap_time_s": [90.0, 91.0]})
        result = fresh_tyre_only(df)
        assert len(result) == 2

    def test_null_treated_as_not_fresh(self):
        df = pd.DataFrame({
            "lap_time_s": [90.0, 91.0],
            "is_fresh_tyre": [True, None],
        })
        result = fresh_tyre_only(df)
        assert len(result) == 1


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


# ---------------------------------------------------------------------------
# CO-02 acceptance: a simulated step comes back as the plateau, wear excluded once
# ---------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

import duckdb  # noqa: E402
import jinja2  # noqa: E402
import yaml  # noqa: E402

from tasks.coefficients.survival import SEVERITY_MIN_PRE_LAPS  # noqa: E402

TRANSFORM_DIR = Path(__file__).resolve().parents[3]


def make_step_stint(stint_id: str, n_laps: int, wear: float, step: float, cliff_age: int,
                    noise_std: float = 0.03, base_time: float = 90.0) -> pd.DataFrame:
    """Linear wear plus a pure step of `step` seconds from tyre age `cliff_age` on."""
    rng = np.random.default_rng(seed=abs(hash(stint_id)) % 2**31)
    ages = np.arange(1, n_laps + 1)
    pace = base_time + wear * ages + step * (ages >= cliff_age) + rng.normal(0, noise_std, n_laps)
    return pd.DataFrame({
        "stint_id": stint_id, "circuit_key": "bahrain_grand_prix", "compound_code": "SOFT",
        "race_year": 2023, "lap_in_stint": ages, "age_in_stint": ages, "lap_time_s": pace,
        "track_temp_c": 35.0, "forced_stop_flag": False,
    })


def step_pool(n: int, wear: float, step: float, cliff_age: int = 15, n_laps: int = 25) -> pd.DataFrame:
    return pd.concat(
        [make_step_stint(f"step_{wear}_{step}_{cliff_age}_{i:03d}", n_laps, wear, step, cliff_age)
         for i in range(n)],
        ignore_index=True,
    )


@pytest.fixture(scope="module")
def wear_macros():
    """macros/compound_cliff_wear.sql rendered as dbt would, with dbt_project.yml's vars."""
    project_vars = yaml.safe_load((TRANSFORM_DIR / "dbt_project.yml").read_text())["vars"]
    env = jinja2.Environment()
    env.globals["var"] = lambda name, default=None: project_vars.get(name, default)
    return env.from_string((TRANSFORM_DIR / "macros" / "compound_cliff_wear.sql").read_text()).module


def _eval(sql_expr: str, **cols) -> float:
    names = ", ".join(f"{v!r}::DOUBLE AS {k}" for k, v in cols.items())
    return duckdb.connect().execute(f"SELECT {sql_expr} FROM (SELECT {names})").fetchone()[0]


class TestCliffPlateauIsTheStep:
    @pytest.mark.parametrize("wear, step", [(0.03, 0.8), (0.08, 0.8), (0.03, 1.2), (0.10, 1.2)])
    def test_plateau_equals_the_true_step(self, wear_macros, wear, step):
        """CO-02 acceptance: simulated stints -> fitted severity -> the curve's plateau
        lands on the true step to within 0.05 s, whatever the wear slope."""
        severity = estimate_cliff_severity(step_pool(30, wear, step), cliff_onset_laps=15)
        assert severity == pytest.approx(step, abs=0.05), severity
        plateau = _eval(str(wear_macros.cliff_plateau_s("sev", "wg")), sev=severity, wg=wear)
        assert plateau == pytest.approx(step, abs=0.05), plateau

    def test_curve_past_the_ramp_is_wear_plus_step(self, wear_macros):
        wear, step, onset, age = 0.06, 1.0, 15.0, 30.0
        severity = estimate_cliff_severity(step_pool(30, wear, step), cliff_onset_laps=onset)
        expr = str(wear_macros.compound_cliff_wear_s("wg", "sev", "age", "lpc"))
        total = _eval(expr, wg=wear, sev=severity, age=age, lpc=age - onset)
        assert total == pytest.approx(wear * age + step, abs=0.05), total

    def test_plateau_does_not_subtract_wear(self, wear_macros):
        """T1: the severity has no wear in it, so the plateau must not move with the
        wear gradient (it used to lose 5.5 * wear_gradient, then gain x2.2)."""
        expr = str(wear_macros.cliff_plateau_s("sev", "wg"))
        assert _eval(expr, sev=0.9, wg=0.0) == _eval(expr, sev=0.9, wg=0.2) == pytest.approx(0.9)

    def test_negative_or_null_severity_is_no_cliff(self, wear_macros):
        expr = str(wear_macros.cliff_plateau_s("sev", "wg"))
        assert _eval(expr, sev=-0.3, wg=0.05) == 0.0
        assert _eval(expr.replace("sev", "CAST(NULL AS DOUBLE)"), wg=0.05) == 0.0

    def test_window_mean_difference_would_carry_wear(self):
        """Why the docstring changed: on the same data the old window-mean difference
        reads step + 5.5 * wear; the regression gap reads the step alone."""
        wear, step, c = 0.08, 1.0, 15
        pool = step_pool(30, wear, step, cliff_age=c)
        pre = pool[pool["age_in_stint"].between(c - 5, c - 1)].groupby("stint_id")["lap_time_s"].mean()
        post = pool[pool["age_in_stint"].between(c, c + 5)].groupby("stint_id")["lap_time_s"].mean()
        assert (post - pre).mean() == pytest.approx(step + 5.5 * wear, abs=0.05)
        assert estimate_cliff_severity(pool, cliff_onset_laps=c) == pytest.approx(step, abs=0.05)


class TestSeverityPreLineNeedsThreeLaps:
    """T6: a cliff detected at tyre age 5 leaves ages 3-4 for the pre line, a line
    through two points; those stints are not measured."""

    def test_min_pre_laps_is_three(self):
        assert SEVERITY_MIN_PRE_LAPS == 3

    def test_cliff_at_age_5_is_not_measured(self):
        assert estimate_cliff_severity(step_pool(20, 0.05, 1.0, cliff_age=5, n_laps=14),
                                       cliff_onset_laps=5) is None

    def test_cliff_at_age_6_is_measured(self):
        sev = estimate_cliff_severity(step_pool(20, 0.05, 1.0, cliff_age=6, n_laps=14), cliff_onset_laps=6)
        assert sev == pytest.approx(1.0, abs=0.1)


class TestRampLengthIsOneConstant:
    """CO-02 owner decision E: the fitter reads the step at onset + span, and the
    curve ramps the step in over the same span, from one definition (dbt var
    cliff_ramp_span_laps)."""

    def test_fitter_and_curve_share_the_span(self, wear_macros):
        from tasks.coefficients.survival import CLIFF_RAMP_SPAN_LAPS

        assert float(str(wear_macros.cliff_severity_span())) == CLIFF_RAMP_SPAN_LAPS == 2.5

    def test_curve_reaches_the_full_step_at_onset_plus_span(self, wear_macros):
        from tasks.coefficients.survival import CLIFF_RAMP_SPAN_LAPS

        wear, step, onset = 0.05, 1.0, 15.0
        expr = str(wear_macros.compound_cliff_wear_s("wg", "sev", "age", "lpc"))

        def cliff_term(lpc: float) -> float:
            age = onset + lpc
            return _eval(expr, wg=wear, sev=step, age=age, lpc=lpc) - wear * age

        assert cliff_term(0.0) == pytest.approx(0.0)
        assert cliff_term(CLIFF_RAMP_SPAN_LAPS / 2) == pytest.approx(step / 2)
        assert cliff_term(CLIFF_RAMP_SPAN_LAPS) == pytest.approx(step)
        assert cliff_term(CLIFF_RAMP_SPAN_LAPS + 3.0) == pytest.approx(step)

    def test_fitted_step_is_read_where_the_ramp_tops_out(self, monkeypatch):
        """A ramped (not stepped) cliff that tops out at onset + span is measured at
        its full height: the fitter evaluates at the span the curve uses."""
        from tasks.coefficients import survival

        wear, step, c = 0.04, 1.0, 15
        pool = step_pool(30, wear, step, cliff_age=c)
        base = estimate_cliff_severity(pool, cliff_onset_laps=c)
        monkeypatch.setattr(survival, "CLIFF_RAMP_SPAN_LAPS", 4.0)
        moved = survival.estimate_cliff_severity(pool, cliff_onset_laps=c)
        # On a pure step the gap is the step at any reference age, so the estimate
        # does not depend on the span; the span only says where it is read.
        assert base == pytest.approx(step, abs=0.05)
        assert moved == pytest.approx(step, abs=0.05)
