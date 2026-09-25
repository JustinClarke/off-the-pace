"""
T31 (WI-02, F41) and the fitter side of T5 (F7): the compound seed says where every
parameter came from, and the fitter measures what its docstrings say it measures.

  * fit_group records provenance per parameter, and never writes "fitted" notes
    for a cell holding a class default (F41a);
  * the live seed carries consistent per-parameter provenance;
  * the fitted pace series has the fuel burn removed, and NULL-age laps are
    excluded (F41b);
  * estimate_wear_gradient uses uncensored stints only, as its docstring says;
  * fill_coverage_gaps carries the fallback hierarchy forward explicitly (F7).

Synthetic data and an in-memory DuckDB only -- no warehouse needed.
"""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from tasks.coefficients import fit_compound_cliff as F
from tasks.coefficients.survival import estimate_wear_gradient
from tasks.coefficients.tests.test_fit_compound_cliff import make_clean_stint, make_stint_pool

SEED_PATH = F.SEEDS_DIR / "compound_cliff_params.csv"
PARAMS = {  # source column -> (seed value column, COMPOUND_DEFAULTS key)
    "onset_source": ("compound_cliff_onset_laps", "cliff_onset_laps"),
    "gradient_source": ("compound_wear_gradient", "wear_gradient"),
    "severity_source": ("compound_cliff_severity", "cliff_severity"),
}


# ---------------------------------------------------------------------------
# fit_group: per-parameter provenance (F41a)
# ---------------------------------------------------------------------------

@pytest.fixture
def pool():
    return make_stint_pool(n_stints=20, cliff_at_lap=20)


def _fit(pool, monkeypatch, onset=18.0, severity=0.8, gradient=0.06, fallback_df=None,
         season=2023):
    """fit_group with the three estimators pinned, so each fallback path is forced."""
    monkeypatch.setattr(F, "fit_cliff_onset_median", lambda *a, **k: onset)
    monkeypatch.setattr(F, "estimate_cliff_severity", lambda *a, **k: severity)
    monkeypatch.setattr(F, "estimate_wear_gradient", lambda *a, **k: gradient)
    return F.fit_group(pool, "bahrain_grand_prix", "SOFT", season, fallback_df=fallback_df)


class TestFitGroupProvenance:
    def test_all_measured_reads_fitted(self, pool, monkeypatch):
        r = _fit(pool, monkeypatch)
        assert r["fit_source"] == "cox_km_survival"
        assert (r["onset_source"], r["gradient_source"], r["severity_source"]) == ("fitted",) * 3
        assert r["notes"].startswith("fitted from 20 stints via cox_km_survival")

    @pytest.mark.parametrize("override, param", [
        ({"onset": None}, "onset_source"),
        ({"gradient": None}, "gradient_source"),
        ({"gradient": 0.9}, "gradient_source"),      # out of range [0.005, 0.3]
        ({"severity": None}, "severity_source"),
        ({"severity": 3.0}, "severity_source"),      # out of range [0.1, 1.5]
    ])
    def test_a_fired_default_is_recorded_on_its_own_parameter(self, pool, monkeypatch, override, param):
        r = _fit(pool, monkeypatch, **override)
        defaults = F.COMPOUND_DEFAULTS["SOFT"]
        col, key = PARAMS[param]
        assert r[param] == "class_default"
        assert r[col] == pytest.approx(defaults[key])
        for other in set(PARAMS) - {param}:
            assert r[other] == "fitted", f"{other} wrongly marked by {param}'s fallback"
        # The cell-level tier is unchanged -- which is exactly why it cannot be the
        # only provenance field.
        assert r["fit_source"] == "cox_km_survival"
        assert "fitted from" not in r["notes"], r["notes"]
        assert param.split("_")[0] in r["notes"]

    def test_cross_season_tier_marks_measured_and_defaulted_separately(self, monkeypatch):
        thin = make_stint_pool(n_stints=3, cliff_at_lap=20)            # < MIN_STINTS
        pooled = make_stint_pool(n_stints=30, cliff_at_lap=20)
        r = _fit(thin, monkeypatch, onset=None, fallback_df=pooled)
        assert r["fit_source"] == "cross_season_fallback"
        assert r["onset_source"] == "class_default"
        assert r["gradient_source"] == r["severity_source"] == "cross_season_fallback"
        assert "fitted from" not in r["notes"]

    def test_class_default_tier_is_class_default_everywhere(self, monkeypatch):
        thin = make_stint_pool(n_stints=3, cliff_at_lap=20)
        r = _fit(thin, monkeypatch, fallback_df=None)
        assert r["fit_source"] == "compound_class_default"
        assert (r["onset_source"], r["gradient_source"], r["severity_source"]) == ("class_default",) * 3


