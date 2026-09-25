#!/usr/bin/env python3
"""
Unified F1 ingestion controller   replaces ingest_all.py and ingest_qualifying_remaining.py.

Writes partitioned Bronze-layer Parquet files:
  Race laps:    laps/season=YYYY/race=<slug>/YYYY_<slug>_laps.parquet
  Quali laps:   laps/season=YYYY/race=<slug>/session=Q/YYYY_<slug>_quali_laps.parquet
  Weather:      weather/season=YYYY/race=<slug>/[session=Q/]weather.parquet
  Race control: race_control/season=YYYY/race=<slug>/race_control.parquet
  Track status: track_status/season=YYYY/race=<slug>/[session=Q/]track_status.parquet
  Sess. status: session_status/season=YYYY/race=<slug>/[session=Q/]session_status.parquet
  Results:      results/season=YYYY/race=<slug>/[session=Q/]results.parquet
  Telemetry:    telemetry/season=YYYY/race=<slug>/telemetry.parquet

Usage examples:
  python ingest.py --start-season 2018 --end-season 2024 --session both
  python ingest.py -s 2024 --session R --force           # re-ingest 2024 races
  python ingest.py -s 2024 --session Q --skip-telemetry
  python ingest.py -s 2026 --dry-run                     # what would be pulled / skipped / not run yet

Per session: rounds that have not finished are skipped without loading; a load
that comes back incomplete ("thin") is retried once and, if still thin, not
written; per-race telemetry coverage, circuit-info failures and slug/venue
changes are recorded in the run manifest (manifests/run_<id>.parquet).
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import fastf1
import pandas as pd

import bronze_checks
from data_quality import DataQualityEngine
from environment import get_config
from logging_config import setup_logging

logger = logging.getLogger(__name__)

PROJECT_ROOT   = Path(__file__).resolve().parent.parent.parent
BRONZE_DIR         = PROJECT_ROOT / "data" / "bronze"
LAPS_DIR           = BRONZE_DIR / "laps"
WEATHER_DIR        = BRONZE_DIR / "weather"
RC_DIR             = BRONZE_DIR / "race_control"
TELEMETRY_DIR      = BRONZE_DIR / "telemetry"
TELEMETRY_FULL_DIR = BRONZE_DIR / "telemetry_full"
POS_DATA_DIR       = BRONZE_DIR / "pos_data"
RESULTS_DIR        = BRONZE_DIR / "results"
TRACK_STATUS_DIR   = BRONZE_DIR / "track_status"
SESSION_STATUS_DIR = BRONZE_DIR / "session_status"
CIRCUIT_INFO_DIR   = BRONZE_DIR / "circuit_info"
SCHEDULE_DIR       = BRONZE_DIR / "schedule"
MANIFESTS_DIR      = BRONZE_DIR / "manifests"
CACHE_DIR          = PROJECT_ROOT / "data" / "cache"


def _bronze_paths(root: Path) -> dict[str, Path]:
    """Every module-level output directory, derived from one bronze root."""
    root = Path(root)
    return {
        "BRONZE_DIR":         root,
        "LAPS_DIR":           root / "laps",
        "WEATHER_DIR":        root / "weather",
        "RC_DIR":             root / "race_control",
        "TELEMETRY_DIR":      root / "telemetry",
        "TELEMETRY_FULL_DIR": root / "telemetry_full",
        "POS_DATA_DIR":       root / "pos_data",
        "RESULTS_DIR":        root / "results",
        "TRACK_STATUS_DIR":   root / "track_status",
        "SESSION_STATUS_DIR": root / "session_status",
        "CIRCUIT_INFO_DIR":   root / "circuit_info",
        "SCHEDULE_DIR":       root / "schedule",
        "MANIFESTS_DIR":      root / "manifests",
    }


def set_bronze_root(root: Path) -> None:
    """Redirect every writer to a different bronze root (--bronze-dir, tests, probes).

    The writers read these module globals at call time, so this takes effect for
    everything that runs afterwards. The layout under the root is unchanged.
    """
    globals().update(_bronze_paths(root))


# A "thin" load is one FastF1 returned without error but with key columns
# missing (bronze_checks.assess_session). It is retried once, after this pause,
# with the FastF1 cache bypassed so a cached failure cannot be served again. If
# it is still thin, nothing is written (unless --accept-thin): the laps file
# stays absent, so the next run re-pulls it instead of skipping it as done.
THIN_RETRY_DELAY_S = 30.0

# Bronze written per race weekend with default flags (race + qualifying, race
# telemetry): 2025 on disk averages ~47 MB. Only used for the --dry-run estimate.
BRONZE_GB_PER_RACE = 0.05

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


# Columns added to the manifest after its first version. Always present on new
# rows (so one run's file has one schema); older manifest files simply lack them,
# and manifest_report.py treats a missing column as "not recorded".
MANIFEST_EXTRA_DEFAULTS: dict = {
    "thin_reasons":             "",    # '; '-joined completeness failures (empty = complete)
    "known_gap_note":           "",    # a KNOWN_THIN / KNOWN_TELEMETRY_GAPS entry that applied
    "telemetry_laps_attempted": None,  # laps get_telemetry() was tried on (None = not attempted)
    "telemetry_laps_merged":    None,  # laps that came back with telemetry
    "telemetry_coverage":       None,  # merged / attempted
    "telemetry_car_drivers":    None,  # drivers with car-data (speed/throttle) samples
    "telemetry_pos_drivers":    None,  # drivers with position (X/Y/Z) samples
    "telemetry_note":           "",    # top per-lap errors, 'low coverage', 'known gap', ...
    "circuit_info_status":      "",    # 'ok: N corners' | 'none' | 'failed: ...' (race only)
    "venue_note":               "",    # slug now names a different venue than before, etc.
}


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
    **extra,
) -> dict:
    unknown = set(extra) - set(MANIFEST_EXTRA_DEFAULTS)
    if unknown:
        raise TypeError(f"unknown manifest field(s): {sorted(unknown)}")
    return {
        "run_id":              run_id,
        "ingested_at_utc":     datetime.now(timezone.utc).isoformat(),
        "season":              year,
        "round_number":        round_num,
        "race_slug":           slug,
        "session_type":        session_type,
        "status":              status,          # ok | skip | error | thin
        "row_count":           row_count,
        "dq_passed":           dq_passed,
        "duplicate_lap_keys":  duplicate_lap_keys,
        "schema_fingerprint":  schema_fingerprint,
        **MANIFEST_EXTRA_DEFAULTS,
        **extra,
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
    return bronze_checks.event_slug(event_name)


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
            # Handles both timedelta64 and datetime-with-timezone correctly
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


def _channel_drivers(session, attr: str) -> Optional[int]:
    """How many drivers have samples in a telemetry channel (car_data / pos_data).

    None when the channel could not be read at all (e.g. not loaded).
    """
    try:
        data = getattr(session, attr)
    except Exception:
        return None
    if data is None:
        return 0
    try:
        if isinstance(data, dict):  # FastF1 3.x: {driver_number: Telemetry}
            return sum(1 for v in data.values() if v is not None and len(v) > 0)
        if len(data) == 0:
            return 0
        return int(data.index.get_level_values(0).nunique())
    except Exception:
        return None


def _short_exc(exc: Exception) -> str:
    msg = str(exc).splitlines()[0][:80] if str(exc) else ""
    return f"{type(exc).__name__}: {msg}" if msg else type(exc).__name__


def _write_telemetry(session, year: int, round_num: int, slug: str) -> dict:
    """Per-lap merged telemetry -> telemetry/season=YYYY/race=<slug>/telemetry.parquet.

    Returns a coverage record for the manifest (laps attempted vs merged, which
    channels the session had, the commonest per-lap errors). What is written is
    unchanged; the record only makes a partial race distinguishable from a
    healthy one.
    """
    records = []
    attempted = 0
    errors: Counter = Counter()          # exception type -> laps
    examples: dict[str, str] = {}        # exception type -> first message seen
    for _, lap_row in session.laps.iterrows():
        driver  = lap_row["Driver"]
        lap_num = lap_row["LapNumber"]
        attempted += 1
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
        except Exception as exc:
            # Isolated failures (a lap with no samples) are normal; the coverage
            # record below is what flags a race where most laps fail.
            kind = type(exc).__name__
            errors[kind] += 1
            examples.setdefault(kind, _short_exc(exc))

    merged = len(records)
    coverage = {
        "telemetry_laps_attempted": attempted,
        "telemetry_laps_merged":    merged,
        "telemetry_coverage":       round(merged / attempted, 4) if attempted else None,
        "telemetry_car_drivers":    _channel_drivers(session, "car_data"),
        "telemetry_pos_drivers":    _channel_drivers(session, "pos_data"),
        "telemetry_note":           "; ".join(
            f"{kind} on {n} laps (e.g. {examples[kind]})" for kind, n in errors.most_common(3)
        ),
    }

    if not records:
        logger.warning(f"  No telemetry for {slug}")
        return coverage

    df = pd.concat(records, ignore_index=True).rename(columns={
        "Speed":    "speed_kph",
        "Throttle": "throttle_pct",
        "Brake":    "brake",
        "Distance": "distance_m",
    })
    out = TELEMETRY_DIR / f"season={year}" / f"race={slug}"
    os.makedirs(out, exist_ok=True)
    df.to_parquet(out / "telemetry.parquet", index=False, compression="snappy")
    logger.info(f"  Telemetry: {len(df):,} samples ({merged}/{attempted} laps)")
    return coverage


def _judge_telemetry(coverage: dict, year: int, round_num: int, slug: str) -> dict:
    """Log and annotate a coverage record: known gap, low coverage, or fine."""
    note = coverage.get("telemetry_note", "")
    attempted = coverage.get("telemetry_laps_attempted") or 0
    merged = coverage.get("telemetry_laps_merged") or 0
    share = coverage.get("telemetry_coverage")
    known = bronze_checks.known_telemetry_gap(year, round_num)
    channels = (f"car data for {coverage.get('telemetry_car_drivers')} drivers, "
                f"position data for {coverage.get('telemetry_pos_drivers')}")
    if known:
        logger.info(f"  [KNOWN GAP] telemetry {year} Rd{round_num} {slug}: "
                    f"{merged}/{attempted} laps; {known}")
        return {**coverage, "known_gap_note": f"telemetry: {known}",
                "telemetry_note": f"known gap; {note}".rstrip("; ")}
    if share is None or share < bronze_checks.TELEMETRY_LOW_COVERAGE:
        pct = "n/a" if share is None else f"{share:.1%}"
        logger.warning(
            f"  [LOW TELEMETRY] {year} Rd{round_num} {slug}: telemetry merged on "
            f"{merged}/{attempted} laps ({pct}, threshold "
            f"{bronze_checks.TELEMETRY_LOW_COVERAGE:.0%}); session had {channels}"
            + (f"; top errors: {note}" if note else "")
        )
        return {**coverage, "telemetry_note": f"low coverage; {note}".rstrip("; ")}
    return coverage


def _write_telemetry_full(session, year: int, round_num: int, slug: str) -> None:
    """Full-channel car_data (Speed, Throttle, Brake, nGear, RPM, DRS) per driver."""
    try:
        car_data = session.car_data
        if car_data is None or car_data.empty:
            logger.warning(f"  No car_data for {slug}")
            return

        for driver in car_data.index.get_level_values(0).unique():
            try:
                driver_data = car_data.loc[driver].reset_index()
                driver_data["driver_id"] = driver
                driver_data["race_id"] = f"{year}_{round_num}"
                driver_data["season"] = year

                out = TELEMETRY_FULL_DIR / f"season={year}" / f"race={slug}" / f"driver={driver}"
                os.makedirs(out, exist_ok=True)
                driver_data.to_parquet(out / "car_data.parquet", index=False, compression="zstd")
            except Exception as e:
                logger.warning(f"  Car data failed for {slug} driver {driver}: {e}")

        logger.info(f"  Car data: {len(car_data.index.get_level_values(0).unique())} drivers")
    except Exception as exc:
        logger.warning(f"  Car data failed for {slug}: {exc}")


def _write_pos_data(session, year: int, round_num: int, slug: str) -> None:
    """Full position data (X, Y, Z) per driver at full rate."""
    try:
        pos_data = session.pos_data
        if pos_data is None or pos_data.empty:
            logger.warning(f"  No pos_data for {slug}")
            return

        for driver in pos_data.index.get_level_values(0).unique():
            try:
                driver_pos = pos_data.loc[driver].reset_index()
                driver_pos["driver_id"] = driver
                driver_pos["race_id"] = f"{year}_{round_num}"
                driver_pos["season"] = year

                out = POS_DATA_DIR / f"season={year}" / f"race={slug}" / f"driver={driver}"
                os.makedirs(out, exist_ok=True)
                driver_pos.to_parquet(out / "pos_data.parquet", index=False, compression="zstd")
            except Exception as e:
                logger.warning(f"  Pos data failed for {slug} driver {driver}: {e}")

        logger.info(f"  Pos data: {len(pos_data.index.get_level_values(0).unique())} drivers")
    except Exception as exc:
        logger.warning(f"  Pos data failed for {slug}: {exc}")


def _write_results(
    session, year: int, round_num: int, slug: str, session_type: str = "R",
) -> None:
    """Official classified results.

    Race: ClassifiedPosition, Status, GridPosition, Points. The Q1/Q2/Q3 columns
    are present in the frame but always null on a race session   the segment
    times only populate on the qualifying session's own results, which is why
    this is written for Q as well.
    """
    try:
        if not hasattr(session, "results") or session.results is None or session.results.empty:
            return
        results = pd.DataFrame(session.results).reset_index()
        results["race_id"] = f"{year}_{round_num}"
        results["season"] = year
        if session_type == "Q":
            results["session_type"] = "Q"
        out = RESULTS_DIR / f"season={year}" / f"race={slug}"
        if session_type == "Q":
            out = out / "session=Q"
        os.makedirs(out, exist_ok=True)
        results.to_parquet(out / "results.parquet", index=False, compression="snappy")
        logger.info(f"  Results ({session_type}): {len(results)} drivers")
    except Exception as exc:
        logger.warning(f"  Results failed for {slug}: {exc}")


def _write_track_status(
    session, year: int, round_num: int, slug: str, session_type: str = "R",
) -> None:
    """SC/VSC timeline (track_status events)."""
    try:
        if not hasattr(session, "track_status") or session.track_status is None or session.track_status.empty:
            return
        ts = pd.DataFrame(session.track_status).reset_index()
        ts["race_id"] = f"{year}_{round_num}"
        ts["season"] = year
        if session_type == "Q":
            ts["session_type"] = "Q"
        if "Time" in ts.columns:
            raw = ts["Time"]
            if pd.api.types.is_timedelta64_dtype(raw):
                ts["session_time_s"] = raw.dt.total_seconds()
            elif pd.api.types.is_datetime64_any_dtype(raw):
                epoch = raw.iloc[0].replace(hour=0, minute=0, second=0, microsecond=0)
                ts["session_time_s"] = (raw - epoch).dt.total_seconds()
        out = TRACK_STATUS_DIR / f"season={year}" / f"race={slug}"
        if session_type == "Q":
            out = out / "session=Q"
        os.makedirs(out, exist_ok=True)
        ts.to_parquet(out / "track_status.parquet", index=False, compression="snappy")
        logger.info(f"  Track status ({session_type}): {len(ts)} events")
    except Exception as exc:
        logger.warning(f"  Track status failed for {slug}: {exc}")


def _write_session_status(
    session, year: int, round_num: int, slug: str, session_type: str = "R",
) -> None:
    """Session lifecycle events (Inactive / Started / Aborted / Finished).

    For qualifying this is the only record of where Q1, Q2 and Q3 begin and end:
    the lap table carries no segment column, so the Started/Finished pairs here
    are what int_qualifying_segments splits the session on.
    """
    try:
        if not hasattr(session, "session_status") or session.session_status is None or session.session_status.empty:
            return
        ss = pd.DataFrame(session.session_status).reset_index()
        ss["race_id"] = f"{year}_{round_num}"
        ss["season"] = year
        if session_type == "Q":
            ss["session_type"] = "Q"
        if "Time" in ss.columns:
            raw = ss["Time"]
            if pd.api.types.is_timedelta64_dtype(raw):
                ss["session_time_s"] = raw.dt.total_seconds()
            elif pd.api.types.is_datetime64_any_dtype(raw):
                epoch = raw.iloc[0].replace(hour=0, minute=0, second=0, microsecond=0)
                ss["session_time_s"] = (raw - epoch).dt.total_seconds()
        out = SESSION_STATUS_DIR / f"season={year}" / f"race={slug}"
        if session_type == "Q":
            out = out / "session=Q"
        os.makedirs(out, exist_ok=True)
        ss.to_parquet(out / "session_status.parquet", index=False, compression="snappy")
        logger.info(f"  Session status ({session_type}): {len(ss)} events")
    except Exception as exc:
        logger.warning(f"  Session status failed for {slug}: {exc}")


def _write_circuit_info(session, year: int, round_num: int, slug: str) -> str:
    """Circuit geometry (corners, coordinates, marshal sectors).

    Returns a status for the manifest: 'ok: N corners', 'none' (FastF1 had no
    circuit info) or 'failed: <error>'. A failure is tolerated (corner models
    simply have no row for the race) but recorded, so it is visible in the
    manifest and not only as a log line.
    """
    try:
        if not hasattr(session, "get_circuit_info"):
            return "none"
        circuit = session.get_circuit_info()
        if circuit is None:
            logger.warning(f"  Circuit info unavailable for {slug}")
            return "none"
        ci = pd.DataFrame(circuit.corners).reset_index()
        ci["race_id"] = f"{year}_{round_num}"
        ci["season"] = year
        out = CIRCUIT_INFO_DIR / f"season={year}" / f"race={slug}"
        os.makedirs(out, exist_ok=True)
        ci.to_parquet(out / "circuit_info.parquet", index=False, compression="snappy")
        logger.info(f"  Circuit info: {len(ci)} corners")
        return f"ok: {len(ci)} corners"
    except Exception as exc:
        logger.warning(f"  Circuit info failed for {slug}: {exc}")
        return f"failed: {_short_exc(exc)}"


def _write_event_schedule(year: int) -> None:
    """Event schedule for the season."""
    try:
        schedule = pd.DataFrame(fastf1.get_event_schedule(year, backend="fastf1"))
        schedule["season"] = year
        out = SCHEDULE_DIR / f"season={year}"
        os.makedirs(out, exist_ok=True)
        schedule.to_parquet(out / "schedule.parquet", index=False, compression="snappy")
        logger.info(f"  Schedule: {len(schedule)} events")
    except Exception as exc:
        logger.warning(f"  Schedule failed for {year}: {exc}")


# ---------------------------------------------------------------------------
# Session-level ingest functions
# ---------------------------------------------------------------------------

def _frame(session, attr: str) -> Optional[pd.DataFrame]:
    """session.<attr> if it is a loaded DataFrame, else None (not loaded, missing, mock)."""
    try:
        value = getattr(session, attr)
    except Exception:
        return None
    return value if isinstance(value, pd.DataFrame) else None


def _assess_loaded(session, session_type: str, year: int, round_num: int) -> tuple[dict, Optional[str]]:
    """(unexplained completeness problems, known-gap note) for a loaded session."""
    problems = bronze_checks.assess_session(
        session_type,
        laps=_frame(session, "laps"),
        results=_frame(session, "results"),
        weather=_frame(session, "weather_data"),
        race_control=_frame(session, "race_control_messages") if session_type == "R" else None,
    )
    return bronze_checks.split_known_thin(year, round_num, session_type, problems)


def _load_checked(loader, session_type: str, year: int, round_num: int, slug: str):
    """Load a session (with the usual retry/backoff), then check it is complete.

    A thin load is retried ONCE, after THIN_RETRY_DELAY_S, with the FastF1 cache
    bypassed. The retry's result is kept unless it came back worse. Returns
    (session, unexplained problems, known-gap note); problems empty = complete.
    """
    session = _with_retry(lambda: loader(year, round_num))
    thin, known = _assess_loaded(session, session_type, year, round_num)
    if not thin:
        return session, thin, known

    logger.warning(
        f"  [THIN] {session_type}  {year} Rd{round_num} {slug}: {'; '.join(thin.values())}"
        f"   retrying once in {THIN_RETRY_DELAY_S:.0f}s with the FastF1 cache bypassed"
    )
    time.sleep(THIN_RETRY_DELAY_S)
    try:
        retry = loader(year, round_num, fresh=True)
    except Exception as exc:
        logger.warning(f"  Thin-load retry failed for {slug}: {_short_exc(exc)}")
        return session, thin, known
    thin_retry, known_retry = _assess_loaded(retry, session_type, year, round_num)
    if len(thin_retry) <= len(thin):
        session, thin, known = retry, thin_retry, known_retry
    if not thin:
        logger.info(f"  [RECOVERED] {session_type}  {year} Rd{round_num} {slug}: complete on retry")
    return session, thin, known


def _thin_not_written(session_type: str, year: int, round_num: int, slug: str,
                      target: Path, thin: dict) -> None:
    kept = " Existing files for it were left as they were." if target.exists() else ""
    logger.warning(
        f"  [THIN] {session_type}  {year} Rd{round_num} {slug}: still incomplete after the retry "
        f"({'; '.join(thin.values())}). NOT written, so the next run pulls it again.{kept} "
        f"If the source is genuinely incomplete, re-run with --accept-thin to write it as is."
    )


def ingest_race(
    year: int, round_num: int, slug: str, force: bool, skip_telemetry: bool,
    telemetry_full: bool = False,
    run_id: str = "",
    accept_thin: bool = False,
    venue_note: str = "",
) -> tuple[str, dict]:
    """
    Ingest a single Race session. Returns (status, manifest_row).
    Status is one of: 'ok', 'skip', 'error', 'thin' (loaded but incomplete,
    nothing written; see _load_checked).
    """
    target = _laps_path_race(year, slug)

    if target.exists() and not force:
        logger.info(f"  [SKIP] R  {year} Rd{round_num} {slug}")
        return "skip", _make_manifest_row(run_id, year, round_num, slug, "R", "skip",
                                          venue_note=venue_note)

    logger.info(f"  [PULL] R  {year} Rd{round_num} {slug}")
    try:
        session, thin, known_note = _load_checked(_load_race_session, "R", year, round_num, slug)

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
                thin_reasons="; ".join(thin.values()), venue_note=venue_note,
            )

        thin_text = "; ".join(thin.values())
        if thin and not accept_thin:
            _thin_not_written("R", year, round_num, slug, target, thin)
            return "thin", _make_manifest_row(
                run_id, year, round_num, slug, "R", "thin",
                row_count=len(laps_df), dq_passed=True, duplicate_lap_keys=dupe_count,
                thin_reasons=thin_text, known_gap_note=known_note or "", venue_note=venue_note,
            )
        if thin:
            logger.warning(f"  [THIN-ACCEPTED] R  {year} Rd{round_num} {slug}: writing as is "
                           f"(--accept-thin): {thin_text}")
        if known_note:
            logger.info(f"  [KNOWN GAP] R  {year} Rd{round_num} {slug}: {known_note}")

        os.makedirs(target.parent, exist_ok=True)
        laps_df.to_parquet(target, index=False, compression="snappy")
        logger.info(f"  [OK]   R  {year} Rd{round_num} {slug}   {len(laps_df)} laps")

        _write_weather(session, year, round_num, slug, "R")
        _write_race_control(session, year, round_num, slug)

        if skip_telemetry:
            tel_fields: dict = {"telemetry_note": "not requested (--skip-telemetry)"}
        else:
            try:
                tel_fields = _judge_telemetry(
                    _write_telemetry(session, year, round_num, slug), year, round_num, slug,
                )
            except Exception as exc:
                logger.warning(f"  Telemetry failed for {slug}: {exc}")
                tel_fields = {"telemetry_note": f"telemetry writer failed: {_short_exc(exc)}"}

        if telemetry_full:
            try:
                _write_telemetry_full(session, year, round_num, slug)
                _write_pos_data(session, year, round_num, slug)
            except Exception as exc:
                logger.warning(f"  Full telemetry/pos failed for {slug}: {exc}")

        _write_results(session, year, round_num, slug)
        _write_track_status(session, year, round_num, slug)
        _write_session_status(session, year, round_num, slug)
        circuit_info_status = _write_circuit_info(session, year, round_num, slug)

        known_notes = [n for n in (known_note, tel_fields.pop("known_gap_note", "")) if n]
        time.sleep(0.5)
        row = _make_manifest_row(
            run_id, year, round_num, slug, "R", "ok",
            row_count=len(laps_df), dq_passed=True,
            duplicate_lap_keys=dupe_count,
            schema_fingerprint=_schema_fingerprint(laps_df),
            thin_reasons=thin_text,
            known_gap_note="; ".join(known_notes),
            circuit_info_status=circuit_info_status,
            venue_note=venue_note,
            **tel_fields,
        )
        return "ok", row

    except Exception as exc:
        logger.warning(f"  [ERR]  R  {year} Rd{round_num} {slug}: {exc}")
        return "error", _make_manifest_row(run_id, year, round_num, slug, "R", "error",
                                           venue_note=venue_note)


def ingest_qualifying(
    year: int, round_num: int, slug: str, force: bool,
    run_id: str = "",
    accept_thin: bool = False,
    venue_note: str = "",
) -> tuple[str, dict]:
    """
    Ingest a single Qualifying session. Returns (status, manifest_row).
    Status is one of: 'ok', 'skip', 'error', 'thin' (loaded but incomplete,
    nothing written; see _load_checked).
    """
    target = _laps_path_quali(year, slug)

    if target.exists() and not force:
        logger.info(f"  [SKIP] Q  {year} Rd{round_num} {slug}")
        return "skip", _make_manifest_row(run_id, year, round_num, slug, "Q", "skip",
                                          venue_note=venue_note)

    logger.info(f"  [PULL] Q  {year} Rd{round_num} {slug}")
    try:
        session, thin, known_note = _load_checked(
            _load_qualifying_session, "Q", year, round_num, slug,
        )

        laps = session.laps
        if laps is None or laps.empty:
            logger.warning(f"  [WARN] Q  {year} Rd{round_num}   no lap data")
            return "error", _make_manifest_row(run_id, year, round_num, slug, "Q", "error",
                                               thin_reasons="; ".join(thin.values()),
                                               venue_note=venue_note)

        laps = laps.copy()
        laps["season"]       = year
        laps["race_name"]    = slug
        laps["session_type"] = "Q"
        laps["race_id"]      = f"{year}_{round_num}"

        label = f"{year} Rd{round_num} Q"
        _, dupe_count = _run_quality_checks(laps, label)  # warn only   don't gate on schema

        thin_text = "; ".join(thin.values())
        if thin and not accept_thin:
            _thin_not_written("Q", year, round_num, slug, target, thin)
            return "thin", _make_manifest_row(
                run_id, year, round_num, slug, "Q", "thin",
                row_count=len(laps), dq_passed=True, duplicate_lap_keys=dupe_count,
                thin_reasons=thin_text, known_gap_note=known_note or "", venue_note=venue_note,
            )
        if thin:
            logger.warning(f"  [THIN-ACCEPTED] Q  {year} Rd{round_num} {slug}: writing as is "
                           f"(--accept-thin): {thin_text}")
        if known_note:
            logger.info(f"  [KNOWN GAP] Q  {year} Rd{round_num} {slug}: {known_note}")

        os.makedirs(target.parent, exist_ok=True)
        laps.to_parquet(target, index=False, compression="snappy")
        logger.info(f"  [OK]   Q  {year} Rd{round_num} {slug}   {len(laps)} laps")

        _write_weather(session, year, round_num, slug, "Q")
        _write_track_status(session, year, round_num, slug, "Q")
        _write_session_status(session, year, round_num, slug, "Q")
        _write_results(session, year, round_num, slug, "Q")

        time.sleep(0.3)
        row = _make_manifest_row(
            run_id, year, round_num, slug, "Q", "ok",
            row_count=len(laps), dq_passed=True,
            duplicate_lap_keys=dupe_count,
            schema_fingerprint=_schema_fingerprint(laps),
            thin_reasons=thin_text,
            known_gap_note=known_note or "",
            venue_note=venue_note,
        )
        return "ok", row

    except Exception as exc:
        logger.warning(f"  [ERR]  Q  {year} Rd{round_num} {slug}: {exc}")
        return "error", _make_manifest_row(run_id, year, round_num, slug, "Q", "error",
                                           venue_note=venue_note)


def _load_race_session(year: int, round_num: int, fresh: bool = False):
    """Load a race. fresh=True bypasses the FastF1 cache (used by the thin-load retry)."""
    session = fastf1.get_session(year, round_num, "R")
    if fresh:
        with fastf1.Cache.disabled():
            session.load()
    else:
        session.load()
    return session


def _load_qualifying_session(year: int, round_num: int, fresh: bool = False):
    """Load qualifying (no telemetry). fresh=True bypasses the FastF1 cache."""
    session = fastf1.get_session(year, round_num, "Q", backend="fastf1")
    if fresh:
        with fastf1.Cache.disabled():
            session.load(laps=True, telemetry=False, weather=True)
    else:
        session.load(laps=True, telemetry=False, weather=True)
    return session


# ---------------------------------------------------------------------------
# Season-level orchestration
# ---------------------------------------------------------------------------

def _fmt_elapsed(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def _fmt_utc(ts: Optional[pd.Timestamp]) -> str:
    return "unknown" if ts is None else ts.strftime("%Y-%m-%d %H:%M UTC")


def plan_season(
    schedule: pd.DataFrame,
    year: int,
    sessions: str,
    only_rounds: Optional[set[int]] = None,
    now_utc: Optional[datetime] = None,
    ready_after: timedelta = bronze_checks.SESSION_READY_AFTER,
    include_unfinished: bool = False,
    venue_history: Optional[pd.DataFrame] = None,
) -> list[dict]:
    """Decide, per (round, session), whether this run attempts it.

    action is 'attempt' or 'not_run'. A session is 'not_run' when its scheduled
    start + ready_after is still in the future: loading it would only fail inside
    _with_retry (four attempts with backoff) and record an 'error' for a race
    that simply has not happened. With sessions='both' the ROUND is the unit:
    qualifying is held back until the race is ready too, so a default run never
    leaves a qualifying-only round in bronze (pass --session Q to pull it alone).
    A session with no date on the schedule is attempted, as before.
    include_unfinished=True attempts everything.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    session_types = {"R": ["R"], "Q": ["Q"], "both": ["R", "Q"]}[sessions]
    plan: list[dict] = []
    for _, row in schedule.iterrows():
        rn = row["RoundNumber"]
        if pd.isna(rn) or int(rn) == 0:
            continue
        round_num = int(rn)
        if only_rounds is not None and round_num not in only_rounds:
            continue
        event_name = str(row["EventName"])
        slug = _slug(event_name)
        location = str(row.get("Location", "") or "")
        note = bronze_checks.venue_note(slug, location, venue_history)
        race_start = bronze_checks.session_start_utc(row, "R")
        race_ready = bronze_checks.session_is_ready(race_start, now_utc, ready_after)
        for stype in session_types:
            start = race_start if stype == "R" else bronze_checks.session_start_utc(row, stype)
            ready = race_ready if stype == "R" else bronze_checks.session_is_ready(start, now_utc, ready_after)
            waits_for_race = sessions == "both" and stype == "Q" and race_ready is False
            if include_unfinished or not (ready is False or waits_for_race):
                action, reason = "attempt", ""
            elif ready is False:
                action, reason = "not_run", "session not run yet"
            else:
                action, reason = "not_run", "round not complete: the race is not run yet"
            plan.append({
                "round": round_num, "slug": slug, "event_name": event_name,
                "location": location, "session_type": stype,
                "start_utc": start, "ready_at_utc": None if start is None else start + ready_after,
                "race_ready_at_utc": None if race_start is None else race_start + ready_after,
                "ready": ready, "action": action, "reason": reason, "venue_note": note,
            })
    return plan


