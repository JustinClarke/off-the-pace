import pytest
import pandas as pd
import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from api_client import F1ApiClient
from data_quality import DataQualityEngine
import ingest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_laps_df():
    return pd.DataFrame({
        "DriverNumber": [1, 2, 3] * 20,
        "LapNumber":    list(range(1, 61)),
        "LapTime":      [90.0 + i * 0.1 for i in range(60)],
        "Compound":     ["SOFT", "MEDIUM", "HARD"] * 20,
        "TyreLife":     list(range(1, 61)),
        "race_id":      ["2024_1"] * 60,
    })


@pytest.fixture
def minimal_laps_df():
    """Two rows   below min_rows threshold."""
    return pd.DataFrame({
        "DriverNumber": [1, 2],
        "LapNumber":    [1, 2],
        "LapTime":      [90.0, 91.0],
        "Compound":     ["SOFT", "MEDIUM"],
        "TyreLife":     [1, 2],
        "race_id":      ["2021_01", "2021_01"],
    })


# ---------------------------------------------------------------------------
# DataQualityEngine   existing tests kept + extended
# ---------------------------------------------------------------------------

def test_validate_bronze_schema(mock_laps_df):
    assert DataQualityEngine.validate_bronze_schema(mock_laps_df) is True

    invalid_df = mock_laps_df.drop(columns=["LapTime"])
    with pytest.raises(ValueError, match="Missing required columns"):
        DataQualityEngine.validate_bronze_schema(invalid_df)


def test_check_null_rates(mock_laps_df):
    mock_laps_df.loc[0, "LapTime"] = None
    null_rates = DataQualityEngine.check_null_rates(mock_laps_df, threshold=0.1)
    # 1 null out of 60 rows
    assert abs(null_rates["LapTime"]-1 / 60) < 1e-9


def test_assert_row_count(mock_laps_df, minimal_laps_df):
    assert DataQualityEngine.assert_row_count(mock_laps_df, min_rows=1) is True
    with pytest.raises(ValueError, match="Insufficient rows"):
        DataQualityEngine.assert_row_count(minimal_laps_df, min_rows=10)


def test_generate_quality_report(mock_laps_df):
    report = DataQualityEngine.generate_quality_report(mock_laps_df)
    assert report["row_count"] == 60
    assert "race_id" in report["columns"]
    assert report["valid_schema"] is True


# ---------------------------------------------------------------------------
# F1ApiClient   OpenF1 retry (existing test kept)
# ---------------------------------------------------------------------------

@patch("api_client.requests.get")
def test_get_live_lap(mock_get):
    client = F1ApiClient()
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [{"lap_number": 1, "driver_number": 1}]
    lap = client.get_live_lap(1, 1)
    assert lap["lap_number"] == 1


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def test_cli_single_season_shorthand():
    parser = ingest._build_parser()
    args = parser.parse_args(["-s", "2024", "--session", "R"])
    assert args.season == 2024
    assert args.sessions == "R"
    assert not args.force
    assert not args.skip_telemetry


def test_cli_range():
    parser = ingest._build_parser()
    args = parser.parse_args(["--start-season", "2018", "--end-season", "2024", "--session", "both"])
    assert args.start_season == 2018
    assert args.end_season == 2024


def test_cli_force_and_skip_telemetry():
    parser = ingest._build_parser()
    args = parser.parse_args(["-s", "2024", "--force", "--skip-telemetry"])
    assert args.force is True
    assert args.skip_telemetry is True


def test_cli_mutually_exclusive_season_args():
    """--season and --start-season cannot both be specified."""
    parser = ingest._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["-s", "2024", "--start-season", "2023"])


def test_cli_season_required():
    parser = ingest._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--sessions", "R"])


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def test_retry_succeeds_first_attempt():
    calls = []
    def fn():
        calls.append(1)
        return "result"
    assert ingest._with_retry(fn, max_attempts=4) == "result"
    assert len(calls) == 1


