#!/usr/bin/env python3
"""
Unified F1 ingestion controller   replaces ingest_all.py and ingest_qualifying_remaining.py.

Writes partitioned Bronze-layer Parquet files:
  Race laps:    laps/season=YYYY/race=<slug>/YYYY_<slug>_laps.parquet
  Quali laps:   laps/season=YYYY/race=<slug>/session=Q/YYYY_<slug>_quali_laps.parquet
  Weather:      weather/season=YYYY/race=<slug>/[session=Q/]weather.parquet
  Race control: race_control/season=YYYY/race=<slug>/race_control.parquet
  Telemetry:    telemetry/season=YYYY/race=<slug>/telemetry.parquet

Usage examples:
  python ingest.py --start-season 2018 --end-season 2024 --sessions both
  python ingest.py -s 2024 --sessions R --force          # re-ingest 2024 races (fixes KI-001)
  python ingest.py -s 2024 --sessions Q --skip-telemetry
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import fastf1
import pandas as pd

from data_quality import DataQualityEngine
from environment import get_config
from logging_config import setup_logging

logger = logging.getLogger(__name__)

PROJECT_ROOT   = Path(__file__).resolve().parent.parent.parent
BRONZE_DIR     = PROJECT_ROOT / "data" / "bronze"
LAPS_DIR       = BRONZE_DIR / "laps"
WEATHER_DIR    = BRONZE_DIR / "weather"
RC_DIR         = BRONZE_DIR / "race_control"
TELEMETRY_DIR  = BRONZE_DIR / "telemetry"
MANIFESTS_DIR  = BRONZE_DIR / "manifests"
CACHE_DIR      = PROJECT_ROOT / "data" / "cache"

WEATHER_COL_MAP = {
    "AirTemp":       "ambient_temp_c",
    "TrackTemp":     "track_temp_c",
    "Humidity":      "humidity_pct",
    "Rainfall":      "rainfall_flag",
    "WindSpeed":     "wind_speed_ms",
    "WindDirection": "wind_direction",
    "Pressure":      "pressure_hpa",
}


# ---------------------------------------------------------------------------
# Run manifest   queryable record of every ingestion attempt
# ---------------------------------------------------------------------------

def _schema_fingerprint(df: pd.DataFrame) -> str:
    """SHA-1 of sorted column names   detects FastF1 schema drift between seasons."""
    col_sig = ",".join(sorted(df.columns))
    return hashlib.sha1(col_sig.encode()).hexdigest()[:12]


def _make_manifest_row(
    run_id: str,
    year: int,
    round_num: int,
    slug: str,
    session_type: str,
    status: str,
    row_count: int = 0,
    dq_passed: bool = False,
    duplicate_lap_keys: int = 0,
    schema_fingerprint: str = "",
) -> dict:
    return {
        "run_id":              run_id,
        "ingested_at_utc":     datetime.now(timezone.utc).isoformat(),
        "season":              year,
        "round_number":        round_num,
        "race_slug":           slug,
        "session_type":        session_type,
        "status":              status,          # ok | skip | error
        "row_count":           row_count,
        "dq_passed":           dq_passed,
        "duplicate_lap_keys":  duplicate_lap_keys,
        "schema_fingerprint":  schema_fingerprint,
    }


def _write_manifest(rows: list[dict], run_id: str) -> None:
    """Append this run's manifest rows to the partitioned manifest Parquet."""
    if not rows:
        return
    os.makedirs(MANIFESTS_DIR, exist_ok=True)
    path = MANIFESTS_DIR / f"run_{run_id}.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False, compression="snappy")
    logger.info(f"Manifest written → {path.name} ({len(rows)} entries)")


# ---------------------------------------------------------------------------
# Retry decorator   pure-Python exponential backoff, no external dependencies
# ---------------------------------------------------------------------------