def _not_run_text(p: dict) -> str:
    if p.get("reason", "").startswith("round not complete"):
        return (f"held back until the race is loadable ({_fmt_utc(p['race_ready_at_utc'])}) so the "
                f"round lands whole; --session Q pulls qualifying alone")
    return f"starts {_fmt_utc(p['start_utc'])}, loadable from {_fmt_utc(p['ready_at_utc'])}"


def _log_plan(year: int, plan: list[dict], ready_after: timedelta = bronze_checks.SESSION_READY_AFTER) -> None:
    """Say plainly what this run will not attempt and why, and any slug/venue traps."""
    not_run = [p for p in plan if p["action"] == "not_run"]
    if not_run:
        rounds = sorted({p["round"] for p in not_run})
        logger.info(
            f"Season {year}: {len(not_run)} session(s) in {len(rounds)} round(s) are not run "
            f"yet (scheduled start + {ready_after.total_seconds() / 3600:g} h has not passed) "
            f"and are skipped without loading: nothing is fetched and no manifest row is "
            f"written for them. Re-run after they finish; rounds already on disk are skipped."
        )
        for p in not_run:
            logger.info(f"  [NOT RUN] {p['session_type']}  {year} Rd{p['round']} {p['slug']}: "
                        f"{_not_run_text(p)}")
    for p in plan:
        if p["ready"] is None and p["action"] == "attempt":
            logger.info(f"  {p['session_type']}  {year} Rd{p['round']} {p['slug']}: no session "
                        f"date on the schedule, attempting it")
    seen = set()
    for p in plan:
        if p["venue_note"] and p["round"] not in seen:
            seen.add(p["round"])
            logger.warning(f"  [VENUE] {year} Rd{p['round']} {p['event_name']} ({p['location']}): "
                           f"{p['venue_note']}. Check its race_to_track / circuit_reference rows.")


