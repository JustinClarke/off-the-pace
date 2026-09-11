#!/usr/bin/env python3
"""
check_stint_reconstruction_2018.py    sanity-check pit-stop-derived stint
boundaries against FastF1-derived ground truth, for the one season where both
exist (2018).

03b (`_improvements/work/03-driver-vs-car.md`) definition of done requires
stint boundaries "reconstructed from pit data and sanity-checked against 2018
(where both methods are available)". This script:

1. Loads 2018 Jolpica pit stops (bronze, already ingested).
2. Loads the FastF1-derived actual stint boundaries for 2018 from the
   warehouse (`int_stint_geometry`, dbt-materialized in data/dev.duckdb),
   which is built from telemetry-grade tyre-change detection, not pit-lane
   visits.
3. Runs the same `reconstruct_stints` logic (ingestion/scripts/
   reconstruct_stints.py) used for the 2011-2017 production data, but feeds it
   each driver's *actual* last lap from the FastF1 warehouse instead of
   pulling Jolpica laps for 2018. That's a deliberate scope choice: the thing
   under test is "does a classified pit stop's in-lap correctly predict a
   FastF1 tyre-change boundary", not "does Jolpica's own lap count agree with
   FastF1's" -- a separate question. Sourcing the last-lap fact from the
   warehouse avoids an extra, purely-for-validation Jolpica pull while still
   exercising the exact boundary logic that will run on 2011-2017.
4. Compares, per (round, driver): the set of pit-implied stint-end laps
   against the set of FastF1 stint-end laps (every stint's end_lap except the
   driver's final one, which both methods define as "wherever their data
   ends" rather than a boundary).

Driver identity: Jolpica pit_stops key on the Ergast driverId ("hamilton");
the warehouse keys on the FastF1 3-letter code ("HAM"). The mapping comes from
Jolpica's own 2018 driver_standings (`driver_code` column) -- verified unique
within 2018 (the MSC collision between Michael Schumacher, 2011-2012, and Mick
Schumacher, 2021-2022, never overlaps a single season, so keying by
(season, code) is safe; this script only ever looks at one season at a time).

Usage
-----
    python ingestion/scripts/check_stint_reconstruction_2018.py
    python ingestion/scripts/check_stint_reconstruction_2018.py --show-divergences 20
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
JOLPICA_DIR = PROJECT_ROOT / "data" / "bronze" / "reference" / "jolpica"
DUCKDB_PATH = PROJECT_ROOT / "data" / "dev.duckdb"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reconstruct_stints as rs  # noqa: E402

logger = logging.getLogger(__name__)


def load_2018_pit_stops() -> pd.DataFrame:
    return rs.load_pit_stops(2018, 2018)


def load_driver_code_map(season: int = 2018) -> dict[str, str]:
    """Jolpica driver_id -> FastF1 3-letter code, from that season's own
    driver_standings bronze."""
    path = JOLPICA_DIR / "driver_standings" / f"season={season}" / "driver_standings.parquet"
    df = pd.read_parquet(path)
    mapping = dict(zip(df["driver_id"], df["driver_code"]))
    dupes = df["driver_code"].value_counts()
    dupes = dupes[dupes > 1]
    if not dupes.empty:
        logger.warning(f"  driver_code collisions within season {season}: {dupes.to_dict()}")
    return mapping


def load_fastf1_actual_stints_2018() -> pd.DataFrame:
    """Actual stint boundaries from the warehouse: one row per
    (round, driver_code, stint_number) with start_lap/end_lap, derived from
    int_stint_geometry's chronological lap_number within each stint."""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        df = con.execute("""
            SELECT
                CAST(SPLIT_PART(race_id, '_', 2) AS INTEGER) AS round,
                driver_id AS driver_code,
                stint_number,
                MIN(lap_number) AS start_lap,
                MAX(lap_number) AS end_lap
            FROM main.int_stint_geometry
            -- 343 rows in 2018 (only) carry stint_number IS NULL, confined to
            -- lap_number 1-2 of a race: an early-season FastF1 telemetry gap
            -- where the opening lap(s) have no Stint/Compound recorded, not a
            -- genuine extra stint. Left in, a NULL sorts after every real
            -- stint number and corrupts "drop the driver's final stint" below.
            WHERE race_year = 2018 AND stint_number IS NOT NULL
            GROUP BY 1, 2, 3
            ORDER BY 1, 2, 3
        """).fetchdf()
    finally:
        con.close()
    return df


def fastf1_last_lap(actual_stints: pd.DataFrame) -> pd.DataFrame:
    return (
        actual_stints.groupby(["round", "driver_code"], as_index=False)["end_lap"]
        .max()
        .rename(columns={"end_lap": "last_lap_number"})
    )


def breakpoints(stints: pd.DataFrame, key_cols: list[str], end_col: str = "end_lap",
                 final_flag_col: str | None = None) -> dict[tuple, set]:
    """Per driver-race, the set of stint-end laps that are boundaries (i.e.
    every stint's end except the final one)."""
    out: dict[tuple, set] = {}
    for key, sub in stints.groupby(key_cols):
        sub = sub.sort_values("stint_number")
        if final_flag_col is not None:
            ends = sub.loc[sub[final_flag_col], end_col].tolist()
        else:
            ends = sub[end_col].tolist()[:-1]  # all but the last stint
        out[key] = set(ends)
    return out


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show-divergences", type=int, default=10, help="Number of divergent driver-races to print")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    pit_stops = load_2018_pit_stops()
    logger.info(f"Loaded {len(pit_stops)} 2018 Jolpica pit stops across {pit_stops['round'].nunique()} rounds")

    code_map = load_driver_code_map(2018)
    code_to_id = {v: k for k, v in code_map.items() if v}

    actual = load_fastf1_actual_stints_2018()
    actual["driver_id"] = actual["driver_code"].map(code_to_id)
    unmapped = actual[actual["driver_id"].isna()]["driver_code"].unique().tolist()
    if unmapped:
        logger.warning(f"  {len(unmapped)} FastF1 driver codes have no Jolpica mapping (excluded): {unmapped}")
    actual = actual.dropna(subset=["driver_id"]).copy()
    actual["season"] = 2018

    last_lap = fastf1_last_lap(actual).rename(columns={"driver_code": "_dc"})
    last_lap["driver_id"] = last_lap["_dc"].map(code_to_id)
    last_lap = last_lap.dropna(subset=["driver_id"]).drop(columns="_dc")
    last_lap["season"] = 2018

    reconstructed = rs.reconstruct_stints(pit_stops, last_lap)
    logger.info(f"Reconstructed {len(reconstructed)} stints across "
                f"{reconstructed[['round','driver_id']].drop_duplicates().shape[0]} driver-races from pit stops")

    pit_bp = breakpoints(reconstructed, ["round", "driver_id"], "end_lap", final_flag_col="ends_in_pit_stop")
    actual_bp = breakpoints(actual, ["round", "driver_id"], "end_lap")

    # Only compare driver-races present on both sides.
    common_keys = sorted(set(pit_bp) & set(actual_bp))
    only_pit = sorted(set(pit_bp) - set(actual_bp))
    only_actual = sorted(set(actual_bp) - set(pit_bp))
    logger.info(f"\nDriver-races comparable on both sides: {len(common_keys)}")
    if only_pit:
        logger.warning(f"  In pit-stop reconstruction only (no FastF1 stint rows): {len(only_pit)} -> {only_pit[:10]}")
    if only_actual:
        logger.warning(f"  In FastF1 actual only (no pit-stop rows -- likely zero-stop drivers): {len(only_actual)} -> {only_actual[:10]}")

    exact = 0
    divergent: list[dict] = []
    total_pit_bp = 0
    total_actual_bp = 0
    total_matched_bp = 0
    for key in common_keys:
        p, a = pit_bp[key], actual_bp[key]
        total_pit_bp += len(p)
        total_actual_bp += len(a)
        total_matched_bp += len(p & a)
        if p == a:
            exact += 1
        else:
            divergent.append({
                "round": key[0], "driver_id": key[1],
                "pit_only": sorted(p - a), "fastf1_only": sorted(a - p),
            })

    n = len(common_keys)
    logger.info(f"\n=== Stint-boundary agreement, 2018 (pit-stop reconstruction vs FastF1 actual) ===")
    logger.info(f"Driver-races compared: {n}")
    logger.info(f"Exact boundary-set match: {exact}/{n} ({100*exact/n:.1f}%)" if n else "No comparable driver-races")
    if total_pit_bp or total_actual_bp:
        precision = total_matched_bp / total_pit_bp if total_pit_bp else float("nan")
        recall = total_matched_bp / total_actual_bp if total_actual_bp else float("nan")
        logger.info(f"Boundary-level: {total_matched_bp} matched / {total_pit_bp} pit-implied / {total_actual_bp} FastF1-actual "
                    f"(precision={precision:.3f}, recall={recall:.3f})")
        logger.info("  precision < 1: pit stops that didn't register as a FastF1 tyre change (e.g. penalty-serving stops, nose changes)")
        logger.info("  recall < 1: FastF1 stint changes with no matching classified pit stop")

    logger.info(f"\n{len(divergent)} divergent driver-races. Showing up to {args.show_divergences}:")
    for d in divergent[: args.show_divergences]:
        logger.info(f"  Rd{d['round']:>2} {d['driver_id']:<15} pit_only={d['pit_only']} fastf1_only={d['fastf1_only']}")


if __name__ == "__main__":
    main()