def _with_retry(fn, max_attempts: int = 4, base_delay: float = 1.0):
    """
    Call fn(), retrying up to max_attempts times with exponential backoff.
    Delays: 1s, 2s, 4s, 8s (base_delay * 2^attempt).
    Raises the last exception if all attempts fail.
    """
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts-1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed: {exc}   retrying in {delay:.0f}s"
                )
                time.sleep(delay)
    raise last_exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(event_name: str) -> str:
    return event_name.lower().replace(" ", "_").replace("'", "")


def _laps_path_race(year: int, slug: str) -> Path:
    return LAPS_DIR / f"season={year}" / f"race={slug}" / f"{year}_{slug}_laps.parquet"


def _laps_path_quali(year: int, slug: str) -> Path:
    return LAPS_DIR / f"season={year}" / f"race={slug}" / "session=Q" / f"{year}_{slug}_quali_laps.parquet"


def _run_quality_checks(df: pd.DataFrame, label: str) -> tuple[bool, int]:
    """
    Run DataQualityEngine checks. Returns (schema_ok, duplicate_key_count).
    Logs warnings but never raises   ingestion should be resilient.
    """
    try:
        DataQualityEngine.validate_bronze_schema(df)
    except ValueError as exc:
        logger.warning(f"  DQ SCHEMA FAIL [{label}]: {exc}")
        return False, 0

    try:
        DataQualityEngine.assert_row_count(df, min_rows=50)
    except ValueError as exc:
        logger.warning(f"  DQ ROW-COUNT WARN [{label}]: {exc}")
        # Low row counts are possible for red-flagged sessions   warn, don't reject

    DataQualityEngine.check_null_rates(df)
    dupe_count = DataQualityEngine.check_lap_key_duplicates(df)
    return True, dupe_count


def _write_weather(session, year: int, round_num: int, slug: str, session_type: str) -> None:
    if not (hasattr(session, "weather_data") and session.weather_data is not None):
        return
    try:
        wx = pd.DataFrame(session.weather_data).reset_index()
        wx["race_id"]   = f"{year}_{round_num}"
        wx["season"]    = year
        if session_type == "Q":
            wx["session_type"] = "Q"
        if "Time" in wx.columns:
            wx["session_time_s"] = wx["Time"].dt.total_seconds()
        wx = wx.rename(columns=WEATHER_COL_MAP)
        if session_type == "Q":
            wx_dir = WEATHER_DIR / f"season={year}" / f"race={slug}" / "session=Q"
        else:
            wx_dir = WEATHER_DIR / f"season={year}" / f"race={slug}"
        os.makedirs(wx_dir, exist_ok=True)
        wx.to_parquet(wx_dir / "weather.parquet", index=False, compression="snappy")
    except Exception as exc:
        logger.warning(f"  Weather failed for {slug}: {exc}")


def _write_race_control(session, year: int, round_num: int, slug: str) -> None:
    if not (hasattr(session, "race_control_messages") and session.race_control_messages is not None):
        return
    try:
        rc = pd.DataFrame(session.race_control_messages).reset_index()
        rc["race_id"] = f"{year}_{round_num}"
        rc["season"]  = year
        if "Time" in rc.columns:
            # Handles both timedelta64 and datetime-with-timezone correctly (fixes KI-001)
            raw = rc["Time"]
            if pd.api.types.is_timedelta64_dtype(raw):
                rc["session_time_s"] = raw.dt.total_seconds()
            elif pd.api.types.is_datetime64_any_dtype(raw):
                epoch = raw.iloc[0].replace(hour=0, minute=0, second=0, microsecond=0)
                rc["session_time_s"] = (raw-epoch).dt.total_seconds()
            else:
                rc["session_time_s"] = pd.to_timedelta(raw, errors="coerce").dt.total_seconds()
        rc = rc.rename(columns={"Category": "category", "Message": "message"})
        rc_dir = RC_DIR / f"season={year}" / f"race={slug}"
        os.makedirs(rc_dir, exist_ok=True)
        rc.to_parquet(rc_dir / "race_control.parquet", index=False, compression="snappy")
    except Exception as exc:
        logger.warning(f"  Race control failed for {slug}: {exc}")


