"""
create_fixtures.py   extract a small subset of bronze parquet data for CI fixtures.

Usage:
    python ingestion/src/create_fixtures.py \
        --output transform/tests/fixtures/bronze

Hardcoded races (chosen for coverage):
    2020 / italian_grand_prix   Monza, low-energy, sprint strategy
    2023 / bahrain_grand_prix   clean dry race, multi-compound baseline
    2024 / sao_paulo_grand_prix   wet/mixed, exercises rain-lap handling
"""

import argparse
import shutil
from pathlib import Path

RACES = [
    ("2020", "italian_grand_prix"),
    ("2023", "bahrain_grand_prix"),
    ("2024", "são_paulo_grand_prix"),
]

DATASETS = ["laps", "weather", "telemetry", "race_control"]


def copy_race(bronze_root: Path, output_root: Path, season: str, race_id: str) -> None:
    for dataset in DATASETS:
        src = bronze_root / dataset / f"season={season}" / f"race={race_id}"
        dst = output_root / dataset / f"season={season}" / f"race={race_id}"
        if not src.exists():
            print(f"  SKIP (not found): {src}")
            continue
        for parquet in src.rglob("*.parquet"):
            rel_path = parquet.relative_to(src)
            dest_file = dst / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(parquet, dest_file)
        print(f"  OK: {dataset}/{season}/{race_id} → {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract CI fixture parquet files from bronze.")
    parser.add_argument(
        "--bronze",
        default="data/bronze",
        help="Path to the full bronze root (default: data/bronze)",
    )
    parser.add_argument(
        "--output",
        default="transform/tests/fixtures/bronze",
        help="Destination root for fixture files",
    )
    args = parser.parse_args()

    bronze_root = Path(args.bronze)
    output_root = Path(args.output)

    if not bronze_root.exists():
        raise SystemExit(f"Bronze root not found: {bronze_root}")

    output_root.mkdir(parents=True, exist_ok=True)
    print(f"Copying {len(RACES)} races × {len(DATASETS)} datasets to {output_root} …")

    for season, race_id in RACES:
        print(f"\n{season}/{race_id}")
        copy_race(bronze_root, output_root, season, race_id)

    total = sum(
        f.stat().st_size
        for f in output_root.rglob("*.parquet")
    )
    print(f"\nDone. Total fixture size: {total / 1_048_576:.1f} MB")


if __name__ == "__main__":
    main()
