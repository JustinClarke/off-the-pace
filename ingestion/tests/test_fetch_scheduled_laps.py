"""Offline tests for the scheduled-distance pull (WI-05: F6, F32, F52). No network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fetch_scheduled_laps as fsl  # noqa: E402


def test_scheduled_is_the_first_total_not_the_last():
    # 2024 São Paulo: 71 laps announced, cut to 69 after the aborted start. The fuel
    # load was planned for 71, so scheduled_laps keeps the pre-race value.
    out = fsl.summarise_lap_count([71, None, None, 69, None], [None, 1, 2, 3, 69])
    assert out == {"scheduled_laps": 71, "total_laps_final": 69, "max_current_lap": 69}


def test_red_flagged_race_keeps_its_scheduled_distance():
    # 2021 Belgium: 44 announced, 39 after the delay, 4 laps behind the safety car.
    out = fsl.summarise_lap_count([44, None, 39], [1, 2, 3, 4])
    assert out["scheduled_laps"] == 44
    assert out["max_current_lap"] == 4


def test_no_total_laps_is_unknown_not_guessed():
    out = fsl.summarise_lap_count([None, None], [1, 2])
    assert out["scheduled_laps"] is None and out["total_laps_final"] is None


def test_merge_replaces_one_season_and_keeps_order():
    existing = [
        {"race_id": "2025_2", "race_year": "2025", "round_number": "2", "scheduled_laps": "56"},
        {"race_id": "2025_1", "race_year": "2025", "round_number": "1", "scheduled_laps": "58"},
        {"race_id": "2024_24", "race_year": "2024", "round_number": "24", "scheduled_laps": "58"},
    ]
    fresh = [{"race_id": "2025_2", "race_year": 2025, "round_number": 2, "scheduled_laps": 57}]
    merged = fsl.merge_rows(existing, fresh)
    assert [r["race_id"] for r in merged] == ["2024_24", "2025_1", "2025_2"]
    assert merged[-1]["scheduled_laps"] == 57
