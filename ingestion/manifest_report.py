#!/usr/bin/env python3
"""
Manifest report   turn the ingestion run manifests into observability.

Every ingestion attempt is logged to `data/bronze/manifests/run_<id>.parquet`
(see ingest.py:_write_manifest) with status, row count, DQ flag and a schema
fingerprint (SHA-1 of sorted column names). This script reads every manifest
back and reports two things the raw files never surfaced on their own:

  1. Last-run status   the most recent ingestion outcome per (season, round,
     session), so you can see at a glance what is ok / skipped / errored.
  2. Schema drift   when FastF1's column set changes between runs for the same
     (season, session_type), the fingerprint changes. We flag those transitions
     so a silent upstream schema change can't slip through unnoticed.

Usage:
    python ingestion/manifest_report.py                 # human-readable report
    python ingestion/manifest_report.py --markdown      # markdown tables (for docs)
"""

import argparse
import glob
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFESTS_DIR = PROJECT_ROOT / "data" / "bronze" / "manifests"


def load_manifests() -> pd.DataFrame:
    """Read and concatenate every run manifest, oldest first."""
    files = sorted(glob.glob(str(MANIFESTS_DIR / "run_*.parquet")))
    if not files:
        return pd.DataFrame()
    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    # run_id is an ISO-ish UTC stamp; sorting it chronologically orders the runs.
    return df.sort_values("ingested_at_utc").reset_index(drop=True)


def last_run_status(df: pd.DataFrame) -> pd.DataFrame:
    """Most recent outcome per (season, round_number, session_type)."""
    keys = ["season", "round_number", "session_type"]
    latest = df.groupby(keys, as_index=False).tail(1)
    return latest.sort_values(keys).reset_index(drop=True)


def schema_drift(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect fingerprint changes over time within each (season, session_type).

    Only rows that actually wrote data carry a fingerprint, so we ignore blanks.
    Returns one row per detected transition (from_fp → to_fp).
    """
    rows = []
    fp_df = df[df["schema_fingerprint"].astype(str).str.len() > 0]
    for (season, stype), grp in fp_df.groupby(["season", "session_type"]):
        seen = grp["schema_fingerprint"].tolist()
        stamps = grp["ingested_at_utc"].tolist()
        prev = None
        for fp, when in zip(seen, stamps):
            if prev is not None and fp != prev:
                rows.append({
                    "season": season,
                    "session_type": stype,
                    "from_fingerprint": prev,
                    "to_fingerprint": fp,
                    "changed_at_utc": when,
                })
            prev = fp
    return pd.DataFrame(rows)


def _status_counts(latest: pd.DataFrame) -> dict:
    return latest["status"].value_counts().to_dict()


def print_human(df: pd.DataFrame) -> int:
    latest = last_run_status(df)
    drift = schema_drift(df)
    counts = _status_counts(latest)

    print("\n" + "=" * 72)
    print("INGESTION MANIFEST REPORT")
    print("=" * 72)
    print(f"Runs on record:  {df['run_id'].nunique()}")
    print(f"Sessions tracked:{len(latest):>4}  "
          f"(ok={counts.get('ok', 0)}, skip={counts.get('skip', 0)}, error={counts.get('error', 0)})")

    errors = latest[latest["status"] == "error"]
    if not errors.empty:
        print("\nLatest-run ERRORS (need attention):")
        for _, r in errors.iterrows():
            print(f"  ✗ {int(r['season'])} Rd{int(r['round_number'])} {r['session_type']:<4} {r['race_slug']}")

    print("\nSchema drift:")
    if drift.empty:
        print("  ✓ no fingerprint changes detected   FastF1 schema stable across all runs")
    else:
        for _, r in drift.iterrows():
            print(f"  ⚠ {int(r['season'])} {r['session_type']}: "
                  f"{r['from_fingerprint']} → {r['to_fingerprint']} (at {r['changed_at_utc']})")
    print()
    # Non-zero exit if anything errored or drifted   usable as a CI gate.
    return 0 if (errors.empty and drift.empty) else 1


def print_markdown(df: pd.DataFrame) -> int:
    latest = last_run_status(df)
    drift = schema_drift(df)
    counts = _status_counts(latest)

    print("## Ingestion manifest report\n")
    print(f"- Runs on record: **{df['run_id'].nunique()}**")
    print(f"- Sessions tracked: **{len(latest)}** "
          f"(ok={counts.get('ok', 0)}, skip={counts.get('skip', 0)}, error={counts.get('error', 0)})\n")

    print("### Schema drift\n")
    if drift.empty:
        print("No fingerprint changes detected   FastF1 schema stable across all runs.\n")
    else:
        print("| Season | Session | From | To | Changed (UTC) |")
        print("|---|---|---|---|---|")
        for _, r in drift.iterrows():
            print(f"| {int(r['season'])} | {r['session_type']} | "
                  f"`{r['from_fingerprint']}` | `{r['to_fingerprint']}` | {r['changed_at_utc']} |")
        print()
    return 0 if drift.empty else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Report on ingestion run manifests")
    parser.add_argument("--markdown", action="store_true", help="Emit markdown tables (for docs)")
    args = parser.parse_args()

    df = load_manifests()
    if df.empty:
        print(f"No manifests found in {MANIFESTS_DIR}. Run an ingestion first.", file=sys.stderr)
        return 1

    return print_markdown(df) if args.markdown else print_human(df)


if __name__ == "__main__":
    sys.exit(main())