def test_retry_succeeds_on_third_attempt():
    attempts = []
    def fn():
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("transient")
        return "ok"

    with patch("ingest.time.sleep"):  # suppress real delays in tests
        result = ingest._with_retry(fn, max_attempts=4, base_delay=0.01)
    assert result == "ok"
    assert len(attempts) == 3


def test_retry_exhausted_raises():
    def fn():
        raise ValueError("permanent failure")

    with patch("ingest.time.sleep"):
        with pytest.raises(ValueError, match="permanent failure"):
            ingest._with_retry(fn, max_attempts=3, base_delay=0.01)


# ---------------------------------------------------------------------------
# Checkpointing (idempotency)
# ---------------------------------------------------------------------------

def test_ingest_race_skips_existing(tmp_path, mock_laps_df, monkeypatch):
    """If the target Parquet already exists, ingest_race returns 'skip' without hitting any API."""
    monkeypatch.setattr(ingest, "LAPS_DIR", tmp_path / "laps")
    target = ingest._laps_path_race(2024, "bahrain_grand_prix")
    target.parent.mkdir(parents=True)
    mock_laps_df.to_parquet(target, index=False)

    with patch("ingest._load_race_session") as mock_load:
        status, mrow = ingest.ingest_race(2024, 1, "bahrain_grand_prix", force=False, skip_telemetry=True)

    assert status == "skip"
    assert mrow["status"] == "skip"
    assert mrow["session_type"] == "R"
    mock_load.assert_not_called()


def test_ingest_race_force_overwrites_existing(tmp_path, mock_laps_df, monkeypatch):
    """--force bypasses the checkpoint and re-ingests even if the file exists."""
    monkeypatch.setattr(ingest, "LAPS_DIR", tmp_path / "laps")
    monkeypatch.setattr(ingest, "WEATHER_DIR", tmp_path / "weather")
    monkeypatch.setattr(ingest, "RC_DIR", tmp_path / "rc")
    monkeypatch.setattr(ingest, "TELEMETRY_DIR", tmp_path / "telemetry")

    target = ingest._laps_path_race(2024, "bahrain_grand_prix")
    target.parent.mkdir(parents=True)
    mock_laps_df.to_parquet(target, index=False)

    mock_session = MagicMock()
    mock_session.laps = mock_laps_df
    mock_session.weather_data = None
    mock_session.race_control_messages = None

    with patch("ingest._with_retry", return_value=mock_session):
        status, mrow = ingest.ingest_race(2024, 1, "bahrain_grand_prix", force=True, skip_telemetry=True)

    assert status == "ok"
    assert mrow["status"] == "ok"
    assert mrow["row_count"] == 60
    assert mrow["dq_passed"] is True
    assert mrow["schema_fingerprint"] != ""


def test_ingest_qualifying_skips_existing(tmp_path, mock_laps_df, monkeypatch):
    monkeypatch.setattr(ingest, "LAPS_DIR", tmp_path / "laps")
    target = ingest._laps_path_quali(2024, "bahrain_grand_prix")
    target.parent.mkdir(parents=True)
    mock_laps_df.to_parquet(target, index=False)

    with patch("ingest._load_qualifying_session") as mock_load:
        status, mrow = ingest.ingest_qualifying(2024, 1, "bahrain_grand_prix", force=False)

    assert status == "skip"
    assert mrow["status"] == "skip"
    mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# Partition path helpers
# ---------------------------------------------------------------------------

def test_laps_path_race_structure():
    p = ingest._laps_path_race(2024, "bahrain_grand_prix")
    assert "season=2024" in str(p)
    assert "race=bahrain_grand_prix" in str(p)
    assert p.name == "2024_bahrain_grand_prix_laps.parquet"
    assert "session=Q" not in str(p)