def ingest_season(
    year: int,
    sessions: str,
    force: bool,
    skip_telemetry: bool,
    telemetry_full: bool = False,
    run_id: str = "",
    only_round: int | None = None,
    only_rounds: Optional[set[int]] = None,
    now_utc: Optional[datetime] = None,
    ready_after: timedelta = bronze_checks.SESSION_READY_AFTER,
    include_unfinished: bool = False,
    accept_thin: bool = False,
) -> tuple[dict, list[dict]]:
    """
    Ingest the finished rounds of a season (all of them, only_round, or only_rounds).
    Returns (counts, manifest_rows) where counts has ok/skip/error/thin/not_run per
    session type. Sessions that have not finished are counted as not_run and get no
    manifest row.
    """
    if only_round is not None:
        only_rounds = {only_round} | (only_rounds or set())
    if only_rounds is not None:
        logger.info(f"=== Season {year} Rd{','.join(str(r) for r in sorted(only_rounds))} ===")
    else:
        logger.info(f"=== Season {year} ===")

    counts = {f"{s}_{k}": 0 for s in ("R", "Q") for k in ("ok", "skip", "error", "thin", "not_run")}
    manifest_rows: list[dict] = []

    try:
        schedule = _with_retry(lambda: fastf1.get_event_schedule(year, backend="fastf1"))
    except Exception as exc:
        logger.error(f"Schedule fetch failed for {year}: {exc}")
        counts["schedule_error"] = 1
        return counts, manifest_rows

    history = bronze_checks.load_venue_history(SCHEDULE_DIR, year)
    plan = plan_season(schedule, year, sessions, only_rounds, now_utc, ready_after,
                       include_unfinished, history)
    _log_plan(year, plan, ready_after)
    for p in plan:
        if p["action"] == "not_run":
            counts[f"{p['session_type']}_not_run"] += 1

    to_attempt = [p for p in plan if p["action"] == "attempt"]
    rounds = sorted({p["round"] for p in to_attempt})
    started = time.monotonic()
    for i, round_num in enumerate(rounds, 1):
        items = [p for p in to_attempt if p["round"] == round_num]
        slug, note = items[0]["slug"], items[0]["venue_note"]
        logger.info(f"── [{i}/{len(rounds)}] {year} Rd{round_num} {slug}   "
                    f"elapsed {_fmt_elapsed(time.monotonic() - started)}")
        for p in items:
            if p["session_type"] == "R":
                result, mrow = ingest_race(year, round_num, slug, force, skip_telemetry,
                                           telemetry_full, run_id,
                                           accept_thin=accept_thin, venue_note=note)
            else:
                result, mrow = ingest_qualifying(year, round_num, slug, force, run_id,
                                                 accept_thin=accept_thin, venue_note=note)
            counts[f"{p['session_type']}_{result}"] += 1
            manifest_rows.append(mrow)

    _write_event_schedule(year)
    _log_season_summary(year, sessions, counts)
    return counts, manifest_rows


