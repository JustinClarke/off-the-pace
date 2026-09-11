#!/usr/bin/env python3
"""
reconstruct_stints.py    stint boundaries from Jolpica pit-stop data.

03b (`_improvements/work/03-driver-vs-car.md`): 2011-2017 has no telemetry and
no compound data, but pit stops are classified from 2011 onward and refuelling
was already banned, so a stint (the run of laps between pit visits, or
race-start/race-end) is recoverable from pit-stop data alone -- no telemetry
needed. This is pure derivation: a stint boundary is the in-lap of each pit
stop; the final stint runs to the driver's last classified lap (race finish or
retirement), not to the scheduled race distance.

Input
-----
pit_stops : season, round, driver_id, stop, lap, duration_s, ...
    (the `data/bronze/reference/jolpica/pit_stops` schema; `lap` is the in-lap
    of the stop.)
last_lap  : season, round, driver_id, last_lap_number
    The driver's final recorded lap for that race -- classified finish or
    retirement lap, whichever came first. The caller supplies this because the
    source differs: for 2011-2017 production use it comes from this client's
    own `laps` bronze (the driver's max lap_number); for the 2018 sanity check
    in `check_stint_reconstruction_2018.py` it comes from the FastF1 warehouse,
    which already has it and avoids an extra Jolpica pull for a validation-only
    run.

Output
------
One row per (season, round, driver_id, stint_number): start_lap, end_lap,
stint_length, ends_in_pit_stop (False only for a driver's final stint if they
never pitted again before their last lap -- i.e. every stint boundary that
isn't "the race/driver's data ended").

Usage
-----
    python ingestion/scripts/reconstruct_stints.py --start-season 2011 --end-season 2017
    python -m ingestion.scripts.reconstruct_stints --start-season 2011 --end-season 2017
"""
from __future__ import annotations

import argparse
import glob
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
JOLPICA_DIR = PROJECT_ROOT / "data" / "bronze" / "reference" / "jolpica"

logger = logging.getLogger(__name__)


def reconstruct_stints(pit_stops: pd.DataFrame, last_lap: pd.DataFrame) -> pd.DataFrame:
    """
    Derive stint boundaries for every (season, round, driver_id) present in
    `last_lap` (the full set of driver-races to reconstruct), using the pit
    stops in `pit_stops` as boundaries. A driver with zero recorded pit stops
    gets a single stint spanning their whole race.

    A pit lap that lands on or after the driver's last recorded lap (a data
    wrinkle, not expected but not assumed away either) is clipped to
    `last_lap_number - 1` so it can never produce a zero/negative-length final
    stint; such rows are flagged via `clipped_pit_lap=True` for the caller to
    inspect rather than silently dropped.
    """
    key = ["season", "round", "driver_id"]
    boundaries = (
        pit_stops[key + ["lap"]]
        .dropna(subset=["lap"])
        .assign(lap=lambda d: d["lap"].astype(int))
        .drop_duplicates()
        .groupby(key)["lap"]
        .apply(lambda s: sorted(set(s.tolist())))
        .rename("pit_laps")
        .reset_index()
    )

    races = last_lap[key + ["last_lap_number"]].drop_duplicates().merge(
        boundaries, on=key, how="left"
    )
    races["pit_laps"] = races["pit_laps"].apply(lambda v: v if isinstance(v, list) else [])

    rows: list[dict] = []
    for row in races.itertuples(index=False):
        last = int(row.last_lap_number)
        pit_laps = [lp for lp in row.pit_laps if lp is not None]
        # Clip any boundary at/after the driver's last lap -- can't end a
        # stint past the data we have for them.
        clipped = False
        clean_laps: list[int] = []
        for lp in pit_laps:
            if lp >= last:
                clipped = True
                continue
            clean_laps.append(lp)
        clean_laps = sorted(set(clean_laps))

        start = 1
        for stint_num, boundary in enumerate(clean_laps, start=1):
            rows.append({
                "season": row.season, "round": row.round, "driver_id": row.driver_id,
                "stint_number": stint_num, "start_lap": start, "end_lap": boundary,
                "stint_length": boundary - start + 1,
                "ends_in_pit_stop": True, "clipped_pit_lap": clipped,
            })
            start = boundary + 1

        if start <= last:
            rows.append({
                "season": row.season, "round": row.round, "driver_id": row.driver_id,
                "stint_number": len(clean_laps) + 1, "start_lap": start, "end_lap": last,
                "stint_length": last - start + 1,
                "ends_in_pit_stop": False, "clipped_pit_lap": clipped,
            })

    return pd.DataFrame(rows, columns=[
        "season", "round", "driver_id", "stint_number", "start_lap", "end_lap",
        "stint_length", "ends_in_pit_stop", "clipped_pit_lap",
    ])


def last_lap_from_jolpica_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """The driver's max recorded lap_number per (season, round, driver_id) --
    race finish or retirement lap, from this client's own `laps` bronze."""
    return (
        laps.groupby(["season", "round", "driver_id"], as_index=False)["lap_number"]
        .max()
        .rename(columns={"lap_number": "last_lap_number"})
    )


# ----------------------------------------------------------------------
# Bronze I/O
# ----------------------------------------------------------------------

def load_pit_stops(start_season: int, end_season: int) -> pd.DataFrame:
    files = []
    for season in range(start_season, end_season + 1):
        files += glob.glob(str(JOLPICA_DIR / "pit_stops" / f"season={season}" / "round=*" / "*.parquet"))
    if not files:
        return pd.DataFrame(columns=["season", "round", "driver_id", "stop", "lap", "duration_s"])
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def load_laps(start_season: int, end_season: int) -> pd.DataFrame:
    files = []
    for season in range(start_season, end_season + 1):
        files += glob.glob(str(JOLPICA_DIR / "laps" / f"season={season}" / "round=*" / "*.parquet"))
    if not files:
        return pd.DataFrame(columns=["season", "round", "driver_id", "lap_number"])
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def write_stints(df: pd.DataFrame) -> None:
    for (season, round_num), sub in df.groupby(["season", "round"]):
        sub_dir = JOLPICA_DIR / "stints" / f"season={season}" / f"round={round_num}"
        os.makedirs(sub_dir, exist_ok=True)
        path = sub_dir / "stints.parquet"
        sub.to_parquet(path, index=False, compression="snappy")
    logger.info(f"  stints written for {df[['season','round']].drop_duplicates().shape[0]} races, {len(df)} stint rows")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-season", type=int, required=True)
    parser.add_argument("--end-season", type=int, required=True)
    parser.add_argument("--write", action="store_true", help="Write output to data/bronze/reference/jolpica/stints/")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")

    pit_stops = load_pit_stops(args.start_season, args.end_season)
    laps = load_laps(args.start_season, args.end_season)
    if laps.empty:
        logger.error("No Jolpica laps bronze found for this range -- run jolpica_client.py --with-laps first.")
        sys.exit(1)

    last_lap = last_lap_from_jolpica_laps(laps)
    stints = reconstruct_stints(pit_stops, last_lap)
    logger.info(f"Reconstructed {len(stints)} stints across {stints[['season','round','driver_id']].drop_duplicates().shape[0]} driver-races")
    n_clipped = int(stints["clipped_pit_lap"].sum())
    if n_clipped:
        logger.warning(f"  {n_clipped} stint rows had a pit lap clipped at/after the driver's last recorded lap")

    if args.write:
        write_stints(stints)


if __name__ == "__main__":
    main()