# ---------------------------------------------------------------------------
# The live seed (F41a acceptance: provenance per parameter, honest notes)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def seed():
    return pd.read_csv(SEED_PATH)


def _is_default(row, col, key):
    return abs(float(row[col]) - float(F.COMPOUND_DEFAULTS[row["compound_code"]][key])) < 1e-9


class TestLiveSeedProvenance:
    def test_every_parameter_has_a_source_in_the_vocabulary(self, seed):
        for col in PARAMS:
            assert col in seed.columns
            assert seed[col].notna().all(), f"{col} has NULLs"
            assert set(seed[col]) <= set(F.PARAM_SOURCES), set(seed[col]) - set(F.PARAM_SOURCES)

    def test_parameter_sources_agree_with_the_cell_tier(self, seed):
        allowed = {
            "cox_km_survival": {"fitted", "class_default"},
            "cross_season_fallback": {"cross_season_fallback", "class_default"},
            "compound_class_default": {"class_default"},
        }
        for _, r in seed.iterrows():
            ok = allowed.get(r["fit_source"], {"carried_forward", "class_default"})
            if r["fit_source"] not in allowed:
                assert r["fit_source"].startswith("carried_forward_"), r["fit_source"]
            for col in PARAMS:
                assert r[col] in ok, (r["circuit_key"], r["compound_code"], r["season"], col, r[col])

    # Deliberately NOT asserted here: "no parameter labelled measured equals its class
    # default". It reads like F41a's signature, but a genuine estimate can land exactly
    # on a default -- a KM median is an integer lap count -- and a scratch refit of
    # 2018-2024 with provenance recorded at fit time produced 3-4 such parameters out
    # of ~1,200. The fitter tests above guard the defect where it lives (fit_group);
    # a seed-level rule would fail an honest refit.

    def test_a_class_default_label_means_the_class_default_value(self, seed):
        wrong = [
            (r["circuit_key"], r["compound_code"], r["season"], col)
            for _, r in seed[seed["fit_source"].isin(["cox_km_survival", "cross_season_fallback"])].iterrows()
            for col, (vcol, key) in PARAMS.items()
            if r[col] == "class_default" and not _is_default(r, vcol, key)
        ]
        assert not wrong, wrong[:5]

    def test_notes_never_claim_fitted_when_a_default_fired(self, seed):
        has_default = (seed[list(PARAMS)] == "class_default").any(axis=1)
        liars = seed[has_default & seed["notes"].str.contains("fitted from", regex=False)]
        assert liars.empty, liars[["circuit_key", "compound_code", "season", "notes"]].head().to_string()

    def test_carried_rows_copy_their_source_and_keep_its_defaults(self, seed):
        carried = seed[seed["fit_source"].str.startswith("carried_forward_")]
        assert len(carried)
        by_key = seed.set_index(["circuit_key", "compound_code", "season"])
        for _, r in carried.iterrows():
            src_season = int(r["fit_source"].rsplit("_", 1)[1])
            assert src_season < r["season"], "a carried cell must come from an earlier season"
            src = by_key.loc[(r["circuit_key"], r["compound_code"], src_season)]
            for col, (vcol, _key) in PARAMS.items():
                assert r[vcol] == pytest.approx(src[vcol])
                expected = "class_default" if src[col] == "class_default" else "carried_forward"
                assert r[col] == expected, (r["circuit_key"], r["compound_code"], r["season"], col)


# ---------------------------------------------------------------------------
# F41b: the fitted series is fuel-corrected; NULL-age laps are excluded
# ---------------------------------------------------------------------------