def test_laps_path_quali_structure():
    p = ingest._laps_path_quali(2024, "bahrain_grand_prix")
    assert "season=2024" in str(p)
    assert "race=bahrain_grand_prix" in str(p)
    assert "session=Q" in str(p)
    assert p.name == "2024_bahrain_grand_prix_quali_laps.parquet"


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("event_name,expected", [
    ("Bahrain Grand Prix", "bahrain_grand_prix"),
    ("Abu Dhabi Grand Prix", "abu_dhabi_grand_prix"),
    ("Monaco Grand Prix", "monaco_grand_prix"),
    ("São Paulo Grand Prix", "são_paulo_grand_prix"),
])
def test_slug(event_name, expected):
    assert ingest._slug(event_name) == expected


# ---------------------------------------------------------------------------
# DataQualityEngine   duplicate lap key detection
# ---------------------------------------------------------------------------

def test_check_lap_key_duplicates_clean(mock_laps_df):
    """Clean data has zero duplicate keys."""
    assert DataQualityEngine.check_lap_key_duplicates(mock_laps_df) == 0


def test_check_lap_key_duplicates_detects_corruption():
    """Exact duplicate rows are flagged."""
    df = pd.DataFrame({
        "race_id":      ["2024_1", "2024_1", "2024_1"],
        "DriverNumber": [1, 1, 2],
        "LapNumber":    [5, 5, 3],   # driver 1 lap 5 is duplicated
        "LapTime":      [90.0, 90.1, 88.0],
        "Compound":     ["SOFT", "SOFT", "MEDIUM"],
        "TyreLife":     [5, 5, 3],
    })
    assert DataQualityEngine.check_lap_key_duplicates(df) == 2  # both rows of the duplicate pair


def test_check_lap_key_duplicates_missing_columns():
    """If key columns are absent the check warns and returns 0 rather than crashing."""
    df = pd.DataFrame({"LapTime": [90.0, 91.0]})
    result = DataQualityEngine.check_lap_key_duplicates(df)
    assert result == 0


def test_generate_quality_report_includes_duplicate_key_count(mock_laps_df):
    report = DataQualityEngine.generate_quality_report(mock_laps_df)
    assert "duplicate_lap_keys" in report
    assert report["duplicate_lap_keys"] == 0


# ---------------------------------------------------------------------------
# Run manifest
# ---------------------------------------------------------------------------

def test_write_manifest_creates_parquet(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "MANIFESTS_DIR", tmp_path / "manifests")
    rows = [
        ingest._make_manifest_row("run1", 2024, 1, "bahrain", "R", "ok", row_count=120, dq_passed=True),
        ingest._make_manifest_row("run1", 2024, 1, "bahrain", "Q", "skip"),
    ]
    ingest._write_manifest(rows, "run1")

    written = pd.read_parquet(tmp_path / "manifests" / "run_run1.parquet")
    assert len(written) == 2
    assert set(written["status"]) == {"ok", "skip"}
    assert written.loc[written["session_type"] == "R", "row_count"].iloc[0] == 120
    assert written.loc[written["session_type"] == "R", "dq_passed"].iloc[0] == True


def test_write_manifest_empty_noop(tmp_path, monkeypatch):
    """Empty row list should not create any file."""
    monkeypatch.setattr(ingest, "MANIFESTS_DIR", tmp_path / "manifests")
    ingest._write_manifest([], "run_empty")
    assert not (tmp_path / "manifests" / "run_run_empty.parquet").exists()


def test_schema_fingerprint_differs_on_column_change(mock_laps_df):
    fp1 = ingest._schema_fingerprint(mock_laps_df)
    fp2 = ingest._schema_fingerprint(mock_laps_df.drop(columns=["Compound"]))
    assert fp1 != fp2
    assert len(fp1) == 12


# ---------------------------------------------------------------------------
# ingest_season orchestration
# ---------------------------------------------------------------------------

