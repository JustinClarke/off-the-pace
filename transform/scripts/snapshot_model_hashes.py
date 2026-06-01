#!/usr/bin/env python3
"""Byte-stability oracle for dbt model relations (work.md §6 Phase B).

Computes an *order-independent* content hash for every dbt model materialized in a
DuckDB warehouse, so a cosmetic change (lint fix, refactor) can be proven to leave
model *output* byte-identical. The 7 `fct_*` marts are the mandatory byte-stable
subset (work.md §5/§6.1): drift in any of them fails the check.

Two modes:
  snapshot (default)  write target/model_hashes.baseline.json
  --check             recompute and diff vs the baseline; exit 1 on any fct_* drift

Hashing: each row is hashed as its struct-cast-to-text, then the per-row hashes are
aggregated with `string_agg(... ORDER BY ...)` so row order never affects the result.
Relations in the manifest but absent from the DB are recorded as "missing" (e.g.
fct_ghost_race_finish does not build on CI fixtures) rather than treated as drift.

Usage:
  python scripts/snapshot_model_hashes.py                       # snapshot ci.duckdb
  python scripts/snapshot_model_hashes.py --db ../data/dev.duckdb
  python scripts/snapshot_model_hashes.py --check              # gate vs baseline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
TRANSFORM_ROOT = HERE.parent
DEFAULT_DB = TRANSFORM_ROOT.parent / "data" / "ci.duckdb"
DEFAULT_MANIFEST = TRANSFORM_ROOT / "target" / "manifest.json"
DEFAULT_BASELINE = TRANSFORM_ROOT / "target" / "model_hashes.baseline.json"

# Mandatory byte-stable subset: any drift here is a hard failure (work.md §5/§6.1).
MANDATORY_PREFIX = "fct_"

# Columns that legitimately vary build-to-build (wall-clock build metadata) and must be
# excluded from the content hash, else they create spurious "drift". `fit_timestamp` is
# `CAST(CURRENT_TIMESTAMP AS VARCHAR)` in the constructor-pace family. Real byte-stability
# additionally requires DuckDB's *internal* thread count pinned to 1 (profiles `settings:
# threads: 1`) so non-associative float aggregation can't reorder — dbt's own `threads:`
# only controls model-level concurrency, not intra-query parallelism. See work.md §6.
VOLATILE_COLS = {"fit_timestamp"}


def load_model_relations(manifest_path: Path) -> dict[str, dict[str, str]]:
    """Return {model_name: {schema, identifier}} for every dbt model node."""
    manifest = json.loads(manifest_path.read_text())
    out: dict[str, dict[str, str]] = {}
    for node in manifest["nodes"].values():
        if node["resource_type"] != "model":
            continue
        out[node["name"]] = {
            "schema": node["schema"],
            "identifier": node["alias"] or node["name"],
        }
    return out


def relation_exists(con: duckdb.DuckDBPyConnection, schema: str, identifier: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = ? AND table_name = ?",
        [schema, identifier],
    ).fetchone()
    return row is not None


def relation_columns(con: duckdb.DuckDBPyConnection, schema: str, identifier: str) -> list[str]:
    rows = con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = ? AND table_name = ?",
        [schema, identifier],
    ).fetchall()
    return [r[0] for r in rows]


def hash_relation(con: duckdb.DuckDBPyConnection, schema: str, identifier: str) -> str:
    """Order-independent md5 of a relation's contents, excluding volatile columns."""
    quoted = f'"{schema}"."{identifier}"'
    exclude = VOLATILE_COLS & set(relation_columns(con, schema, identifier))
    if exclude:
        cols = ", ".join(f'"{c}"' for c in sorted(exclude))
        source = f"(SELECT * EXCLUDE ({cols}) FROM {quoted})"
    else:
        source = quoted
    sql = (
        "SELECT md5(string_agg(rh, '' ORDER BY rh)) FROM ("
        f"SELECT md5(CAST(t AS VARCHAR)) AS rh FROM {source} t)"
    )
    return con.execute(sql).fetchone()[0]


def snapshot(con: duckdb.DuckDBPyConnection, models: dict[str, dict[str, str]]) -> dict:
    hashes: dict[str, str | None] = {}
    rowcounts: dict[str, int] = {}
    missing: list[str] = []
    for name, rel in sorted(models.items()):
        if not relation_exists(con, rel["schema"], rel["identifier"]):
            hashes[name] = None
            missing.append(name)
            continue
        hashes[name] = hash_relation(con, rel["schema"], rel["identifier"])
        rowcounts[name] = con.execute(
            f'SELECT count(*) FROM "{rel["schema"]}"."{rel["identifier"]}"'
        ).fetchone()[0]
    return {"hashes": hashes, "rowcounts": rowcounts, "missing": missing}


def do_check(current: dict, baseline_path: Path) -> int:
    if not baseline_path.exists():
        print(f"ERROR: no baseline at {baseline_path}. Run a snapshot first.", file=sys.stderr)
        return 2
    baseline = json.loads(baseline_path.read_text())
    base_hashes = baseline["hashes"]
    cur_hashes = current["hashes"]

    drift_mandatory: list[str] = []
    drift_other: list[str] = []
    new_models: list[str] = []
    gone_missing: list[str] = []

    for name, cur in cur_hashes.items():
        if name not in base_hashes:
            new_models.append(name)
            continue
        base = base_hashes[name]
        if base == cur:
            continue
        # baseline had a hash, now None (or vice versa) is also drift.
        if name.startswith(MANDATORY_PREFIX):
            drift_mandatory.append(name)
            if base is not None and cur is None:
                gone_missing.append(name)
        else:
            drift_other.append(name)

    if new_models:
        print(f"NEW models (not in baseline): {', '.join(sorted(new_models))}")
    if drift_other:
        print(f"WARNING: non-fct model output changed ({len(drift_other)}): "
              f"{', '.join(sorted(drift_other))}")
    if drift_mandatory:
        print(f"FAIL: byte-stable fct_* models drifted ({len(drift_mandatory)}): "
              f"{', '.join(sorted(drift_mandatory))}", file=sys.stderr)
        for name in sorted(drift_mandatory):
            print(f"  {name}: {base_hashes[name]} -> {cur_hashes[name]}", file=sys.stderr)
        return 1

    print(f"OK: all {sum(1 for n in cur_hashes if n.startswith(MANDATORY_PREFIX))} "
          "fct_* models byte-stable vs baseline.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="DuckDB warehouse (default: ../data/ci.duckdb)")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="dbt manifest.json")
    p.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="baseline JSON path")
    p.add_argument("--check", action="store_true", help="diff vs baseline instead of writing it")
    args = p.parse_args()

    if not args.db.exists():
        print(f"ERROR: warehouse not found: {args.db} (run a dbt build first).", file=sys.stderr)
        return 2
    if not args.manifest.exists():
        print(f"ERROR: manifest not found: {args.manifest} (run `dbt parse`).", file=sys.stderr)
        return 2

    models = load_model_relations(args.manifest)
    con = duckdb.connect(str(args.db), read_only=True)
    try:
        current = snapshot(con, models)
    finally:
        con.close()

    if current["missing"]:
        print(f"note: {len(current['missing'])} model(s) not materialized in "
              f"{args.db.name}: {', '.join(current['missing'])}", file=sys.stderr)

    if args.check:
        return do_check(current, args.baseline)

    args.baseline.parent.mkdir(parents=True, exist_ok=True)
    args.baseline.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    n = sum(1 for v in current["hashes"].values() if v is not None)
    print(f"wrote baseline for {n} models ({len(current['missing'])} missing) -> {args.baseline}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
