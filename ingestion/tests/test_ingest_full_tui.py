"""Offline tests for the ingest_full terminal view: line parsing and state only."""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ingest_full_tui.py"


@pytest.fixture(scope="module")
def tui():
    spec = importlib.util.spec_from_file_location("ingest_full_tui", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ingest_full_tui"] = mod  # dataclasses look the module up while it loads
    spec.loader.exec_module(mod)
    return mod


def test_phase_line_sets_phase(tui):
    s = tui.RunState()
    tui.apply_line(s, "=== 2026-11-16 10:56:46  pass 1 (R+Q, telemetry, fill missing): attempt 1/6\n")
    assert s.phase == "pass 1 (R+Q, telemetry, fill missing): attempt 1/6"


def test_ok_lines_count_by_session_type(tui):
    s = tui.RunState()
    tui.apply_line(s, "2026-11-15 00:00:47 | __main__ | INFO |   [OK]   Q  2018 Rd2 bahrain_grand_prix   244 laps")
    tui.apply_line(s, "2026-11-15 00:00:47 | __main__ | INFO |   [OK]   R  2018 Rd2 bahrain_grand_prix   244 laps")
    tui.apply_line(s, "2026-11-15 00:00:47 | __main__ | INFO |   [OK]   R  2018 Rd3 chinese_grand_prix   1 laps")
    assert s.ok == {"R": 2, "Q": 1}


def test_season_complete_recorded_once(tui):
    s = tui.RunState()
    line = "2026-11-15 00:30:37 | __main__ | INFO | Season 2018 complete   R: 20 ok, 0 skip, 1 error | Q: 21 ok, 0 skip, 0 error"
    tui.apply_line(s, line)
    tui.apply_line(s, line)
    assert s.seasons_done == ["2018"]


def test_rate_limit_sets_wait_and_countdown_start(tui):
    s = tui.RunState()
    tui.apply_line(s, "2026-11-15 08:07:58 | __main__ | WARNING |   [RATE LIMIT] any API: 500 calls/h   "
                      "waiting 3600s for the hourly window to reset (wait 6/24 this run)", now=1000.0)
    assert (s.waits, s.wait_cap, s.wait_started) == (6, 24, 1000.0)


def test_problems_only_from_script_lines(tui):
    s = tui.RunState()
    tui.apply_line(s, "2026-11-15 00:18:59 | __main__ | WARNING |   [ERR]  R  2018 Rd14 italian_grand_prix: boom")
    tui.apply_line(s, "2026-11-15 14:39:18 | __main__ | WARNING |   FAILED 2018 Rd14 R italian_grand_prix: load")
    tui.apply_line(s, "2026-11-15 14:39:18 | __main__ | WARNING | === NOTES: written, but worth a look")
    tui.apply_line(s, "2026-11-15 00:00:38 | fastf1.fastf1.core | DEBUG | Traceback for failure in telemetry data")
    assert len(s.problems) == 2
    assert all("NOTES" not in p and "fastf1" not in p for p in s.problems)


def test_done_and_failed_phases_set_result(tui):
    s = tui.RunState()
    tui.apply_line(s, "=== 2026-11-16 10:56:46  DONE: full Bronze 2018-2026 ingested, locked and verified")
    assert s.result.startswith("DONE")
    s2 = tui.RunState()
    tui.apply_line(s2, "=== 2026-11-16 10:56:46  pass 1: FAILED after 6 attempts")
    assert "FAILED after" in s2.result


def test_missing_known_gaps_file_is_empty_not_an_error(tui):
    assert tui.load_known_gaps(Path("/nonexistent/known_gaps.txt")) == []


def test_known_gaps_file_parses_to_entries(tui):
    gaps = tui.load_known_gaps()
    assert "2018 R italian_grand_prix" in gaps
    assert "2026 R bahrain_grand_prix" in gaps
    assert all(not g.startswith("#") for g in gaps)
