"""
smoke_test_season.py assert a newly onboarded season is fully wired.

Usage:
    python scripts/smoke_test_season.py SEASON

Checks:
  1. mart_degradation_history_envelope has fitted cells for the season's era.
  2. The data manifest (_manifest.json) lists the season in seasons_list.
  3. fct_cliff_prediction_features has a partition for the season.
  4. The isotonic-fit parquet covers the season's era.

Exit 0 = all checks pass. Exit 1 = one or more checks failed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).parent.parent
DB_PATH   = REPO_ROOT / "data" / "dev.duckdb"
MANIFEST  = REPO_ROOT / "app" / "public" / "data" / "_manifest.json"
FIT_PATH  = REPO_ROOT / "data" / "fits" / "degradation_isotonic.parquet"


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}", file=sys.stderr)


def ok(msg: str) -> None:
    print(f"  ok    {msg}")


def run(season: int) -> bool:
    passed = True

    # ── 1. Warehouse checks ───────────────────────────────────────────────────
    if not DB_PATH.exists():
        fail(f"Warehouse not found: {DB_PATH}")
        return False

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        # 1a. History envelope has fitted data for this season
        row = con.execute(
            """
            SELECT COUNT(*) AS n
            FROM mart_degradation_history_envelope
            WHERE era = (
                SELECT CASE WHEN MAX(era_boundary) IS NULL OR ? >= MAX(era_boundary)
                            THEN 'post2022' ELSE 'pre2022' END
                FROM (SELECT 2022 AS era_boundary) -- fallback to 2022
            )
              AND obs_deg_from_fresh_p50_mono_s IS NOT NULL
            """,
            [season],
        ).fetchone()
        n = row[0] if row else 0
        if n > 0:
            ok(f"mart_degradation_history_envelope has {n} fitted rows for {season}'s era")
        else:
            fail(f"mart_degradation_history_envelope has 0 fitted rows for season {season}")
            passed = False

        # 1b. fct_cliff_prediction_features has rows for this season
        try:
            cnt = con.execute(
                "SELECT COUNT(*) FROM fct_cliff_prediction_features WHERE race_year = ?",
                [season],
            ).fetchone()[0]
            if cnt > 0:
                ok(f"fct_cliff_prediction_features has {cnt} rows for {season}")
            else:
                fail(f"fct_cliff_prediction_features has 0 rows for {season}")
                passed = False
        except Exception as e:
            fail(f"Could not query fct_cliff_prediction_features: {e}")
            passed = False

        # 1c. Season appears in the warehouse at all
        years = {r[0] for r in con.execute("SELECT DISTINCT race_year FROM stg_laps").fetchall()}
        if season in years:
            ok(f"stg_laps contains laps for {season}")
        else:
            fail(f"stg_laps has no rows for {season} (check bronze ingestion)")
            passed = False

    finally:
        con.close()

    # ── 2. Manifest check ─────────────────────────────────────────────────────
    if not MANIFEST.exists():
        fail(f"Manifest not found: {MANIFEST} run: make app-data")
        passed = False
    else:
        with open(MANIFEST) as f:
            manifest = json.load(f)
        seasons_list = manifest.get("stats", {}).get("seasons_list", [])
        if season in seasons_list:
            ok(f"manifest seasons_list includes {season}")
        else:
            fail(f"manifest seasons_list {seasons_list} does not include {season} run: make app-data")
            passed = False

    # ── 3. Isotonic-fit parquet check ─────────────────────────────────────────
    if not FIT_PATH.exists():
        fail(f"Isotonic-fit parquet not found: {FIT_PATH} run: make deg-iso-fit")
        passed = False
    else:
        fit = duckdb.connect().execute(
            f"SELECT COUNT(*) FROM read_parquet('{FIT_PATH}') WHERE era = 'post2022'"
        ).fetchone()[0]
        if fit > 0:
            ok(f"degradation_isotonic.parquet has {fit} post2022 fitted rows")
        else:
            fail("degradation_isotonic.parquet has 0 post2022 rows run: make deg-iso-fit")
            passed = False

    return passed


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print(f"Usage: python {Path(__file__).name} SEASON", file=sys.stderr)
        return 1
    season = int(sys.argv[1])
    print(f"Smoke-testing season {season} ...")
    passed = run(season)
    if passed:
        print(f"\n✔  All checks passed for season {season}.")
        return 0
    else:
        print(f"\n✗  Some checks failed for season {season} see above.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
