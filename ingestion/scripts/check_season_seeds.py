#!/usr/bin/env python3
"""
check_season_seeds.py -- before building a newly ingested season, list the
non-FastF1 seed rows it still needs and the command (or manual step) that fills
each one.

A season's bronze comes from FastF1, but four hand-kept or separately fetched
seeds in transform/seeds/ are keyed by race and need rows for it too. WI-05 made
the dbt build refuse to silently drop a race over them
(assert_race_to_track_covers_all_races, assert_fuel_load_matches_scheduled_distance),
but those only fire during `dbt build` / `dbt test`, after the long full build.
This script front-runs the same requirements from bronze and the seed CSVs alone
(no warehouse), so `make add-season` stops early with a to-do list.

REQUIRED (the build fails, or a dbt test fails, without them):
  race_to_track.csv        race_id -> track_id (a circuit_reference.circuit_key). Manual.
  circuit_reference.csv    one row per track_id the season uses. Manual.
  race_scheduled_laps.csv  scheduled race distance per race_id. Generated:
                           python ingestion/scripts/fetch_scheduled_laps.py --write --season YYYY
                           (reads race_ids from race_to_track, so fill that first).
OPTIONAL (the build succeeds; values are NULL):
  tyre_allocations.csv     Pirelli C-codes per (race_year, circuit_key); without it
                           compound_code is NULL for the season. Manual.
  raw_dim_events.csv       manual incident log (2021 only); nothing required per season.

Usage:
    python ingestion/scripts/check_season_seeds.py --season 2026
    python ingestion/scripts/check_season_seeds.py --season 2026 --bronze-dir PATH

Exit 0 = every REQUIRED seed covers the season's races in bronze; 1 otherwise.
Read-only: it never edits a seed.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "ingestion" / "src"))
import bronze_checks  # noqa: E402

BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"
SEEDS_DIR = PROJECT_ROOT / "transform" / "seeds"


def season_races(bronze: Path, season: int) -> list[dict]:
    """[{race_id, round, slug}] for every race with a race-laps file in bronze."""
    out = []
    season_dir = bronze / "laps" / f"season={season}"
    for race_dir in sorted(season_dir.glob("race=*")) if season_dir.exists() else []:
        slug = race_dir.name.split("=", 1)[1]
        laps = race_dir / f"{season}_{slug}_laps.parquet"
        if not laps.exists():
            continue
        try:
            race_id = str(pq.ParquetFile(laps).read(columns=["race_id"]).column("race_id")[0].as_py())
            rnd = int(race_id.split("_")[1])
        except Exception:
            continue
        out.append({"race_id": race_id, "round": rnd, "slug": slug})
    return sorted(out, key=lambda r: r["round"])


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _venue_notes(bronze: Path, season: int) -> dict[str, str]:
    """slug -> venue note for this season's schedule snapshot (empty if none)."""
    snap = bronze / "schedule" / f"season={season}" / "schedule.parquet"
    if not snap.exists():
        return {}
    history = bronze_checks.load_venue_history(bronze / "schedule", season)
    sched = pq.ParquetFile(snap).read(columns=["RoundNumber", "EventName", "Location"]).to_pandas()
    notes = {}
    for _, row in sched.iterrows():
        if not row["RoundNumber"] or int(row["RoundNumber"]) == 0:
            continue
        slug = bronze_checks.event_slug(str(row["EventName"]))
        note = bronze_checks.venue_note(slug, str(row["Location"]), history)
        if note:
            notes[slug] = note
    return notes


