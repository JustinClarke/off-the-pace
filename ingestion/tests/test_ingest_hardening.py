"""Offline tests for ingest.py's season hardening (no network, no data/bronze):

  * rounds that have not run yet are skipped without loading or a manifest row;
  * a thin (incomplete) load is retried once, then not written unless accepted;
  * per-race telemetry coverage and circuit-info status reach the manifest;
  * slug -> venue changes are detected;
  * the end-of-run summary and exit code, the dry run and the log monitor.

conftest.py points every ingest output at a tmp bronze root and disables FastF1's
network entry points for all of these.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import bronze_checks
import ingest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import monitor_ingest  # noqa: E402

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------

def _schedule(rows):
    """rows: (round, name, location, quali_start_utc, race_start_utc) -> FastF1-shaped schedule."""
    return pd.DataFrame({
        "RoundNumber": [r[0] for r in rows],
        "EventName": [r[1] for r in rows],
        "Location": [r[2] for r in rows],
        "Session4": ["Qualifying"] * len(rows),
        "Session4DateUtc": [pd.Timestamp(r[3]) for r in rows],
        "Session5": ["Race"] * len(rows),
        "Session5DateUtc": [pd.Timestamp(r[4]) for r in rows],
    })


SCHED_2026 = _schedule([
    (0, "Pre-Season Testing", "Bahrain", "2026-02-20 07:00", "2026-02-21 07:00"),
    (14, "Spanish Grand Prix", "Madrid", "2026-09-12 14:00", "2026-09-13 13:00"),
    (15, "Azerbaijan Grand Prix", "Baku", "2026-09-25 12:00", "2026-09-26 11:00"),
    (16, "Bahrain Grand Prix", "Kuala Lumpur", "2026-10-03 08:00", "2026-10-04 07:00"),
])


def _laps(n_drivers=4, n_laps=20, **overrides) -> pd.DataFrame:
    rows = []
    for d in range(1, n_drivers + 1):
        for lap in range(1, n_laps + 1):
            rows.append({"Driver": f"D{d}", "DriverNumber": str(d), "LapNumber": float(lap),
                         "LapTime": pd.Timedelta(seconds=90 + lap * 0.1), "Compound": "SOFT",
                         "TyreLife": float(lap), "Stint": 1.0})
    df = pd.DataFrame(rows)
    for col, value in overrides.items():
        df[col] = value
    return df


def _session(laps=None, *, points=True, q1=True, weather=True, race_control=True, stype="R"):
    laps = _laps() if laps is None else laps
    drivers = sorted(laps["DriverNumber"].unique())
    s = MagicMock()
    s.laps = laps
    s.results = pd.DataFrame({
        "DriverNumber": drivers,
        "Abbreviation": [f"D{d}" for d in drivers],
        "Points": [1.0] * len(drivers) if points else [float("nan")] * len(drivers),
        "GridPosition": [1.0] * len(drivers) if points else [float("nan")] * len(drivers),
        "Q1": (pd.to_timedelta([80.0] * len(drivers), unit="s") if q1
               else pd.to_timedelta([None] * len(drivers))),
    })
    s.weather_data = (pd.DataFrame({"Time": pd.to_timedelta([0, 60], unit="s"), "AirTemp": [25.0, 26.0]})
                      if weather else pd.DataFrame())
    s.race_control_messages = (pd.DataFrame({"Time": pd.to_timedelta([0], unit="s"),
                                             "Category": ["Flag"], "Message": ["GREEN"]})
                               if race_control else pd.DataFrame())
    s.track_status = pd.DataFrame()
    s.session_status = pd.DataFrame()
    s.get_circuit_info.return_value = None
    return s


# ---------------------------------------------------------------------------
# 1. Rounds that have not run yet
# ---------------------------------------------------------------------------

def test_session_start_and_readiness():
    row = SCHED_2026.iloc[2]  # Baku
    start = bronze_checks.session_start_utc(row, "R")
    assert start == pd.Timestamp("2026-09-26 11:00", tz="UTC")
    assert bronze_checks.session_is_ready(start, NOW) is False
    assert bronze_checks.session_is_ready(start, NOW + timedelta(days=1, hours=5)) is True
    # scheduled start + margin, not start alone
    assert bronze_checks.session_is_ready(start, datetime(2026, 9, 26, 13, tzinfo=timezone.utc)) is False
    assert bronze_checks.session_start_utc(pd.Series({"RoundNumber": 1, "EventName": "X"}), "R") is None
    assert bronze_checks.session_is_ready(None, NOW) is None


def test_plan_marks_unrun_sessions_not_run():
    plan = ingest.plan_season(SCHED_2026, 2026, "both", now_utc=NOW)
    actions = {(p["round"], p["session_type"]): p["action"] for p in plan}
    assert actions == {
        (14, "R"): "attempt", (14, "Q"): "attempt",
        (15, "R"): "not_run", (15, "Q"): "not_run",   # Q started at 12:00 today, +6 h not passed
        (16, "R"): "not_run", (16, "Q"): "not_run",
    }
    # After Baku qualifying is loadable but before its race: with --session both the
    # round is the unit, so qualifying waits for the race (no quali-only round in bronze) ...
    evening = datetime(2026, 9, 25, 18, 30, tzinfo=timezone.utc)
    later = ingest.plan_season(SCHED_2026, 2026, "both", now_utc=evening)
    assert {(p["round"], p["session_type"]) for p in later if p["action"] == "attempt"} == {(14, "R"), (14, "Q")}
    held = [p for p in later if (p["round"], p["session_type"]) == (15, "Q")][0]
    assert held["reason"].startswith("round not complete") and "race is loadable" in ingest._not_run_text(held)
    # ... while --session Q pulls it on its own.
    q_only = ingest.plan_season(SCHED_2026, 2026, "Q", now_utc=evening)
    assert {p["round"] for p in q_only if p["action"] == "attempt"} == {14, 15}


def test_plan_margin_and_include_unfinished():
    two_hours_after_start = datetime(2026, 9, 26, 13, 0, tzinfo=timezone.utc)
    plan = ingest.plan_season(SCHED_2026, 2026, "R", only_rounds={15}, now_utc=two_hours_after_start)
    assert [p["action"] for p in plan] == ["not_run"]
    plan = ingest.plan_season(SCHED_2026, 2026, "R", only_rounds={15}, now_utc=two_hours_after_start,
                              ready_after=timedelta(hours=1))
    assert [p["action"] for p in plan] == ["attempt"]
    plan = ingest.plan_season(SCHED_2026, 2026, "R", now_utc=NOW, include_unfinished=True)
    assert {p["action"] for p in plan} == {"attempt"}


def test_plan_without_dates_attempts_everything():
    """Backward compatible: a schedule with no session dates is attempted, as before."""
    sched = pd.DataFrame({"RoundNumber": [1, 2], "EventName": ["A Grand Prix", "B Grand Prix"]})
    plan = ingest.plan_season(sched, 2024, "both", now_utc=NOW)
    assert {p["action"] for p in plan} == {"attempt"} and len(plan) == 4


def test_ingest_season_skips_unrun_rounds_without_loading_or_manifest_rows(caplog):
    with patch("ingest._with_retry", return_value=SCHED_2026), \
         patch("ingest.ingest_race", return_value=("ok", {"status": "ok"})) as race, \
         patch("ingest.ingest_qualifying", return_value=("ok", {"status": "ok"})) as quali, \
         patch("ingest._write_event_schedule"):
        caplog.set_level("INFO")
        counts, rows = ingest.ingest_season(2026, "both", force=False, skip_telemetry=True, now_utc=NOW)

    assert [c.args[1] for c in race.call_args_list] == [14]
    assert [c.args[1] for c in quali.call_args_list] == [14]
    assert len(rows) == 2                        # no rows for rounds 15-16
    assert counts["R_not_run"] == 2 and counts["Q_not_run"] == 2
    assert counts["R_error"] == 0 and counts["Q_error"] == 0
    assert "[NOT RUN] R  2026 Rd15 azerbaijan_grand_prix" in caplog.text
    assert "[1/1] 2026 Rd14 spanish_grand_prix" in caplog.text


def test_ingest_season_schedule_failure_is_counted():
    with patch("ingest._with_retry", side_effect=RuntimeError("network")):
        counts, rows = ingest.ingest_season(2026, "both", False, True)
    assert counts["schedule_error"] == 1 and rows == []


def test_ingest_season_only_rounds():
    with patch("ingest._with_retry", return_value=SCHED_2026), \
         patch("ingest.ingest_race", return_value=("ok", {})) as race, \
         patch("ingest.ingest_qualifying", return_value=("ok", {})), \
         patch("ingest._write_event_schedule"):
        ingest.ingest_season(2026, "R", force=False, skip_telemetry=True,
                             only_rounds={14, 16}, now_utc=NOW, include_unfinished=True)
    assert [c.args[1] for c in race.call_args_list] == [14, 16]


@pytest.mark.parametrize("spec,expected", [
    ("1-3", {1, 2, 3}), ("3,5,7", {3, 5, 7}), ("1-3,9", {1, 2, 3, 9}), ("14", {14}),
])
def test_parse_rounds(spec, expected):
    assert ingest._parse_rounds(spec) == expected


@pytest.mark.parametrize("spec", ["", "a-b", "5-3", "0-2", "1,,x"])
def test_parse_rounds_rejects_bad_specs(spec):
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        ingest._parse_rounds(spec)


def test_cli_rounds_and_round_are_exclusive():
    parser = ingest._build_parser()
    assert parser.parse_args(["-s", "2026", "--rounds", "1-14"]).rounds == set(range(1, 15))
    with pytest.raises(SystemExit):
        parser.parse_args(["-s", "2026", "--rounds", "1-3", "--round", "2"])


# ---------------------------------------------------------------------------
# 2. Thin loads
# ---------------------------------------------------------------------------

def test_assess_complete_race_and_quali():
    s = _session()
    assert bronze_checks.assess_session("R", s.laps, s.results, s.weather_data, s.race_control_messages) == {}
    assert bronze_checks.assess_session("Q", s.laps, s.results, s.weather_data) == {}


def test_assess_flags_ergast_failure():
    """2026 Miami's first load: results came back with Points/GridPosition 0% non-null."""
    s = _session(points=False)
    problems = bronze_checks.assess_session("R", s.laps, s.results, s.weather_data, s.race_control_messages)
    assert set(problems) == {"results.Points", "results.GridPosition"}
    q = _session(q1=False)
    assert set(bronze_checks.assess_session("Q", q.laps, q.results, q.weather_data)) == {"results.Q1"}


