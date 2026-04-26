#!/usr/bin/env python3
"""
Comprehensive verification of Bronze layer ingestion (2020–2023).
Checks: dataset presence, row counts, nulls, duplicates, schema conformance.
"""

import json
import sys
import pandas as pd
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent / "src"))
from data_quality import DataQualityEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"

# Expected race counts per season (known from F1 calendar)
EXPECTED_RACES = {
    2020: 17,  # COVID-shortened
    2021: 22,
    2022: 22,
    2023: 21,  # Emilia Romagna cancelled
}

# Expected datasets for each race
EXPECTED_DATASETS = ["laps", "weather", "race_control", "telemetry"]

# Known issues to account for
KNOWN_ISSUES = {
    "2018_round_01": "telemetry",  # Not covered in this run, but good to know
    "2018_round_02": "telemetry",
}


def check_dataset_presence():
    """Verify all expected datasets exist for 2020–2023."""
    print("\n" + "="*80)
    print("1. DATASET PRESENCE CHECK")
    print("="*80)

    results = {}
    missing = defaultdict(list)

    for season in EXPECTED_RACES.keys():
        results[season] = {"expected": EXPECTED_RACES[season], "present": 0, "complete": 0}

        season_dir = BRONZE_DIR / "laps" / f"season={season}"
        if not season_dir.exists():
            print(f"❌ Season {season} directory missing!")
            continue

        race_dirs = sorted([d for d in season_dir.iterdir() if d.is_dir()])
        results[season]["present"] = len(race_dirs)

        # Check each race has all datasets
        complete_races = 0
        for race_dir in race_dirs:
            datasets_found = []
            for dataset in EXPECTED_DATASETS:
                dataset_dir = BRONZE_DIR / dataset / f"season={season}" / race_dir.name
                if dataset_dir.exists():
                    datasets_found.append(dataset)
                else:
                    race_slug = race_dir.name
                    missing[season].append(f"{race_slug}: missing {dataset}")

            if len(datasets_found) == len(EXPECTED_DATASETS):
                complete_races += 1

        results[season]["complete"] = complete_races
        status = "✅" if results[season]["complete"] == results[season]["present"] else "⚠️"
        print(f"{status} {season}: {results[season]['present']}/{results[season]['expected']} races, "
              f"{results[season]['complete']} complete")

        if missing[season]:
            for issue in missing[season][:3]:  # Show first 3 issues
                print(f"   - {issue}")
            if len(missing[season]) > 3:
                print(f"   ... and {len(missing[season]) - 3} more")

    return results, missing


def check_data_quality():
    """Run data quality checks on all ingested laps files."""
    print("\n" + "="*80)
    print("2. DATA QUALITY CHECK (laps files)")
    print("="*80)

    issues = {
        "schema_invalid": [],
        "insufficient_rows": [],
        "high_null_rate": [],
        "duplicate_keys": [],
    }

    quality_stats = {"total_files": 0, "passed": 0, "failed": 0}

    for season in EXPECTED_RACES.keys():
        season_dir = BRONZE_DIR / "laps" / f"season={season}"
        if not season_dir.exists():
            continue

        for race_dir in season_dir.rglob("season=*"):
            if race_dir.is_dir():
                parquet_files = list(race_dir.glob("*.parquet"))

                for pf in parquet_files:
                    quality_stats["total_files"] += 1
                    try:
                        df = pd.read_parquet(pf)

                        # Run all checks
                        try:
                            DataQualityEngine.validate_bronze_schema(df)
                        except ValueError as e:
                            issues["schema_invalid"].append(f"{pf.name}: {e}")
                            quality_stats["failed"] += 1
                            continue

                        try:
                            DataQualityEngine.assert_row_count(df, min_rows=50)
                        except ValueError as e:
                            issues["insufficient_rows"].append(f"{pf.name}: {e}")
                            quality_stats["failed"] += 1
                            continue

                        null_rates = DataQualityEngine.check_null_rates(df, threshold=0.10)
                        high_nulls = {k: v for k, v in null_rates.items() if v > 0.10}
                        if high_nulls:
                            issues["high_null_rate"].append(
                                f"{pf.name}: {high_nulls}"
                            )

                        dup_count = DataQualityEngine.check_lap_key_duplicates(df)
                        if dup_count > 0:
                            issues["duplicate_keys"].append(
                                f"{pf.name}: {dup_count} duplicate keys"
                            )

                        if not high_nulls and dup_count == 0:
                            quality_stats["passed"] += 1
                        else:
                            quality_stats["failed"] += 1

                    except Exception as e:
                        issues["schema_invalid"].append(f"{pf.name}: {type(e).__name__}: {e}")
                        quality_stats["failed"] += 1

    print(f"✅ {quality_stats['passed']}/{quality_stats['total_files']} files passed all checks")
    if quality_stats["failed"] > 0:
        print(f"❌ {quality_stats['failed']} files failed checks\n")
        for issue_type, instances in issues.items():
            if instances:
                print(f"  {issue_type}: {len(instances)} issue(s)")
                for inst in instances[:2]:
                    print(f"    - {inst}")
                if len(instances) > 2:
                    print(f"    ... and {len(instances) - 2} more")

    return quality_stats, issues


def check_row_counts():
    """Sample row counts to ensure data completeness."""
    print("\n" + "="*80)
    print("3. ROW COUNT DISTRIBUTION")
    print("="*80)

    row_count_summary = defaultdict(lambda: {"laps": [], "weather": [], "race_control": [], "telemetry": []})

    for season in EXPECTED_RACES.keys():
        for dataset in EXPECTED_DATASETS:
            dataset_dir = BRONZE_DIR / dataset / f"season={season}"
            if not dataset_dir.exists():
                continue

            for race_dir in dataset_dir.iterdir():
                if race_dir.is_dir():
                    parquet_files = list(race_dir.glob("*.parquet"))
                    for pf in parquet_files:
                        try:
                            df = pd.read_parquet(pf, columns=[])  # Just load metadata
                            row_count_summary[season][dataset].append(len(df))
                        except:
                            pass

    for season in sorted(row_count_summary.keys()):
        print(f"\n{season}:")
        for dataset in EXPECTED_DATASETS:
            counts = row_count_summary[season][dataset]
            if counts:
                print(f"  {dataset:15} {len(counts):3} races | "
                      f"median {int(sum(counts)/len(counts)):8,} rows/race "
                      f"[{min(counts):8,}–{max(counts):8,}]")
            else:
                print(f"  {dataset:15} ⚠️  no files found")


def main():
    print("\n🔍 BRONZE LAYER VERIFICATION (2020–2023)")
    print("="*80)

    # Check 1: Dataset presence
    presence, missing = check_dataset_presence()

    # Check 2: Data quality
    quality, quality_issues = check_data_quality()

    # Check 3: Row count distribution
    check_row_counts()

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    all_present = all(
        presence[season]["complete"] == presence[season]["present"]
        for season in presence
    )
    quality_ok = quality["failed"] == 0

    if all_present and quality_ok:
        print("✅ All checks passed! Data ready for gate re-run.")
    else:
        if not all_present:
            print("⚠️  Some races/datasets are missing. See section 1 above.")
        if not quality_ok:
            print(f"⚠️  {quality['failed']} files failed quality checks. See section 2 above.")

    return 0 if (all_present and quality_ok) else 1


if __name__ == "__main__":
    exit(main())