def check(season: int, bronze: Path = BRONZE_DIR, seeds: Path = SEEDS_DIR) -> dict:
    """Coverage report: {'races', 'required': [...], 'optional': [...], 'info': [...]}.

    Each required/optional entry is {'seed', 'missing', 'how'} (+ 'rows' for
    suggested race_to_track lines)."""
    races = season_races(bronze, season)
    report: dict = {"season": season, "races": races, "required": [], "optional": [], "info": []}
    if not races:
        report["info"].append(f"no race laps for {season} under {bronze}; ingest the season first")
        return report

    race_ids = [r["race_id"] for r in races]
    circuit_keys = {r["circuit_key"] for r in _read_csv(seeds / "circuit_reference.csv")}
    notes = _venue_notes(bronze, season)

    # race_to_track -------------------------------------------------------------
    r2t = {r["race_id"]: r["track_id"] for r in _read_csv(seeds / "race_to_track.csv")}
    missing_r2t = [r for r in races if not r2t.get(r["race_id"])]
    if missing_r2t:
        rows = []
        for r in missing_r2t:
            flags = []
            if r["slug"] not in circuit_keys:
                flags.append("no circuit_reference row for this key yet")
            if r["slug"] in notes:
                flags.append(notes[r["slug"]])
            rows.append((f"{r['race_id']},{r['slug']}", "; ".join(flags)))
        report["required"].append({
            "seed": "race_to_track.csv",
            "missing": [r["race_id"] for r in missing_r2t],
            "how": ("add one row per race by hand: race_id,track_id, where track_id is a "
                    "circuit_reference.circuit_key. Suggested rows (the event slug; CHECK any "
                    "flagged one, a slug can now name a different venue):"),
            "rows": rows,
        })

    # circuit_reference (only checkable for races race_to_track already maps) -----
    mapped = {rid: r2t[rid] for rid in race_ids if r2t.get(rid)}
    unknown_tracks = sorted({t for t in mapped.values() if t not in circuit_keys})
    if unknown_tracks:
        report["required"].append({
            "seed": "circuit_reference.csv",
            "missing": unknown_tracks,
            "how": ("add a row per track_id by hand (lap_length_km, corner_count, pit_lane_loss_s, "
                    "...; see transform/seeds/README.md), or point race_to_track at an existing key"),
        })

    # race_scheduled_laps ---------------------------------------------------------
    sched_laps = {r["race_id"]: r.get("scheduled_laps", "")
                  for r in _read_csv(seeds / "race_scheduled_laps.csv")}
    missing_laps = [rid for rid in race_ids if not str(sched_laps.get(rid, "")).strip()]
    if missing_laps:
        how = f"python ingestion/scripts/fetch_scheduled_laps.py --write --season {season}"
        if missing_r2t:
            how += "   (run it AFTER race_to_track has the season's rows: it reads race_ids from there)"
        report["required"].append({"seed": "race_scheduled_laps.csv", "missing": missing_laps,
                                   "how": how})

    # tyre_allocations (optional) ------------------------------------------------
    alloc = {(r["race_year"], r["circuit_key"]) for r in _read_csv(seeds / "tyre_allocations.csv")}
    track_of = {r["race_id"]: (r2t.get(r["race_id"]) or r["slug"]) for r in races}
    missing_alloc = [rid for rid in race_ids if (str(season), track_of[rid]) not in alloc]
    if missing_alloc:
        latest = max((int(y) for y, _ in alloc), default=None)
        report["optional"].append({
            "seed": "tyre_allocations.csv",
            "missing": missing_alloc,
            "how": ("compound_code (Pirelli C1-C5) stays NULL for these races. Fill by hand from "
                    "Pirelli's per-race preview: race_year,circuit_key,hard_code,medium_code,"
                    f"soft_code,source_url (latest season in the seed: {latest})"),
        })

    # raw_dim_events (informational) ---------------------------------------------
    n_events = sum(1 for r in _read_csv(seeds / "raw_dim_events.csv")
                   if str(r.get("race_id", "")).startswith(f"{season}_"))
    report["info"].append(f"raw_dim_events.csv: {n_events} row(s) for {season}. It is a manual "
                          f"incident log, not required per season.")
    return report


def _fmt_ids(ids: list[str]) -> str:
    return ", ".join(ids) if len(ids) <= 8 else f"{', '.join(ids[:4])} ... {', '.join(ids[-2:])}"


def print_report(report: dict) -> int:
    season, races = report["season"], report["races"]
    rounds = [r["round"] for r in races]
    span = f"rounds {min(rounds)}-{max(rounds)}" if rounds else "none"
    print(f"Season {season} seed coverage: {len(races)} race(s) in bronze ({span})")
    if report["required"]:
        print("\nREQUIRED (dbt fails or drops these races without them):")
        for item in report["required"]:
            print(f"  ✗ {item['seed']}: {len(item['missing'])} missing ({_fmt_ids(item['missing'])})")
            print(f"      {item['how']}")
            for row, flag in item.get("rows", []):
                print(f"        {row}" + (f"      <- {flag}" if flag else ""))
    else:
        print("\nREQUIRED: ✓ race_to_track, circuit_reference and race_scheduled_laps cover every race")
    if report["optional"]:
        print("\nOPTIONAL (the build succeeds; values stay NULL):")
        for item in report["optional"]:
            print(f"  ! {item['seed']}: {len(item['missing'])} missing ({_fmt_ids(item['missing'])})")
            print(f"      {item['how']}")
    for line in report["info"]:
        print(f"\n  · {line}")
    if report["required"]:
        print(f"\nNext: fill the REQUIRED rows, then re-run `make add-season SEASON={season}` "
              f"(ingest skips what is already on disk).")
        return 1
    return 0 if races else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--bronze-dir", type=Path, default=BRONZE_DIR)
    parser.add_argument("--seeds-dir", type=Path, default=SEEDS_DIR)
    args = parser.parse_args(argv)
    return print_report(check(args.season, args.bronze_dir, args.seeds_dir))


if __name__ == "__main__":
    sys.exit(main())