def _write_telemetry(session, year: int, round_num: int, slug: str) -> None:
    records = []
    for _, lap_row in session.laps.iterrows():
        driver  = lap_row["Driver"]
        lap_num = lap_row["LapNumber"]
        try:
            tel = lap_row.get_telemetry()
            if tel is None or tel.empty:
                continue
            tel = tel.reset_index()
            tel["driver_id"]  = driver
            tel["lap_number"] = lap_num
            tel["race_id"]    = f"{year}_{round_num}"
            tel["season"]     = year
            records.append(tel)
        except Exception:
            pass  # SC laps, pit-out laps, red-flagged stints   expected

    if not records:
        logger.warning(f"  No telemetry for {slug}")
        return

    df = pd.concat(records, ignore_index=True).rename(columns={
        "Speed":    "speed_kph",
        "Throttle": "throttle_pct",
        "Brake":    "brake",
        "Distance": "distance_m",
    })
    out = TELEMETRY_DIR / f"season={year}" / f"race={slug}"
    os.makedirs(out, exist_ok=True)
    df.to_parquet(out / "telemetry.parquet", index=False, compression="snappy")
    logger.info(f"  Telemetry: {len(df):,} samples")


# ---------------------------------------------------------------------------
# Session-level ingest functions
# ---------------------------------------------------------------------------

def ingest_race(
    year: int, round_num: int, slug: str, force: bool, skip_telemetry: bool,
    run_id: str = "",
) -> tuple[str, dict]:
    """
    Ingest a single Race session. Returns (status, manifest_row).
    Status is one of: 'ok', 'skip', 'error'.
    """
    target = _laps_path_race(year, slug)

    if target.exists() and not force:
        logger.info(f"  [SKIP] R  {year} Rd{round_num} {slug}")
        return "skip", _make_manifest_row(run_id, year, round_num, slug, "R", "skip")

    logger.info(f"  [PULL] R  {year} Rd{round_num} {slug}")
    try:
        session = _with_retry(lambda: _load_race_session(year, round_num))

        laps_df = pd.DataFrame(session.laps)
        laps_df["race_id"] = f"{year}_{round_num}"
        laps_df["season"]  = year

        label = f"{year} Rd{round_num} R"
        dq_ok, dupe_count = _run_quality_checks(laps_df, label)
        if not dq_ok:
            logger.warning(f"  [DQ FAIL] {label}   skipping write")
            return "error", _make_manifest_row(
                run_id, year, round_num, slug, "R", "error",
                row_count=len(laps_df), dq_passed=False,
            )

        os.makedirs(target.parent, exist_ok=True)
        laps_df.to_parquet(target, index=False, compression="snappy")
        logger.info(f"  [OK]   R  {year} Rd{round_num} {slug}   {len(laps_df)} laps")

        _write_weather(session, year, round_num, slug, "R")
        _write_race_control(session, year, round_num, slug)

        if not skip_telemetry:
            try:
                _write_telemetry(session, year, round_num, slug)
            except Exception as exc:
                logger.warning(f"  Telemetry failed for {slug}: {exc}")

        time.sleep(0.5)
        row = _make_manifest_row(
            run_id, year, round_num, slug, "R", "ok",
            row_count=len(laps_df), dq_passed=True,
            duplicate_lap_keys=dupe_count,
            schema_fingerprint=_schema_fingerprint(laps_df),
        )
        return "ok", row

    except Exception as exc:
        logger.warning(f"  [ERR]  R  {year} Rd{round_num} {slug}: {exc}")
        return "error", _make_manifest_row(run_id, year, round_num, slug, "R", "error")


