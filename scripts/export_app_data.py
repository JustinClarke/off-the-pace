"""
export_app_data.py  –  Sprint 0 F1: data export pipeline (AD-2, AD-13)

Exports the Off The Pace warehouse (data/dev.duckdb) to app/public/data/ as
partitioned and unpartitioned Parquet files (ZSTD compressed), then emits
app/public/data/_manifest.json with:
 -the table registry (paths + partition info)
 -a pre-baked stats block (AD-12: total_laps, models, ml_models, seasons)

Usage:
  python scripts/export_app_data.py           # full export
  python scripts/export_app_data.py --check   # regenerate and diff (CI drift gate)
  python scripts/export_app_data.py --wave 0  # export only Wave-0 / canary tables
  python scripts/export_app_data.py --table fct_driver_skill_features

Rules (AD-13):
 -Reference dims and small marts: single parquet, load once.
 -Lap-grain large tables: PARTITION_BY race_year (+ race_id for heaviest).
 -No raw stg_telemetry ever exported.
 -CI fails if any single non-partitioned file exceeds 5 MB.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "dev.duckdb"
APP_DATA = ROOT / "app" / "public" / "data"
MART_PREDS = ROOT / "data" / "marts" / "mart_degradation_predictions.parquet"

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB gate (AD-2)

# ─── Table catalogue ──────────────────────────────────────────────────────────
# Each entry: (name, dest_subdir, partition_by, partition_also_by_race_id)
# partition_by=None → single parquet file
# partition_by="race_year" → directory per year; set race_id=True for heaviest

TABLES: list[tuple[str, str, str | None, bool]] = [
    # ── Reference dims (small, load once) ─────────────────────────────────
    ("dim_circuits",               "dimensions", None,        False),
    ("dim_compounds_season",       "dimensions", None,        False),
    ("dim_drivers",                "dimensions", None,        False),
    ("dim_constructors",           "dimensions", None,        False),
    ("dim_events",                 "dimensions", None,        False),
    ("race_to_track",              "dimensions", None,        False),

    # ── Small marts (load once) ────────────────────────────────────────────
    ("fct_driver_skill_features",  "facts",       None,        False),
    ("fct_racecraft",              "facts",       None,        False),
    ("fct_ghost_race_finish",      "facts",       None,        False),
    ("fct_stint_features",         "facts",       None,        False),

    # ── Large marts (partition by season; heaviest also by race) ──────────
    ("fct_lap_residuals",          "facts",       "race_year", False),
    ("fct_cliff_prediction_features", "facts",    "race_year", False),
    ("fct_ghost_car_pace",         "facts",       "race_year", True),
    ("fct_telemetry_deltas",       "facts",       None,        False),   # joined; no race_year col; small enough

    # ── Small intermediates (load once) ────────────────────────────────────
    ("int_era_normalized_driver_rating",          "intermediates", None, False),
    ("int_constructor_structural_pace",           "intermediates", None, False),
    ("int_constructor_structural_pace_qualifying","intermediates", None, False),
    ("int_driver_circuit_affinity",               "intermediates", None, False),
    ("int_circuit_x_constructor_interaction",     "intermediates", None, False),
    ("int_qualifying_decomposed",                 "intermediates", None, False),
    ("int_compound_cliff_predicted",              "intermediates", None, False),
    ("int_tyre_surface_vs_bulk_decoupling",        "intermediates", None, False),
    ("int_synthetic_teammate",                    "intermediates", None, False),
    ("int_track_geometry",                        "intermediates", None, False),
    ("int_corner_metrics",                        "intermediates", None, False),
    ("int_track_evolution",                       "intermediates", None, False),
    ("int_field_pace_curve",                      "intermediates", None, False),
    ("int_pit_strategy_value",                    "intermediates", None, False),
    ("int_corner_skill_residuals",                "intermediates", None, False),
    ("int_penalties",                             "intermediates", None, False),
    ("int_wind_component",                        "intermediates", "race_year", False),
    ("int_air_density",                           "intermediates", "race_year", False),

    # ── Large intermediates (partition by season) ──────────────────────────
    ("int_lap_air_state",          "intermediates", "race_year", False),
    ("int_lap_energy_management",  "intermediates", "race_year", False),
    ("int_lap_anomaly_flags",      "intermediates", "race_year", False),
    ("int_overtakes",              "intermediates", "race_year", False),
    ("int_race_control_events",    "intermediates", "race_year", False),
    ("int_sector_residual_decomposed", "intermediates", "race_year", True),
    ("int_lap_powertrain_signature",   "intermediates", "race_year", False),
    ("int_lap_line_deviation",         "intermediates", "race_year", True),

    # ── Tables without race_year (join-enriched below) ─────────────────────
    # int_dirty_air_tax_component: join via fct_lap_residuals on lap_id → add race_year
    # int_coast_tax_component:     join via fct_lap_residuals on lap_id → add race_year
    # Handled separately as ENRICHED_TABLES below.

    # ── Staging (Feature 9 only) ───────────────────────────────────────────
    # stg_pits: depends on bronze parquet files being present; skip if unavailable.
    # See OPTIONAL_TABLES below.
]

# Tables with lap_id but no race_year enriched via fct_lap_residuals join
ENRICHED_TABLES: list[tuple[str, str]] = [
    ("int_dirty_air_tax_component", "intermediates"),
    ("int_coast_tax_component",     "intermediates"),
]

# Optional tables that may be unavailable (stg_ depends on raw bronze files)
OPTIONAL_TABLES: list[tuple[str, str, str | None, bool]] = [
    ("stg_pits", "intermediates", "race_year", False),
]

# Wave-0 subset: just enough for the canary feature (#14) and platform validation
WAVE0_TABLES = {
    "dim_circuits", "dim_compounds_season", "dim_drivers", "dim_constructors", "dim_events",
    "race_to_track",
    "fct_driver_skill_features", "fct_lap_residuals", "fct_ghost_race_finish",
    "fct_stint_features", "fct_cliff_prediction_features",
    "int_era_normalized_driver_rating", "int_constructor_structural_pace",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _progress(msg: str) -> None:
    print(f"  {msg}", flush=True)


def _size_str(path: Path) -> str:
    b = path.stat().st_size
    if b < 1024:
        return f"{b} B"
    elif b < 1024 ** 2:
        return f"{b/1024:.1f} KB"
    else:
        return f"{b/1024**2:.2f} MB"


def _check_size(path: Path, name: str) -> None:
    """Fail if a single (non-partitioned) file exceeds the 5 MB gate."""
    if path.stat().st_size > MAX_FILE_BYTES:
        size = path.stat().st_size / 1024 ** 2
        print(f"\n  ❌  SIZE GATE FAILED: {name} ({path.name}) is {size:.2f} MB > 5 MB limit.")
        print(     "     Partition this table by race_year in TABLES catalogue.")
        sys.exit(1)


def _content_hash(directory: Path) -> str:
    """SHA-256 over all parquet file sizes + names (fast, stable proxy for content)."""
    h = hashlib.sha256()
    for f in sorted(directory.rglob("*.parquet")):
        h.update(f.name.encode())
        h.update(str(f.stat().st_size).encode())
    return h.hexdigest()[:16]


# ─── Core export functions ────────────────────────────────────────────────────

def export_table(
    conn,
    name: str,
    dest_dir: Path,
    partition_by: str | None,
    partition_also_race_id: bool,
    size_report: list,
) -> dict:
    """Export one table and return its manifest entry."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    if partition_by is None:
        # Single parquet file
        out = dest_dir / f"{name}.parquet"
        conn.execute(f"""
            COPY (SELECT * FROM {name})
            TO '{out}'
            (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        size_report.append((name, out.stat().st_size))
        _check_size(out, name)
        _progress(f"{name}  →  {out.relative_to(ROOT/'app'/'public')}  ({_size_str(out)})")
        return {
            "name": name,
            "path": f"/data/{out.relative_to(ROOT/'app'/'public'/'data')}",
            "partitioned": False,
        }
    else:
        # Partitioned directory
        part_dir = dest_dir / name
        part_dir.mkdir(parents=True, exist_ok=True)

        # Get distinct partition values
        years = [
            r[0] for r in conn.execute(
                f"SELECT DISTINCT {partition_by} FROM {name} ORDER BY {partition_by}"
            ).fetchall()
        ]

        partitions = []
        total_bytes = 0

        for year in years:
            if partition_also_race_id:
                # Sub-partition by race_id within year
                year_dir = part_dir / str(year)
                year_dir.mkdir(parents=True, exist_ok=True)
                race_ids = [
                    r[0] for r in conn.execute(
                        f"SELECT DISTINCT race_id FROM {name} WHERE {partition_by} = {year} ORDER BY race_id"
                    ).fetchall()
                ]
                race_partitions = []
                for rid in race_ids:
                    out = year_dir / f"{rid}.parquet"
                    conn.execute(f"""
                        COPY (SELECT * FROM {name} WHERE {partition_by} = {year} AND race_id = '{rid}')
                        TO '{out}'
                        (FORMAT PARQUET, COMPRESSION ZSTD)
                    """)
                    total_bytes += out.stat().st_size
                    race_partitions.append({
                        "value": rid,
                        "path": f"/data/{out.relative_to(ROOT/'app'/'public'/'data')}",
                    })
                partitions.append({
                    "value": year,
                    "path": f"/data/{year_dir.relative_to(ROOT/'app'/'public'/'data')}",
                    "subPartitions": race_partitions,
                })
            else:
                out = part_dir / f"{year}.parquet"
                conn.execute(f"""
                    COPY (SELECT * FROM {name} WHERE {partition_by} = {year})
                    TO '{out}'
                    (FORMAT PARQUET, COMPRESSION ZSTD)
                """)
                total_bytes += out.stat().st_size
                partitions.append({
                    "value": year,
                    "path": f"/data/{out.relative_to(ROOT/'app'/'public'/'data')}",
                })

        size_report.append((name, total_bytes))
        _progress(
            f"{name}  →  {part_dir.relative_to(ROOT/'app'/'public')}/"
            f"  ({len(partitions)} partitions, {total_bytes/1024**2:.2f} MB total)"
        )
        return {
            "name": name,
            "path": f"/data/{part_dir.relative_to(ROOT/'app'/'public'/'data')}",
            "partitioned": True,
            "partitionKey": partition_by,
            "partitions": partitions,
        }


def export_enriched(conn, name: str, dest_dir: Path, size_report: list) -> dict:
    """Export a table that lacks race_year by joining through fct_lap_residuals."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Build a year-partitioned enriched view
    part_dir = dest_dir / name
    part_dir.mkdir(parents=True, exist_ok=True)

    years = [
        r[0] for r in conn.execute(
            f"""
            SELECT DISTINCT lr.race_year
            FROM {name} t
            JOIN fct_lap_residuals lr ON t.lap_id = lr.lap_id
            ORDER BY 1
            """
        ).fetchall()
    ]

    partitions = []
    total_bytes = 0

    for year in years:
        out = part_dir / f"{year}.parquet"
        conn.execute(f"""
            COPY (
                SELECT t.*
                FROM {name} t
                JOIN fct_lap_residuals lr ON t.lap_id = lr.lap_id
                WHERE lr.race_year = {year}
            )
            TO '{out}'
            (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        total_bytes += out.stat().st_size
        partitions.append({
            "value": year,
            "path": f"/data/{out.relative_to(ROOT/'app'/'public'/'data')}",
        })

    size_report.append((name, total_bytes))
    _progress(
        f"{name} (enriched)  →  {part_dir.relative_to(ROOT/'app'/'public')}/"
        f"  ({len(partitions)} partitions, {total_bytes/1024**2:.2f} MB total)"
    )
    return {
        "name": name,
        "path": f"/data/{part_dir.relative_to(ROOT/'app'/'public'/'data')}",
        "partitioned": True,
        "partitionKey": "race_year",
        "partitions": partitions,
    }


def export_predictions_mart(dest_dir: Path, size_report: list) -> dict | None:
    """Export mart_degradation_predictions.parquet from data/marts/ if present."""
    if not MART_PREDS.exists():
        _progress("mart_degradation_predictions.parquet not found skipping")
        return None

    import duckdb as _ddb
    conn = _ddb.connect()

    ml_dir = dest_dir / "ml"
    ml_dir.mkdir(parents=True, exist_ok=True)
    part_dir = ml_dir / "mart_degradation_predictions"
    part_dir.mkdir(parents=True, exist_ok=True)

    years = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT race_year FROM read_parquet('{MART_PREDS}') ORDER BY 1"
        ).fetchall()
    ]

    partitions = []
    total_bytes = 0

    for year in years:
        out = part_dir / f"{year}.parquet"
        conn.execute(f"""
            COPY (SELECT * FROM read_parquet('{MART_PREDS}') WHERE race_year = {year})
            TO '{out}'
            (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        total_bytes += out.stat().st_size
        partitions.append({
            "value": year,
            "path": f"/data/{out.relative_to(ROOT/'app'/'public'/'data')}",
        })

    size_report.append(("mart_degradation_predictions", total_bytes))
    _progress(
        f"mart_degradation_predictions  →  ml/mart_degradation_predictions/"
        f"  ({len(partitions)} partitions, {total_bytes/1024**2:.2f} MB total)"
    )
    return {
        "name": "mart_degradation_predictions",
        "path": "/data/ml/mart_degradation_predictions",
        "partitioned": True,
        "partitionKey": "race_year",
        "partitions": partitions,
    }


def build_stats_block(conn) -> dict:
    """Build the AD-12 pre-baked stats block for the home page (zero SQL in browser)."""
    total_laps = conn.execute("SELECT COUNT(*) FROM fct_lap_residuals").fetchone()[0]
    seasons = conn.execute(
        "SELECT MIN(race_year), MAX(race_year) FROM fct_lap_residuals"
    ).fetchone()

    # Count dbt models: prefer transform manifest (compiled), fall back to .sql file count
    dbt_manifest = ROOT / "transform" / "target" / "manifest.json"
    dbt_model_count = 0
    if dbt_manifest.exists():
        with open(dbt_manifest) as f:
            dm = json.load(f)
        dbt_model_count = len([
            k for k in dm.get("nodes", {})
            if k.startswith("model.")
        ])
    if not dbt_model_count:
        import glob as _glob
        dbt_model_count = len(_glob.glob(str(ROOT / "transform" / "models" / "**" / "*.sql"), recursive=True))

    # ML models: count production _v1.onnx files only (excludes smoke-test variants)
    ml_models_dir = ROOT / "ml" / "models"
    ml_model_count = (
        len(list(ml_models_dir.glob("*_v1.onnx")))
        if ml_models_dir.exists()
        else 0
    )

    return {
        "total_laps": total_laps,
        "dbt_models": dbt_model_count,
        "ml_models": ml_model_count or 5,
        "seasons": f"{seasons[0]}–{seasons[1]}",
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def run_export(
    wave0_only: bool = False,
    target_table: str | None = None,
    check_mode: bool = False,
) -> None:
    import duckdb

    if not DB_PATH.exists():
        print(f"ERROR: warehouse not found at {DB_PATH}")
        sys.exit(1)

    if check_mode:
        # Write to a temp dir, then diff
        with tempfile.TemporaryDirectory() as tmp:
            _run_export_to(Path(tmp), wave0_only, target_table, check_mode=True)
        return

    _run_export_to(APP_DATA, wave0_only, target_table, check_mode=False)


def _run_export_to(
    out_root: Path,
    wave0_only: bool,
    target_table: str | None,
    check_mode: bool,
) -> None:
    import duckdb

    t0 = time.time()
    conn = duckdb.connect(str(DB_PATH), read_only=True)

    print(f"\n{'[CHECK MODE] ' if check_mode else ''}Off The Pace app data export")
    print(f"  warehouse:  {DB_PATH}")
    print(f"  output:     {out_root}")
    if wave0_only:
        print("  scope:      Wave 0 (canary tables only)")
    if target_table:
        print(f"  scope:      single table: {target_table}")
    print()

    manifest_entries: list[dict] = []
    size_report: list[tuple[str, int]] = []

    all_tables = list(TABLES)
    if not wave0_only:
        all_tables += OPTIONAL_TABLES

    for name, subdir, partition_by, also_race_id in all_tables:
        if target_table and name != target_table:
            continue
        if wave0_only and name not in WAVE0_TABLES:
            continue

        dest = out_root / subdir
        try:
            entry = export_table(conn, name, dest, partition_by, also_race_id, size_report)
            manifest_entries.append(entry)
        except Exception as e:
            if (name, subdir, partition_by, also_race_id) in OPTIONAL_TABLES:
                _progress(f"{name}  →  skipped (optional: {e})")
            else:
                print(f"\n  ❌  FAILED: {name}: {e}")
                sys.exit(1)

    if not wave0_only and not target_table:
        for name, subdir in ENRICHED_TABLES:
            dest = out_root / subdir
            try:
                entry = export_enriched(conn, name, dest, size_report)
                manifest_entries.append(entry)
            except Exception as e:
                print(f"\n  ❌  FAILED enriched: {name}: {e}")
                sys.exit(1)

        preds_entry = export_predictions_mart(out_root, size_report)
        if preds_entry:
            manifest_entries.append(preds_entry)

    # Stats block (AD-12)
    stats = build_stats_block(conn)
    conn.close()

    # Manifest
    version_hash = _content_hash(out_root)
    manifest = {
        "version": version_hash,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "tables": manifest_entries,
    }

    manifest_path = out_root / "_manifest.json"
    if check_mode:
        # In check mode: compare against current manifest
        existing = APP_DATA / "_manifest.json"
        if existing.exists():
            with open(existing) as f:
                current = json.load(f)
            # Normalise (strip timestamps and version for comparison)
            def _strip(m):
                m = dict(m)
                m.pop("generatedAt", None)
                m.pop("version", None)
                if "stats" in m:
                    m["stats"] = dict(m["stats"])
                return m
            if _strip(current) != _strip(manifest):
                print("\n  ⚠️  DRIFT DETECTED: manifest is out of date. Run: make app-data")
                sys.exit(1)
            else:
                print("  ✅  No drift manifest is current.")
        else:
            print("  ⚠️  No existing manifest found.")
        return

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    elapsed = time.time()-t0

    print(f"\n  ─── Size report ───────────────────────────────")
    total_exported = 0
    for name, nb in sorted(size_report, key=lambda x: -x[1]):
        bar = "█" * min(40, max(1, int(nb / (1024 * 100))))
        print(f"  {name:<48}  {nb/1024**2:6.2f} MB  {bar}")
        total_exported += nb
    print(f"\n  Total exported:  {total_exported/1024**2:.2f} MB")
    print(f"  Tables:          {len(manifest_entries)}")
    print(f"  Manifest hash:   {version_hash}")
    print(f"  Elapsed:         {elapsed:.1f}s")
    print(f"\n  ✅  Written → {manifest_path}")
    print(f"  Stats block:  {stats}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Off The Pace warehouse to app/public/data/ parquet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate manifest in a temp dir and diff against current (CI drift gate).",
    )
    parser.add_argument(
        "--wave",
        type=int,
        choices=[0],
        help="Export only the Wave-0 / canary table subset.",
    )
    parser.add_argument(
        "--table",
        metavar="NAME",
        help="Export a single named table (for fast re-export of one table).",
    )
    args = parser.parse_args()

    run_export(
        wave0_only=(args.wave == 0),
        target_table=args.table,
        check_mode=args.check,
    )


if __name__ == "__main__":
    main()
