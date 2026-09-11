"""Offline tests for the driver x constructor x season mover panel (no network)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import mover_panel as mp  # noqa: E402


def _standings(rows):
    """rows: list of (season, driver_id, constructor_ids_str)"""
    return pd.DataFrame(rows, columns=["season", "driver_id", "constructor_ids"])


def test_build_cells_explodes_multi_constructor():
    standings = _standings([
        (2019, "gasly", "red_bull;toro_rosso"),
        (2019, "albon", "toro_rosso;red_bull"),
        (2019, "hamilton", "mercedes"),
    ])
    cells = mp.build_cells(standings)
    assert len(cells) == 5
    gasly_cons = set(cells.loc[cells["driver_id"] == "gasly", "constructor_id"])
    assert gasly_cons == {"red_bull", "toro_rosso"}


def test_build_cells_requires_constructor_ids_column():
    bad = pd.DataFrame([{"season": 2019, "driver_id": "gasly", "constructor_id": "red_bull"}])
    with pytest.raises(ValueError, match="constructor_ids"):
        mp.build_cells(bad)


def test_stayer_gets_one_multi_season_spell():
    standings = _standings([
        (2018, "hamilton", "mercedes"),
        (2019, "hamilton", "mercedes"),
        (2020, "hamilton", "mercedes"),
    ])
    cells = mp.build_cells(standings)
    spells = mp.build_spells(cells)
    assert len(spells) == 1
    row = spells.iloc[0]
    assert row["constructor_id"] == "mercedes"
    assert row["start_season"] == 2018
    assert row["end_season"] == 2020
    assert row["n_seasons"] == 3


def test_between_season_move_gives_two_spells():
    standings = _standings([
        (2018, "vettel", "ferrari"),
        (2019, "vettel", "ferrari"),
        (2021, "vettel", "aston_martin"),
        (2022, "vettel", "aston_martin"),
    ])
    cells = mp.build_cells(standings)
    spells = mp.build_spells(cells)
    assert len(spells) == 2
    cons = set(spells["constructor_id"])
    assert cons == {"ferrari", "aston_martin"}


def test_mid_season_switch_gives_two_single_season_spells():
    """GAS 2019: red_bull then toro_rosso, same season -- two spells, not one."""
    standings = _standings([(2019, "gasly", "red_bull;toro_rosso")])
    cells = mp.build_cells(standings)
    spells = mp.build_spells(cells)
    assert len(spells) == 2
    assert set(spells["constructor_id"]) == {"red_bull", "toro_rosso"}
    assert (spells["n_seasons"] == 1).all()


def test_return_to_same_constructor_after_gap_is_two_spells():
    """Left, raced elsewhere, came back: NOT one continuous spell (the
    conservative documented choice -- a spell breaks on any season gap even
    at the same constructor)."""
    standings = _standings([
        (2018, "magnussen", "haas"),
        (2019, "magnussen", "haas"),
        (2021, "magnussen", "other_team"),
        (2022, "magnussen", "haas"),
    ])
    cells = mp.build_cells(standings)
    spells = mp.build_spells(cells)
    haas_spells = spells[spells["constructor_id"] == "haas"]
    assert len(haas_spells) == 2
    assert sorted(haas_spells["start_season"]) == [2018, 2022]


def test_movers_need_two_distinct_constructors():
    standings = _standings([
        (2018, "hamilton", "mercedes"),
        (2019, "hamilton", "mercedes"),
        (2018, "vettel", "ferrari"),
        (2020, "vettel", "aston_martin"),
    ])
    cells = mp.build_cells(standings)
    spells = mp.build_spells(cells)
    movers = mp.compute_movers(spells)
    m = movers.set_index("driver_id")["n_constructors"].to_dict()
    assert m["hamilton"] == 1
    assert m["vettel"] == 2


def test_connected_components_bridged_by_mover():
    """Two otherwise-disjoint constructor islands, bridged into one component
    by a driver who raced for both."""
    standings = _standings([
        (2018, "a", "team1"),
        (2018, "b", "team1"),
        (2018, "c", "team2"),
        (2019, "b", "team2"),  # bridges team1 and team2
    ])
    cells = mp.build_cells(standings)
    comps = mp.connected_components(cells)
    assert len(comps) == 1
    assert len(comps[0]) == 5  # 3 drivers + 2 constructors


def test_connected_components_isolated_island():
    standings = _standings([
        (2018, "a", "team1"),
        (2018, "b", "team2"),  # never connects to team1
    ])
    cells = mp.build_cells(standings)
    comps = mp.connected_components(cells)
    assert len(comps) == 2


def test_same_season_multi_constructor_flagging():
    standings = _standings([
        (2018, "perez", "force_india"),   # single entry -- not flagged
        (2019, "gasly", "red_bull;toro_rosso"),  # flagged
    ])
    cells = mp.build_cells(standings)
    flagged = mp.find_same_season_multi_constructor_drivers(cells)
    assert set(flagged["driver_id"]) == {"gasly"}
