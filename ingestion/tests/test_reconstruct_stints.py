"""Offline tests for stint reconstruction from pit-stop data (no network)."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import reconstruct_stints as rs  # noqa: E402


def test_two_stops_three_stints():
    pit_stops = pd.DataFrame([
        {"season": 2018, "round": 1, "driver_id": "hamilton", "stop": 1, "lap": 20, "duration_s": 22.0},
        {"season": 2018, "round": 1, "driver_id": "hamilton", "stop": 2, "lap": 40, "duration_s": 21.0},
    ])
    last_lap = pd.DataFrame([{"season": 2018, "round": 1, "driver_id": "hamilton", "last_lap_number": 58}])
    out = rs.reconstruct_stints(pit_stops, last_lap)
    assert len(out) == 3
    assert out["start_lap"].tolist() == [1, 21, 41]
    assert out["end_lap"].tolist() == [20, 40, 58]
    assert out["stint_length"].tolist() == [20, 20, 18]
    assert out["ends_in_pit_stop"].tolist() == [True, True, False]


def test_zero_stops_single_stint():
    pit_stops = pd.DataFrame(columns=["season", "round", "driver_id", "stop", "lap", "duration_s"])
    last_lap = pd.DataFrame([{"season": 2018, "round": 1, "driver_id": "vettel", "last_lap_number": 58}])
    out = rs.reconstruct_stints(pit_stops, last_lap)
    assert len(out) == 1
    assert out.iloc[0]["start_lap"] == 1
    assert out.iloc[0]["end_lap"] == 58
    assert out.iloc[0]["ends_in_pit_stop"] == False  # noqa: E712


def test_retirement_before_any_stop():
    pit_stops = pd.DataFrame(columns=["season", "round", "driver_id", "stop", "lap", "duration_s"])
    last_lap = pd.DataFrame([{"season": 2018, "round": 1, "driver_id": "bottas", "last_lap_number": 3}])
    out = rs.reconstruct_stints(pit_stops, last_lap)
    assert len(out) == 1
    assert out.iloc[0]["end_lap"] == 3
    assert out.iloc[0]["stint_length"] == 3


def test_duplicate_pit_lap_rows_deduped():
    """Same in-lap logged twice (e.g. a data glitch) should not create a
    zero-length stint."""
    pit_stops = pd.DataFrame([
        {"season": 2018, "round": 1, "driver_id": "raikkonen", "stop": 1, "lap": 15, "duration_s": 22.0},
        {"season": 2018, "round": 1, "driver_id": "raikkonen", "stop": 1, "lap": 15, "duration_s": 22.0},
    ])
    last_lap = pd.DataFrame([{"season": 2018, "round": 1, "driver_id": "raikkonen", "last_lap_number": 50}])
    out = rs.reconstruct_stints(pit_stops, last_lap)
    assert len(out) == 2
    assert out["start_lap"].tolist() == [1, 16]


def test_pit_lap_at_or_after_last_lap_is_clipped_not_dropped():
    """A stop recorded on/after the driver's final lap (e.g. towed in after
    the flag) must not create a negative-length final stint."""
    pit_stops = pd.DataFrame([
        {"season": 2018, "round": 1, "driver_id": "perez", "stop": 1, "lap": 58, "duration_s": 22.0},
    ])
    last_lap = pd.DataFrame([{"season": 2018, "round": 1, "driver_id": "perez", "last_lap_number": 58}])
    out = rs.reconstruct_stints(pit_stops, last_lap)
    assert len(out) == 1
    assert out.iloc[0]["end_lap"] == 58
    assert out.iloc[0]["clipped_pit_lap"] == True  # noqa: E712
    assert (out["end_lap"] >= out["start_lap"]).all()


def test_multiple_driver_races_independent():
    pit_stops = pd.DataFrame([
        {"season": 2018, "round": 1, "driver_id": "hamilton", "stop": 1, "lap": 20, "duration_s": 22.0},
        {"season": 2018, "round": 2, "driver_id": "hamilton", "stop": 1, "lap": 10, "duration_s": 22.0},
    ])
    last_lap = pd.DataFrame([
        {"season": 2018, "round": 1, "driver_id": "hamilton", "last_lap_number": 58},
        {"season": 2018, "round": 2, "driver_id": "hamilton", "last_lap_number": 44},
    ])
    out = rs.reconstruct_stints(pit_stops, last_lap)
    assert len(out) == 4
    r1 = out[out["round"] == 1]
    r2 = out[out["round"] == 2]
    assert r1["end_lap"].tolist() == [20, 58]
    assert r2["end_lap"].tolist() == [10, 44]


def test_last_lap_from_jolpica_laps():
    laps = pd.DataFrame([
        {"season": 2011, "round": 1, "driver_id": "vettel", "lap_number": 1},
        {"season": 2011, "round": 1, "driver_id": "vettel", "lap_number": 2},
        {"season": 2011, "round": 1, "driver_id": "vettel", "lap_number": 58},
        {"season": 2011, "round": 1, "driver_id": "webber", "lap_number": 1},
        {"season": 2011, "round": 1, "driver_id": "webber", "lap_number": 30},  # retired lap 30
    ])
    out = rs.last_lap_from_jolpica_laps(laps)
    assert set(out.columns) == {"season", "round", "driver_id", "last_lap_number"}
    assert out.set_index("driver_id")["last_lap_number"].to_dict() == {"vettel": 58, "webber": 30}
