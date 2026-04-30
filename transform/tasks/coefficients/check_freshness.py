"""
Freshness gate for coefficient seeds.

Exits 0 if all managed seeds are fresh (fit_date within MAX_AGE_DAYS).
Exits 1 if any seed is stale or missing   CI uses this to warn.

Usage:
    python -m tasks.coefficients.check_freshness          # exits 0/1
    python -m tasks.coefficients.check_freshness --json   # prints JSON report

The Makefile's 'dbt-dev-full' target calls this before running dbt, so
stale coefficients are surfaced before the build rather than silently
baking placeholder values into the warehouse.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

SEEDS_DIR = Path(__file__).parents[2] / "seeds"
MAX_AGE_DAYS = 365

MANAGED_SEEDS = [
    "compound_cliff_params",
    "circuit_reference",
]


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check coefficient seed freshness.")
    parser.add_argument("--json", action="store_true", help="Output JSON report.")
    args = parser.parse_args(argv)

    reports = [check_seed(name) for name in MANAGED_SEEDS]
    all_fresh = all(r["status"] == "FRESH" for r in reports)

    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        print("Coefficient freshness check:")
        for r in reports:
            icon = "✓" if r["status"] == "FRESH" else "✗"
            print(f"  {icon} {r['seed']}: [{r['status']}] {r['message']}")

    if not all_fresh:
        stale = [r["seed"] for r in reports if r["status"] != "FRESH"]
        if not args.json:
            print(f"\nStale seeds: {stale}")
            print("Run: make coefficients-fit  (then make coefficients-promote after review)")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
