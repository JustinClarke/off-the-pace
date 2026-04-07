#!/usr/bin/env python3
"""Source-freshness check.

Classic dbt `source freshness` keys on a per-row `loaded_at_field`. The bronze sources here are
file-based external parquet (FastF1 / Jolpica), which carry session timestamps but no ingestion
timestamp so dbt's built-in freshness doesn't apply. The meaningful freshness signal in this
world is season recency: "has the warehouse ingested through the season we expect?"

This asserts the newest season present is at least --min-season, and reports how far behind it is.
Non-fatal by default (the dataset updates per F1 season, so being a season behind is often correct);
pass --strict to fail (use that in the orchestration DAG once a new season is expected).

Usage:
  python transform/scripts/check_source_freshness.py --db data/dev.duckdb --min-season 2024
  python transform/scripts/check_source_freshness.py --db data/dev.duckdb --min-season 2025 --strict
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "data" / "dev.duckdb"

# (table, season_column) candidates, tried in order the first that exists is used.
SEASON_SOURCES = [
    ("fct_lap_residuals", "race_year"),
    ("stg_laps", "season"),
    ("dim_events", "race_year"),
]


def newest_season(con: duckdb.DuckDBPyConnection) -> tuple[str, int] | None:
    have = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()}
    for table, col in SEASON_SOURCES:
        if table in have:
            val = con.execute(f'SELECT MAX("{col}") FROM "{table}"').fetchone()[0]
            if val is not None:
                return table, int(val)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--min-season", type=int, default=2024, help="newest season expected (inclusive)")
    ap.add_argument("--strict", action="store_true", help="exit 1 (not just warn) when behind")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"❌  warehouse not found: {args.db}", file=sys.stderr)
        return 1

    con = duckdb.connect(str(args.db), read_only=True)
    found = newest_season(con)
    if found is None:
        print("❌  could not determine the newest season (no season source table found)", file=sys.stderr)
        return 1

    table, season = found
    if season >= args.min_season:
        print(f"  ✅  source freshness OK newest season {season} ≥ {args.min_season} (via {table})")
        return 0

    behind = args.min_season - season
    msg = f"source freshness: newest season {season} is {behind} behind the expected {args.min_season} (via {table})"
    if args.strict:
        print(f"❌  {msg}", file=sys.stderr)
        return 1
    print(f"  ⚠ {msg} review (not failing; use --strict to gate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