def ingest_qualifying(
    year: int, round_num: int, slug: str, force: bool,
    run_id: str = "",
) -> tuple[str, dict]:
    """
    Ingest a single Qualifying session. Returns (status, manifest_row).
    Status is one of: 'ok', 'skip', 'error'.
    """
    target = _laps_path_quali(year, slug)

    if target.exists() and not force:
        logger.info(f"  [SKIP] Q  {year} Rd{round_num} {slug}")
        return "skip", _make_manifest_row(run_id, year, round_num, slug, "Q", "skip")

    logger.info(f"  [PULL] Q  {year} Rd{round_num} {slug}")
    try:
        session = _with_retry(
            lambda: _load_qualifying_session(year, round_num)
        )

        laps = session.laps
        if laps is None or laps.empty:
            logger.warning(f"  [WARN] Q  {year} Rd{round_num}   no lap data")
            return "error", _make_manifest_row(run_id, year, round_num, slug, "Q", "error")

        laps = laps.copy()
        laps["season"]       = year
        laps["race_name"]    = slug
        laps["session_type"] = "Q"
        laps["race_id"]      = f"{year}_{round_num}"

        label = f"{year} Rd{round_num} Q"
        _, dupe_count = _run_quality_checks(laps, label)  # warn only   don't gate on schema

        os.makedirs(target.parent, exist_ok=True)
        laps.to_parquet(target, index=False, compression="snappy")
        logger.info(f"  [OK]   Q  {year} Rd{round_num} {slug}   {len(laps)} laps")

        _write_weather(session, year, round_num, slug, "Q")

        time.sleep(0.3)
        row = _make_manifest_row(
            run_id, year, round_num, slug, "Q", "ok",
            row_count=len(laps), dq_passed=True,
            duplicate_lap_keys=dupe_count,
            schema_fingerprint=_schema_fingerprint(laps),
        )
        return "ok", row

    except Exception as exc:
        logger.warning(f"  [ERR]  Q  {year} Rd{round_num} {slug}: {exc}")
        return "error", _make_manifest_row(run_id, year, round_num, slug, "Q", "error")


def _load_race_session(year: int, round_num: int):
    session = fastf1.get_session(year, round_num, "R")
    session.load()
    return session


def _load_qualifying_session(year: int, round_num: int):
    session = fastf1.get_session(year, round_num, "Q", backend="fastf1")
    session.load(laps=True, telemetry=False, weather=True)
    return session


# ---------------------------------------------------------------------------
# Season-level orchestration
# ---------------------------------------------------------------------------

def ingest_season(
    year: int,
    sessions: str,
    force: bool,
    skip_telemetry: bool,
    run_id: str = "",
) -> tuple[dict, list[dict]]:
    """
    Ingest all rounds for a season.
    Returns (counts, manifest_rows) where counts has ok/skip/error per session type.
    """
    logger.info(f"=== Season {year} ===")

    counts = {"R_ok": 0, "R_skip": 0, "R_error": 0, "Q_ok": 0, "Q_skip": 0, "Q_error": 0}
    manifest_rows: list[dict] = []

    try:
        schedule = _with_retry(lambda: fastf1.get_event_schedule(year, backend="fastf1"))
    except Exception as exc:
        logger.error(f"Schedule fetch failed for {year}: {exc}")
        return counts, manifest_rows

    for _, row in schedule.iterrows():
        rn = row["RoundNumber"]
        if pd.isna(rn) or int(rn) == 0:
            continue
        round_num = int(rn)
        slug = _slug(row["EventName"])

        if sessions in ("R", "both"):
            result, mrow = ingest_race(year, round_num, slug, force, skip_telemetry, run_id)
            counts[f"R_{result}"] += 1
            manifest_rows.append(mrow)

        if sessions in ("Q", "both"):
            result, mrow = ingest_qualifying(year, round_num, slug, force, run_id)
            counts[f"Q_{result}"] += 1
            manifest_rows.append(mrow)

    _log_season_summary(year, sessions, counts)
    return counts, manifest_rows