def test_assess_flags_missing_tyre_columns_results_and_empty_frames():
    laps = _laps()
    laps.loc[laps.index[: len(laps) // 2], "Stint"] = None       # 50% null
    s = _session(laps, weather=False, race_control=False)
    s.results = s.results.iloc[:2]                                  # 2 results for 4 drivers
    problems = bronze_checks.assess_session("R", s.laps, s.results, s.weather_data, s.race_control_messages)
    assert set(problems) == {"laps.Stint", "results.rows", "weather.rows", "race_control.rows"}
    assert problems["results.rows"] == "results: 2 rows for 4 drivers who set laps"
    assert set(bronze_checks.assess_session("R", None, None, None, None)) == {
        "laps.rows", "results.rows", "weather.rows", "race_control.rows"}


def test_assess_short_neutralised_race_is_not_thin():
    """2021 Belgium: LapTime 33% non-null on a legitimately short race."""
    laps = _laps()
    laps.loc[laps.index[: int(len(laps) * 0.67)], "LapTime"] = pd.NaT
    s = _session(laps)
    assert bronze_checks.assess_session("R", s.laps, s.results, s.weather_data, s.race_control_messages) == {}


def test_known_thin_split():
    problems = {"laps.Stint": "a", "laps.TyreLife": "b"}
    unexplained, note = bronze_checks.split_known_thin(2025, 6, "R", problems)
    assert unexplained == {} and "known source gap" in note
    unexplained, note = bronze_checks.split_known_thin(2025, 6, "R", {**problems, "results.Points": "c"})
    assert unexplained == {"results.Points": "c"} and note
    assert bronze_checks.split_known_thin(2025, 7, "R", problems) == (problems, None)


def test_thin_race_recovers_on_retry():
    thin, good = _session(points=False), _session()
    with patch("ingest._load_race_session", side_effect=[thin, good]) as load, \
         patch("ingest.time.sleep") as sleep:
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", force=False, skip_telemetry=True)
    assert status == "ok" and row["status"] == "ok" and row["thin_reasons"] == ""
    assert load.call_count == 2 and load.call_args_list[1].kwargs == {"fresh": True}
    sleep.assert_any_call(ingest.THIN_RETRY_DELAY_S)
    assert ingest._laps_path_race(2026, "miami_grand_prix").exists()
    written = pd.read_parquet(ingest.RESULTS_DIR / "season=2026" / "race=miami_grand_prix" / "results.parquet")
    assert written["Points"].notna().all()                # the retry's results, not the thin ones


def test_thin_race_twice_is_not_written_and_not_done():
    thin = _session(points=False)
    with patch("ingest._load_race_session", side_effect=[thin, thin]), patch("ingest.time.sleep"):
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", force=False, skip_telemetry=True)
    assert status == "thin" and row["status"] == "thin"
    assert "results.Points 0% non-null" in row["thin_reasons"]
    assert row["schema_fingerprint"] == ""
    assert not ingest._laps_path_race(2026, "miami_grand_prix").exists()
    assert not (ingest.RESULTS_DIR / "season=2026").exists()
    # Not done: the next run pulls it again instead of skipping it.
    with patch("ingest._load_race_session", side_effect=[_session()]), patch("ingest.time.sleep"):
        status, _ = ingest.ingest_race(2026, 4, "miami_grand_prix", force=False, skip_telemetry=True)
    assert status == "ok"


def test_thin_forced_reload_keeps_existing_files():
    good = _session()
    with patch("ingest._load_race_session", return_value=good), patch("ingest.time.sleep"):
        assert ingest.ingest_race(2026, 4, "miami_grand_prix", False, True)[0] == "ok"
    results_path = ingest.RESULTS_DIR / "season=2026" / "race=miami_grand_prix" / "results.parquet"
    before = pd.read_parquet(results_path)

    thin = _session(points=False)
    with patch("ingest._load_race_session", side_effect=[thin, thin]), patch("ingest.time.sleep"):
        status, _ = ingest.ingest_race(2026, 4, "miami_grand_prix", force=True, skip_telemetry=True)
    assert status == "thin"
    pd.testing.assert_frame_equal(pd.read_parquet(results_path), before)


def test_accept_thin_writes_and_records_reasons():
    thin = _session(points=False)
    with patch("ingest._load_race_session", side_effect=[thin, thin]), patch("ingest.time.sleep"):
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", False, True, accept_thin=True)
    assert status == "ok" and "results.Points" in row["thin_reasons"]
    assert ingest._laps_path_race(2026, "miami_grand_prix").exists()


def test_thin_qualifying_not_written():
    thin = _session(q1=False, stype="Q")
    with patch("ingest._load_qualifying_session", side_effect=[thin, thin]), patch("ingest.time.sleep"):
        status, row = ingest.ingest_qualifying(2026, 4, "miami_grand_prix", force=False)
    assert status == "thin" and "results.Q1" in row["thin_reasons"]
    assert not ingest._laps_path_quali(2026, "miami_grand_prix").exists()


def test_known_thin_session_is_written_with_note_and_no_retry():
    laps = _laps()
    laps.loc[laps.index[: len(laps) // 2], ["Stint", "TyreLife"]] = None
    with patch("ingest._load_race_session", return_value=_session(laps)) as load, \
         patch("ingest.time.sleep"):
        status, row = ingest.ingest_race(2025, 6, "miami_grand_prix", False, True)
    assert status == "ok" and load.call_count == 1
    assert row["thin_reasons"] == "" and "known source gap" in row["known_gap_note"]


def test_retry_failure_keeps_first_result_as_thin():
    thin = _session(points=False)
    with patch("ingest._load_race_session", side_effect=[thin, RuntimeError("503")]), \
         patch("ingest.time.sleep"):
        status, _ = ingest.ingest_race(2026, 4, "miami_grand_prix", False, True)
    assert status == "thin"


# ---------------------------------------------------------------------------
# 3. Telemetry coverage
# ---------------------------------------------------------------------------

class _Lap(dict):
    def __init__(self, driver, lap, tel):
        super().__init__(Driver=driver, LapNumber=lap)
        self._tel = tel

    def get_telemetry(self):
        if isinstance(self._tel, Exception):
            raise self._tel
        return self._tel


def _tel_session(n_ok, n_fail, car=3, pos=1):
    laps = []
    for i in range(n_ok):
        laps.append(_Lap("VER", float(i + 1), pd.DataFrame({"Speed": [300.0, 301.0], "Throttle": [99, 100],
                                                          "Brake": [False, False], "Distance": [0.0, 10.0]})))
    for i in range(n_fail):
        laps.append(_Lap("HAM", float(i + 1), KeyError("Date")))
    s = MagicMock()
    s.laps.iterrows.return_value = iter(enumerate(laps))
    s.car_data = {str(d): pd.DataFrame({"Speed": [1.0]}) for d in range(car)}
    s.pos_data = {str(d): pd.DataFrame({"X": [1.0]}) for d in range(pos)}
    return s


def test_write_telemetry_records_coverage_and_writes_same_rows():
    cov = ingest._write_telemetry(_tel_session(n_ok=3, n_fail=7), 2026, 6, "monaco_grand_prix")
    assert cov["telemetry_laps_attempted"] == 10 and cov["telemetry_laps_merged"] == 3
    assert cov["telemetry_coverage"] == 0.3
    assert cov["telemetry_car_drivers"] == 3 and cov["telemetry_pos_drivers"] == 1
    assert cov["telemetry_note"].startswith("KeyError on 7 laps")
    written = pd.read_parquet(ingest.TELEMETRY_DIR / "season=2026" / "race=monaco_grand_prix" / "telemetry.parquet")
    # Healthy laps are written exactly as before: renamed channels + the four key columns.
    assert list(written.columns) == ["index", "speed_kph", "throttle_pct", "brake", "distance_m",
                                     "driver_id", "lap_number", "race_id", "season"]
    assert len(written) == 6 and set(written["driver_id"]) == {"VER"}


def test_write_telemetry_nothing_merged_writes_nothing():
    cov = ingest._write_telemetry(_tel_session(n_ok=0, n_fail=5, pos=0), 2018, 1, "australian_grand_prix")
    assert cov["telemetry_laps_merged"] == 0 and cov["telemetry_coverage"] == 0.0
    assert not (ingest.TELEMETRY_DIR / "season=2018").exists()


def test_judge_telemetry_low_known_and_healthy(caplog):
    caplog.set_level("INFO")
    low = ingest._judge_telemetry({"telemetry_laps_attempted": 1452, "telemetry_laps_merged": 128,
                                   "telemetry_coverage": 0.0882, "telemetry_note": ""},
                                  2026, 6, "monaco_grand_prix")
    assert low["telemetry_note"].startswith("low coverage")
    assert "[LOW TELEMETRY] 2026 Rd6 monaco_grand_prix" in caplog.text

    known = ingest._judge_telemetry({"telemetry_laps_attempted": 940, "telemetry_laps_merged": 0,
                                     "telemetry_coverage": 0.0, "telemetry_note": ""},
                                    2018, 1, "australian_grand_prix")
    assert known["telemetry_note"].startswith("known gap") and "ADR-009" in known["known_gap_note"]

    healthy = {"telemetry_laps_attempted": 1000, "telemetry_laps_merged": 999,
               "telemetry_coverage": 0.999, "telemetry_note": ""}
    assert ingest._judge_telemetry(dict(healthy), 2026, 7, "barcelona_grand_prix") == healthy


def test_ingest_race_manifest_carries_coverage_and_circuit_status():
    cov = {"telemetry_laps_attempted": 1452, "telemetry_laps_merged": 128, "telemetry_coverage": 0.0882,
           "telemetry_car_drivers": 22, "telemetry_pos_drivers": 22, "telemetry_note": ""}
    with patch("ingest._load_race_session", return_value=_session()), \
         patch("ingest._write_telemetry", return_value=cov), patch("ingest.time.sleep"):
        status, row = ingest.ingest_race(2026, 6, "monaco_grand_prix", False, skip_telemetry=False)
    assert status == "ok"
    assert row["telemetry_laps_merged"] == 128 and row["telemetry_note"].startswith("low coverage")
    assert row["circuit_info_status"] == "none"


# ---------------------------------------------------------------------------
# 6. Circuit info + slug/venue traps
# ---------------------------------------------------------------------------

def test_circuit_info_status_values():
    ok = MagicMock()
    ok.get_circuit_info.return_value.corners = pd.DataFrame({"Number": [1, 2]})
    assert ingest._write_circuit_info(ok, 2026, 1, "x") == "ok: 2 corners"

    failing = MagicMock()
    failing.get_circuit_info.side_effect = AttributeError("'NoneType' object has no attribute 'add_marker_distance'")
    status = ingest._write_circuit_info(failing, 2026, 14, "spanish_grand_prix")
    assert status.startswith("failed: AttributeError")
    assert not (ingest.CIRCUIT_INFO_DIR / "season=2026" / "race=spanish_grand_prix").exists()


def _history():
    rows = [(s, "spanish_grand_prix", "Barcelona") for s in range(2018, 2026)]
    rows += [(s, "bahrain_grand_prix", "Sakhir") for s in range(2018, 2026)]
    rows += [(2019, "monaco_grand_prix", "Monaco"), (2024, "monaco_grand_prix", "Monte Carlo")]
    return pd.DataFrame(rows, columns=["season", "slug", "location"])


def test_venue_note_detects_moved_and_new_slugs():
    h = _history()
    moved = bronze_checks.venue_note("spanish_grand_prix", "Madrid", h)
    assert "at Madrid this season but was at Barcelona in 2018-2025" in moved
    assert "Kuala Lumpur" in bronze_checks.venue_note("bahrain_grand_prix", "Kuala Lumpur", h)
    new = bronze_checks.venue_note("barcelona_grand_prix", "Barcelona", h)
    assert "new slug 'barcelona_grand_prix'" in new and "spanish_grand_prix" in new
    assert bronze_checks.venue_note("monaco_grand_prix", "Monte Carlo", h) == ""
    assert bronze_checks.venue_note("spanish_grand_prix", "Barcelona", h) == ""
    assert bronze_checks.venue_note("las_vegas_grand_prix", "Las Vegas", h) == ""
    assert bronze_checks.venue_note("spanish_grand_prix", "Madrid", pd.DataFrame()) == ""


def test_load_venue_history_reads_earlier_snapshots_only(tmp_path):
    for season, loc in [(2024, "Barcelona"), (2025, "Barcelona"), (2026, "Madrid")]:
        d = tmp_path / f"season={season}"
        d.mkdir()
        pd.DataFrame({"RoundNumber": [0, 9], "EventName": ["Pre-Season Testing", "Spanish Grand Prix"],
                      "Location": ["Sakhir", loc]}).to_parquet(d / "schedule.parquet")
    h = bronze_checks.load_venue_history(tmp_path, before_season=2026)
    assert sorted(h["season"]) == [2024, 2025] and set(h["location"]) == {"Barcelona"}


def test_ingest_season_passes_venue_note_to_the_manifest(tmp_path):
    snap = ingest.SCHEDULE_DIR / "season=2025"
    snap.mkdir(parents=True)
    pd.DataFrame({"RoundNumber": [9], "EventName": ["Spanish Grand Prix"],
                  "Location": ["Barcelona"]}).to_parquet(snap / "schedule.parquet")
    with patch("ingest._with_retry", return_value=SCHED_2026), \
         patch("ingest.ingest_race", return_value=("ok", {})) as race, \
         patch("ingest.ingest_qualifying", return_value=("ok", {})), \
         patch("ingest._write_event_schedule"):
        ingest.ingest_season(2026, "R", False, True, now_utc=NOW)
    assert "was at Barcelona" in race.call_args.kwargs["venue_note"]


# ---------------------------------------------------------------------------
# Manifest, summary, exit code, dry run, monitor
# ---------------------------------------------------------------------------

def test_manifest_row_is_additive():
    row = ingest._make_manifest_row("r", 2026, 1, "x", "R", "ok")
    old = ["run_id", "ingested_at_utc", "season", "round_number", "race_slug", "session_type",
           "status", "row_count", "dq_passed", "duplicate_lap_keys", "schema_fingerprint"]
    assert list(row)[: len(old)] == old
    assert set(row) - set(old) == set(ingest.MANIFEST_EXTRA_DEFAULTS)
    with pytest.raises(TypeError):
        ingest._make_manifest_row("r", 2026, 1, "x", "R", "ok", not_a_field=1)


def test_manifest_with_new_fields_round_trips(tmp_path):
    rows = [
        ingest._make_manifest_row("r", 2026, 4, "miami_grand_prix", "R", "thin", thin_reasons="results.Points 0%"),
        ingest._make_manifest_row("r", 2026, 6, "monaco_grand_prix", "R", "ok", telemetry_laps_attempted=1452,
                                  telemetry_laps_merged=128, telemetry_coverage=0.0882),
        ingest._make_manifest_row("r", 2026, 6, "monaco_grand_prix", "Q", "skip"),
    ]
    ingest._write_manifest(rows, "r")
    back = pd.read_parquet(ingest.MANIFESTS_DIR / "run_r.parquet")
    assert list(back["status"]) == ["thin", "ok", "skip"]
    assert back.loc[1, "telemetry_laps_merged"] == 128


def test_attention_lines():
    rows = [
        ingest._make_manifest_row("r", 2026, 3, "japanese_grand_prix", "R", "error"),
        ingest._make_manifest_row("r", 2026, 4, "miami_grand_prix", "R", "thin", thin_reasons="results.Points 0%"),
        ingest._make_manifest_row("r", 2026, 6, "monaco_grand_prix", "R", "ok", telemetry_laps_attempted=1452,
                                  telemetry_laps_merged=128, telemetry_coverage=0.0882,
                                  circuit_info_status="failed: KeyError"),
        ingest._make_manifest_row("r", 2018, 1, "australian_grand_prix", "R", "ok", telemetry_laps_attempted=940,
                                  telemetry_laps_merged=0, telemetry_coverage=0.0, telemetry_note="known gap"),
        ingest._make_manifest_row("r", 2026, 14, "spanish_grand_prix", "R", "ok", venue_note="moved"),
        ingest._make_manifest_row("r", 2026, 14, "spanish_grand_prix", "Q", "ok", venue_note="moved"),
    ]
    blocking, notes = ingest._attention_lines(rows)
    assert len(blocking) == 2 and blocking[0].startswith("FAILED") and blocking[1].startswith("THIN")
    assert not any(" ERROR " in line for line in blocking)   # would trip monitor_ingest's FAILURE_RE
    assert any(n.startswith("LOW TELEMETRY 2026 Rd6") for n in notes)
    assert any(n.startswith("NO CIRCUIT INFO 2026 Rd6") for n in notes)
    assert not any("australian" in n for n in notes)       # known gap is not flagged
    assert sum(n.startswith("VENUE") for n in notes) == 1  # once per round


def _run_main(monkeypatch, tmp_path, argv):
    monkeypatch.setattr(sys, "argv", ["ingest.py", *argv, "--bronze-dir", str(tmp_path / "bronze"),
                                      "--cache-dir", str(tmp_path / "cache")])
    monkeypatch.setattr(ingest.fastf1.Cache, "enable_cache", MagicMock())
    return ingest.main()


def test_main_exit_code_and_manifest_location(monkeypatch, tmp_path):
    thin_row = ingest._make_manifest_row("r", 2026, 4, "miami_grand_prix", "R", "thin", thin_reasons="x")
    ok_row = ingest._make_manifest_row("r", 2026, 5, "canadian_grand_prix", "R", "ok")
    with patch("ingest.ingest_season", return_value=({}, [thin_row])):
        assert _run_main(monkeypatch, tmp_path, ["-s", "2026"]) == 1
    with patch("ingest.ingest_season", return_value=({}, [ok_row])):
        assert _run_main(monkeypatch, tmp_path, ["-s", "2026"]) == 0
    manifests = list((tmp_path / "bronze" / "manifests").glob("run_*.parquet"))
    assert manifests                                         # written under --bronze-dir
    with patch("ingest.ingest_season", return_value=({"schedule_error": 1}, [])):
        assert _run_main(monkeypatch, tmp_path, ["-s", "2026"]) == 1


def test_dry_run_lists_plan_and_writes_nothing(monkeypatch, tmp_path, capsys):
    # main() installs its own stdout handler (setup_logging), so read stdout, not caplog.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sched = _schedule([
        (1, "Australian Grand Prix", "Melbourne", now - timedelta(days=30, hours=1), now - timedelta(days=30)),
        (2, "Chinese Grand Prix", "Shanghai", now + timedelta(days=6), now + timedelta(days=7)),
    ])
    with patch("ingest._with_retry", return_value=sched), \
         patch("ingest.ingest_season") as season:
        assert _run_main(monkeypatch, tmp_path, ["-s", "2026", "--dry-run"]) == 0
    season.assert_not_called()
    out = capsys.readouterr().out
    assert "Rd 1 australian_grand_prix" in out and "would pull" in out
    assert "Rd 2 chinese_grand_prix" in out and "not run yet" in out
    assert not (tmp_path / "bronze").exists()


def test_monitor_flags_completed_run_that_needs_attention(tmp_path, capsys):
    log = tmp_path / "ingest.log"
    log.write_text("x | ingest | WARNING | === NEEDS ATTENTION: ... ===\n"
                   "x | ingest | WARNING |   THIN   2026 Rd4 R miami_grand_prix: results.Points\n"
                   "x | ingest | INFO | === COMPLETE: 3 sessions newly written ===\n")
    assert monitor_ingest.monitor(log, poll_interval=0) == 1
    clean = tmp_path / "clean.log"
    clean.write_text("x | ingest | INFO | === COMPLETE: 3 sessions newly written ===\n")
    assert monitor_ingest.monitor(clean, poll_interval=0) == 0