def _log_season_summary(year: int, sessions: str, counts: dict) -> None:
    parts = []
    for stype in ("R", "Q"):
        if sessions not in (stype, "both"):
            continue
        text = (f"{stype}: {counts[f'{stype}_ok']} ok, {counts[f'{stype}_skip']} skip, "
                f"{counts[f'{stype}_error']} error")
        if counts.get(f"{stype}_thin"):
            text += f", {counts[f'{stype}_thin']} thin"
        if counts.get(f"{stype}_not_run"):
            text += f", {counts[f'{stype}_not_run']} not run yet"
        parts.append(text)
    logger.info(f"Season {year} complete   " + " | ".join(parts))


def _attention_lines(rows: list[dict]) -> tuple[list[str], list[str]]:
    """(blocking problems, informational notes) from this run's manifest rows.

    Blocking = a session that still needs work: 'error' (load failed after
    retries) or 'thin' (loaded incomplete, not written). Informational = written,
    but worth a look: low telemetry coverage, accepted thin loads, no circuit
    info, slug/venue changes.
    """
    blocking, notes = [], []
    for r in rows:
        tag = f"{r['season']} Rd{r['round_number']} {r['session_type']} {r['race_slug']}"
        if r["status"] == "error":
            blocking.append(f"FAILED {tag}: load or write failed (see [ERR] / [DQ FAIL] above)")
        elif r["status"] == "thin":
            blocking.append(f"THIN   {tag}: {r.get('thin_reasons', '')} -> not written")
        if r["status"] != "ok":
            continue
        if r.get("thin_reasons"):
            notes.append(f"THIN (accepted) {tag}: {r['thin_reasons']}")
        share = r.get("telemetry_coverage")
        note = r.get("telemetry_note") or ""
        if (r["session_type"] == "R" and r.get("telemetry_laps_attempted") is not None
                and not note.startswith("known gap")
                and (share is None or share < bronze_checks.TELEMETRY_LOW_COVERAGE)):
            notes.append(f"LOW TELEMETRY {tag}: {r.get('telemetry_laps_merged')}/"
                         f"{r.get('telemetry_laps_attempted')} laps merged")
        ci = r.get("circuit_info_status") or ""
        if r["session_type"] == "R" and ci and not ci.startswith("ok"):
            notes.append(f"NO CIRCUIT INFO {tag}: {ci}")
    seen_venue = set()
    for r in rows:
        key = (r["season"], r["round_number"])
        if r.get("venue_note") and key not in seen_venue:
            seen_venue.add(key)
            notes.append(f"VENUE  {r['season']} Rd{r['round_number']} {r['race_slug']}: {r['venue_note']}")
    return blocking, notes


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _parse_rounds(spec: str) -> set[int]:
    """'1-14' / '3,5,7' / '1-3,9' -> {rounds}."""
    rounds: set[int] = set()
    try:
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                lo, hi = (int(x) for x in part.split("-", 1))
                if lo > hi:
                    raise ValueError
                rounds.update(range(lo, hi + 1))
            else:
                rounds.add(int(part))
    except ValueError:
        raise argparse.ArgumentTypeError(f"bad round list {spec!r}: use e.g. 1-14 or 3,5,7")
    if not rounds or min(rounds) < 1:
        raise argparse.ArgumentTypeError(f"bad round list {spec!r}: rounds start at 1")
    return rounds


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Unified F1 Bronze-layer ingestion controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ingest.py --season 2024 --round 1 --session R
                 Ingest a single race (2024 Rd1, Bahrain)
  python ingest.py --season 2024 --session R
                 Ingest 2024 races only
  python ingest.py --season 2024 --session both
                 Ingest 2024 races and qualifying
  python ingest.py --season 2026 --dry-run
                 Show which rounds would be pulled, skipped, or are not run yet
  python ingest.py --season 2026 --rounds 1-14
                 Ingest a list or range of rounds
  python ingest.py --start-season 2018 --end-season 2024 --session both
                 Full historical backfill (4–6 hours)
  python ingest.py --season 2024 --force
                 Re-ingest 2024, overwriting existing files
  python ingest.py --season 2024 --round 1 --bronze-dir /tmp/bronze
                 Write to a scratch bronze root instead of data/bronze

