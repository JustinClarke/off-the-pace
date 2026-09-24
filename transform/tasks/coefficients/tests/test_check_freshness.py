"""
Unit tests for the coefficient-seed and offline-fit freshness gate.

All tests write synthetic seed CSVs / fit parquets / a tiny warehouse into a tmp
dir and monkeypatch SEEDS_DIR / FITS_DIR -- no real seeds, fits or warehouse
touched.
"""

from datetime import date, timedelta

import duckdb
import pandas as pd

from tasks.coefficients import check_freshness
from tasks.coefficients.check_freshness import (
    MAX_AGE_DAYS,
    check_fit,
    check_seed,
    main,
    warehouse_latest_season,
)


def _write_seed(seeds_dir, name: str, fit_date: str | None) -> None:
    cols = {"value": [1.0]}
    if fit_date is not None:
        cols["fit_date"] = [fit_date]
    pd.DataFrame(cols).to_csv(seeds_dir / f"{name}.csv", index=False)


def _write_fit(fits_dir, name: str, data_window: str | None) -> None:
    cols = {"value": [1.0, 2.0]}
    if data_window is not None:
        cols["data_window"] = [data_window, data_window]
    pd.DataFrame(cols).to_parquet(fits_dir / f"{name}.parquet", index=False)


def _write_warehouse(path, seasons: list[int]) -> None:
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE fct_lap_residuals (race_year INTEGER)")
    for s in seasons:
        con.execute("INSERT INTO fct_lap_residuals VALUES (?)", [s])
    con.close()


def _all_fresh(tmp_path, monkeypatch, fit_window: str = "2018_to_2025"):
    """Fresh seeds, fits whose window is `fit_window`, a warehouse ending 2025."""
    seeds, fits = tmp_path / "seeds", tmp_path / "fits"
    seeds.mkdir()
    fits.mkdir()
    monkeypatch.setattr(check_freshness, "SEEDS_DIR", seeds)
    monkeypatch.setattr(check_freshness, "FITS_DIR", fits)
    recent = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    for name in check_freshness.MANAGED_SEEDS:
        _write_seed(seeds, name, recent)
    for name in check_freshness.MANAGED_FITS:
        _write_fit(fits, name, fit_window)
    db = tmp_path / "wh.duckdb"
    _write_warehouse(db, [2018, 2024, 2025])
    return db


class TestCheckSeed:
    def test_fresh_seed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_freshness, "SEEDS_DIR", tmp_path)
        recent = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
        _write_seed(tmp_path, "compound_cliff_params", recent)
        r = check_seed("compound_cliff_params")
        assert r["status"] == "FRESH"
        assert r["age_days"] == 10

    def test_stale_seed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_freshness, "SEEDS_DIR", tmp_path)
        old = (date.today() - timedelta(days=MAX_AGE_DAYS + 5)).strftime("%Y-%m-%d")
        _write_seed(tmp_path, "circuit_reference", old)
        r = check_seed("circuit_reference")
        assert r["status"] == "STALE"
        assert r["age_days"] > MAX_AGE_DAYS

    def test_missing_seed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_freshness, "SEEDS_DIR", tmp_path)
        r = check_seed("does_not_exist")
        assert r["status"] == "MISSING"
        assert r["fit_date"] is None

    def test_empty_seed_reports_no_fit_date(self, tmp_path, monkeypatch):
        # A seed with a fit_date column but zero rows → NO_FIT_DATE.
        monkeypatch.setattr(check_freshness, "SEEDS_DIR", tmp_path)
        pd.DataFrame({"fit_date": pd.Series([], dtype="object")}).to_csv(
            tmp_path / "empty_seed.csv", index=False
        )
        r = check_seed("empty_seed")
        assert r["status"] == "NO_FIT_DATE"

    def test_missing_fit_date_column_reports_error(self, tmp_path, monkeypatch):
        # usecols=['fit_date'] on a seed without that column raises → ERROR.
        monkeypatch.setattr(check_freshness, "SEEDS_DIR", tmp_path)
        _write_seed(tmp_path, "no_date_seed", fit_date=None)
        r = check_seed("no_date_seed")
        assert r["status"] == "ERROR"


