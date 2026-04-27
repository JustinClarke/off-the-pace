"""Offline tests for the Jolpica reference-data client (no network)."""

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

import jolpica_client as jc


# ---------------------------------------------------------------------------
# Ergast-shaped fixtures (trimmed to the fields we flatten)
# ---------------------------------------------------------------------------

@pytest.fixture
def driver_standings_payload():
    return {"MRData": {"total": "2", "StandingsTable": {"StandingsLists": [{
        "season": "2024", "round": "24",
        "DriverStandings": [
            {"position": "1", "positionText": "1", "points": "437", "wins": "9",
             "Driver": {"driverId": "max_verstappen", "permanentNumber": "1",
                        "code": "VER", "givenName": "Max", "familyName": "Verstappen"},
             "Constructors": [{"constructorId": "red_bull", "name": "Red Bull"}]},
            {"position": "2", "positionText": "2", "points": "374", "wins": "2",
             "Driver": {"driverId": "norris", "permanentNumber": "4",
                        "code": "NOR", "givenName": "Lando", "familyName": "Norris"},
             "Constructors": [{"constructorId": "mclaren", "name": "McLaren"}]},
        ],
    }]}}}


@pytest.fixture
def constructor_standings_payload():
    return {"MRData": {"total": "1", "StandingsTable": {"StandingsLists": [{
        "season": "2024", "round": "24",
        "ConstructorStandings": [
            {"position": "1", "positionText": "1", "points": "666", "wins": "6",
             "Constructor": {"constructorId": "mclaren", "name": "McLaren",
                             "nationality": "British"}},
        ],
    }]}}}


@pytest.fixture
def pit_stops_payload():
    return {"MRData": {"total": "2", "RaceTable": {"Races": [{
        "raceName": "Bahrain Grand Prix",
        "PitStops": [
            {"driverId": "max_verstappen", "stop": "1", "lap": "14", "time": "16:18:09", "duration": "22.4"},
            {"driverId": "norris", "stop": "1", "lap": "16", "time": "16:21:55", "duration": "23.1"},
        ],
    }]}}}


def _mock_response(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Flatteners
# ---------------------------------------------------------------------------

def test_flatten_driver_standings(driver_standings_payload):
    df = jc._flatten_standings(driver_standings_payload["MRData"], kind="driver", season=2024)
    assert len(df) == 2
    assert df["round"].iloc[0] == 24
    assert df["driver_id"].tolist() == ["max_verstappen", "norris"]
    assert df["constructor_id"].iloc[0] == "red_bull"
    assert df["points"].iloc[0] == 437.0
    assert df["position"].iloc[0] == 1  # coerced to int


def test_flatten_constructor_standings(constructor_standings_payload):
    df = jc._flatten_standings(constructor_standings_payload["MRData"], kind="constructor", season=2024)
    assert len(df) == 1
    assert df["constructor_id"].iloc[0] == "mclaren"
    assert df["nationality"].iloc[0] == "British"
    assert df["points"].iloc[0] == 666.0


def test_flatten_pit_stops(pit_stops_payload):
    df = jc._flatten_pit_stops(pit_stops_payload["MRData"], season=2024, round_num=1)
    assert len(df) == 2
    assert df["duration_s"].iloc[0] == 22.4
    assert df["lap"].iloc[1] == 16
    assert df["race_name"].iloc[0] == "Bahrain Grand Prix"


def test_flatten_empty_standings():
    df = jc._flatten_standings({"StandingsTable": {"StandingsLists": []}}, kind="driver", season=2024)
    assert df.empty


def test_flatten_empty_pit_stops():
    df = jc._flatten_pit_stops({"RaceTable": {"Races": []}}, season=2024, round_num=1)
    assert df.empty
    assert "duration_s" in df.columns  # schema preserved


def test_coercers_handle_garbage():
    assert jc._to_int("") is None
    assert jc._to_int(None) is None
    assert jc._to_int("7") == 7
    assert jc._to_float("nan-ish") is None
    assert jc._to_float("1.5") == 1.5


# ---------------------------------------------------------------------------
# Client (mocked HTTP) — accessors, throttle, retry
# ---------------------------------------------------------------------------

def test_get_driver_standings_calls_correct_path(driver_standings_payload):
    client = jc.JolpicaClient(min_interval_s=0.0)
    with patch.object(jc.requests, "get", return_value=_mock_response(driver_standings_payload)) as mget:
        df = client.get_driver_standings(2024)
    assert len(df) == 2
    url = mget.call_args.args[0]
    assert url.endswith("/2024/driverStandings.json")


def test_get_pit_stops_round_path(pit_stops_payload):
    client = jc.JolpicaClient(min_interval_s=0.0)
    with patch.object(jc.requests, "get", return_value=_mock_response(pit_stops_payload)) as mget:
        df = client.get_pit_stops(2024, 1)
    assert len(df) == 2
    assert mget.call_args.args[0].endswith("/2024/1/pitstops.json")


def test_get_retries_on_failure(driver_standings_payload):
    client = jc.JolpicaClient(min_interval_s=0.0)
    good = _mock_response(driver_standings_payload)
    with patch.object(jc.requests, "get", side_effect=[ConnectionError("boom"), good]), \
         patch.object(jc.time, "sleep"):  # don't actually back off
        mrdata = client._get("2024/driverStandings")
    assert mrdata["total"] == "2"


def test_get_raises_after_max_attempts():
    client = jc.JolpicaClient(min_interval_s=0.0)
    with patch.object(jc.requests, "get", side_effect=ConnectionError("down")), \
         patch.object(jc.time, "sleep"):
        with pytest.raises(ConnectionError):
            client._get("2024/driverStandings", max_attempts=3)


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def test_write_driver_standings(tmp_path, monkeypatch, driver_standings_payload):
    monkeypatch.setattr(jc, "JOLPICA_DIR", tmp_path / "jolpica")
    df = jc._flatten_standings(driver_standings_payload["MRData"], kind="driver", season=2024)
    path = jc.write_driver_standings(df, 2024)
    written = pd.read_parquet(path)
    assert len(written) == 2
    assert path.parent.name == "season=2024"


def test_write_pit_stops_partition(tmp_path, monkeypatch, pit_stops_payload):
    monkeypatch.setattr(jc, "JOLPICA_DIR", tmp_path / "jolpica")
    df = jc._flatten_pit_stops(pit_stops_payload["MRData"], season=2024, round_num=5)
    path = jc.write_pit_stops(df, 2024, 5)
    assert path.parent.name == "round=5"
    assert pd.read_parquet(path)["stop"].iloc[0] == 1
