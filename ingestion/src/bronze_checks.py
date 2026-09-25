"""
bronze_checks.py -- completeness rules and known source gaps, shared by the
ingest controller (in memory, before anything is written), verify_bronze.py (on
the files already on disk) and scripts/check_season_seeds.py.

Five things live here so the three callers cannot disagree about them:

  1. Session timing: which sessions on a FastF1 schedule have finished long
     enough ago to be worth loading (SESSION_READY_AFTER).
  2. Thin-load rules: the per-session completeness checks (assess_session) and
     their thresholds. A "thin" load is one FastF1 returned without error but
     with key columns missing, e.g. 2026 Miami's first load, whose results came
     back with Points and GridPosition 0% non-null because the Ergast/Jolpica
     call failed; a retry a minute later was complete.
  3. Telemetry coverage: the share of laps FastF1 could merge per-lap telemetry
     for, and the level below which a race is flagged (TELEMETRY_LOW_COVERAGE).
  4. The registry of KNOWN source-level gaps (KNOWN_THIN, KNOWN_TELEMETRY_GAPS),
     so real, documented gaps are reported as known and a NEW gap still fails.
  5. Event slug -> venue history, to warn when a slug starts naming a different
     venue (2026: 'spanish_grand_prix' moved from Barcelona to Madrid).

The thresholds are judgment calls, calibrated on 2018-2025 bronze as of
2026-09-25: every healthy session on disk passes them, and each is set well
below the lowest healthy value so a genuinely short race (2021 Belgium, run
entirely behind the safety car) is not called thin. Change them here, not at
the call sites.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Session timing
# ---------------------------------------------------------------------------

# How long after a session's scheduled START it is treated as finished and
# published. Covers the session itself (a race runs up to ~2 h, longer with a
# red flag) plus the delay before F1's archive and Jolpica's results are
# complete. Too short risks thin loads (caught below, but they cost a retry);
# too long only delays the pull. Override per run with --ready-after-hours.
SESSION_READY_AFTER = timedelta(hours=6)

# The FastF1 schedule's session names for the two session types we ingest.
SESSION_NAMES = {"R": "Race", "Q": "Qualifying"}


def session_start_utc(event_row, session_type: str) -> Optional[pd.Timestamp]:
    """Scheduled start (UTC) of the R or Q session in one schedule row, or None.

    FastF1 lists a weekend's sessions as Session1..Session5 with a matching
    SessionNDateUtc (naive UTC). None when the row has no such session or date.
    """
    name = SESSION_NAMES[session_type]
    for i in range(1, 6):
        if str(event_row.get(f"Session{i}", "")) != name:
            continue
        raw = event_row.get(f"Session{i}DateUtc")
        if raw is None or pd.isna(raw):
            return None
        ts = pd.Timestamp(raw)
        return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return None


def session_is_ready(
    start_utc: Optional[pd.Timestamp],
    now_utc: datetime,
    ready_after: timedelta = SESSION_READY_AFTER,
) -> Optional[bool]:
    """True once start + ready_after has passed, False before, None if unknown."""
    if start_utc is None:
        return None
    now = pd.Timestamp(now_utc)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    return start_utc + ready_after <= now


# ---------------------------------------------------------------------------
# 2. Thin-load rules
# ---------------------------------------------------------------------------

# Laps: tyre columns every stint model reads. Lowest healthy share on disk is
# 0.94 (2018 Belgium Q, lap-1 Stint nulls, WI-05 F25).
MIN_LAP_KEY_SHARE = 0.90
LAP_KEY_COLUMNS = ("Compound", "TyreLife", "Stint")

# Laps: LapTime is legitimately sparse in qualifying (out/in laps, lowest 0.39)
# and in neutralised races (2021 Belgium 0.33), so this only catches a load that
# came back with lap times essentially missing.
MIN_LAPTIME_SHARE = 0.25

# Race results: Points and GridPosition come from Ergast/Jolpica; when that
# call fails FastF1 falls back to the F1 driver list and both come back null.
# Lowest healthy share on disk is 0.95 (one pit-lane starter).
MIN_RACE_RESULT_SHARE = 0.90
RACE_RESULT_COLUMNS = ("Points", "GridPosition")

# Qualifying results: Q1 times, same source. Lowest healthy share 0.86 (drivers
# who set no time); a failed call gives 0.
MIN_QUALI_Q1_SHARE = 0.50


def _share(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns or len(df) == 0:
        return 0.0
    return float(df[col].notna().mean())


def _rows(df) -> int:
    return len(df) if isinstance(df, pd.DataFrame) else 0


def assess_session(
    session_type: str,
    laps: Optional[pd.DataFrame],
    results: Optional[pd.DataFrame],
    weather: Optional[pd.DataFrame],
    race_control: Optional[pd.DataFrame] = None,
) -> dict[str, str]:
    """Completeness problems for one R or Q session, as {check_key: message}.

    Empty dict = complete. Works on FastF1's in-memory frames and on the bronze
    parquet written from them (same column names). check_key is stable
    ("laps.Stint", "results.Points", "weather.rows", ...) so KNOWN_THIN can name
    the exact checks a documented gap is allowed to fail.
    """
    problems: dict[str, str] = {}

    n_laps = _rows(laps)
    if n_laps == 0:
        problems["laps.rows"] = "laps: no rows"
    else:
        for col in LAP_KEY_COLUMNS:
            share = _share(laps, col)
            if share < MIN_LAP_KEY_SHARE:
                problems[f"laps.{col}"] = (
                    f"laps.{col} {share:.0%} non-null (< {MIN_LAP_KEY_SHARE:.0%})"
                )
        lt = _share(laps, "LapTime")
        if lt < MIN_LAPTIME_SHARE:
            problems["laps.LapTime"] = f"laps.LapTime {lt:.0%} non-null (< {MIN_LAPTIME_SHARE:.0%})"

    n_results = _rows(results)
    field = 0
    if n_laps:
        driver_col = "Driver" if "Driver" in laps.columns else "DriverNumber"
        field = int(laps[driver_col].nunique()) if driver_col in laps.columns else 0
    if n_results == 0:
        problems["results.rows"] = "results: no rows"
    else:
        if n_results < field:
            problems["results.rows"] = (
                f"results: {n_results} rows for {field} drivers who set laps"
            )
        if session_type == "R":
            for col in RACE_RESULT_COLUMNS:
                share = _share(results, col)
                if share < MIN_RACE_RESULT_SHARE:
                    problems[f"results.{col}"] = (
                        f"results.{col} {share:.0%} non-null (< {MIN_RACE_RESULT_SHARE:.0%})"
                    )
        else:
            share = _share(results, "Q1")
            if share < MIN_QUALI_Q1_SHARE:
                problems["results.Q1"] = (
                    f"results.Q1 {share:.0%} non-null (< {MIN_QUALI_Q1_SHARE:.0%})"
                )

    if _rows(weather) == 0:
        problems["weather.rows"] = "weather: no rows"
    if session_type == "R" and _rows(race_control) == 0:
        problems["race_control.rows"] = "race_control: no rows"

    return problems


# ---------------------------------------------------------------------------
# 3. Telemetry coverage
# ---------------------------------------------------------------------------

# Share of a race's laps that FastF1 merged per-lap telemetry for. Every
# healthy race 2018-2025 is >= 99.7%; 2026 Monaco (position channel truncated
# at source) is 8.8%.
TELEMETRY_LOW_COVERAGE = 0.95


# ---------------------------------------------------------------------------
# 4. Known source-level gaps
# ---------------------------------------------------------------------------

# (season, round) -> (race slug, reason). The race has no per-lap telemetry at
# source; documented in ADR-009 (docs/platform/architecture-decisions.mdx) and
# data/README.md. Checked against F1's archive 2026-09-25.
KNOWN_TELEMETRY_GAPS: dict[tuple[int, int], tuple[str, str]] = {
    (2018, 1): (
        "australian_grand_prix",
        "F1's archive has the race car-data stream but no position stream, and "
        "FastF1 merges per-lap telemetry only when it has both (ADR-009)",
    ),
    (2018, 2): (
        "bahrain_grand_prix",
        "F1's archive has neither the race car-data nor the position stream (ADR-009)",
    ),
}

# (season, round, session_type) -> (checks allowed to fail, reason). A session
# that fails ONLY these checks is complete as far as the source goes; failing
# any other check is still thin.
KNOWN_THIN: dict[tuple[int, int, str], tuple[frozenset, str]] = {
    (2025, 6, "R"): (
        frozenset({"laps.TyreLife", "laps.Stint"}),
        "FastF1 leaves Stint/TyreLife null on ~35% of 2025 Miami race laps at source "
        "(reloaded fresh 2026-09-25: same); staging quarantines 2025_6 (WI-05, F24)",
    ),
    (2025, 6, "Q"): (
        frozenset({"results.Q1"}),
        "Jolpica's 2025 Miami qualifying results carry empty Q1/Q2/Q3 at source "
        "(checked 2026-09-25)",
    ),
}


def split_known_thin(
    season: int, round_num: int, session_type: str, problems: dict[str, str],
) -> tuple[dict[str, str], Optional[str]]:
    """(problems not explained by KNOWN_THIN, known-gap note or None)."""
    known = KNOWN_THIN.get((season, round_num, session_type))
    if not problems or known is None:
        return dict(problems), None
    allowed, reason = known
    unexplained = {k: v for k, v in problems.items() if k not in allowed}
    explained = sorted(k for k in problems if k in allowed)
    note = f"known source gap ({', '.join(explained)}): {reason}" if explained else None
    return unexplained, note


def known_telemetry_gap(season: int, round_num: int) -> Optional[str]:
    entry = KNOWN_TELEMETRY_GAPS.get((season, round_num))
    return entry[1] if entry else None


# ---------------------------------------------------------------------------
# 5. Event slug -> venue history (slug traps)
# ---------------------------------------------------------------------------

def event_slug(event_name: str) -> str:
    """The race slug used for bronze partitions: 'Abu Dhabi Grand Prix' -> 'abu_dhabi_grand_prix'."""
    return event_name.lower().replace(" ", "_").replace("'", "")


def load_venue_history(schedule_dir: Path, before_season: int) -> pd.DataFrame:
    """(season, slug, location) for every race round in the bronze schedule snapshots
    of seasons earlier than before_season. Empty frame if there are none."""
    frames = []
    for path in sorted(Path(schedule_dir).glob("season=*/schedule.parquet")):
        try:
            season = int(path.parent.name.split("=", 1)[1])
        except (IndexError, ValueError):
            continue
        if season >= before_season:
            continue
        try:
            df = pd.read_parquet(path, columns=["RoundNumber", "EventName", "Location"])
        except Exception:
            continue
        df = df[df["RoundNumber"].fillna(0).astype(int) > 0]
        frames.append(pd.DataFrame({
            "season": season,
            "slug": df["EventName"].astype(str).map(event_slug),
            "location": df["Location"].astype(str),
        }))
    if not frames:
        return pd.DataFrame(columns=["season", "slug", "location"])
    return pd.concat(frames, ignore_index=True)


def venue_note(slug: str, location: str, history: pd.DataFrame) -> str:
    """A warning when a slug's venue differs from every earlier season's, or when a
    new slug appears at a venue an earlier season ingested under another slug.

    Empty string when nothing looks off (or there is no history to compare to).
    Location strings are compared as FastF1 publishes them; a new spelling of the
    same place ('Yas Marina' vs 'Yas Island') also triggers the note, which is
    cheap to dismiss.
    """
    if history is None or history.empty or not location:
        return ""
    same_slug = history[history["slug"] == slug]
    if not same_slug.empty:
        known = sorted(set(same_slug["location"]))
        if location not in known:
            seasons = sorted(set(same_slug["season"]))
            span = f"{seasons[0]}-{seasons[-1]}" if len(seasons) > 1 else str(seasons[0])
            return (f"slug '{slug}' is at {location} this season but was at "
                    f"{' / '.join(known)} in {span}; it now names two venues")
        return ""
    same_place = history[history["location"] == location]
    if not same_place.empty:
        others = sorted(set(same_place["slug"]))
        return (f"new slug '{slug}' at {location}, a venue earlier seasons ingested as "
                f"{' / '.join(others)}")
    return ""
