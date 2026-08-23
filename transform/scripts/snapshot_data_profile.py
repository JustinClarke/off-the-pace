#!/usr/bin/env python3
"""Build-over-build data-profile diff.

The byte-stability oracle (snapshot_model_hashes.py) proves fct_* output is *byte-identical*
across builds  perfect for catching cosmetic refactors, but it says nothing about *how* data
drifted when it legitimately changes. This profiles each mart at a coarser, semantic grain 
row count, per-column null-rate, the mean of numeric columns, and the category-share vector of
low-cardinality categorical columns  and diffs against a committed baseline with tolerances. It
surfaces volume drift (rows dropped/exploded), null-rate spikes, target-mean shift, and
class-distribution shift between two builds, complementing the dbt anomaly tests.

The categorical half exists because the numeric half is blind to it: a relabel that moved 9,405
rows of `laps_until_cliff_class` between classes changed no row count, no null-rate and no
numeric mean, so the gate passed clean on a mart whose target had been redefined.

Like the byte oracle, the baseline is an approval artefact: regenerate + commit it when the data
*should* have changed (e.g. a season was added); the --check then guards against unintended drift.

Modes:
  (default)   snapshot → transform/tests/data_profile.baseline.json
  --check     recompute and diff vs the baseline; exit 1 on any drift beyond tolerance

Usage:
  python transform/scripts/snapshot_data_profile.py --db data/dev.duckdb
  python transform/scripts/snapshot_data_profile.py --db data/dev.duckdb --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
TRANSFORM_ROOT = HERE.parent
REPO_ROOT = TRANSFORM_ROOT.parent
DEFAULT_DB = REPO_ROOT / "data" / "dev.duckdb"
DEFAULT_BASELINE = TRANSFORM_ROOT / "tests" / "data_profile.baseline.json"

# Bumped when the profile gains a dimension. A --check against an older baseline is
# refused rather than silently skipped: a baseline that predates a dimension is blind
# to it, and a blind gate that reports PASS is worse than no gate.
PROFILE_SCHEMA_VERSION = 2

# Mart prefixes worth profiling (the published, analytics-facing grain).
TABLE_PREFIXES = ("fct_", "mart_", "dim_")

# Default tolerances (override on the CLI).
ROW_TOL = 0.0       # relative row-count drift allowed (0 = exact, like the oracle)
NULL_TOL = 0.02     # absolute null-rate drift allowed
MEAN_TOL = 0.02     # relative drift allowed on a column mean
SHARE_TOL = 0.01    # absolute drift allowed on any one category's share of the table
DISTINCT_TOL = 0.02  # relative drift allowed on n_distinct (high-cardinality columns)

# Above this many distinct values a column is an identifier, not a class: record the
# cardinality and skip the share vector, which would otherwise dominate the baseline.
MAX_CATEGORIES = 40

NUMERIC_TYPES = {
    "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
    "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT",
    "FLOAT", "DOUBLE", "DECIMAL", "REAL",
}

CATEGORICAL_TYPES = {"VARCHAR", "BOOLEAN", "ENUM"}


def _tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' ORDER BY table_name"
    ).fetchall()
    return [r[0] for r in rows if r[0].startswith(TABLE_PREFIXES)]


def _category_shares(
    con: duckdb.DuckDBPyConnection, table: str, column: str, n: int
) -> dict | None:
    """Share-of-table for each distinct value, or {'n_distinct': k} once the column is
    too wide to be a class. NULL is not a category  it is already the null_rate, so the
    shares sum to 1 - null_rate by construction."""
    rows = con.execute(
        f'SELECT CAST("{column}" AS VARCHAR) AS v, COUNT(*) AS c FROM "{table}" '
        f'WHERE "{column}" IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT {MAX_CATEGORIES + 1}'
    ).fetchall()
    if len(rows) > MAX_CATEGORIES:
        k = con.execute(f'SELECT COUNT(DISTINCT "{column}") FROM "{table}"').fetchone()[0]
        return {"n_distinct": int(k)}
    return {"category_shares": {str(v): round(c / n, 6) for v, c in rows}}


def _profile_table(con: duckdb.DuckDBPyConnection, table: str) -> dict:
    cols = con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()

    n = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    profile: dict = {"row_count": int(n), "columns": {}}
    if n == 0:
        return profile

    # One pass: null-rate for every column, mean for numeric columns.
    selects, meta, categorical = [], [], []
    for name, dtype in cols:
        base = dtype.split("(")[0].upper()
        selects.append(f'SUM(CASE WHEN "{name}" IS NULL THEN 1 ELSE 0 END)')
        meta.append((name, "null"))
        if base in NUMERIC_TYPES:
            selects.append(f'AVG(CAST("{name}" AS DOUBLE))')
            meta.append((name, "mean"))
        elif base in CATEGORICAL_TYPES:
            categorical.append(name)
    row = con.execute(f'SELECT {", ".join(selects)} FROM "{table}"').fetchone()

    for (name, kind), val in zip(meta, row):
        entry = profile["columns"].setdefault(name, {})
        if kind == "null":
            entry["null_rate"] = round((val or 0) / n, 6)
        elif kind == "mean" and val is not None:
            entry["mean"] = round(float(val), 6)

    # Second pass, one GROUP BY per categorical column.
    for name in categorical:
        profile["columns"].setdefault(name, {}).update(_category_shares(con, table, name, n))
    return profile


def snapshot(con: duckdb.DuckDBPyConnection) -> dict:
    return {
        "profile_schema_version": PROFILE_SCHEMA_VERSION,
        "tables": {t: _profile_table(con, t) for t in _tables(con)},
    }


def _check_categories(table: str, col: str, bstats: dict, cstats: dict,
                      share_tol: float, distinct_tol: float) -> list[str]:
    drift: list[str] = []
    if "n_distinct" in bstats:
        if "n_distinct" not in cstats:
            drift.append(f"{table}.{col}: was high-cardinality ({bstats['n_distinct']} distinct), "
                         f"now a {len(cstats.get('category_shares', {}))}-value category vector")
        else:
            b, c = bstats["n_distinct"], cstats["n_distinct"]
            if abs(c - b) / (b or 1) > distinct_tol:
                drift.append(f"{table}.{col}.n_distinct: {b} → {c}")
        return drift

    if "category_shares" not in bstats:
        return drift
    bshares = bstats["category_shares"]
    cshares = cstats.get("category_shares")
    if cshares is None:
        drift.append(f"{table}.{col}: category vector gone (now high-cardinality, "
                     f"{cstats.get('n_distinct')} distinct)")
        return drift
    for value in sorted(set(bshares) | set(cshares)):
        b, c = bshares.get(value, 0.0), cshares.get(value, 0.0)
        if abs(c - b) > share_tol:
            if value not in bshares:
                drift.append(f"{table}.{col}: NEW category '{value}' at share {c}")
            elif value not in cshares:
                drift.append(f"{table}.{col}: category '{value}' GONE (was {b})")
            else:
                drift.append(f"{table}.{col}.share['{value}']: {b} → {c} ({c - b:+.4f})")
    return drift


def check(current: dict, baseline: dict, row_tol: float, null_tol: float, mean_tol: float,
          share_tol: float = SHARE_TOL, distinct_tol: float = DISTINCT_TOL) -> list[str]:
    drift: list[str] = []
    for table, base in baseline.items():
        if table not in current:
            drift.append(f"{table}: MISSING from current build")
            continue
        cur = current[table]
        b_rows, c_rows = base["row_count"], cur["row_count"]
        if b_rows == 0:
            if c_rows != 0:
                drift.append(f"{table}.row_count: 0 → {c_rows}")
        elif abs(c_rows - b_rows) / b_rows > row_tol:
            drift.append(f"{table}.row_count: {b_rows} → {c_rows} ({(c_rows - b_rows) / b_rows:+.1%})")
        for col, bstats in base.get("columns", {}).items():
            cstats = cur.get("columns", {}).get(col)
            if cstats is None:
                drift.append(f"{table}.{col}: column MISSING")
                continue
            if "null_rate" in bstats and "null_rate" in cstats:
                if abs(cstats["null_rate"] - bstats["null_rate"]) > null_tol:
                    drift.append(f"{table}.{col}.null_rate: {bstats['null_rate']} → {cstats['null_rate']}")
            if "mean" in bstats and "mean" in cstats:
                denom = abs(bstats["mean"]) or 1.0
                if abs(cstats["mean"] - bstats["mean"]) / denom > mean_tol:
                    drift.append(f"{table}.{col}.mean: {bstats['mean']} → {cstats['mean']}")
            drift += _check_categories(table, col, bstats, cstats, share_tol, distinct_tol)
    new = set(current) - set(baseline)
    for table in sorted(new):
        drift.append(f"{table}: NEW table not in baseline")
    return drift


def _load_baseline(path: Path) -> dict:
    """Return the {table: profile} map, refusing a baseline older than the current
    profile schema  it would be blind to whatever dimension the bump added."""
    raw = json.loads(path.read_text())
    version = raw.get("profile_schema_version") if isinstance(raw, dict) else None
    if version != PROFILE_SCHEMA_VERSION:
        found = version if version is not None else "1 (pre-versioning)"
        raise SystemExit(
            f"❌  baseline at {path} is profile_schema_version {found}, this script writes "
            f"{PROFILE_SCHEMA_VERSION}.\n    It cannot see every dimension the gate now checks, so "
            f"PASS would be meaningless. Regenerate it:\n"
            f"      make data-profile-snapshot"
        )
    return raw["tables"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    ap.add_argument("--check", action="store_true", help="diff vs baseline; exit 1 on drift")
    ap.add_argument("--row-tol", type=float, default=ROW_TOL)
    ap.add_argument("--null-tol", type=float, default=NULL_TOL)
    ap.add_argument("--mean-tol", type=float, default=MEAN_TOL)
    ap.add_argument("--share-tol", type=float, default=SHARE_TOL,
                    help="absolute drift allowed on any one category's share of the table")
    ap.add_argument("--distinct-tol", type=float, default=DISTINCT_TOL,
                    help="relative drift allowed on n_distinct for high-cardinality columns")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"❌  warehouse not found: {args.db}", file=sys.stderr)
        return 1

    con = duckdb.connect(str(args.db), read_only=True)
    current = snapshot(con)

    if not args.check:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"  ✅  Profiled {len(current['tables'])} tables → {args.baseline}")
        return 0

    if not args.baseline.exists():
        print(f"❌  no baseline at {args.baseline}  run without --check first", file=sys.stderr)
        return 1
    baseline = _load_baseline(args.baseline)
    drift = check(current["tables"], baseline, args.row_tol, args.null_tol, args.mean_tol,
                  args.share_tol, args.distinct_tol)
    if drift:
        print(f"❌  data-profile drift ({len(drift)}):")
        for d in drift:
            print(f"    {d}")
        return 1
    print(f"  ✅  No data-profile drift across {len(baseline)} tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