def _mini_warehouse() -> duckdb.DuckDBPyConnection:
    """The tables load_stint_data reads, two laps of one stint plus a quarantined lap.
    Lap 3 is a green-flag lap the fuel model does not price (not is_valid_lap)."""
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE int_stint_geometry AS SELECT * FROM (VALUES
            ('s1', 'l2', 2023, '2023_1', 'VER', 1, 1, 30, 1),
            ('s1', 'l3', 2023, '2023_1', 'VER', 2, 2, 30, 1),
            ('s1', 'l4', 2023, '2023_1', 'VER', 3, NULL, 30, 1)
        ) t(stint_id, lap_id, race_year, race_id, driver_id, lap_in_stint, age_in_stint,
            stint_length_actual, stint_number);
        CREATE TABLE stg_laps AS SELECT * FROM (VALUES
            ('l2', 'SOFT', '2023_1', '2023_1', 2, 95.0, TRUE),
            ('l3', 'SOFT', '2023_1', '2023_1', 3, 94.0, FALSE),
            ('l4', 'SOFT', '2023_1', '2023_1', 4, 93.0, TRUE)
        ) t(lap_id, compound, circuit_key, race_id, lap_number, lap_time_s, is_valid_lap);
        ALTER TABLE stg_laps ADD COLUMN is_safety_car_lap BOOLEAN DEFAULT FALSE;
        ALTER TABLE stg_laps ADD COLUMN is_vsc_lap BOOLEAN DEFAULT FALSE;
        ALTER TABLE stg_laps ADD COLUMN is_pit_lap BOOLEAN DEFAULT FALSE;
        ALTER TABLE stg_laps ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE;
        ALTER TABLE stg_laps ADD COLUMN is_fresh_tyre BOOLEAN DEFAULT TRUE;
        CREATE TABLE stg_weather (lap_id VARCHAR, track_temp_c DOUBLE, rainfall_flag BOOLEAN,
                                  wind_speed_ms DOUBLE);
        CREATE TABLE stg_events (driver_id VARCHAR, race_id VARCHAR, event_type VARCHAR);
        CREATE TABLE stg_results (driver_id VARCHAR, race_id VARCHAR, status VARCHAR, is_dnf BOOLEAN);
        CREATE TABLE race_to_track AS SELECT '2023_1' AS race_id, 'bahrain_grand_prix' AS track_id;
        CREATE TABLE dim_circuits AS
            SELECT 'bahrain_grand_prix' AS circuit_key, 'bahrain' AS circuit_id,
                   0.03 AS weight_penalty_factor;
        -- dirty-air normalization removes 0.5 s from lap 2 only
        CREATE TABLE int_lap_normalized_pace AS SELECT * FROM (VALUES
            ('l2', 94.5), ('l3', 94.0), ('l4', 93.0)) t(lap_id, normalized_pace_s);
        -- 110 kg over 55 scheduled laps = 2 kg/lap; lap 2 carries 108 kg
        CREATE TABLE int_lap_fuel_state AS SELECT * FROM (VALUES
            ('l2', '2023_1', 108.0 * 0.03, 110.0, 2.0),
            ('l4', '2023_1', 104.0 * 0.03, 110.0, 2.0)
        ) t(lap_id, race_id, weight_penalty_s, initial_fuel_kg, fuel_consumption_rate_kg_per_lap);
    """)
    return c


class TestFuelCorrectedSeries:
    def test_loader_removes_the_fuel_burn(self):
        df = F.load_stint_data(_mini_warehouse(), [2023]).set_index("lap_id")
        # a priced lap: dirty-air-normalized pace minus the fuel model's own penalty
        assert df.loc["l2", "fuel_corrected_pace_s"] == pytest.approx(94.5 - 108.0 * 0.03)
        # an unpriced green-flag lap: the same race's linear burn, 106 kg on lap 3
        assert df.loc["l3", "fuel_corrected_pace_s"] == pytest.approx(94.0 - 106.0 * 0.03)
        # normalized_pace_s itself is unchanged (dirty air out, fuel still in)
        assert df.loc["l2", "normalized_pace_s"] == pytest.approx(94.5)

    def test_loader_drops_laps_with_unknown_tyre_age(self):
        df = F.load_stint_data(_mini_warehouse(), [2023])
        assert "l4" not in set(df["lap_id"])
        assert df["age_in_stint"].notna().all()

    def test_fit_group_fits_the_fuel_corrected_series(self, monkeypatch):
        """Pace falls 0.06 s/lap with fuel burn while the tyre wears 0.04 s/lap: the
        fuel-left-in series reads almost no wear; the fitter must read 0.04."""
        pool = make_stint_pool(n_stints=30, cliff_at_lap=25)             # wear 0.04 s/lap
        pool["fuel_corrected_pace_s"] = pool["lap_time_s"]
        pool["normalized_pace_s"] = pool["lap_time_s"] - 0.06 * pool["age_in_stint"]
        seen = {}

        def spy(df, onset, pace_col="lap_time_s"):
            seen["pace_col"] = pace_col
            return estimate_wear_gradient(df, onset, pace_col=pace_col)

        monkeypatch.setattr(F, "estimate_wear_gradient", spy)
        r = F.fit_group(pool, "bahrain_grand_prix", "SOFT", 2023)
        assert seen["pace_col"] == "fuel_corrected_pace_s"
        assert r["gradient_source"] == "fitted"
        assert 0.03 < r["compound_wear_gradient"] < 0.05, r["compound_wear_gradient"]


# ---------------------------------------------------------------------------
# estimate_wear_gradient: uncensored stints only (its docstring)
# ---------------------------------------------------------------------------

def _mixed_pool(dnf_on_censored: bool = False) -> pd.DataFrame:
    """20 stints that run into a cliff (wear 0.08 s/lap) and 20 pitted voluntarily
    before any cliff (wear 0.02 s/lap). Both slopes are clean enough to pass R^2."""
    parts = []
    for i in range(20):
        parts.append(make_clean_stint(f"cliff_{i:02d}", "bahrain_grand_prix", "SOFT", 2023,
                                      n_laps=28, wear_gradient=0.08, cliff_at_lap=20,
                                      noise_std=0.01))
        pit = make_clean_stint(f"pit_{i:02d}", "bahrain_grand_prix", "SOFT", 2023,
                               n_laps=18, wear_gradient=0.02, cliff_at_lap=None, noise_std=0.01)
        pit["dnf_status"] = "Engine" if dnf_on_censored else None
        parts.append(pit)
    return pd.concat(parts, ignore_index=True)


class TestUncensoredOnly:
    def test_voluntary_pit_stints_do_not_enter_the_gradient(self):
        g = estimate_wear_gradient(_mixed_pool(), cliff_onset_laps=20)
        assert g is not None
        assert g == pytest.approx(0.08, abs=0.01), f"censored stints leaked in: {g}"

    def test_a_forced_stop_counts_as_uncensored(self):
        g = estimate_wear_gradient(_mixed_pool(dnf_on_censored=True), cliff_onset_laps=20)
        assert g is not None
        assert g < 0.07, f"retired stints were dropped: {g}"


# ---------------------------------------------------------------------------
# F7: fill_coverage_gaps -- venue history, then class default, provenance kept
# ---------------------------------------------------------------------------

def _seed_row(circuit_key, compound, season, onset, grad, sev, sources, fit_source="cox_km_survival"):
    return {
        "circuit_key": circuit_key, "compound_code": compound, "season": season,
        "compound_grip_peak": 1.0, "compound_wear_gradient": grad,
        "compound_optimal_temp_low": 78, "compound_optimal_temp_high": 105,
        "compound_cliff_onset_laps": onset, "compound_cliff_severity": sev,
        "fit_date": "2026-09-08", "data_window": "2018_to_2024", "fit_method": "km_survival_v1",
        "git_sha": "abc1234", "fit_timestamp": "2026-09-08T00:00:00Z", "fit_source": fit_source,
        "onset_source": sources[0], "gradient_source": sources[1], "severity_source": sources[2],
        "n_stints": 20, "notes": "x",
    }


class TestFillCoverageGaps:
    @pytest.fixture
    def seed_df(self):
        return pd.DataFrame([
            _seed_row("bahrain_grand_prix", "MEDIUM", 2022, 21.0, 0.05, 0.7, ("fitted",) * 3),
            # the latest earlier cell; its onset is a class default
            _seed_row("bahrain_grand_prix", "MEDIUM", 2023, 33.0, 0.06, 0.8,
                      ("class_default", "fitted", "fitted")),
            # a LATER cell that must never be used to fill 2024
            _seed_row("bahrain_grand_prix", "MEDIUM", 2025, 12.0, 0.09, 0.9, ("fitted",) * 3),
        ])

    def test_venue_history_uses_latest_earlier_season_and_keeps_defaults(self, seed_df):
        needed = pd.DataFrame({"circuit_key": ["bahrain_grand_prix"], "compound_code": ["MEDIUM"],
                               "season": [2024]})
        out = F.fill_coverage_gaps(seed_df, needed)
        assert len(out) == 1
        r = out.iloc[0]
        assert r["season"] == 2024 and r["fit_source"] == "carried_forward_2023"
        assert r["compound_cliff_onset_laps"] == 33.0 and r["compound_wear_gradient"] == 0.06
        assert r["onset_source"] == "class_default"          # a carried default stays a default
        assert r["gradient_source"] == r["severity_source"] == "carried_forward"
        assert list(out.columns) == F.SEED_COLUMNS

    def test_no_venue_history_falls_to_class_default(self, seed_df):
        needed = pd.DataFrame({"circuit_key": ["belgian_grand_prix"],
                               "compound_code": ["INTERMEDIATE"], "season": [2025]})
        r = F.fill_coverage_gaps(seed_df, needed).iloc[0]
        d = F.COMPOUND_DEFAULTS["INTERMEDIATE"]
        assert r["fit_source"] == "compound_class_default"
        assert (r["onset_source"], r["gradient_source"], r["severity_source"]) == ("class_default",) * 3
        assert r["compound_cliff_onset_laps"] == d["cliff_onset_laps"]
        assert r["compound_wear_gradient"] == d["wear_gradient"]
        assert r["compound_cliff_severity"] == d["cliff_severity"]
        assert r["data_window"] == "2022_to_2024"             # nothing from the season itself

    def test_covered_cells_are_left_alone(self, seed_df):
        needed = seed_df[["circuit_key", "compound_code", "season"]]
        assert F.fill_coverage_gaps(seed_df, needed).empty