Sessions that have not finished (scheduled start + --ready-after-hours still in
the future) are skipped without loading. Exit code is 1 if any session ended
'error' or 'thin' (loaded incomplete, not written), else 0.
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
    round_group = p.add_mutually_exclusive_group()
    round_group.add_argument(
        "--round", type=int, metavar="N", default=None,
        help="Ingest only this round number (requires a single season via -s/--season)",
    )
    round_group.add_argument(
        "--rounds", type=_parse_rounds, metavar="LIST", default=None,
        help="Ingest only these rounds, e.g. 1-14 or 3,5,7 (requires a single season)",
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
        "--telemetry-full", action="store_true",
        help="Ingest full-channel car_data (Speed, Throttle, Brake, nGear, RPM, DRS) and pos_data (v0.2)",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Overwrite existing Parquet files instead of skipping them",
    )
    p.add_argument(
        "--ready-after-hours", type=float, metavar="H",
        default=bronze_checks.SESSION_READY_AFTER.total_seconds() / 3600,
        help="Treat a session as finished this many hours after its scheduled start "
             "(default: %(default).0f)",
    )
    p.add_argument(
        "--include-unfinished", action="store_true",
        help="Also attempt sessions the schedule says have not finished yet",
    )
    p.add_argument(
        "--accept-thin", action="store_true",
        help="Write a session even if it is still incomplete after the retry "
             "(recorded as thin_reasons in the manifest)",
    )
    p.add_argument(
        "--bronze-dir", type=Path, metavar="PATH", default=None,
        help="Bronze root to write under (default: $INGESTION_BRONZE_DIR or data/bronze)",
    )
    p.add_argument(
        "--cache-dir", type=Path, metavar="PATH", default=None,
        help="FastF1 cache directory (default: $FASTF1_CACHE_DIR or data/cache)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Fetch the schedule and list what would be pulled, skipped, or is not run "
             "yet, without loading sessions or writing to bronze",
    )
    p.add_argument(
        "--log-level", type=str, default="INFO",
        help="Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)",
    )
    return p


