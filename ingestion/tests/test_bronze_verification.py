"""Offline tests for verify_bronze.py (derived expectations, KNOWN vs NEW gaps),
scripts/check_season_seeds.py and manifest_report.py's handling of the new
manifest fields. Every test builds a small synthetic bronze tree under tmp_path.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import check_season_seeds  # noqa: E402
import manifest_report  # noqa: E402
import verify_bronze  # noqa: E402

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


def _laps(round_num, season, n_drivers=4, n_laps=15, stint_null_share=0.0):
    rows = []
    for d in range(1, n_drivers + 1):
        for lap in range(1, n_laps + 1):
            rows.append({"Driver": f"D{d}", "DriverNumber": str(d), "LapNumber": float(lap),
                         "LapTime": pd.Timedelta(seconds=90), "Compound": "SOFT",
                         "TyreLife": float(lap), "Stint": 1.0,
                         "race_id": f"{season}_{round_num}", "season": season})
    df = pd.DataFrame(rows)
    df.loc[df.index[: int(len(df) * stint_null_share)], ["Stint", "TyreLife"]] = None
    return df


def _write(path: Path, df: pd.DataFrame):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _race(bronze, season, rnd, slug, *, telemetry_share=1.0, telemetry=True, points=True,
          q1=True, stint_null_share=0.0, quali=True):
    laps = _laps(rnd, season, stint_null_share=stint_null_share)
    _write(bronze / "laps" / f"season={season}" / f"race={slug}" / f"{season}_{slug}_laps.parquet", laps)
    drivers = sorted(laps["DriverNumber"].unique())
    res = pd.DataFrame({"DriverNumber": drivers,
                        "Points": [1.0 if points else None] * len(drivers),
                        "GridPosition": [1.0 if points else None] * len(drivers)})
    _write(bronze / "results" / f"season={season}" / f"race={slug}" / "results.parquet", res)
    for ds, name in [("weather", "weather.parquet"), ("race_control", "race_control.parquet")]:
        _write(bronze / ds / f"season={season}" / f"race={slug}" / name, pd.DataFrame({"x": [1, 2]}))
    if telemetry:
        n = int(len(laps) * telemetry_share)
        tel = pd.DataFrame({"driver_id": laps["Driver"].iloc[:n].repeat(3).values,
                            "lap_number": laps["LapNumber"].iloc[:n].repeat(3).values,
                            "speed_kph": 300.0})
        _write(bronze / "telemetry" / f"season={season}" / f"race={slug}" / "telemetry.parquet", tel)
    if quali:
        q = _laps(rnd, season)
        _write(bronze / "laps" / f"season={season}" / f"race={slug}" / "session=Q"
               / f"{season}_{slug}_quali_laps.parquet", q)
        qres = pd.DataFrame({"DriverNumber": drivers,
                             "Q1": pd.to_timedelta([80.0 if q1 else None] * len(drivers), unit="s")})
        _write(bronze / "results" / f"season={season}" / f"race={slug}" / "session=Q" / "results.parquet", qres)
        _write(bronze / "weather" / f"season={season}" / f"race={slug}" / "session=Q" / "weather.parquet",
               pd.DataFrame({"x": [1]}))


def _schedule(bronze, season, rounds):
    """rounds: [(round, EventName, Location, race_start_utc)]"""
    df = pd.DataFrame({
        "RoundNumber": [0] + [r[0] for r in rounds],
        "EventName": ["Pre-Season Testing"] + [r[1] for r in rounds],
        "Location": ["Sakhir"] + [r[2] for r in rounds],
        "Session4": [None] + ["Qualifying"] * len(rounds),
        "Session4DateUtc": [pd.NaT] + [pd.Timestamp(r[3]) - pd.Timedelta(days=1) for r in rounds],
        "Session5": [None] + ["Race"] * len(rounds),
        "Session5DateUtc": [pd.NaT] + [pd.Timestamp(r[3]) for r in rounds],
    })
    _write(bronze / "schedule" / f"season={season}" / "schedule.parquet", df)


def _levels(findings, section=None):
    return [(f.level, f.message) for f in findings if section is None or f.section == section]


# ---------------------------------------------------------------------------
# verify_bronze
# ---------------------------------------------------------------------------

def test_expected_races_come_from_the_schedule_and_skip_unrun_rounds(tmp_path):
    b = tmp_path
    _schedule(b, 2026, [(1, "Australian Grand Prix", "Melbourne", "2026-03-08 04:00"),
                        (2, "Chinese Grand Prix", "Shanghai", "2026-03-15 07:00"),
                        (15, "Azerbaijan Grand Prix", "Baku", "2026-09-26 11:00")])   # not run yet
    _race(b, 2026, 1, "australian_grand_prix")
    findings = verify_bronze.verify_season(b, 2026, NOW)
    new = [m for lvl, m in _levels(findings) if lvl == "new"]
    assert new == ["Rd2 chinese_grand_prix: finished on the schedule but has no laps in bronze"]
    _race(b, 2026, 2, "chinese_grand_prix")
    assert not [f for f in verify_bronze.verify_season(b, 2026, NOW) if f.level == "new"]


def test_known_telemetry_gap_is_known_but_a_new_one_fails(tmp_path):
    b = tmp_path
    _schedule(b, 2018, [(1, "Australian Grand Prix", "Melbourne", "2018-03-25 05:10"),
                        (2, "Bahrain Grand Prix", "Sakhir", "2018-04-08 15:10"),
                        (3, "Chinese Grand Prix", "Shanghai", "2018-04-15 06:10")])
    _race(b, 2018, 1, "australian_grand_prix", telemetry=False)
    _race(b, 2018, 2, "bahrain_grand_prix", telemetry=False)
    _race(b, 2018, 3, "chinese_grand_prix", telemetry=False)
    findings = verify_bronze.verify_season(b, 2018, NOW)
    presence = _levels(findings, "presence")
    assert sum(lvl == "known" for lvl, _ in presence) == 2
    assert ("new", "Rd3 chinese_grand_prix: missing telemetry") in presence


def test_low_telemetry_coverage_is_flagged(tmp_path):
    b = tmp_path
    _schedule(b, 2026, [(6, "Monaco Grand Prix", "Monte Carlo", "2026-06-07 13:00"),
                        (7, "Barcelona Grand Prix", "Barcelona", "2026-06-14 13:00")])
    _race(b, 2026, 6, "monaco_grand_prix", telemetry_share=0.09)
    _race(b, 2026, 7, "barcelona_grand_prix", telemetry_share=1.0)
    tel = _levels(verify_bronze.verify_season(b, 2026, NOW), "telemetry")
    assert len(tel) == 1 and tel[0][0] == "new" and tel[0][1].startswith("Rd6 monaco_grand_prix: telemetry on")


def test_thin_session_on_disk_is_new_unless_known(tmp_path):
    b = tmp_path
    _schedule(b, 2025, [(6, "Miami Grand Prix", "Miami", "2025-05-04 20:00"),
                        (7, "Emilia Romagna Grand Prix", "Imola", "2025-05-18 13:00")])
    _race(b, 2025, 6, "miami_grand_prix", stint_null_share=0.35, q1=False)   # the registered 2025 Miami gaps
    _race(b, 2025, 7, "emilia_romagna_grand_prix", points=False)              # a new thin load
    comp = _levels(verify_bronze.verify_season(b, 2025, NOW), "completeness")
    known = [m for lvl, m in comp if lvl == "known"]
    new = [m for lvl, m in comp if lvl == "new"]
    assert len(known) == 2 and all("miami" in m for m in known)
    assert new == ["Rd7 R emilia_romagna_grand_prix: thin: results.Points 0% non-null (< 90%); "
                   "results.GridPosition 0% non-null (< 90%)"]


def test_no_schedule_snapshot_still_checks_what_is_on_disk(tmp_path):
    _race(tmp_path, 2026, 1, "australian_grand_prix", telemetry=False)
    findings = verify_bronze.verify_season(tmp_path, 2026, NOW)
    assert ("info" in {f.level for f in findings})
    assert ("new", "Rd1 australian_grand_prix: missing telemetry") in _levels(findings, "presence")


def test_report_exit_codes(tmp_path, capsys):
    _schedule(tmp_path, 2018, [(1, "Australian Grand Prix", "Melbourne", "2018-03-25 05:10")])
    _race(tmp_path, 2018, 1, "australian_grand_prix", telemetry=False)
    assert verify_bronze.main(["--bronze-dir", str(tmp_path)]) == 0
    assert "1 known gap(s)" in capsys.readouterr().out
    _race(tmp_path, 2018, 1, "australian_grand_prix", telemetry=False, points=False)
    assert verify_bronze.main(["--bronze-dir", str(tmp_path)]) == 1
    assert verify_bronze.main(["--bronze-dir", str(tmp_path), "--season", "2030"]) == 1


def test_markdown_table_keeps_its_season_range(tmp_path, capsys):
    _race(tmp_path, 2024, 1, "bahrain_grand_prix")
    _race(tmp_path, 2025, 1, "australian_grand_prix")
    verify_bronze.main(["--markdown", "--bronze-dir", str(tmp_path)])
    out = capsys.readouterr().out.splitlines()
    assert out[2] == "| 2024 | 1 ✓ | 1 ✓ | 1 ✓ | 1 ✓ |" and len(out) == 3


# ---------------------------------------------------------------------------
# check_season_seeds
# ---------------------------------------------------------------------------

def _seeds(tmp_path, race_to_track="", scheduled="", circuits=("australian_grand_prix",
                                                                 "spanish_grand_prix"), alloc=""):
    s = tmp_path / "seeds"
    s.mkdir()
    (s / "race_to_track.csv").write_text("race_id,track_id\n2025_1,australian_grand_prix\n" + race_to_track)
    (s / "race_scheduled_laps.csv").write_text(
        "race_id,race_year,round_number,event_name,scheduled_laps,total_laps_final,max_current_lap,source,note\n"
        "2025_1,2025,1,Australian Grand Prix,58,58,58,f1,\n" + scheduled)
    (s / "circuit_reference.csv").write_text("circuit_key,circuit_name\n" + "".join(f"{c},x\n" for c in circuits))
    (s / "tyre_allocations.csv").write_text(
        "race_year,circuit_key,hard_code,medium_code,soft_code,source_url\n" + alloc)
    (s / "raw_dim_events.csv").write_text("event_id,race_id\nE001,2021_10\n")
    return s


def test_season_seeds_lists_missing_rows_and_commands(tmp_path, capsys):
    bronze = tmp_path / "bronze"
    _schedule(bronze, 2025, [(9, "Spanish Grand Prix", "Barcelona", "2025-06-01 13:00")])
    _schedule(bronze, 2026, [(1, "Australian Grand Prix", "Melbourne", "2026-03-08 04:00"),
                             (7, "Barcelona Grand Prix", "Barcelona", "2026-06-14 13:00"),
                             (14, "Spanish Grand Prix", "Madrid", "2026-09-13 13:00")])
    for rnd, slug in [(1, "australian_grand_prix"), (7, "barcelona_grand_prix"), (14, "spanish_grand_prix")]:
        _race(bronze, 2026, rnd, slug)
    seeds = _seeds(tmp_path)

    report = check_season_seeds.check(2026, bronze, seeds)
    required = {item["seed"]: item for item in report["required"]}
    assert set(required) == {"race_to_track.csv", "race_scheduled_laps.csv"}
    assert required["race_to_track.csv"]["missing"] == ["2026_1", "2026_7", "2026_14"]
    rows = dict(required["race_to_track.csv"]["rows"])
    assert rows["2026_1,australian_grand_prix"] == ""
    assert "no circuit_reference row" in rows["2026_7,barcelona_grand_prix"]
    assert "new slug" in rows["2026_7,barcelona_grand_prix"]
    assert "was at Barcelona" in rows["2026_14,spanish_grand_prix"]
    assert "fetch_scheduled_laps.py --write --season 2026" in required["race_scheduled_laps.csv"]["how"]
    assert "AFTER race_to_track" in required["race_scheduled_laps.csv"]["how"]
    assert [o["seed"] for o in report["optional"]] == ["tyre_allocations.csv"]

    assert check_season_seeds.main(["--season", "2026", "--bronze-dir", str(bronze),
                                    "--seeds-dir", str(seeds)]) == 1
    out = capsys.readouterr().out
    assert "REQUIRED" in out and "make add-season SEASON=2026" in out


def test_season_seeds_passes_when_required_rows_exist(tmp_path):
    bronze = tmp_path / "bronze"
    _race(bronze, 2026, 1, "australian_grand_prix")
    seeds = _seeds(tmp_path, race_to_track="2026_1,australian_grand_prix\n",
                   scheduled="2026_1,2026,1,Australian Grand Prix,58,58,58,f1,\n",
                   alloc="2026,australian_grand_prix,C3,C4,C5,https://x\n")
    report = check_season_seeds.check(2026, bronze, seeds)
    assert report["required"] == [] and report["optional"] == []
    assert check_season_seeds.print_report(report) == 0


def test_season_seeds_flags_unknown_track_id(tmp_path):
    bronze = tmp_path / "bronze"
    _race(bronze, 2026, 7, "barcelona_grand_prix")
    seeds = _seeds(tmp_path, race_to_track="2026_7,barcelona_grand_prix\n",
                   scheduled="2026_7,2026,7,Barcelona Grand Prix,66,66,66,f1,\n")
    report = check_season_seeds.check(2026, bronze, seeds)
    assert [(i["seed"], i["missing"]) for i in report["required"]] == [
        ("circuit_reference.csv", ["barcelona_grand_prix"])]


def test_season_seeds_with_no_bronze_fails(tmp_path):
    assert check_season_seeds.main(["--season", "2026", "--bronze-dir", str(tmp_path),
                                    "--seeds-dir", str(_seeds(tmp_path))]) == 1


# ---------------------------------------------------------------------------
# manifest_report with old + new manifest files
# ---------------------------------------------------------------------------

OLD_COLUMNS = dict(duplicate_lap_keys=0, dq_passed=True, row_count=900)


def test_manifest_report_reads_old_and_new_files(tmp_path, monkeypatch, capsys):
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    old = pd.DataFrame([{"run_id": "a", "ingested_at_utc": "2026-06-01T00:00:00+00:00", "season": 2025,
                         "round_number": 1, "race_slug": "australian_grand_prix", "session_type": "R",
                         "status": "ok", "schema_fingerprint": "abc", **OLD_COLUMNS}])
    old.to_parquet(mdir / "run_a.parquet")
    new = pd.DataFrame([
        {"run_id": "b", "ingested_at_utc": "2026-09-25T00:00:00+00:00", "season": 2026, "round_number": 4,
         "race_slug": "miami_grand_prix", "session_type": "R", "status": "thin", "schema_fingerprint": "",
         "thin_reasons": "results.Points 0% non-null", **OLD_COLUMNS},
        {"run_id": "b", "ingested_at_utc": "2026-09-25T00:00:01+00:00", "season": 2026, "round_number": 6,
         "race_slug": "monaco_grand_prix", "session_type": "R", "status": "ok", "schema_fingerprint": "abc",
         "telemetry_laps_attempted": 1452, "telemetry_laps_merged": 128, "telemetry_coverage": 0.0882,
         "telemetry_note": "low coverage", "circuit_info_status": "failed: KeyError", **OLD_COLUMNS},
    ])
    new.to_parquet(mdir / "run_b.parquet")
    # a later skip must not hide the flags of the last real write
    skip = new.iloc[[1]].assign(run_id="c", ingested_at_utc="2026-09-26T00:00:00+00:00", status="skip",
                                telemetry_laps_attempted=None, telemetry_coverage=None, circuit_info_status="")
    skip.to_parquet(mdir / "run_c.parquet")

    assert manifest_report.main(["--bronze-dir", str(tmp_path)]) == 1   # thin needs attention
    out = capsys.readouterr().out
    assert "miami_grand_prix [thin]" in out
    assert "LOW TELEMETRY" in out and "NO CIRCUIT INFO" in out


@pytest.mark.parametrize("status,expected", [("ok", 0), ("error", 1)])
def test_manifest_report_old_files_only(tmp_path, capsys, status, expected):
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    pd.DataFrame([{"run_id": "a", "ingested_at_utc": "2026-06-01T00:00:00+00:00", "season": 2025,
                   "round_number": 1, "race_slug": "x", "session_type": "R", "status": status,
                   "schema_fingerprint": "abc", **OLD_COLUMNS}]).to_parquet(mdir / "run_a.parquet")
    assert manifest_report.main(["--bronze-dir", str(tmp_path)]) == expected
