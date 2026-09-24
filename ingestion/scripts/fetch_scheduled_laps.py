#!/usr/bin/env python3
"""
fetch_scheduled_laps.py -- the race's scheduled distance, in laps, per race.

WI-05 (F6, F32, F52; `_roadmap/_fixes/wi/WI-05-season-onboarding.md`). The fuel
model needs the number of laps a car was fuelled for, which is a PRE-RACE
quantity. Until WI-05 it was read off the race itself (MAX(lap_number) over valid
laps), which encodes how the race ended: a neutralised finish shortens it, and so
does a red flag or a time limit.

Where the number comes from. The bronze event schedule (`data/bronze/schedule/`)
has no lap count, and nor does any other bronze table. The F1 live-timing feed
does: its `LapCount` stream carries `TotalLaps`, "the intended number of total
laps", published before the start and re-published whenever race control changes
the distance. FastF1 exposes it as `fastf1.api.lap_count`; its own
`Session.total_laps` keeps the LAST value. This script keeps both ends:

  scheduled_laps    first TotalLaps value = the distance announced before the
                    start. This is what the fuel load is planned against, and
                    what int_lap_fuel_state reads.
  total_laps_final  last TotalLaps value. Differs from scheduled_laps only where
                    race control changed the distance (e.g. an aborted start
                    taking laps off); kept for audit, not used by the fuel model.
  max_current_lap   the last CurrentLap the feed reported (laps actually run).

Output: transform/seeds/race_scheduled_laps.csv, one row per race_id in
transform/seeds/race_to_track.csv (the per-race map every model joins). Races the
feed has no LapCount data for are written with an empty scheduled_laps and a note,
never guessed; `assert_fuel_load_matches_scheduled_distance` fails the build on
them, so a gap is loud.

Usage
-----
    python ingestion/scripts/fetch_scheduled_laps.py            # print, no write
    python ingestion/scripts/fetch_scheduled_laps.py --write    # write the seed
    python ingestion/scripts/fetch_scheduled_laps.py --write --season 2026

Needs network access to livetiming.formula1.com (and FastF1's schedule backend).
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
import tempfile
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SEEDS_DIR = PROJECT_ROOT / "transform" / "seeds"
RACE_TO_TRACK = SEEDS_DIR / "race_to_track.csv"
OUT = SEEDS_DIR / "race_scheduled_laps.csv"
SOURCE = "f1_livetiming_lapcount"
COLUMNS = [
    "race_id", "race_year", "round_number", "event_name",
    "scheduled_laps", "total_laps_final", "max_current_lap", "source", "note",
]

logger = logging.getLogger(__name__)


def summarise_lap_count(total_laps: list, current_lap: list) -> dict:
    """First and last non-null TotalLaps, and the last non-null CurrentLap."""
    totals = [int(t) for t in total_laps if t is not None]
    currents = [int(c) for c in current_lap if c is not None]
    return {
        "scheduled_laps": totals[0] if totals else None,
        "total_laps_final": totals[-1] if totals else None,
        "max_current_lap": max(currents) if currents else None,
    }


def read_race_ids(season: Optional[int]) -> list[str]:
    with RACE_TO_TRACK.open() as fh:
        ids = [row["race_id"] for row in csv.DictReader(fh)]
    if season is not None:
        ids = [r for r in ids if r.startswith(f"{season}_")]
    return sorted(ids, key=lambda r: (int(r.split("_")[0]), int(r.split("_")[1])))


def fetch_one(race_id: str) -> dict:
    import fastf1
    from fastf1 import api

    year, rnd = (int(x) for x in race_id.split("_"))
    row = {"race_id": race_id, "race_year": year, "round_number": rnd,
           "event_name": None, "scheduled_laps": None, "total_laps_final": None,
           "max_current_lap": None, "source": SOURCE, "note": ""}
    try:
        session = fastf1.get_session(year, rnd, "R")
        row["event_name"] = session.event["EventName"]
        lc = api.lap_count(session.api_path)
        row.update(summarise_lap_count(lc.get("TotalLaps", []), lc.get("CurrentLap", [])))
        if row["scheduled_laps"] is None:
            row["note"] = "no TotalLaps in the LapCount stream"
        elif row["scheduled_laps"] != row["total_laps_final"]:
            row["note"] = (f"race control changed the distance {row['scheduled_laps']} -> "
                           f"{row['total_laps_final']}; scheduled_laps keeps the pre-race value")
    except Exception as exc:  # a missing session must not abort the whole pull
        row["note"] = f"fetch failed: {type(exc).__name__}: {str(exc).splitlines()[0][:120]}"
    return row


def merge_rows(existing: list[dict], fresh: list[dict]) -> list[dict]:
    by_id = {r["race_id"]: r for r in existing}
    by_id.update({r["race_id"]: r for r in fresh})
    return sorted(by_id.values(), key=lambda r: (int(r["race_year"]), int(r["round_number"])))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--season", type=int, help="only this season (merged into the existing seed)")
    parser.add_argument("--write", action="store_true", help=f"write {OUT.relative_to(PROJECT_ROOT)}")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    import fastf1
    logging.getLogger("fastf1").setLevel(logging.WARNING)
    # A throwaway HTTP cache: this pull is small, and it must not write into data/cache.
    fastf1.Cache.enable_cache(tempfile.mkdtemp(prefix="ff1_lapcount_"))

    fresh = [fetch_one(r) for r in read_race_ids(args.season)]
    for r in fresh:
        logger.info("%s %-32s scheduled=%s final=%s ran=%s %s", r["race_id"], r["event_name"],
                    r["scheduled_laps"], r["total_laps_final"], r["max_current_lap"], r["note"])

    missing = [r["race_id"] for r in fresh if r["scheduled_laps"] is None]
    if missing:
        logger.warning("no scheduled distance for %d race(s): %s", len(missing), missing)

    if args.write:
        existing: list[dict] = []
        if args.season is not None and OUT.exists():
            with OUT.open() as fh:
                existing = list(csv.DictReader(fh))
        rows = merge_rows(existing, fresh)
        with OUT.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            for r in rows:
                w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in COLUMNS})
        logger.info("wrote %d rows -> %s", len(rows), OUT)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