def _dry_run(years: range, args, only_rounds: Optional[set[int]], ready_after: timedelta) -> int:
    """Print the per-session plan for each season. Reads the schedule (FastF1 cache
    or network) and checks bronze for existing files; loads no session, writes nothing
    to bronze."""
    n_pull = 0
    for year in years:
        try:
            schedule = _with_retry(lambda: fastf1.get_event_schedule(year, backend="fastf1"))
        except Exception as exc:
            logger.error(f"DRY RUN: schedule fetch failed for {year}: {exc}")
            continue
        history = bronze_checks.load_venue_history(SCHEDULE_DIR, year)
        plan = plan_season(schedule, year, args.sessions, only_rounds, None, ready_after,
                           args.include_unfinished, history)
        logger.info(f"DRY RUN {year}: {len({p['round'] for p in plan})} round(s) in scope")
        for p in plan:
            target = (_laps_path_race if p["session_type"] == "R" else _laps_path_quali)(year, p["slug"])
            if p["action"] == "not_run":
                what = f"not run yet: {_not_run_text(p)}"
            elif target.exists() and not args.force:
                what = "on disk, would skip"
            else:
                what = "would pull" + (" (overwrite)" if target.exists() else "")
                n_pull += p["session_type"] == "R"
            extra = f"   [VENUE] {p['venue_note']}" if p["venue_note"] else ""
            logger.info(f"  {p['session_type']}  Rd{p['round']:>2} {p['slug']:<32} {what}{extra}")
    logger.info(f"DRY RUN: {n_pull} race session(s) would be pulled (~{n_pull * BRONZE_GB_PER_RACE:.1f} GB "
                f"of bronze at ~{BRONZE_GB_PER_RACE} GB per race weekend); nothing was written")
    return 0


