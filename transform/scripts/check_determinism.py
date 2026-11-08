#!/usr/bin/env python3
"""Rebuild selected dbt models N times and check the content hashes agree (TX-14).

Runs in its OWN scratch folder: copies the warehouse to <scratch>/dev.duckdb (the copy
must keep the name dev.duckdb, staging views reference the `dev` catalog), writes a
profiles.yml with `threads: 1` + `settings: {threads: 1}`, and sends dbt's --target-path
and --log-path there. The real warehouse is only read (copied), never opened by dbt.
Hashing is snapshot_model_hashes.hash_relation, so the property checked is the same one
the byte-stability oracle relies on. Not wired into the Makefile or CI (two builds are
too slow); the owner runs it before re-taking baselines.

Usage (from transform/):
  ../.venv/bin/python scripts/check_determinism.py \\
      --select fct_driver_isolation_stint int_pit_strategy_cost_curve \\
      int_sector_residual_decomposed --runs 2
  ... --db ../data/dev.duckdb --scratch /path/to/own/folder --keep

Exit 0 if every model gave one hash across all runs, 1 if any differ, 2 on setup error.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snapshot_model_hashes as smh  # noqa: E402

TRANSFORM_ROOT = smh.TRANSFORM_ROOT
DEFAULT_DB = TRANSFORM_ROOT.parent / "data" / "dev.duckdb"
DBT = TRANSFORM_ROOT.parent / ".venv" / "bin" / "dbt"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--select", nargs="+", required=True, help="dbt model names to rebuild")
    p.add_argument("--runs", type=int, default=2, help="number of rebuilds (default 2)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="warehouse to COPY (default data/dev.duckdb)")
    p.add_argument("--scratch", type=Path, default=None, help="own scratch folder (default: new temp dir)")
    p.add_argument("--keep", action="store_true", help="keep the scratch folder")
    p.add_argument("--dbt", type=Path, default=DBT, help="dbt executable")
    args = p.parse_args()

    if args.runs < 2:
        print("ERROR: --runs must be >= 2", file=sys.stderr)
        return 2
    if not args.db.exists():
        print(f"ERROR: warehouse not found: {args.db}", file=sys.stderr)
        return 2

    scratch = args.scratch or Path(tempfile.mkdtemp(prefix="check_determinism_"))
    scratch.mkdir(parents=True, exist_ok=True)
    work_db = scratch / "dev.duckdb"
    prof = scratch / "profiles"
    prof.mkdir(exist_ok=True)
    (prof / "profiles.yml").write_text(
        "off_the_pace:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n"
        f"      path: '{work_db}'\n      threads: 1\n      settings:\n        threads: 1\n"
    )
    print(f"scratch: {scratch}\ncopying {args.db} -> {work_db}")
    shutil.copyfile(args.db, work_db)

    base = [
        str(args.dbt), "run", "--profiles-dir", str(prof), "--target-path", str(scratch / "target"),
        "--log-path", str(scratch / "logs"), "--select", *args.select,
    ]
    hashes: dict[str, list[str]] = {m: [] for m in args.select}
    try:
        for i in range(1, args.runs + 1):
            r = subprocess.run(base, cwd=TRANSFORM_ROOT, capture_output=True, text=True)
            if r.returncode != 0:
                print(r.stdout[-3000:], r.stderr[-2000:], file=sys.stderr)
                print(f"ERROR: dbt run {i} failed", file=sys.stderr)
                return 2
            models = smh.load_model_relations(scratch / "target" / "manifest.json")
            con = duckdb.connect(str(work_db), read_only=True)
            try:
                for m in args.select:
                    if m not in models:
                        print(f"ERROR: unknown model {m}", file=sys.stderr)
                        return 2
                    rel = models[m]
                    hashes[m].append(smh.hash_relation(con, rel["schema"], rel["identifier"]))
            finally:
                con.close()
            print(f"run {i}/{args.runs} done")
    finally:
        if not args.keep and args.scratch is None:
            shutil.rmtree(scratch, ignore_errors=True)

    bad = 0
    for m, hs in hashes.items():
        ok = len(set(hs)) == 1
        bad += not ok
        print(f"{'OK  ' if ok else 'DIFF'} {m}: {' '.join(h[:8] for h in hs)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
