#!/usr/bin/env python3
"""
mover_panel.py    driver x constructor x season spell table, connected
components, and mover count -- the widened 2011-2024 recomputation of 03a's
2018-2024 baseline (21 movers, 76 driver-constructor spells, 158 cells).

03a ("`_improvements/work/03-driver-vs-car.md`) built its panel from
`fct_lap_residuals` (FastF1-derived, per-lap `Team` strings), which only
exists 2018-2024. 03b widens the panel to 2011-2024 using Jolpica reference
data instead, since that's what's available before 2018 -- so this script
recomputes the WHOLE panel (including the 2018-2024 slice) from Jolpica
driver_standings, not just the new 2011-2017 seasons, so the count is one
consistent method end to end rather than splicing two different data sources.
That the 2018-2024 slice, recomputed this way, may not reproduce 21 exactly is
expected and reported, not treated as a bug (see the module docstring section
"Method note" below).

Definitions
-----------
Cell     : a (driver_id, constructor_id, season) triple -- a driver raced for
           a constructor in a season, per Jolpica's Constructors list on that
           season's final driver standings (see "Data source" below).
Spell    : a maximal run of consecutive seasons a driver spent at one
           constructor. A driver who left and later returned to the same
           constructor after racing elsewhere in between gets two spells, not
           one (conservative choice, documented as a judgment call below --
           there is no long gap in this panel to test it against, since every
           season 2011-2024 is populated).
Mover    : a driver with >=2 distinct constructors across their spells (i.e.
           degree >=2 in the driver-constructor bipartite graph). This is the
           standard AKM sense -- any change of constructor identity, whether
           within one season (GAS/ALB 2019) or across a season boundary
           (Vettel Ferrari->Aston Martin) -- not only mid-season switches.
Connected: components of the bipartite graph (drivers + constructors, edge on
           every cell). 03c needs this graph connected (or needs to work
           within its largest component) for the two-way FE to be identified
           at all.

Data source and the Force-India/Racing-Point trap
---------------------------------------------------
Jolpica's season-end driverStandings lists, per driver, EVERY constructor they
scored points with that season (`Constructors`, a list) -- correctly showing
GAS 2019 as ['red_bull', 'toro_rosso'] and RUS 2020 as ['williams',
'mercedes']. But for the Force India -> Racing Point rename (2018, OCO/PER),
it shows only ['force_india'] for the whole season: Ergast's own season
standings already collapse the rename to one constructor_id (constructor_
standings for 2018 lists only 'force_india', not 'racing_point', at all --
the stewards' ruling that Racing Point forfeited the constructors' points
earned before administration appears to be why Racing Point never accrues a
separate season-total entry). So, unlike 03a working from FastF1's per-lap
Team strings (which DO show 'Force India' and 'Racing Point' as different
literal values), this Jolpica-standings method never manufactures the FI/RP
cell split in the first place -- there is nothing to exclude for it here. This
script still explicitly checks every season for any driver with >1
constructor_id AND reports them, so a similar rename elsewhere in 1976-2024 is
caught rather than assumed away by construction (see `find_same_season_multi_
constructor_drivers`).

Open judgment call (flagged, not resolved)
-------------------------------------------
Jolpica's `Constructors` list is scored-points-based: if a driver drove for a
constructor but scored zero points there (a struggling backmarker seat, or a
short substitute stint that didn't score), that constructor may not appear in
their season row at all. This would under-count a cell/spell for a genuinely
raced-for constructor. A fully robust method would use race-by-race `results`
data instead of season-end standings; that is a materially larger ingest
(one request per race rather than one per season) and out of the scope 03b's
leaf doc specifies (driver_standings + constructor_standings + pit stops +
laps). Flagged here rather than silently assumed away.

Usage
-----
    python ingestion/scripts/mover_panel.py --start-season 2011 --end-season 2024
    python ingestion/scripts/mover_panel.py --start-season 2018 --end-season 2024  # 03a baseline slice, same method
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
JOLPICA_DIR = PROJECT_ROOT / "data" / "bronze" / "reference" / "jolpica"

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Load + explode
# ----------------------------------------------------------------------

def load_driver_standings(start_season: int, end_season: int) -> pd.DataFrame:
    frames = []
    missing = []
    for season in range(start_season, end_season + 1):
        path = JOLPICA_DIR / "driver_standings" / f"season={season}" / "driver_standings.parquet"
        if not path.exists():
            missing.append(season)
            continue
        frames.append(pd.read_parquet(path))
    if missing:
        logger.warning(f"  Missing driver_standings for seasons: {missing}")
    if not frames:
        return pd.DataFrame(columns=["season", "driver_id", "constructor_ids"])
    return pd.concat(frames, ignore_index=True)


def build_cells(driver_standings: pd.DataFrame) -> pd.DataFrame:
    """Explode `constructor_ids` (';'-joined) into one row per
    (driver_id, constructor_id, season) cell. Rows with no constructor at all
    (a classified driver who scored with nobody -- e.g. DNQ'd all season) are
    dropped; they cannot contribute a spell."""
    if "constructor_ids" not in driver_standings.columns:
        raise ValueError(
            "driver_standings is missing 'constructor_ids' -- this bronze predates the "
            "03b flattener fix (see jolpica_client.py _flatten_standings). Re-run "
            "`python ingestion/src/jolpica_client.py --start-season <S> --end-season <E>` "
            "for the affected seasons before computing the mover panel."
        )
    df = driver_standings.dropna(subset=["constructor_ids"]).copy()
    df["constructor_id"] = df["constructor_ids"].str.split(";")
    df = df.explode("constructor_id")
    cells = df[["driver_id", "constructor_id", "season"]].drop_duplicates()
    return cells.sort_values(["driver_id", "season", "constructor_id"]).reset_index(drop=True)


def find_same_season_multi_constructor_drivers(cells: pd.DataFrame) -> pd.DataFrame:
    """Drivers with >1 constructor in the SAME season -- genuine mid-season
    switches (GAS/ALB 2019, RUS 2020, BEA 2024) unless investigation shows
    otherwise (the FI/RP-style rename trap). Every one of these should be
    manually reasoned about, the way 03a did for FI/RP, not assumed clean."""
    counts = cells.groupby(["driver_id", "season"])["constructor_id"].nunique()
    flagged = counts[counts > 1].reset_index().rename(columns={"constructor_id": "n_constructors"})
    detail = flagged.merge(cells, on=["driver_id", "season"])
    return detail.sort_values(["season", "driver_id"])


# ----------------------------------------------------------------------
# Spells
# ----------------------------------------------------------------------

def build_spells(cells: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse (driver, constructor, season) cells into spells: a maximal run
    of CONSECUTIVE seasons a driver spent at one constructor. A driver active
    at two constructors in the same season (a mid-season switch) contributes
    one single-season spell per constructor for that season; if either
    extends into adjacent seasons at the same constructor, the spell grows.

    Implementation: for each driver, walk their (season, constructor) cells
    in season order. A new spell starts whenever the constructor differs from
    the immediately preceding season's constructor set membership continuing
    that constructor, OR the season isn't consecutive with the spell's last
    season.
    """
    rows = []
    for driver_id, g in cells.groupby("driver_id"):
        g = g.sort_values(["season", "constructor_id"])
        # open spells: constructor_id -> (start_season, last_season)
        open_spells: dict[str, list[int]] = {}
        seasons_seen = sorted(g["season"].unique())
        by_season = {s: set(g.loc[g["season"] == s, "constructor_id"]) for s in seasons_seen}

        for s in seasons_seen:
            active = by_season[s]
            # extend or open a spell for every constructor active this season
            for cid in active:
                if cid in open_spells and open_spells[cid][1] == s - 1:
                    open_spells[cid][1] = s
                else:
                    if cid in open_spells:
                        # gap: close the old spell, start a new one
                        rows.append((driver_id, cid, open_spells[cid][0], open_spells[cid][1]))
                    open_spells[cid] = [s, s]
            # close any spell whose constructor isn't active this season
            for cid in list(open_spells):
                if cid not in active and open_spells[cid][1] < s:
                    rows.append((driver_id, cid, open_spells[cid][0], open_spells[cid][1]))
                    del open_spells[cid]
        for cid, (start, last) in open_spells.items():
            rows.append((driver_id, cid, start, last))

    spells = pd.DataFrame(rows, columns=["driver_id", "constructor_id", "start_season", "end_season"])
    spells["n_seasons"] = spells["end_season"] - spells["start_season"] + 1
    return spells.sort_values(["driver_id", "start_season"]).reset_index(drop=True)


# ----------------------------------------------------------------------
# Movers + connected components
# ----------------------------------------------------------------------

def compute_movers(spells: pd.DataFrame) -> pd.DataFrame:
    per_driver = spells.groupby("driver_id")["constructor_id"].nunique().rename("n_constructors")
    return per_driver.reset_index().sort_values("n_constructors", ascending=False)


def connected_components(cells: pd.DataFrame) -> list[set[str]]:
    """Union-find over the driver-constructor bipartite graph (nodes prefixed
    'D:'/'C:' so a driver_id and constructor_id that happen to collide as
    strings can't merge into one node)."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for row in cells.itertuples(index=False):
        union(f"D:{row.driver_id}", f"C:{row.constructor_id}")

    groups: dict[str, set[str]] = {}
    for node in parent:
        groups.setdefault(find(node), set()).add(node)
    return list(groups.values())


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------

def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-season", type=int, required=True)
    parser.add_argument("--end-season", type=int, required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    standings = load_driver_standings(args.start_season, args.end_season)
    cells = build_cells(standings)
    spells = build_spells(cells)
    movers = compute_movers(spells)
    components = connected_components(cells)
    components.sort(key=len, reverse=True)

    n_drivers = cells["driver_id"].nunique()
    n_constructors = cells["constructor_id"].nunique()
    n_seasons = cells["season"].nunique()
    n_movers = int((movers["n_constructors"] >= 2).sum())

    logger.info(f"=== Mover panel, {args.start_season}-{args.end_season} (Jolpica driver_standings method) ===")
    logger.info(f"Drivers: {n_drivers}  Constructors: {n_constructors}  Seasons: {n_seasons}")
    logger.info(f"Cells (driver x constructor x season): {len(cells)}")
    logger.info(f"Spells (driver-constructor, consecutive-season runs): {len(spells)}")
    logger.info(f"Movers (drivers with >=2 constructors): {n_movers} / {n_drivers}")
    logger.info(f"Connected components: {len(components)}")
    for i, comp in enumerate(components):
        drivers = sorted(n[2:] for n in comp if n.startswith("D:"))
        cons = sorted(n[2:] for n in comp if n.startswith("C:"))
        logger.info(f"  Component {i+1}: {len(drivers)} drivers, {len(cons)} constructors" +
                    (f"  -> {cons}" if len(cons) <= 6 else ""))
        if len(comp) < 8:
            logger.info(f"    drivers: {drivers}  constructors: {cons}")

    same_season_multi = find_same_season_multi_constructor_drivers(cells)
    logger.info(f"\nDrivers with >1 constructor in the SAME season ({len(same_season_multi['driver_id'].unique()) if not same_season_multi.empty else 0} driver-seasons) -- inspect each for a rename trap:")
    for (driver_id, season), g in same_season_multi.groupby(["driver_id", "season"]):
        logger.info(f"  {season} {driver_id}: {sorted(g['constructor_id'].unique())}")


if __name__ == "__main__":
    main()