def main() -> int:
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

    if (args.round is not None or args.rounds is not None) and start_year != end_year:
        parser.error("--round/--rounds require a single season (use -s/--season N, not a season range)")

    only_rounds = args.rounds if args.rounds is not None else (
        {args.round} if args.round is not None else None
    )
    ready_after = timedelta(hours=args.ready_after_hours)

    set_bronze_root(args.bronze_dir or config.bronze_dir)
    cache_dir = Path(args.cache_dir or config.fastf1_cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))

    if args.dry_run:
        logger.info(f"Bronze: {BRONZE_DIR} | FastF1 cache: {cache_dir}")
        return _dry_run(range(start_year, end_year + 1), args, only_rounds, ready_after)

    for d in [LAPS_DIR, WEATHER_DIR, RC_DIR, TELEMETRY_DIR, TELEMETRY_FULL_DIR, POS_DATA_DIR, RESULTS_DIR, TRACK_STATUS_DIR, SESSION_STATUS_DIR, CIRCUIT_INFO_DIR, SCHEDULE_DIR, MANIFESTS_DIR]:
        os.makedirs(d, exist_ok=True)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    logger.info(
        f"Ingestion run {run_id}: {start_year}–{end_year} | sessions={args.sessions} | "
        f"force={args.force} | skip_telemetry={args.skip_telemetry} | telemetry_full={args.telemetry_full}"
    )
    logger.info(f"Bronze: {BRONZE_DIR} | FastF1 cache: {cache_dir}")

    total_ok = 0
    not_run = 0
    failed_schedules: list[int] = []
    all_manifest_rows: list[dict] = []
    for year in range(start_year, end_year + 1):
        counts, manifest_rows = ingest_season(
            year,
            sessions=args.sessions,
            force=args.force,
            skip_telemetry=args.skip_telemetry,
            telemetry_full=args.telemetry_full,
            run_id=run_id,
            only_rounds=only_rounds,
            ready_after=ready_after,
            include_unfinished=args.include_unfinished,
            accept_thin=args.accept_thin,
        )
        total_ok += counts.get("R_ok", 0) + counts.get("Q_ok", 0)
        not_run += counts.get("R_not_run", 0) + counts.get("Q_not_run", 0)
        if counts.get("schedule_error"):
            failed_schedules.append(year)
        all_manifest_rows.extend(manifest_rows)

    _write_manifest(all_manifest_rows, run_id)

    blocking, notes = _attention_lines(all_manifest_rows)
    blocking += [f"FAILED {y}: schedule fetch failed, nothing attempted" for y in failed_schedules]
    if blocking:
        logger.warning("=== NEEDS ATTENTION: these sessions are not done; re-run the same "
                       "command to retry them (finished sessions are skipped) ===")
        for line in blocking:
            logger.warning(f"  {line}")
    if notes:
        logger.warning("=== NOTES: written, but worth a look (also in the run manifest) ===")
        for line in notes:
            logger.warning(f"  {line}")
    if not_run:
        logger.info(f"{not_run} session(s) not run yet were skipped (see [NOT RUN] above)")
    logger.info(f"=== COMPLETE: {total_ok} sessions newly written ===")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
