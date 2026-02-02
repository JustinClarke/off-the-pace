"""
Atomic seed CSV writer with promotion workflow.

Write flow:
    1. write_pending(df, name)  → seeds/_pending/{name}_pending.csv  (temp)
    2. Human reviews the pending file
    3. promote(name, confirm=True) → moves to seeds/{name}.csv, archives old

The atomic write (tmp file + rename) prevents dbt from reading a partial CSV
if the fitter is interrupted mid-write.

Usage (CLI):
    python -m tasks.coefficients.seed_writer promote --seed compound_cliff_params --confirm
    python -m tasks.coefficients.seed_writer promote --all --confirm
    python -m tasks.coefficients.seed_writer status
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

import pandas as pd

SEEDS_DIR = Path(__file__).parents[2] / "seeds"
PENDING_DIR = SEEDS_DIR / "_pending"
ARCHIVE_DIR = SEEDS_DIR / "_archive"

MANAGED_SEEDS = ["compound_cliff_params", "circuit_reference"]


def write_pending(df: pd.DataFrame, seed_name: str) -> Path:
    """
    Atomically write df to seeds/_pending/{seed_name}_pending.csv.

    Returns the path written.
    """
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    target = PENDING_DIR / f"{seed_name}_pending.csv"
    tmp = PENDING_DIR / f"{seed_name}_pending.csv.tmp"

    df.to_csv(tmp, index=False)
    tmp.rename(target)  # atomic on POSIX; near-atomic on macOS HFS+
    print(f"[seed_writer] Written: {target}  ({len(df)} rows)")
    return target


def promote(seed_name: str, confirm: bool = False) -> None:
    """
    Promote a pending seed to the live seeds/ directory.

    Operations:
    1. Verify _pending/{seed_name}_pending.csv exists.
    2. Archive the current live seed to _archive/{seed_name}_{today}.csv.
    3. Rename pending → live.
    """
    pending_path = PENDING_DIR / f"{seed_name}_pending.csv"
    live_path = SEEDS_DIR / f"{seed_name}.csv"
    archive_path = ARCHIVE_DIR / f"{seed_name}_{date.today().isoformat()}.csv"

    if not pending_path.exists():
        print(f"[seed_writer] ERROR: No pending file found at {pending_path}")
        sys.exit(1)

    # Show summary before confirming
    df = pd.read_csv(pending_path)
    print(f"\n[seed_writer] Pending: {pending_path.name}")
    print(f"  Rows: {len(df)}")
    if "fit_source" in df.columns:
        print(f"  Sources:\n{df['fit_source'].value_counts().to_string()}")
    if "calibration_flag" in df.columns:
        flags = df["calibration_flag"].value_counts()
        print(f"  Calibration flags:\n{flags.to_string()}")

    if not confirm:
        print("\n[seed_writer] DRY RUN   pass --confirm to promote.")
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if live_path.exists():
        shutil.copy2(live_path, archive_path)
        print(f"[seed_writer] Archived: {archive_path.name}")

    shutil.move(str(pending_path), str(live_path))
    print(f"[seed_writer] Promoted: {live_path.name}")


def status() -> None:
    """Print status of all managed seeds."""
    print("Coefficient seed status:")
    print("-" * 60)
    for name in MANAGED_SEEDS:
        live_path = SEEDS_DIR / f"{name}.csv"
        pending_path = PENDING_DIR / f"{name}_pending.csv"

        if live_path.exists():
            df = pd.read_csv(live_path)
            fit_date = df.get("fit_date", pd.Series(["unknown"])).iloc[0] if len(df) > 0 else "?"
            method = df.get("fit_method", pd.Series(["unknown"])).iloc[0] if len(df) > 0 else "?"
            print(f"  {name}")
            print(f"    Live:    {len(df)} rows  fit_date={fit_date}  method={method}")
        else:
            print(f"  {name}  [NO LIVE SEED]")

        if pending_path.exists():
            pdf = pd.read_csv(pending_path)
            print(f"    Pending: {len(pdf)} rows    run 'make coefficients-promote' to review")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coefficient seed promotion tool.")
    sub = parser.add_subparsers(dest="command")

    promote_p = sub.add_parser("promote", help="Promote pending seed(s) to live.")
    promote_p.add_argument("--seed", help="Seed name (e.g. compound_cliff_params).")
    promote_p.add_argument("--all", action="store_true", help="Promote all managed seeds.")
    promote_p.add_argument("--confirm", action="store_true", help="Actually write (omit for dry run).")

    sub.add_parser("status", help="Show current seed state.")

    args = parser.parse_args(argv)

    if args.command == "status":
        status()
        return 0

    if args.command == "promote":
        seeds_to_promote = MANAGED_SEEDS if args.all else ([args.seed] if args.seed else [])
        if not seeds_to_promote:
            print("ERROR: specify --seed <name> or --all")
            return 1
        for name in seeds_to_promote:
            promote(name, confirm=args.confirm)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
