"""
App data export pipeline.

Exports the Off The Pace warehouse (data/dev.duckdb) to app/public/data/ as
partitioned and unpartitioned Parquet files (ZSTD compressed), then emits
app/public/data/_manifest.json with:
 -the table registry (paths + partition info)
 -a pre-baked stats block (total_laps, models, ml_models, seasons)

Usage:
  python scripts/export_app_data.py           # full export
  python scripts/export_app_data.py --check   # regenerate and diff (CI drift gate)
  python scripts/export_app_data.py --canary  # export only canary tables
  python scripts/export_app_data.py --table fct_driver_skill_features
  python scripts/export_app_data.py --db S/dev.duckdb --out S/out          # scratch export
  python scripts/export_app_data.py --db S/dev.duckdb --out S/out --check  # diff vs S/out/_manifest.json

  python scripts/export_app_data.py --finalize [--out DIR] [--check]   # AX-08, no warehouse (see assistant_finalize.py)

  --db PATH   warehouse to read (default data/dev.duckdb)
  --out DIR   output root (default app/public/data); --check compares against
              DIR/_manifest.json. A non-default --db without --out (and without
              --check) is refused, so a scratch warehouse never overwrites
              app/public/data. ML parquet (data/marts/), ml/model_card.json and
              transform/target/manifest.json (stats.dbt_models) do not follow --db.

Rules:
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
OUT_ROOT_GLOBAL = APP_DATA
MART_PREDS = ROOT / "data" / "marts" / "mart_degradation_predictions.parquet"
DRIVER_NETWORK_RATING = ROOT / "data" / "marts" / "driver_network_rating.parquet"
MODEL_CARD = ROOT / "ml" / "models" / "model_card.json"

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB gate

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
    ("race_to_track",              "dimensions", None,        False),

    # ── Small marts (load once) ────────────────────────────────────────────
    ("fct_driver_skill_features",  "facts",       None,        False),
    ("fct_ghost_race_finish",      "facts",       None,        False),
    ("fct_stint_features",         "facts",       None,        False),
    ("mart_corner_skill_driver",   "marts",       "race_year", False),
    ("mart_degradation_history_envelope", "marts", None,        False),
    ("mart_build_provenance",      "marts",       None,        False),
    # TX-11: the rating and isolation marts the assistant quotes (all < 5 MB, one file each).
    # The other fct_driver_isolation_* tables and fct_power_law_training stay unexported.
    ("mart_race_driver_summary",   "marts",       None,        False),
    ("mart_driver_season_summary", "marts",       None,        False),
    ("mart_metric_benchmark",      "marts",       None,        False),
    ("fct_driver_isolation_race",  "facts",       None,        False),
    # AX-15a: the stint isolation mart is exported too, so AX-15b is a build and a switch, not an export change.
    ("fct_driver_isolation_stint", "facts",       None,        False),
    # AX-07: the race.coverage card reads TX-02's coverage table (173 rows, one per race).
    ("mart_race_coverage",         "marts",       None,        False),

    # ── Large marts (partition by season; heaviest also by race) ──────────
    ("fct_lap_residuals",          "facts",       "race_year", False),
    ("fct_cliff_prediction_features", "facts",    "race_year", False),
    ("fct_ghost_car_pace",         "facts",       "race_year", True),
    # fct_telemetry_deltas handled separately (no race_year col; derived inline)

    # ── Small intermediates (load once) ────────────────────────────────────
    ("int_era_normalized_driver_rating",          "intermediates", None, False),
    ("int_constructor_structural_pace",           "intermediates", None, False),
    ("int_constructor_structural_pace_qualifying","intermediates", None, False),
    ("int_driver_circuit_affinity",               "intermediates", None, False),
    ("int_driver_circuit_era_affinity",           "intermediates", None, False),
    ("int_driver_race_skill_loro",                "intermediates", None, False),
    ("int_circuit_x_constructor_interaction",     "intermediates", None, False),
    ("int_qualifying_decomposed",                 "intermediates", None, False),
    ("int_compound_cliff_predicted",              "intermediates", None, False),
    ("int_tyre_surface_vs_bulk_decoupling",        "intermediates", None, False),
    ("int_synthetic_teammate",                    "intermediates", None, False),
    ("int_track_evolution",                       "intermediates", None, False),
    ("int_field_pace_curve",                      "intermediates", None, False),
    ("int_pit_strategy_value",                    "intermediates", None, False),
    # 149 rows, one per (circuit_slug, season). Season-lagged, so every 2018 row
    # is NULL on every rate: see DERIVED_TABLES below and the race-control
    # feature's methodology for the ruling on which columns may be rendered.
    ("int_sc_hazard_history",                     "intermediates", None, False),

    # ── Large intermediates (partition by season) ──────────────────────────
    ("int_corner_metrics",         "intermediates", "race_year", False),
    ("int_corner_skill_residuals", "intermediates", "race_year", False),
    ("int_lap_air_state",          "intermediates", "race_year", False),
    ("int_lap_anomaly_flags",      "intermediates", "race_year", False),
    ("int_sector_residual_decomposed", "intermediates", "race_year", True),

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

# ─── Derived exports ──────────────────────────────────────────────────────────
# Aggregates computed here rather than in dbt, for tables the app needs at a
# coarser grain than any materialised model carries. Same precedent as
# export_enriched / export_telemetry_deltas: the SQL reads live warehouse
# tables, so it cannot drift from them.
#
# race_caution_timeline collapses int_stint_geometry's per-driver lap flags to
# one row per (race, lap). int_stint_geometry is the table that carries real
# caution flags; fct_lap_residuals carries the same three column NAMES and they
# are FALSE on every one of its 137,447 rows, because that mart is pre-filtered
# to green racing laps. stg_track_status holds the event log but has no lap
# axis (session_time_s only) and, like every staging view, resolves its bronze
# parquet path relative to transform/, which is why stg_pits is already an
# optional export. 8,929 rows, 801 of them caution laps.
DERIVED_TABLES: list[tuple[str, str, str]] = [
    (
        "race_caution_timeline",
        "marts",
        """
        WITH race_lap AS (
            SELECT
                race_year,
                race_id,
                lap_number,
                BOOL_OR(is_safety_car_lap) AS is_safety_car_lap,
                BOOL_OR(is_vsc_lap)        AS is_vsc_lap,
                BOOL_OR(is_red_flag_lap)   AS is_red_flag_lap
            FROM int_stint_geometry
            GROUP BY 1, 2, 3
        )
        SELECT
            rl.race_year,
            rl.race_id,
            rt.track_id AS circuit_slug,
            rl.lap_number,
            rl.is_safety_car_lap,
            rl.is_vsc_lap,
            rl.is_red_flag_lap,
            -- Precedence for a lap carrying more than one status: a red flag
            -- outranks a safety car, which outranks a VSC.
            CASE
                WHEN rl.is_red_flag_lap    THEN 'red_flag'
                WHEN rl.is_safety_car_lap  THEN 'safety_car'
                WHEN rl.is_vsc_lap         THEN 'vsc'
                ELSE 'green'
            END AS caution_status,
            MAX(rl.lap_number) OVER (PARTITION BY rl.race_id) AS race_laps
        FROM race_lap AS rl
        LEFT JOIN race_to_track AS rt ON rl.race_id = rt.race_id
        ORDER BY rl.race_year, rl.race_id, rl.lap_number
        """,
    ),
]

# Optional tables that may be unavailable (stg_ depends on raw bronze files
# being present; skipped gracefully if missing).
OPTIONAL_TABLES: list[tuple[str, str, str | None, bool]] = [
    ("stg_pits",                   "intermediates", "race_year", False),
    # AX-07: the race.result card (finish, grid, status, points) reads stg_results,
    # never mart_race_driver_summary.laps_completed (that counts valid timed laps only).
    ("stg_results",                "intermediates", None,        False),
]

# Canary subset: just enough for the canary feature (#14) and platform validation
CANARY_TABLES = {
    "dim_circuits", "dim_compounds_season", "dim_drivers", "dim_constructors",
    "race_to_track",
    "fct_driver_skill_features", "fct_lap_residuals", "fct_ghost_race_finish",
    "fct_stint_features", "fct_cliff_prediction_features",
    "mart_degradation_history_envelope",
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
    # AX-08: assistant/cards/ is excluded; the finalize stage folds the card sha256s into the version.
    from assistant_finalize import table_hash
    return table_hash(directory)


# Per-build metadata, excluded from the content hash exactly as in
# transform/scripts/snapshot_model_hashes.py (VOLATILE_COLS).
VOLATILE_COLS = {"fit_timestamp", "built_at", "dbt_invocation_id"}


def _entry_files(entry: dict, out_root: Path) -> list[Path]:
    rel = entry["path"].removeprefix("/data/")
    p = out_root / rel
    return sorted(p.rglob("*.parquet")) if p.is_dir() else [p]


def add_freshness(entries: list[dict], out_root: Path) -> None:
    """TX-11: give every manifest entry `rows` and `hash` (content, not file size).

    Same method as the byte oracle (md5_number per row, bit_xor combine, order
    independent) over the parquet just written, so a table whose rows changed
    but whose stats did not still moves the manifest and --check fails.
    """
    import duckdb

    conn = duckdb.connect()
    conn.execute("SET TimeZone='UTC'")
    for entry in entries:
        files = _entry_files(entry, out_root)
        glob = "[" + ", ".join("'" + str(f).replace("'", "''") + "'" for f in files) + "]"
        src = f"read_parquet({glob}, union_by_name=true)"
        cols = [r[0] for r in conn.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()]
        drop = sorted(VOLATILE_COLS & set(cols))
        sel = f"SELECT * EXCLUDE ({', '.join(drop)}) FROM {src}" if drop else f"SELECT * FROM {src}"
        rows, digest = conn.execute(
            "SELECT count(*), md5(CAST(bit_xor(md5_number(CAST(t AS VARCHAR))) AS VARCHAR)) "
            f"FROM ({sel}) t"
        ).fetchone()
        entry["rows"] = rows
        entry["hash"] = digest
    conn.close()


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
        _progress(f"{name}  →  {out.relative_to(OUT_ROOT_GLOBAL.parent)}  ({_size_str(out)})")
        return {
            "name": name,
            "path": f"/data/{out.relative_to(OUT_ROOT_GLOBAL)}",
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
                        "path": f"/data/{out.relative_to(OUT_ROOT_GLOBAL)}",
                    })
                partitions.append({
                    "value": year,
                    "path": f"/data/{year_dir.relative_to(OUT_ROOT_GLOBAL)}",
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
                    "path": f"/data/{out.relative_to(OUT_ROOT_GLOBAL)}",
                })

        size_report.append((name, total_bytes))
        _progress(
            f"{name}  →  {part_dir.relative_to(OUT_ROOT_GLOBAL.parent)}/"
            f"  ({len(partitions)} partitions, {total_bytes/1024**2:.2f} MB total)"
        )
        return {
            "name": name,
            "path": f"/data/{part_dir.relative_to(OUT_ROOT_GLOBAL)}",
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
            "path": f"/data/{out.relative_to(OUT_ROOT_GLOBAL)}",
        })

    size_report.append((name, total_bytes))
    _progress(
        f"{name} (enriched)  →  {part_dir.relative_to(OUT_ROOT_GLOBAL.parent)}/"
        f"  ({len(partitions)} partitions, {total_bytes/1024**2:.2f} MB total)"
    )
    return {
        "name": name,
        "path": f"/data/{part_dir.relative_to(OUT_ROOT_GLOBAL)}",
        "partitioned": True,
        "partitionKey": "race_year",
        "partitions": partitions,
    }


def export_derived(conn, name: str, dest_dir: Path, sql: str, size_report: list) -> dict:
    """Export the result of a derived query as a single parquet."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{name}.parquet"
    conn.execute(f"""
        COPY ({sql})
        TO '{out}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    size_report.append((name, out.stat().st_size))
    _check_size(out, name)
    _progress(f"{name} (derived)  →  {out.relative_to(OUT_ROOT_GLOBAL.parent)}  ({_size_str(out)})")
    return {
        "name": name,
        "path": f"/data/{out.relative_to(OUT_ROOT_GLOBAL)}",
        "partitioned": False,
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
            "path": f"/data/{out.relative_to(OUT_ROOT_GLOBAL)}",
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


def export_telemetry_deltas(conn, dest_dir: Path, size_report: list) -> dict:
    """Export fct_telemetry_deltas with race_year derived inline from race_id."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    part_dir = dest_dir / "fct_telemetry_deltas"
    part_dir.mkdir(parents=True, exist_ok=True)

    years = [
        r[0] for r in conn.execute("""
            SELECT DISTINCT CAST(SPLIT_PART(race_id, '_', 1) AS INTEGER) AS race_year
            FROM fct_telemetry_deltas
            ORDER BY 1
        """).fetchall()
    ]

    partitions = []
    total_bytes = 0
    for year in years:
        out = part_dir / f"{year}.parquet"
        conn.execute(f"""
            COPY (
                SELECT *,
                       CAST(SPLIT_PART(race_id, '_', 1) AS INTEGER) AS race_year
                FROM fct_telemetry_deltas
                WHERE CAST(SPLIT_PART(race_id, '_', 1) AS INTEGER) = {year}
            )
            TO '{out}'
            (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        total_bytes += out.stat().st_size
        partitions.append({
            "value": year,
            "path": f"/data/{out.relative_to(OUT_ROOT_GLOBAL)}",
        })

    size_report.append(("fct_telemetry_deltas", total_bytes))
    _progress(
        f"fct_telemetry_deltas  →  {part_dir.relative_to(OUT_ROOT_GLOBAL.parent)}/"
        f"  ({len(partitions)} partitions, {total_bytes/1024**2:.2f} MB total)"
    )
    return {
        "name": "fct_telemetry_deltas",
        "path": f"/data/{part_dir.relative_to(OUT_ROOT_GLOBAL)}",
        "partitioned": True,
        "partitionKey": "race_year",
        "partitions": partitions,
    }


def export_driver_network_rating(dest_dir: Path, size_report: list) -> dict | None:
    """Export driver_network_rating.parquet from data/marts/ if present."""
    if not DRIVER_NETWORK_RATING.exists():
        _progress("driver_network_rating.parquet not found skipping")
        return None

    ml_dir = dest_dir / "ml"
    ml_dir.mkdir(parents=True, exist_ok=True)
    out = ml_dir / "driver_network_rating.parquet"

    import shutil as _shutil
    _shutil.copy2(DRIVER_NETWORK_RATING, out)

    size_report.append(("driver_network_rating", out.stat().st_size))
    _progress(f"driver_network_rating  →  ml/driver_network_rating.parquet  ({_size_str(out)})")
    return {
        "name": "driver_network_rating",
        "path": "/data/ml/driver_network_rating.parquet",
        "partitioned": False,
    }


def count_significant_models(path: Path) -> tuple[int, int] | None:
    """(significant, total) from a model card's ``model_card.models`` list.

    Counts models whose ``beats_baseline_significant`` is true. Returns None when
    the file is missing, unreadable or not shaped ``{"model_card": {"models": [...]}}``.
    """
    try:
        with open(path) as f:
            card = json.load(f)
        models = card["model_card"]["models"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(models, list) or not all(isinstance(m, dict) for m in models):
        return None
    significant = sum(1 for m in models if m.get("beats_baseline_significant") is True)
    return significant, len(models)


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def build_provenance_block(conn) -> dict | None:
    """The one mart_build_provenance row, plus git_sha / git_dirty (dbt cannot read git).

    None (published as null, with a warning) when the warehouse has no such table.
    """
    try:
        cur = conn.execute("SELECT * FROM mart_build_provenance")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    except Exception as e:  # noqa: BLE001 — any catalog error means "not built"
        print(f"  WARNING: no mart_build_provenance in the warehouse ({e}); publishing provenance: null")
        return None
    if len(rows) != 1:
        print(f"  WARNING: mart_build_provenance has {len(rows)} rows, expected 1; publishing provenance: null")
        return None
    from decimal import Decimal

    def _jsonable(v):
        if hasattr(v, "isoformat"):
            return v.isoformat()
        if isinstance(v, Decimal):
            return float(v)
        return v

    block = {c: _jsonable(v) for c, v in zip(cols, rows[0])}
    sha = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    block["git_sha"] = sha.strip() if sha is not None else None
    block["git_dirty"] = bool(status.strip()) if status is not None else None
    return block


def build_stats_block(conn) -> dict:
    """Build the pre-baked stats block for the home page (zero SQL in browser)."""
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

    # ML models: (significant, total) from ml/models/model_card.json. No fallback:
    # an unreadable card publishes null, never a made-up count (TX-07 / AP-04).
    ml_counts = count_significant_models(MODEL_CARD)
    if ml_counts is None:
        print(f"  WARNING: could not count ML models from {MODEL_CARD}; publishing ml_models: null")
        ml_model_count, ml_model_total = None, None
    else:
        ml_model_count, ml_model_total = ml_counts

    # Read era_boundary from transform/dbt_project.yml vars so the manifest
    # stays in sync with the dbt var without a separate hardcode here.
    era_boundary = 2022
    try:
        import yaml as _yaml
        dbt_proj = ROOT / "transform" / "dbt_project.yml"
        if dbt_proj.exists():
            with open(dbt_proj) as _f:
                _dbt = _yaml.safe_load(_f)
            era_boundary = int(_dbt.get("vars", {}).get("era_boundary", 2022))
    except Exception:
        pass  # fall back to default

    total_drivers = conn.execute("SELECT COUNT(*) FROM dim_drivers").fetchone()[0]
    # Count only raced circuits: circuits that appear in race_to_track
    total_circuits = conn.execute(
        "SELECT COUNT(DISTINCT circuit_key) FROM (SELECT DISTINCT track_id AS circuit_key FROM race_to_track)"
    ).fetchone()[0]

    return {
        "total_laps": total_laps,
        "total_drivers": total_drivers,
        "total_circuits": total_circuits,
        "dbt_models": dbt_model_count,
        "ml_models": ml_model_count,
        "ml_models_total": ml_model_total,
        "seasons": f"{seasons[0]}–{seasons[1]}",
        "seasons_list": list(range(seasons[0], seasons[1] + 1)),
        "era_boundary": era_boundary,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def run_export(
    canary_only: bool = False,
    target_table: str | None = None,
    check_mode: bool = False,
    db_path: Path | None = None,
    out_root: Path | None = None,
) -> None:
    import duckdb

    db_path = Path(db_path).resolve() if db_path is not None else DB_PATH
    out_root = Path(out_root).resolve() if out_root is not None else APP_DATA

    if not db_path.exists():
        print(f"ERROR: warehouse not found at {db_path}")
        sys.exit(1)

    # AX-08: the stg_* views resolve their bronze parquet path relative to transform/, so the export
    # always runs from there (stg_results / stg_pits were silently skipped from the repo root).
    # db_path and out_root are absolute by now, so nothing else depends on the cwd.
    prev_cwd = os.getcwd()
    os.chdir(ROOT / "transform")
    try:
        _run_export_dispatch(canary_only, target_table, check_mode, db_path, out_root)
    finally:
        os.chdir(prev_cwd)


def _run_export_dispatch(canary_only, target_table, check_mode, db_path, out_root) -> None:
    if check_mode:
        # Write to a temp dir, then diff against <out_root>/_manifest.json
        with tempfile.TemporaryDirectory() as tmp:
            _run_export_to(Path(tmp), canary_only, target_table, check_mode=True,
                           db_path=db_path, compare_root=out_root)
        return

    _run_export_to(out_root, canary_only, target_table, check_mode=False,
                   db_path=db_path)


def _run_export_to(
    out_root: Path,
    canary_only: bool,
    target_table: str | None,
    check_mode: bool,
    db_path: Path | None = None,
    compare_root: Path | None = None,
) -> None:
    global OUT_ROOT_GLOBAL
    OUT_ROOT_GLOBAL = out_root
    import duckdb

    db_path = db_path if db_path is not None else DB_PATH
    compare_root = compare_root if compare_root is not None else APP_DATA

    t0 = time.time()
    conn = duckdb.connect(str(db_path), read_only=True)

    print(f"\n{'[CHECK MODE] ' if check_mode else ''}Off The Pace app data export")
    print(f"  warehouse:  {db_path}")
    print(f"  output:     {out_root}")
    if canary_only:
        print("  scope:      canary tables only")
    if target_table:
        print(f"  scope:      single table: {target_table}")
    print()

    manifest_entries: list[dict] = []
    size_report: list[tuple[str, int]] = []

    all_tables = list(TABLES)
    if not canary_only:
        all_tables += OPTIONAL_TABLES

    for name, subdir, partition_by, also_race_id in all_tables:
        if target_table and name != target_table:
            continue
        if canary_only and name not in CANARY_TABLES:
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

    for name, subdir, sql in DERIVED_TABLES:
        if target_table and name != target_table:
            continue
        if canary_only:
            continue
        entry = export_derived(conn, name, out_root / subdir, sql, size_report)
        manifest_entries.append(entry)

    if not canary_only and not target_table:
        for name, subdir in ENRICHED_TABLES:
            dest = out_root / subdir
            try:
                entry = export_enriched(conn, name, dest, size_report)
                manifest_entries.append(entry)
            except Exception as e:
                _progress(f"{name}  →  skipped (optional enriched: {e})")

        try:
            telem_entry = export_telemetry_deltas(conn, out_root / "facts", size_report)
            manifest_entries.append(telem_entry)
        except Exception as e:
            _progress(f"fct_telemetry_deltas  →  skipped (optional: {e})")

        preds_entry = export_predictions_mart(out_root, size_report)
        if preds_entry:
            manifest_entries.append(preds_entry)

        network_entry = export_driver_network_rating(out_root, size_report)
        if network_entry:
            manifest_entries.append(network_entry)

        # AX-02: assistant_entities (names from bronze reference data; the one non-published-file input).
        from assistant_entities import export_assistant_entities
        manifest_entries.append(export_assistant_entities(conn, out_root, size_report))

        # AX-05: qv_* query views + assistant/catalogue.json, built from the files written above.
        from assistant_query_views import export_query_views
        manifest_entries.extend(export_query_views(out_root, manifest_entries, size_report, progress=_progress))

    # Stats block
    stats = build_stats_block(conn)
    provenance = build_provenance_block(conn)
    conn.close()

    add_freshness(manifest_entries, out_root)

    # Manifest
    version_hash = _content_hash(out_root)
    manifest = {
        "version": version_hash,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "provenance": provenance,
        "tables": manifest_entries,
    }

    manifest_path = out_root / "_manifest.json"
    if check_mode:
        # In check mode: compare against current manifest
        existing = compare_root / "_manifest.json"
        if existing.exists():
            with open(existing) as f:
                current = json.load(f)
            # Normalise (strip timestamps and version for comparison)
            def _strip(m):
                m = dict(m)
                m.pop("generatedAt", None)
                m.pop("version", None)
                m.pop("assistant", None)  # AX-08: written by --finalize, verified separately below
                if "stats" in m:
                    m["stats"] = dict(m["stats"])
                # git_sha / git_dirty describe the export run, not the data: a
                # committed manifest can never carry its own commit's sha.
                if isinstance(m.get("provenance"), dict):
                    m["provenance"] = {
                        k: v for k, v in m["provenance"].items()
                        if k not in ("git_sha", "git_dirty")
                    }
                return m
            if _strip(current) != _strip(manifest):
                print("\n  ⚠️  DRIFT DETECTED: manifest is out of date. Run: make app-data")
                sys.exit(1)
            else:
                print("  ✅  No drift manifest is current.")
            # AX-08: every file the assistant block names must still hash to the manifest value.
            if current.get("assistant"):
                from assistant_finalize import verify_assistant
                problems = verify_assistant(compare_root, current)
                for pr in problems:
                    print(f"  ⚠️  {pr}")
                if problems:
                    sys.exit(1)
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


def build_parser() -> argparse.ArgumentParser:
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
        "--canary",
        action="store_true",
        help="Export only the canary table subset.",
    )
    parser.add_argument(
        "--table",
        metavar="NAME",
        help="Export a single named table (for fast re-export of one table).",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        type=Path,
        default=DB_PATH,
        help="Warehouse to read (default: data/dev.duckdb).",
    )
    parser.add_argument(
        "--out",
        metavar="DIR",
        type=Path,
        default=APP_DATA,
        help="Output root (default: app/public/data). --check compares against DIR/_manifest.json.",
    )
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="AX-08: no warehouse. Convert assistant/_staging (build-cards --stage) to card parquet, write the "
             "manifest assistant block and the final version. With --check: verify only.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.finalize:
        from assistant_finalize import finalize
        schema = ROOT / "app" / "src" / "assistant" / "cards" / "card.schema.json"
        sys.exit(finalize(args.out.resolve(), schema, check=args.check))

    # Guard: a scratch warehouse must never be written into app/public/data.
    if (
        args.db.resolve() != DB_PATH.resolve()
        and args.out.resolve() == APP_DATA.resolve()
        and not args.check
    ):
        print("ERROR: refusing to write a scratch warehouse into app/public/data; pass --out")
        sys.exit(2)

    run_export(
        canary_only=args.canary,
        target_table=args.table,
        check_mode=args.check,
        db_path=args.db,
        out_root=args.out,
    )


if __name__ == "__main__":
    main()