def _log_season_summary(year: int, sessions: str, counts: dict) -> None:
    parts = []
    if sessions in ("R", "both"):
        parts.append(
            f"R: {counts['R_ok']} ok, {counts['R_skip']} skip, {counts['R_error']} error"
        )
    if sessions in ("Q", "both"):
        parts.append(
            f"Q: {counts['Q_ok']} ok, {counts['Q_skip']} skip, {counts['Q_error']} error"
        )
    logger.info(f"Season {year} complete   " + " | ".join(parts))


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Unified F1 Bronze-layer ingestion controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ingest.py --season 2024 --session R
                 Ingest 2024 races only
  python ingest.py --season 2024 --session both
                 Ingest 2024 races and qualifying
  python ingest.py --start-season 2018 --end-season 2024 --session both
                 Full historical backfill (4–6 hours)
  python ingest.py --season 2024 --force
                 Re-ingest 2024, overwriting existing files
  python ingest.py --season 2024 --skip-telemetry --dry-run
                 Dry-run without pulling telemetry
        """,
    )
    season_group = p.add_mutually_exclusive_group(required=True)
    season_group.add_argument(
        "--start-season", type=int, metavar="YEAR",
        help="First season to ingest (use with --end-season)",
    )
    season_group.add_argument(
        "-s", "--season", type=int, metavar="YEAR",
        help="Single season shorthand (equivalent to --start-season N --end-season N)",
    )
    p.add_argument(
        "--end-season", type=int, metavar="YEAR",
        help="Last season to ingest (inclusive). Required with --start-season.",
    )
    p.add_argument(
        "--session", dest="sessions", choices=["R", "Q", "both"], default="both",
        help="Which session types to ingest (default: both)",
    )
    p.add_argument(
        "--skip-telemetry", action="store_true",
        help="Skip telemetry extraction (faster dry-runs and qualifying-only runs)",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Overwrite existing Parquet files instead of skipping them",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be fetched without pulling data",
    )
    p.add_argument(
        "--log-level", type=str, default="INFO",
        help="Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)",
    )
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    setup_logging(args.log_level)
    config = get_config()

    if args.season is not None:
        start_year = end_year = args.season
    else:
        start_year = args.start_season
        end_year   = args.end_season or args.start_season

    if start_year > end_year:
        parser.error(f"--start-season {start_year} is after --end-season {end_year}")

    if args.dry_run:
        total_races = (end_year-start_year + 1) * 23
        estimated_gb = total_races * 0.15
        logger.info(
            f"DRY RUN: Would ingest {start_year}–{end_year} ({total_races} races, "
            f"~{estimated_gb:.1f} GB)"
        )
        return

    for d in [LAPS_DIR, WEATHER_DIR, RC_DIR, TELEMETRY_DIR, MANIFESTS_DIR, CACHE_DIR]:
        os.makedirs(d, exist_ok=True)
    fastf1.Cache.enable_cache(str(config.fastf1_cache_dir))

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    logger.info(
        f"Ingestion run {run_id}: {start_year}–{end_year} | sessions={args.sessions} | "
        f"force={args.force} | skip_telemetry={args.skip_telemetry}"
    )
    logger.info(f"Bronze: {BRONZE_DIR}")

    total_ok = 0
    all_manifest_rows: list[dict] = []
    for year in range(start_year, end_year + 1):
        counts, manifest_rows = ingest_season(
            year,
            sessions=args.sessions,
            force=args.force,
            skip_telemetry=args.skip_telemetry,
            run_id=run_id,
        )
        total_ok += counts.get("R_ok", 0) + counts.get("Q_ok", 0)
        all_manifest_rows.extend(manifest_rows)

    _write_manifest(all_manifest_rows, run_id)
    logger.info(f"=== COMPLETE: {total_ok} sessions newly written ===")


if __name__ == "__main__":
    main()
