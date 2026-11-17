"""Offline tests for ingest.py's season hardening (no network, no data/bronze):

  * rounds that have not run yet are skipped without loading or a manifest row;
  * a thin (incomplete) load is not written unless accepted, and is never re-fetched
    with the cache bypassed;
  * rate-limit errors wait and retry (bounded per run), recorded in the manifest;
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

import fastf1
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


def test_thin_race_is_not_written_and_not_done():
    thin = _session(points=False)
    with patch("ingest._load_race_session", side_effect=[thin]), patch("ingest.time.sleep"):
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
    with patch("ingest._load_race_session", side_effect=[thin]), patch("ingest.time.sleep"):
        status, _ = ingest.ingest_race(2026, 4, "miami_grand_prix", force=True, skip_telemetry=True)
    assert status == "thin"
    pd.testing.assert_frame_equal(pd.read_parquet(results_path), before)


def test_accept_thin_writes_and_records_reasons():
    thin = _session(points=False)
    with patch("ingest._load_race_session", side_effect=[thin]), patch("ingest.time.sleep"):
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", False, True, accept_thin=True)
    assert status == "ok" and "results.Points" in row["thin_reasons"]
    assert ingest._laps_path_race(2026, "miami_grand_prix").exists()


def test_thin_qualifying_not_written():
    thin = _session(q1=False, stype="Q")
    with patch("ingest._load_qualifying_session", side_effect=[thin]), patch("ingest.time.sleep"):
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


def test_thin_race_manifest_reason_is_source_empty_and_loaded_once():
    with patch("ingest._load_race_session", side_effect=[_session(points=False)]) as load, \
         patch("ingest.time.sleep") as sleep:
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", False, True)
    assert status == "thin" and row["reason"] == "source_empty"
    assert load.call_count == 1 and row["attempts"] == 1 and row["rate_limit_waits"] == 0
    assert load.call_args.kwargs == {}            # never the cache-bypass path
    sleep.assert_not_called()


def test_rate_limit_waits_then_succeeds():
    limited = fastf1.exceptions.RateLimitExceededError("any API: 500 calls/h")
    with patch("ingest._load_race_session", side_effect=[limited, _session()]) as load, \
         patch("ingest.time.sleep") as sleep:
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", False, True)
    assert status == "ok" and row["reason"] == ""
    sleep.assert_any_call(ingest.RATE_LIMIT_WAIT_S)
    assert row["attempts"] == 2 and row["rate_limit_waits"] == 1
    assert row["rate_limit_wait_s"] == ingest.RATE_LIMIT_WAIT_S
    assert all(c.kwargs == {} for c in load.call_args_list)   # cache never bypassed
    assert ingest._laps_path_race(2026, "miami_grand_prix").exists()


def test_rate_limit_matched_by_message_and_qualifying():
    with patch("ingest._load_qualifying_session",
               side_effect=[RuntimeError("429: any API: 500 calls/h"), _session(stype="Q")]), \
         patch("ingest.time.sleep") as sleep:
        status, row = ingest.ingest_qualifying(2026, 4, "miami_grand_prix", force=False)
    assert status == "ok" and row["rate_limit_waits"] == 1
    sleep.assert_any_call(ingest.RATE_LIMIT_WAIT_S)


def test_rate_limit_cap_stops_the_run_and_writes_nothing():
    limited = fastf1.exceptions.RateLimitExceededError("any API: 500 calls/h")
    with patch("ingest._load_race_session", side_effect=limited), patch("ingest.time.sleep") as sleep:
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", False, True)
    assert status == "error" and row["reason"] == "rate_limited"
    assert row["rate_limit_waits"] == ingest.MAX_RATE_LIMIT_WAITS
    assert sleep.call_count == ingest.MAX_RATE_LIMIT_WAITS
    assert not ingest._laps_path_race(2026, "miami_grand_prix").exists()

    # The season loop stops at the first rate-limited session and says so.
    with patch("ingest._with_retry", return_value=SCHED_2026), \
         patch("ingest.ingest_race", return_value=("error", {"reason": "rate_limited"})) as race, \
         patch("ingest.ingest_qualifying", return_value=("ok", {})) as quali, \
         patch("ingest._write_event_schedule"):
        counts, rows = ingest.ingest_season(2026, "both", False, True, only_rounds={14, 16},
                                            now_utc=NOW, include_unfinished=True)
    assert counts["rate_limit_stop"] == 1 and race.call_count == 1 and quali.call_count == 0
    blocking, _ = ingest._attention_lines([{**_row_stub(), "reason": "rate_limited"}])
    assert "rate limited" in blocking[0]


def _row_stub():
    return {"season": 2026, "round_number": 4, "session_type": "R",
            "race_slug": "miami_grand_prix", "status": "error"}


def test_transient_error_uses_short_backoff_not_rate_limit_wait():
    with patch("ingest._load_race_session", side_effect=[RuntimeError("503"), _session()]), \
         patch("ingest.time.sleep") as sleep:
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", False, True)
    assert status == "ok" and row["attempts"] == 2 and row["rate_limit_waits"] == 0
    sleep.assert_any_call(1.0)
    assert ingest.RATE_LIMIT_WAIT_S not in [c.args[0] for c in sleep.call_args_list]


def test_persistent_transient_error_is_reason_error():
    with patch("ingest._load_race_session", side_effect=RuntimeError("503")), patch("ingest.time.sleep"):
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", False, True)
    assert status == "error" and row["reason"] == "error" and row["attempts"] == 4


def test_existing_session_is_skipped_without_loading():
    ingest._laps_path_race(2026, "miami_grand_prix").parent.mkdir(parents=True)
    _laps().to_parquet(ingest._laps_path_race(2026, "miami_grand_prix"))
    with patch("ingest._load_race_session") as load:
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", False, True)
    assert status == "skip" and row["attempts"] == 0
    load.assert_not_called()


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


# ---------------------------------------------------------------------------
# Full-channel telemetry (--telemetry-full): FastF1 3.x car_data / pos_data are
# dicts of driver number -> Telemetry; failures must reach the manifest.
# ---------------------------------------------------------------------------

_CAR_COLS = ["Date", "Speed", "Throttle", "Brake", "nGear", "RPM", "DRS"]
_POS_COLS = ["Date", "X", "Y", "Z"]


def _chan(cols, drivers):
    return {d: pd.DataFrame({c: [1.0, 2.0] for c in cols}) for d in drivers}


def test_full_channels_write_one_parquet_per_driver_from_dicts():
    s = MagicMock()
    s.car_data = _chan(_CAR_COLS, ["1", "44"])
    s.pos_data = _chan(_POS_COLS, ["1", "44"])
    assert ingest._write_telemetry_full(s, 2026, 4, "miami_grand_prix")[0] == "ok"
    assert ingest._write_pos_data(s, 2026, 4, "miami_grand_prix")[0] == "ok"
    for drv in ("1", "44"):
        car = pd.read_parquet(ingest.TELEMETRY_FULL_DIR / "season=2026" / "race=miami_grand_prix"
                              / f"driver={drv}" / "car_data.parquet")
        pos = pd.read_parquet(ingest.POS_DATA_DIR / "season=2026" / "race=miami_grand_prix"
                              / f"driver={drv}" / "pos_data.parquet")
        assert set(_CAR_COLS) | {"driver_id", "race_id", "season"} == set(car.columns)
        assert set(_POS_COLS) | {"driver_id", "race_id", "season"} == set(pos.columns)
        assert (car["driver_id"] == drv).all() and (car["race_id"] == "2026_4").all()


def test_empty_full_channel_is_recorded_in_manifest_not_dropped(caplog):
    s = _session()
    s.car_data = {}                               # loaded but no samples
    s.pos_data = _chan(_POS_COLS, ["1"])
    with caplog.at_level("ERROR"), patch("ingest._load_race_session", return_value=s), \
         patch("ingest.time.sleep"):
        status, row = ingest.ingest_race(2026, 4, "miami_grand_prix", False, True, telemetry_full=True)
    assert status == "ok"                         # one channel never fails the run
    assert row["telemetry_full_status"] == "empty"
    assert "car_data: no samples" in row["telemetry_full_note"]
    assert any(r.levelname == "ERROR" for r in caplog.records)
    assert (ingest.POS_DATA_DIR / "season=2026" / "race=miami_grand_prix" / "driver=1"
            / "pos_data.parquet").exists()


def test_full_channel_ok_and_not_requested_statuses():
    s = _session()
    s.car_data = _chan(_CAR_COLS, ["1"])
    s.pos_data = _chan(_POS_COLS, ["1"])
    with patch("ingest._load_race_session", return_value=s), patch("ingest.time.sleep"):
        _, row = ingest.ingest_race(2026, 5, "a_grand_prix", False, True, telemetry_full=True)
        _, row2 = ingest.ingest_race(2026, 6, "b_grand_prix", False, True)
    assert row["telemetry_full_status"] == "ok"
    assert row2["telemetry_full_status"] == ""


def test_full_channel_driver_write_failure_is_error():
    s = MagicMock()
    s.car_data = {"1": pd.DataFrame({"Speed": [1.0]})}
    s.pos_data = _chan(_POS_COLS, ["1"])
    with patch("pandas.DataFrame.to_parquet", side_effect=OSError("disk full")):
        fields = ingest._full_channel_fields(s, 2026, 4, "x")
    assert fields["telemetry_full_status"] == "error" and "failed" in fields["telemetry_full_note"]


# ---------------------------------------------------------------------------
# Qualifying telemetry path
# ---------------------------------------------------------------------------

def test_load_qualifying_session_requests_telemetry():
    s = MagicMock()
    with patch("ingest.fastf1.get_session", return_value=s) as get:
        assert ingest._load_qualifying_session(2026, 4) is s
    assert get.call_args.args == (2026, 4, "Q")
    s.load.assert_called_once_with(laps=True, telemetry=True, weather=True)


def test_ingest_qualifying_skip_telemetry_writes_note_and_no_telemetry():
    with patch("ingest._load_qualifying_session", return_value=_session(stype="Q")), \
         patch("ingest._write_telemetry") as wt, patch("ingest.time.sleep"):
        status, row = ingest.ingest_qualifying(2026, 4, "miami_grand_prix", False, skip_telemetry=True)
    assert status == "ok"
    wt.assert_not_called()
    assert row["telemetry_note"] == "not requested (--skip-telemetry)"
    assert row["telemetry_laps_attempted"] is None


def test_ingest_qualifying_telemetry_full_merges_fields_and_session_scoped_paths():
    s = _session(stype="Q")
    cov = {"telemetry_laps_attempted": 10, "telemetry_laps_merged": 10, "telemetry_coverage": 1.0,
           "telemetry_car_drivers": 20, "telemetry_pos_drivers": 20, "telemetry_note": ""}
    full = {"telemetry_full_status": "ok", "telemetry_full_note": "car_data: 2 drivers"}
    with patch("ingest._load_qualifying_session", return_value=s), \
         patch("ingest._write_telemetry", return_value=cov) as wt, \
         patch("ingest._full_channel_fields", return_value=full) as ff, patch("ingest.time.sleep"):
        status, row = ingest.ingest_qualifying(2026, 4, "miami_grand_prix", False, telemetry_full=True)
    assert status == "ok"
    wt.assert_called_once_with(s, 2026, 4, "miami_grand_prix", "Q")
    ff.assert_called_once_with(s, 2026, 4, "miami_grand_prix", "Q")
    assert row["telemetry_full_status"] == "ok" and row["telemetry_laps_merged"] == 10


def test_ingest_qualifying_telemetry_writer_failure_does_not_fail_session():
    with patch("ingest._load_qualifying_session", return_value=_session(stype="Q")), \
         patch("ingest._write_telemetry", side_effect=OSError("disk full")), patch("ingest.time.sleep"):
        status, row = ingest.ingest_qualifying(2026, 4, "miami_grand_prix", False)
    assert status == "ok"
    assert row["telemetry_note"].startswith("telemetry writer failed")
    assert ingest._laps_path_quali(2026, "miami_grand_prix").exists()


def test_quali_telemetry_does_not_overwrite_race_and_ignores_known_race_gap():
    race = ingest._write_telemetry(_tel_session(n_ok=2, n_fail=0), 2026, 4, "miami_grand_prix")
    ingest._write_telemetry(_tel_session(n_ok=1, n_fail=0), 2026, 4, "miami_grand_prix", "Q")
    base = ingest.TELEMETRY_DIR / "season=2026" / "race=miami_grand_prix"
    assert len(pd.read_parquet(base / "telemetry.parquet")) == 4          # race file untouched
    q = pd.read_parquet(base / "session=Q" / "telemetry.parquet")
    assert len(q) == 2 and set(q["session_type"]) == {"Q"}
    assert race["telemetry_laps_merged"] == 2
    gap = {"telemetry_laps_attempted": 940, "telemetry_laps_merged": 0,
           "telemetry_coverage": 0.0, "telemetry_note": ""}
    out = ingest._judge_telemetry(dict(gap), 2018, 1, "australian_grand_prix", "Q")
    assert "known_gap_note" not in out and out["telemetry_note"].startswith("low coverage")


def test_quali_full_channels_write_under_session_q():
    s = MagicMock()
    s.car_data = _chan(_CAR_COLS, ["1"])
    s.pos_data = _chan(_POS_COLS, ["1"])
    assert ingest._full_channel_fields(s, 2026, 4, "x", "Q")["telemetry_full_status"] == "ok"
    assert (ingest.TELEMETRY_FULL_DIR / "season=2026" / "race=x" / "session=Q" / "driver=1"
            / "car_data.parquet").exists()
    assert not (ingest.TELEMETRY_FULL_DIR / "season=2026" / "race=x" / "driver=1").exists()


# ---------------------------------------------------------------------------
# Every dataset FastF1 offers, for R and Q: qualifying race control, session
# info, qualifying circuit info, circuit markers; and --fill-missing.
# ---------------------------------------------------------------------------

_INFO = {"Meeting": {"Key": 1000, "Name": "Miami Grand Prix", "Location": "Miami",
                     "Country": {"Key": 19, "Code": "USA", "Name": "United States"},
                     "Circuit": {"Key": 151, "ShortName": "Miami"}},
         "ArchiveStatus": {"Status": "Complete"}, "Key": 9999, "Type": "Qualifying",
         "Name": "Qualifying", "StartDate": datetime(2026, 5, 2, 16, 0),
         "EndDate": datetime(2026, 5, 2, 17, 0), "GmtOffset": timedelta(hours=-4),
         "Path": "2026/2026-05-04_Miami_Grand_Prix/2026-05-02_Qualifying/"}


def _circuit():
    c = MagicMock()
    marker = lambda n: pd.DataFrame({"X": [1.0] * n, "Y": [2.0] * n, "Number": list(range(1, n + 1)),
                                     "Letter": [""] * n, "Angle": [0.0] * n, "Distance": [10.0] * n})
    c.corners, c.marshal_lights, c.marshal_sectors, c.rotation = marker(3), marker(2), marker(4), 92.0
    return c


def _full_session(stype="R"):
    s = _session(stype=stype)
    s.session_info = dict(_INFO)
    s.session_start_time = pd.Timedelta(minutes=55)
    s.total_laps = 57 if stype == "R" else None
    s.t0_date = pd.Timestamp("2026-05-02 19:05:00")
    s.date = pd.Timestamp("2026-05-02 20:00:00")
    s.api_path = _INFO["Path"]
    s.f1_api_support = True
    s.get_circuit_info.return_value = _circuit()
    s.track_status = pd.DataFrame({"Time": pd.to_timedelta([0], unit="s"), "Status": ["1"]})
    s.session_status = pd.DataFrame({"Time": pd.to_timedelta([0], unit="s"), "Status": ["Started"]})
    return s


def _part(root, slug="miami_grand_prix", q=False, season=2026):
    return ingest._session_dir(root, season, slug, "Q" if q else "R")


def test_quali_race_control_goes_under_session_q_and_race_file_is_untouched():
    s = _full_session("Q")
    ingest._write_race_control(_full_session("R"), 2026, 6, "miami_grand_prix")
    s.race_control_messages = pd.DataFrame({"Time": pd.to_timedelta([0, 30], unit="s"),
                                            "Category": ["Flag", "Other"], "Message": ["GREEN", "Q1 ENDED"]})
    ingest._write_race_control(s, 2026, 6, "miami_grand_prix", "Q")
    race = pd.read_parquet(_part(ingest.RC_DIR) / "race_control.parquet")
    q = pd.read_parquet(_part(ingest.RC_DIR, q=True) / "race_control.parquet")
    assert len(race) == 1 and "session_type" not in race.columns       # race output unchanged
    assert len(q) == 2 and set(q["session_type"]) == {"Q"} and list(q["session_time_s"]) == [0.0, 30.0]


@pytest.mark.parametrize("stype", ["R", "Q"])
def test_session_info_is_flattened_to_one_row_with_session_scalars(stype):
    assert ingest._write_session_info(_full_session(stype), 2026, 6, "miami_grand_prix", stype) == "ok"
    df = pd.read_parquet(_part(ingest.SESSION_INFO_DIR, q=stype == "Q") / "session_info.parquet")
    assert len(df) == 1
    row = df.iloc[0]
    assert row["Meeting_Circuit_Key"] == 151 and row["Meeting_Country_Code"] == "USA"
    assert row["Key"] == 9999 and row["GmtOffset"] == pd.Timedelta(hours=-4)
    assert row["session_start_time_s"] == 3300.0 and row["session_type"] == stype
    assert row["race_id"] == "2026_6" and row["f1_api_support"]
    assert (row["total_laps"] == 57) if stype == "R" else pd.isna(row["total_laps"])


def test_session_info_absent_or_unloaded_writes_nothing():
    assert ingest._write_session_info(MagicMock(), 2026, 6, "x") == "none"     # mock attr, not a dict
    s = MagicMock()
    type(s).session_info = property(lambda self: (_ for _ in ()).throw(
        fastf1.exceptions.DataNotLoadedError("not loaded")))
    assert ingest._write_session_info(s, 2026, 6, "x") == "none"
    assert not ingest.SESSION_INFO_DIR.exists()


def test_circuit_info_race_corners_unchanged_and_markers_written_for_r_and_q():
    s = _full_session()
    assert ingest._write_circuit_info(s, 2026, 6, "miami_grand_prix") == "ok: 3 corners"
    assert ingest._write_circuit_info(s, 2026, 6, "miami_grand_prix", "Q") == "ok: 3 corners"
    corners = pd.read_parquet(_part(ingest.CIRCUIT_INFO_DIR) / "circuit_info.parquet")
    assert list(corners.columns) == ["index", "X", "Y", "Number", "Letter", "Angle", "Distance",
                                     "race_id", "season"]                 # race file as before
    q = pd.read_parquet(_part(ingest.CIRCUIT_INFO_DIR, q=True) / "circuit_info.parquet")
    assert set(q["session_type"]) == {"Q"}
    for quali in (False, True):
        m = pd.read_parquet(_part(ingest.CIRCUIT_MARKERS_DIR, q=quali) / "circuit_markers.parquet")
        assert m["marker_type"].value_counts().to_dict() == {"marshal_sector": 4, "corner": 3, "marshal_light": 2}
        assert (m["rotation_deg"] == 92.0).all()
    # Markers live outside circuit_info/, so stg_circuit_info's glob (*/*/*.parquet) sees corners only.
    assert [p.name for p in ingest.CIRCUIT_INFO_DIR.glob("*/*/*.parquet")] == ["circuit_info.parquet"]


def test_circuit_markers_failure_is_appended_not_fatal():
    s = _full_session()
    with patch("ingest._write_circuit_markers", return_value="failed: OSError: disk full"):
        status = ingest._write_circuit_info(s, 2026, 6, "miami_grand_prix")
    assert status == "ok: 3 corners; markers failed: OSError: disk full"


def test_ingest_qualifying_writes_race_control_circuit_and_session_info():
    with patch("ingest._load_qualifying_session", return_value=_full_session("Q")), \
         patch("ingest.time.sleep"):
        status, row = ingest.ingest_qualifying(2026, 6, "miami_grand_prix", False, skip_telemetry=True)
    assert status == "ok"
    assert row["circuit_info_status"] == "ok: 3 corners" and row["session_info_status"] == "ok"
    for root, fname in [(ingest.RC_DIR, "race_control.parquet"),
                        (ingest.CIRCUIT_INFO_DIR, "circuit_info.parquet"),
                        (ingest.CIRCUIT_MARKERS_DIR, "circuit_markers.parquet"),
                        (ingest.SESSION_INFO_DIR, "session_info.parquet")]:
        assert (_part(root, q=True) / fname).exists(), root
        assert not (_part(root) / fname).exists(), root                    # never the race path


def test_ingest_race_writes_session_info_and_markers():
    with patch("ingest._load_race_session", return_value=_full_session("R")), patch("ingest.time.sleep"):
        status, row = ingest.ingest_race(2026, 6, "miami_grand_prix", False, True)
    assert status == "ok" and row["session_info_status"] == "ok"
    assert (_part(ingest.SESSION_INFO_DIR) / "session_info.parquet").exists()
    assert (_part(ingest.CIRCUIT_MARKERS_DIR) / "circuit_markers.parquet").exists()


def _on_disk_quali(slug="miami_grand_prix"):
    """A qualifying session as written before this change: laps + the old writers."""
    with patch("ingest._load_qualifying_session", return_value=_full_session("Q")), \
         patch("ingest.time.sleep"):
        assert ingest.ingest_qualifying(2026, 6, slug, False, skip_telemetry=True)[0] == "ok"
    for root, fname in [(ingest.RC_DIR, "race_control.parquet"),
                        (ingest.SESSION_INFO_DIR, "session_info.parquet"),
                        (ingest.CIRCUIT_INFO_DIR, "circuit_info.parquet"),
                        (ingest.CIRCUIT_MARKERS_DIR, "circuit_markers.parquet")]:
        (_part(root, slug, q=True) / fname).unlink()


def test_missing_datasets_lists_absent_outputs_and_respects_telemetry_flags():
    _on_disk_quali()
    assert ingest._missing_datasets(2026, "miami_grand_prix", "Q", skip_telemetry=True) == [
        "race_control", "session_info", "circuit_info", "circuit_markers"]
    with_tel = ingest._missing_datasets(2026, "miami_grand_prix", "Q", telemetry_full=True)
    assert with_tel[-3:] == ["telemetry", "telemetry_full", "pos_data"]


def test_fill_missing_loads_once_writes_only_missing_and_keeps_existing_files():
    _on_disk_quali()
    laps = ingest._laps_path_quali(2026, "miami_grand_prix")
    weather = _part(ingest.WEATHER_DIR, q=True) / "weather.parquet"
    before = (laps.stat().st_mtime_ns, weather.stat().st_mtime_ns)
    s = _full_session("Q")
    with patch("ingest._load_qualifying_session", return_value=s) as load, \
         patch("ingest._write_weather") as ww, patch("ingest._write_results") as wr:
        status, row = ingest.ingest_qualifying(2026, 6, "miami_grand_prix", False,
                                               skip_telemetry=True, fill_missing=True)
    load.assert_called_once()
    ww.assert_not_called(); wr.assert_not_called()                          # present: not rewritten
    assert (laps.stat().st_mtime_ns, weather.stat().st_mtime_ns) == before
    assert status == "skip" and row["attempts"] == 1
    assert row["fill_note"] == "filled: race_control, session_info, circuit_info, circuit_markers"
    assert row["session_info_status"] == "ok" and row["circuit_info_status"] == "ok: 3 corners"
    assert ingest._missing_datasets(2026, "miami_grand_prix", "Q", skip_telemetry=True) == []
    # Nothing left to fill: the next run skips without loading.
    with patch("ingest._load_qualifying_session") as load2:
        status2, row2 = ingest.ingest_qualifying(2026, 6, "miami_grand_prix", False,
                                                 skip_telemetry=True, fill_missing=True)
    load2.assert_not_called()
    assert status2 == "skip" and row2["fill_note"] == ""


def test_fill_records_what_the_source_lacks_and_only_markers_when_corners_exist():
    _on_disk_quali()
    s = _full_session("Q")
    s.session_info = None                         # source has no SessionInfo
    corners = _part(ingest.CIRCUIT_INFO_DIR, q=True) / "circuit_info.parquet"
    corners.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"Number": [9]}).to_parquet(corners)
    with patch("ingest._load_qualifying_session", return_value=s):
        status, row = ingest.ingest_qualifying(2026, 6, "miami_grand_prix", False,
                                               skip_telemetry=True, fill_missing=True)
    assert status == "skip"
    assert row["fill_note"] == ("filled: race_control, circuit_markers; source has none: session_info")
    assert pd.read_parquet(corners)["Number"].tolist() == [9]                # corners not rewritten
    _, notes = ingest._attention_lines([row])
    assert any(n.startswith("FILL   2026 Rd6 Q miami_grand_prix") for n in notes)


def test_fill_load_failure_is_an_error_row_with_a_fill_note():
    _on_disk_quali()
    with patch("ingest._load_qualifying_session", side_effect=ValueError("boom")), \
         patch("ingest.time.sleep"):
        status, row = ingest.ingest_qualifying(2026, 6, "miami_grand_prix", False,
                                               skip_telemetry=True, fill_missing=True)
    assert status == "error" and row["reason"] == "error"
    assert row["fill_note"].startswith("fill failed for race_control")
    blocking, _ = ingest._attention_lines([row])
    assert blocking == ["FAILED 2026 Rd6 Q miami_grand_prix: load or write failed (see [ERR] / [DQ FAIL] above)"]


def test_fill_race_with_full_channels():
    ingest._laps_path_race(2026, "miami_grand_prix").parent.mkdir(parents=True)
    _laps().to_parquet(ingest._laps_path_race(2026, "miami_grand_prix"))
    s = _full_session("R")
    s.car_data = _chan(_CAR_COLS, ["1"])
    s.pos_data = _chan(_POS_COLS, ["1"])
    with patch("ingest._load_race_session", return_value=s), \
         patch("ingest._write_telemetry", return_value={"telemetry_laps_attempted": 0}):
        status, row = ingest.ingest_race(2026, 6, "miami_grand_prix", False, skip_telemetry=True,
                                         telemetry_full=True, fill_missing=True)
    assert status == "skip" and row["telemetry_full_status"] == "ok"
    assert "telemetry_full, pos_data" in row["fill_note"] and "telemetry," not in row["fill_note"]
    assert (_part(ingest.TELEMETRY_FULL_DIR) / "driver=1" / "car_data.parquet").exists()
    assert ingest._missing_datasets(2026, "miami_grand_prix", "R", skip_telemetry=True,
                                    telemetry_full=True) == []


def test_force_ignores_fill_missing_and_rewrites():
    _on_disk_quali()
    with patch("ingest._load_qualifying_session", return_value=_full_session("Q")), \
         patch("ingest._fill_session") as fill, patch("ingest.time.sleep"):
        status, _ = ingest.ingest_qualifying(2026, 6, "miami_grand_prix", True,
                                             skip_telemetry=True, fill_missing=True)
    fill.assert_not_called()
    assert status == "ok"


def test_cli_fill_missing_flag_reaches_ingest_season(monkeypatch, tmp_path):
    assert ingest._build_parser().parse_args(["-s", "2026", "--fill-missing"]).fill_missing is True
    assert ingest._build_parser().parse_args(["-s", "2026"]).fill_missing is False
    with patch("ingest.ingest_season", return_value=({}, [])) as season:
        assert _run_main(monkeypatch, tmp_path, ["-s", "2026", "--fill-missing"]) == 0
    assert season.call_args.kwargs["fill_missing"] is True


def test_dry_run_shows_what_fill_would_write(monkeypatch, tmp_path, capsys):
    ingest.set_bronze_root(tmp_path / "bronze")
    _on_disk_quali("australian_grand_prix")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sched = _schedule([(6, "Australian Grand Prix", "Melbourne",
                        now - timedelta(days=30, hours=1), now - timedelta(days=30))])
    with patch("ingest._with_retry", return_value=sched):
        assert _run_main(monkeypatch, tmp_path, ["-s", "2026", "--session", "Q", "--dry-run",
                                                 "--fill-missing", "--skip-telemetry"]) == 0
    out = capsys.readouterr().out
    assert "on disk, would fill: race_control, session_info, circuit_info, circuit_markers" in out
