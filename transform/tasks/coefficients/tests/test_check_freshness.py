"""
Unit tests for the coefficient-seed freshness gate.

All tests write a synthetic seed CSV into a tmp dir and monkeypatch
SEEDS_DIR   no real seeds or duckdb connection touched.
"""

from datetime import date, timedelta

import pandas as pd

from tasks.coefficients import check_freshness
from tasks.coefficients.check_freshness import check_seed, MAX_AGE_DAYS, main


def _write_seed(seeds_dir, name: str, fit_date: str | None) -> None:
    cols = {"value": [1.0]}
    if fit_date is not None:
        cols["fit_date"] = [fit_date]
    pd.DataFrame(cols).to_csv(seeds_dir / f"{name}.csv", index=False)


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


class TestMain:
    def test_returns_zero_when_all_fresh(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_freshness, "SEEDS_DIR", tmp_path)
        recent = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
        for name in check_freshness.MANAGED_SEEDS:
            _write_seed(tmp_path, name, recent)
        assert main([]) == 0
        assert main(["--json"]) == 0

    def test_returns_one_when_any_stale(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_freshness, "SEEDS_DIR", tmp_path)
        # Only write one managed seed → the other is MISSING → not all fresh.
        recent = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
        _write_seed(tmp_path, check_freshness.MANAGED_SEEDS[0], recent)
        assert main([]) == 1
