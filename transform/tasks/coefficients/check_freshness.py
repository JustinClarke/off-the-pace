"""
Freshness gate for coefficient seeds and offline parquet fits.

Two kinds of fitted artefact feed the warehouse, and they go stale differently:

* Seeds (MANAGED_SEEDS) are hand-promoted CSVs; they are checked by fit_date age
  (MAX_AGE_DAYS), as before.
* Offline parquet fits (MANAGED_FITS, data/fits/*.parquet) are refitted from the
  warehouse. Age is the wrong test for them: both were only months old when 12a-1
  ingested 2025, yet neither covered it (data_window '2018_to_2024'), so every 2025
  driver-race had a NULL driver_skill_field_s and the 2025 rookies vanished from
  the era-affinity pages (WI-05, F21). They are checked by COVERAGE instead: the
  season their data_window ends on must reach MAX(race_year) in the mart
  (WAREHOUSE_SEASON_SQL, against --db).

Exits 0 if every seed is fresh and every fit covers the warehouse's latest season.
Exits 1 otherwise   CI uses this to warn.

Usage:
    python -m tasks.coefficients.check_freshness          # exits 0/1
    python -m tasks.coefficients.check_freshness --json   # prints JSON report
    python -m tasks.coefficients.check_freshness --db ../data/dev.duckdb

The Makefile's 'dbt-dev-full' target calls this before running dbt, so
stale coefficients are surfaced before the build rather than silently
baking placeholder values into the warehouse.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

SEEDS_DIR = Path(__file__).parents[2] / "seeds"
REPO_ROOT = Path(__file__).parents[3]
FITS_DIR = REPO_ROOT / "data" / "fits"
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
MAX_AGE_DAYS = 365

MANAGED_SEEDS = [
    "compound_cliff_params",
    "circuit_reference",
]

# data/fits/<name>.parquet -> the warehouse model that reads it (for the message).
MANAGED_FITS = {
    "constructor_car_fe": "int_constructor_car_fe",
    "degradation_isotonic": "mart_degradation_history_envelope",
}

# The latest season the mart holds. fct_lap_residuals is a materialised mart over the
# whole lap spine, so it answers without resolving any bronze-backed view.
WAREHOUSE_SEASON_SQL = "SELECT MAX(race_year) FROM fct_lap_residuals"

_WINDOW = re.compile(r"^(\d{4})_to_(\d{4})$")


def check_seed(seed_name: str) -> dict:
    path = SEEDS_DIR / f"{seed_name}.csv"
    if not path.exists():
        return {
            "seed": seed_name,
            "status": "MISSING",
            "fit_date": None,
            "age_days": None,
            "message": f"Seed file not found: {path}",
        }

    try:
        import pandas as pd  # type: ignore
        df = pd.read_csv(path, usecols=["fit_date"])
        if "fit_date" not in df.columns or len(df) == 0:
            return {
                "seed": seed_name,
                "status": "NO_FIT_DATE",
                "fit_date": None,
                "age_days": None,
                "message": "Seed has no fit_date column   may be a placeholder seed.",
            }

        fit_date_str = df["fit_date"].dropna().iloc[0]
        fit_date = datetime.strptime(fit_date_str, "%Y-%m-%d").date()
        age_days = (date.today()-fit_date).days

        if age_days > MAX_AGE_DAYS:
            return {
                "seed": seed_name,
                "status": "STALE",
                "fit_date": fit_date_str,
                "age_days": age_days,
                "message": f"fit_date {fit_date_str} is {age_days} days old (max {MAX_AGE_DAYS}).",
            }

        return {
            "seed": seed_name,
            "status": "FRESH",
            "fit_date": fit_date_str,
            "age_days": age_days,
            "message": f"OK   {age_days} days old.",
        }

    except Exception as exc:
        return {
            "seed": seed_name,
            "status": "ERROR",
            "fit_date": None,
            "age_days": None,
            "message": str(exc),
        }


def warehouse_latest_season(db_path: Path) -> tuple[int | None, str | None]:
    """(MAX(race_year) in the mart, None) or (None, reason it could not be read)."""
    if not db_path.exists():
        return None, f"warehouse not found: {db_path}"
    try:
        import duckdb  # type: ignore
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            value = con.execute(WAREHOUSE_SEASON_SQL).fetchone()[0]
        finally:
            con.close()
    except Exception as exc:  # locked by a running build, missing table, ...
        return None, f"could not read the warehouse's latest season: {exc}"
    if value is None:
        return None, "the mart holds no rows"
    return int(value), None


def check_fit(fit_name: str, latest_season: int | None, warehouse_error: str | None = None) -> dict:
    """Coverage check for one parquet fit: does its data_window reach latest_season?"""
    path = FITS_DIR / f"{fit_name}.parquet"
    report = {
        "fit": fit_name,
        "consumer": MANAGED_FITS.get(fit_name),
        "status": None,
        "data_window": None,
        "window_end": None,
        "warehouse_latest_season": latest_season,
        "message": None,
    }
    if not path.exists():
        return {**report, "status": "MISSING", "message": f"Fit file not found: {path}"}
    try:
        import pyarrow.parquet as pq  # type: ignore
        table = pq.read_table(path)
        if "data_window" not in table.column_names:
            return {**report, "status": "NO_DATA_WINDOW",
                    "message": "Fit has no data_window column, so its coverage cannot be checked."}
        windows = sorted({w for w in table.column("data_window").to_pylist() if w})
    except Exception as exc:
        return {**report, "status": "ERROR", "message": str(exc)}

    parsed = [_WINDOW.match(w) for w in windows]
    if not windows or not all(parsed):
        return {**report, "status": "NO_DATA_WINDOW", "data_window": windows or None,
                "message": f"data_window not of the form YYYY_to_YYYY: {windows!r}"}
    window_end = max(int(m.group(2)) for m in parsed)
    report.update(data_window=windows[0] if len(windows) == 1 else windows, window_end=window_end)

    if latest_season is None:
        return {**report, "status": "ERROR",
                "message": warehouse_error or "warehouse's latest season unknown"}
    if window_end < latest_season:
        missing = (str(latest_season) if window_end + 1 == latest_season
                   else f"{window_end + 1}-{latest_season}")
        return {**report, "status": "STALE",
                "message": (f"data_window ends {window_end} but the mart holds {latest_season}: "
                            f"{report['consumer']} has no fit for {missing}.")}
    return {**report, "status": "FRESH",
            "message": f"OK   data_window reaches {window_end} (mart: {latest_season})."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check coefficient seed and fit freshness.")
    parser.add_argument("--json", action="store_true", help="Output JSON report.")
    parser.add_argument("--db", default=str(DB_PATH),
                        help="Warehouse to read MAX(race_year) from (default: data/dev.duckdb).")
    args = parser.parse_args(argv)

    seed_reports = [check_seed(name) for name in MANAGED_SEEDS]
    latest, warehouse_error = warehouse_latest_season(Path(args.db))
    fit_reports = [check_fit(name, latest, warehouse_error) for name in MANAGED_FITS]
    all_fresh = all(r["status"] == "FRESH" for r in seed_reports + fit_reports)

    if args.json:
        print(json.dumps({"seeds": seed_reports, "fits": fit_reports}, indent=2))
    else:
        print("Coefficient freshness check:")
        for r in seed_reports:
            icon = "✓" if r["status"] == "FRESH" else "✗"
            print(f"  {icon} {r['seed']}: [{r['status']}] {r['message']}")
        print("Offline fit coverage (data_window vs the mart's latest season):")
        for r in fit_reports:
            icon = "✓" if r["status"] == "FRESH" else "✗"
            print(f"  {icon} {r['fit']}: [{r['status']}] {r['message']}")

    if not all_fresh:
        stale_seeds = [r["seed"] for r in seed_reports if r["status"] != "FRESH"]
        stale_fits = [r["fit"] for r in fit_reports if r["status"] != "FRESH"]
        if not args.json:
            if stale_seeds:
                print(f"\nStale seeds: {stale_seeds}")
                print("Run: make coefficients-fit  (then make coefficients-promote after review)")
            if stale_fits:
                print(f"\nFits not covering the warehouse: {stale_fits}")
                print("Run: make car-fe-fit / make deg-iso-fit")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