def _make_schedule_df(rounds: list[tuple[int, str]]) -> pd.DataFrame:
    """Build a minimal schedule DataFrame for a list of (round_num, event_name) pairs."""
    return pd.DataFrame({
        "RoundNumber": [r for r, _ in rounds],
        "EventName":   [n for _, n in rounds],
    })


def test_ingest_season_skips_round_zero(tmp_path, monkeypatch):
    """Round 0 (pre-season test) must never trigger an ingest call."""
    monkeypatch.setattr(ingest, "LAPS_DIR", tmp_path / "laps")
    monkeypatch.setattr(ingest, "MANIFESTS_DIR", tmp_path / "manifests")

    schedule = _make_schedule_df([(0, "Pre-Season Test"), (1, "Bahrain Grand Prix")])

    with patch("ingest._with_retry", return_value=schedule), \
         patch("ingest.ingest_race", return_value=("skip", {})) as mock_race, \
         patch("ingest.ingest_qualifying", return_value=("skip", {})) as mock_quali:
        ingest.ingest_season(2024, sessions="both", force=False, skip_telemetry=True)

    # Only round 1 should be attempted   round 0 skipped
    assert mock_race.call_count == 1
    assert mock_quali.call_count == 1


def test_ingest_season_counts_correctly(tmp_path, monkeypatch):
    """Counts dict correctly tallies ok/skip/error across rounds."""
    monkeypatch.setattr(ingest, "LAPS_DIR", tmp_path / "laps")
    monkeypatch.setattr(ingest, "MANIFESTS_DIR", tmp_path / "manifests")

    schedule = _make_schedule_df([(1, "Bahrain Grand Prix"), (2, "Saudi Arabian Grand Prix")])

    side_effects_race = [
        ("ok",    {"status": "ok"}),
        ("error", {"status": "error"}),
    ]
    side_effects_quali = [
        ("skip",  {"status": "skip"}),
        ("ok",    {"status": "ok"}),
    ]

    with patch("ingest._with_retry", return_value=schedule), \
         patch("ingest.ingest_race", side_effect=side_effects_race), \
         patch("ingest.ingest_qualifying", side_effect=side_effects_quali):
        counts, rows = ingest.ingest_season(2024, sessions="both", force=False, skip_telemetry=True)

    assert counts["R_ok"] == 1
    assert counts["R_error"] == 1
    assert counts["Q_skip"] == 1
    assert counts["Q_ok"] == 1
    assert len(rows) == 4  # 2 races + 2 quali


def test_ingest_season_schedule_failure_returns_empty(tmp_path, monkeypatch):
    """If schedule fetch fails, season returns empty counts and no manifest rows."""
    monkeypatch.setattr(ingest, "LAPS_DIR", tmp_path / "laps")

    with patch("ingest._with_retry", side_effect=RuntimeError("network error")):
        counts, rows = ingest.ingest_season(2024, sessions="R", force=False, skip_telemetry=True)

    assert counts["R_ok"] == 0
    assert rows == []


# ---------------------------------------------------------------------------
# Race control KI-001: elapsed seconds handles both timedelta and datetime columns
# ---------------------------------------------------------------------------

def test_race_control_timedelta_column(tmp_path, monkeypatch):
    """session_time_s is populated correctly when Time is timedelta64."""
    monkeypatch.setattr(ingest, "RC_DIR", tmp_path)

    rc_df = pd.DataFrame({
        "Time":     pd.to_timedelta(["0:01:00", "0:02:00"]),
        "Category": ["Flag", "SafetyCar"],
        "Message":  ["GREEN FLAG", "SAFETY CAR DEPLOYED"],
    })
    mock_session = MagicMock()
    mock_session.race_control_messages = rc_df

    ingest._write_race_control(mock_session, 2024, 1, "test_race")

    written = pd.read_parquet(tmp_path / "season=2024" / "race=test_race" / "race_control.parquet")
    assert list(written["session_time_s"]) == [60.0, 120.0]
    assert written["session_time_s"].notna().all()