class TestCheckFit:
    """F21: parquet fits are judged by data-window COVERAGE of the mart's latest
    season, not by fit-date age."""

    def test_fit_covering_latest_season_is_fresh(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_freshness, "FITS_DIR", tmp_path)
        _write_fit(tmp_path, "constructor_car_fe", "2018_to_2025")
        r = check_fit("constructor_car_fe", 2025)
        assert r["status"] == "FRESH"
        assert r["window_end"] == 2025

    def test_fit_one_season_short_is_stale(self, tmp_path, monkeypatch):
        # The exact F21 state: a young fit whose window stops before the ingested
        # season. Fit-date age alone would call it fresh.
        monkeypatch.setattr(check_freshness, "FITS_DIR", tmp_path)
        _write_fit(tmp_path, "degradation_isotonic", "2018_to_2024")
        r = check_fit("degradation_isotonic", 2025)
        assert r["status"] == "STALE"
        assert "2024" in r["message"] and "2025" in r["message"]

    def test_missing_fit(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_freshness, "FITS_DIR", tmp_path)
        assert check_fit("constructor_car_fe", 2025)["status"] == "MISSING"

    def test_fit_without_data_window(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_freshness, "FITS_DIR", tmp_path)
        _write_fit(tmp_path, "constructor_car_fe", None)
        assert check_fit("constructor_car_fe", 2025)["status"] == "NO_DATA_WINDOW"

    def test_malformed_data_window(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_freshness, "FITS_DIR", tmp_path)
        _write_fit(tmp_path, "constructor_car_fe", "all seasons")
        assert check_fit("constructor_car_fe", 2025)["status"] == "NO_DATA_WINDOW"

    def test_unknown_warehouse_season_is_not_fresh(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_freshness, "FITS_DIR", tmp_path)
        _write_fit(tmp_path, "constructor_car_fe", "2018_to_2025")
        r = check_fit("constructor_car_fe", None, "warehouse not found")
        assert r["status"] == "ERROR"


class TestWarehouseLatestSeason:
    def test_reads_max_race_year(self, tmp_path):
        db = tmp_path / "wh.duckdb"
        _write_warehouse(db, [2018, 2025, 2021])
        assert warehouse_latest_season(db) == (2025, None)

    def test_missing_warehouse(self, tmp_path):
        season, err = warehouse_latest_season(tmp_path / "nope.duckdb")
        assert season is None and "not found" in err


class TestMain:
    def test_returns_zero_when_all_fresh(self, tmp_path, monkeypatch):
        db = _all_fresh(tmp_path, monkeypatch)
        assert main(["--db", str(db)]) == 0
        assert main(["--json", "--db", str(db)]) == 0

    def test_returns_one_when_any_stale(self, tmp_path, monkeypatch):
        db = _all_fresh(tmp_path, monkeypatch)
        # Remove one managed seed → it is MISSING → not all fresh.
        (tmp_path / "seeds" / f"{check_freshness.MANAGED_SEEDS[1]}.csv").unlink()
        assert main(["--db", str(db)]) == 1

    def test_returns_one_when_a_fit_misses_the_latest_season(self, tmp_path, monkeypatch):
        # Seeds fresh, fits recently written -- but their window stops at 2024 while the
        # mart holds 2025. This is F21 and must fail the gate.
        db = _all_fresh(tmp_path, monkeypatch, fit_window="2018_to_2024")
        assert main(["--db", str(db)]) == 1

    def test_returns_one_when_warehouse_unreadable(self, tmp_path, monkeypatch):
        _all_fresh(tmp_path, monkeypatch)
        assert main(["--db", str(tmp_path / "missing.duckdb")]) == 1
