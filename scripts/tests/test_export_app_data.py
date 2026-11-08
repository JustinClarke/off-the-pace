"""TX-12: --db / --out flags, the scratch round trip, and the app/public/data guard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

import export_app_data as ead

SCRIPT = Path(ead.__file__).resolve()


def _tiny_db(path: Path) -> Path:
    """The tables build_stats_block reads, a few rows each."""
    conn = duckdb.connect(str(path))
    conn.execute("CREATE TABLE fct_lap_residuals AS SELECT * FROM (VALUES (2023), (2024)) t(race_year)")
    conn.execute("CREATE TABLE dim_drivers AS SELECT * FROM (VALUES ('VER'), ('HAM')) t(driver_code)")
    conn.execute("CREATE TABLE race_to_track AS SELECT * FROM (VALUES (1, 'monza'), (2, 'spa')) t(race_id, track_id)")
    # TX-05: the one-row provenance table the manifest's `provenance` block copies.
    conn.execute(
        "CREATE TABLE mart_build_provenance AS SELECT "
        "'v16' AS label_version, DATE '2026-10-26' AS label_sealed_on, "
        "CAST(0.331 AS DOUBLE) AS theta_air_label_value, 2025 AS theta_air_fit_season_max, "
        "'flat_theta_0.331_lag1_share_unvalidated' AS dirty_air_method, "
        "2022 AS era_boundary, 2026 AS holdout_season, "
        "2023 AS data_season_min, 2024 AS data_season_max, 2 AS n_races, 2 AS n_races_scheduled, "
        "CAST(NULL AS VARCHAR) AS model_version, 'inv-1' AS dbt_invocation_id, "
        "TIMESTAMPTZ '2026-11-07 12:00:00+00' AS built_at, '1.12.6' AS dbt_version"
    )
    # TX-11: the four rating / isolation tables the export now lists.
    conn.execute("CREATE TABLE mart_race_driver_summary AS SELECT * FROM (VALUES ('VER','2023_1',0.5),('HAM','2023_1',0.7),('LEC','2023_1',0.9)) t(driver_id, race_id, rating_s)")
    conn.execute("CREATE TABLE mart_driver_season_summary AS SELECT * FROM (VALUES ('VER',2023,0.5),('HAM',2023,0.7)) t(driver_id, race_year, rating_s)")
    conn.execute("CREATE TABLE mart_metric_benchmark AS SELECT * FROM (VALUES ('m1',2023,1.5)) t(metric_name, race_year, p50)")
    conn.execute("CREATE TABLE fct_driver_isolation_race AS SELECT * FROM (VALUES ('VER','2023_1',0.1),('HAM','2023_1',0.2)) t(driver_id, race_id, pace_isolated_gain_s)")
    conn.execute("CREATE TABLE fct_driver_isolation_stint AS SELECT * FROM (VALUES ('VER','2023_1',1,0.1),('HAM','2023_1',1,0.2)) t(driver_id, race_id, stint_number, pace_isolated_gain_s)")
    conn.close()
    return path


PROVENANCE_COLS = {
    "label_version", "label_sealed_on", "theta_air_label_value", "theta_air_fit_season_max",
    "dirty_air_method", "era_boundary", "holdout_season", "data_season_min", "data_season_max",
    "n_races", "n_races_scheduled", "model_version", "dbt_invocation_id", "built_at", "dbt_version",
}


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def test_parser_defaults():
    args = ead.build_parser().parse_args([])
    assert args.db == ead.DB_PATH
    assert args.out == ead.APP_DATA
    assert not args.check and not args.canary and args.table is None


def test_main_passes_default_paths(monkeypatch):
    seen = {}

    def spy(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(ead, "run_export", spy)
    ead.main([])
    assert seen["db_path"] == ead.DB_PATH
    assert seen["out_root"] == ead.APP_DATA
    assert seen["check_mode"] is False


def test_scratch_round_trip(tmp_path):
    db = _tiny_db(tmp_path / "tiny.duckdb")
    out = tmp_path / "out"
    flags = ["--db", str(db), "--out", str(out), "--table", "race_to_track"]

    r = _run(*flags)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (out / "_manifest.json").exists()
    assert (out / "dimensions" / "race_to_track.parquet").exists()

    r = _run(*flags, "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "No drift" in r.stdout

    conn = duckdb.connect(str(db))
    conn.execute("INSERT INTO fct_lap_residuals VALUES (2024)")  # stats.total_laps 2 -> 3
    conn.close()

    r = _run(*flags, "--check")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "DRIFT DETECTED" in r.stdout


def test_guard_refuses_scratch_into_app_data(tmp_path):
    db = _tiny_db(tmp_path / "tiny.duckdb")
    manifest = ead.APP_DATA / "_manifest.json"
    before = manifest.stat().st_mtime_ns if manifest.exists() else None

    r = _run("--db", str(db))
    assert r.returncode == 2, r.stdout + r.stderr
    assert "refusing to write a scratch warehouse into app/public/data; pass --out" in r.stdout

    after = manifest.stat().st_mtime_ns if manifest.exists() else None
    assert before == after


def test_manifest_carries_provenance_block(tmp_path):
    import json

    db = _tiny_db(tmp_path / "tiny.duckdb")
    out = tmp_path / "out"
    r = _run("--db", str(db), "--out", str(out), "--table", "race_to_track")
    assert r.returncode == 0, r.stdout + r.stderr
    prov = json.loads((out / "_manifest.json").read_text())["provenance"]
    assert set(prov) == PROVENANCE_COLS | {"git_sha", "git_dirty"}
    assert prov["label_version"] == "v16"
    assert prov["model_version"] is None
    assert prov["label_sealed_on"] == "2026-10-26"
    assert isinstance(prov["git_dirty"], bool)


def test_check_ignores_git_fields_only(tmp_path):
    import json

    db = _tiny_db(tmp_path / "tiny.duckdb")
    out = tmp_path / "out"
    flags = ["--db", str(db), "--out", str(out), "--table", "race_to_track"]
    assert _run(*flags).returncode == 0
    mpath = out / "_manifest.json"
    m = json.loads(mpath.read_text())
    m["provenance"]["git_sha"] = "0" * 40
    m["provenance"]["git_dirty"] = not m["provenance"]["git_dirty"]
    mpath.write_text(json.dumps(m))
    assert _run(*flags, "--check").returncode == 0  # export-run fields are not drift
    m["provenance"]["label_version"] = "v15"
    mpath.write_text(json.dumps(m))
    assert _run(*flags, "--check").returncode == 1  # a data field is


TX11_TABLES = {
    "mart_race_driver_summary": 3,
    "mart_driver_season_summary": 2,
    "mart_metric_benchmark": 1,
    "fct_driver_isolation_race": 2,
    "fct_driver_isolation_stint": 2,  # AX-15a
}


def test_tx11_tables_have_rows_and_hash(tmp_path):
    import json

    db = _tiny_db(tmp_path / "tiny.duckdb")
    out = tmp_path / "out"
    for name in TX11_TABLES:
        r = _run("--db", str(db), "--out", str(out), "--table", name)
        assert r.returncode == 0, r.stdout + r.stderr
        entry = {t["name"]: t for t in json.loads((out / "_manifest.json").read_text())["tables"]}[name]
        assert entry["rows"] == TX11_TABLES[name]
        assert isinstance(entry["hash"], str) and len(entry["hash"]) == 32
        assert entry["partitioned"] is False


def test_tx11_check_fails_on_changed_row_with_same_stats(tmp_path):
    db = _tiny_db(tmp_path / "tiny.duckdb")
    out = tmp_path / "out"
    flags = ["--db", str(db), "--out", str(out), "--table", "mart_race_driver_summary"]
    assert _run(*flags).returncode == 0
    assert _run(*flags, "--check").returncode == 0

    conn = duckdb.connect(str(db))
    # Same row count, same stats block, one value moved: only rows/hash can see it.
    conn.execute("UPDATE mart_race_driver_summary SET rating_s = 0.5 WHERE driver_id = 'LEC'")
    conn.close()
    r = _run(*flags, "--check")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "DRIFT DETECTED" in r.stdout


def test_tx11_volatile_columns_do_not_move_the_hash(tmp_path):
    import json

    db = _tiny_db(tmp_path / "tiny.duckdb")
    out = tmp_path / "out"
    flags = ["--db", str(db), "--out", str(out), "--table", "mart_build_provenance"]
    assert _run(*flags).returncode == 0
    h1 = {t["name"]: t for t in json.loads((out / "_manifest.json").read_text())["tables"]}["mart_build_provenance"]["hash"]
    conn = duckdb.connect(str(db))
    conn.execute("UPDATE mart_build_provenance SET dbt_invocation_id = 'inv-2', built_at = TIMESTAMPTZ '2026-11-08 12:00:00+00'")
    conn.close()
    assert _run(*flags).returncode == 0
    h2 = {t["name"]: t for t in json.loads((out / "_manifest.json").read_text())["tables"]}["mart_build_provenance"]["hash"]
    assert h1 == h2


def test_ax15a_isolation_stint_is_in_tables():
    assert any(t[0] == "fct_driver_isolation_stint" and t[1] == "facts" for t in ead.TABLES)


@pytest.mark.skipif(not __import__("os").environ.get("TX13_EXPORT_DIR"), reason="set TX13_EXPORT_DIR to a scratch export")
def test_tx13_exported_calibration_flag_equals_seed():
    import csv
    import os

    seed = Path(__file__).resolve().parents[2] / "transform" / "seeds" / "circuit_reference.csv"
    with seed.open() as f:
        want = {r["circuit_key"]: r["calibration_flag"] for r in csv.DictReader(f)}
    got = dict(
        duckdb.sql(
            f"SELECT circuit_key, calibration_flag FROM read_parquet('{os.environ['TX13_EXPORT_DIR']}/dimensions/dim_circuits.parquet')"
        ).fetchall()
    )
    assert got == want
    assert all(v for v in got.values())
