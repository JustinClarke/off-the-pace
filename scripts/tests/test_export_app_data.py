"""TX-12: --db / --out flags, the scratch round trip, and the app/public/data guard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

import build_freshness as bf
import export_app_data as ead
from test_build_freshness import make_valid_marker, write_bronze_run

SCRIPT = Path(ead.__file__).resolve()
RUN1, RUN2 = "20261101T000000Z", "20261102T000000Z"


def _fresh(tmp_path: Path, name: str = "tiny.duckdb"):
    """A scratch warehouse with a valid full-build marker, plus the bronze dir it was built from."""
    db = _tiny_db(tmp_path / name)
    bronze = tmp_path / "bronze"
    write_bronze_run(bronze, RUN1)
    write_bronze_run(bronze, RUN2)
    make_valid_marker(db, bronze, tmp_path / "dbt")
    return db, bronze


def _remark(tmp_path: Path, db: Path, bronze: Path) -> None:
    """Re-record the marker after a test changed the warehouse on purpose."""
    make_valid_marker(db, bronze, tmp_path / "dbt")


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


FRESHNESS_KEYS = {"bronze_run_id", "build_id", "build_is_full", "dbt_node_count",
                  "source_coverage", "acknowledged_gaps"}


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
    assert args.bronze_dir == ead.BRONZE_DIR


def test_main_passes_default_paths(monkeypatch):
    seen = {}

    def spy(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(ead, "run_export", spy)
    ead.main([])
    assert seen["db_path"] == ead.DB_PATH
    assert seen["out_root"] == ead.APP_DATA
    assert seen["check_mode"] is False
    assert seen["bronze_dir"] == ead.BRONZE_DIR


def test_scratch_round_trip(tmp_path):
    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    flags = ["--db", str(db), "--out", str(out), "--table", "race_to_track", "--bronze-dir", str(bronze)]

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

    r = _run(*flags, "--check")  # the warehouse changed after its build: the gate refuses before any diff
    assert r.returncode == 1, r.stdout + r.stderr
    assert "warehouse changed after build inv-1" in r.stdout

    _remark(tmp_path, db, bronze)

    r = _run(*flags, "--check")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "DRIFT DETECTED" in r.stdout


def test_guard_refuses_scratch_into_app_data(tmp_path):
    db, _ = _fresh(tmp_path)
    manifest = ead.APP_DATA / "_manifest.json"
    before = manifest.stat().st_mtime_ns if manifest.exists() else None

    r = _run("--db", str(db))
    assert r.returncode == 2, r.stdout + r.stderr
    assert "refusing to write a scratch warehouse into app/public/data; pass --out" in r.stdout

    after = manifest.stat().st_mtime_ns if manifest.exists() else None
    assert before == after


def test_manifest_carries_provenance_block(tmp_path):
    import json

    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    r = _run("--db", str(db), "--out", str(out), "--table", "race_to_track", "--bronze-dir", str(bronze))
    assert r.returncode == 0, r.stdout + r.stderr
    prov = json.loads((out / "_manifest.json").read_text())["provenance"]
    assert set(prov) == PROVENANCE_COLS | {"git_sha", "git_dirty"} | FRESHNESS_KEYS
    assert prov["source_coverage"] == "complete" and prov["acknowledged_gaps"] == []
    assert prov["label_version"] == "v16"
    assert prov["model_version"] is None
    assert prov["label_sealed_on"] == "2026-10-26"
    assert isinstance(prov["git_dirty"], bool)


def test_check_ignores_git_fields_only(tmp_path):
    import json

    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    flags = ["--db", str(db), "--out", str(out), "--table", "race_to_track", "--bronze-dir", str(bronze)]
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

    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    for name in TX11_TABLES:
        r = _run("--db", str(db), "--out", str(out), "--table", name, "--bronze-dir", str(bronze))
        assert r.returncode == 0, r.stdout + r.stderr
        entry = {t["name"]: t for t in json.loads((out / "_manifest.json").read_text())["tables"]}[name]
        assert entry["rows"] == TX11_TABLES[name]
        assert isinstance(entry["hash"], str) and len(entry["hash"]) == 32
        assert entry["partitioned"] is False


def test_tx11_check_fails_on_changed_row_with_same_stats(tmp_path):
    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    flags = ["--db", str(db), "--out", str(out), "--table", "mart_race_driver_summary", "--bronze-dir", str(bronze)]
    assert _run(*flags).returncode == 0
    assert _run(*flags, "--check").returncode == 0

    conn = duckdb.connect(str(db))
    # Same row count, same stats block, one value moved: only rows/hash can see it.
    conn.execute("UPDATE mart_race_driver_summary SET rating_s = 0.5 WHERE driver_id = 'LEC'")
    conn.close()
    _remark(tmp_path, db, bronze)
    r = _run(*flags, "--check")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "DRIFT DETECTED" in r.stdout


def test_tx11_volatile_columns_do_not_move_the_hash(tmp_path):
    import json

    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    flags = ["--db", str(db), "--out", str(out), "--table", "mart_build_provenance", "--bronze-dir", str(bronze)]
    assert _run(*flags).returncode == 0
    h1 = {t["name"]: t for t in json.loads((out / "_manifest.json").read_text())["tables"]}["mart_build_provenance"]["hash"]
    conn = duckdb.connect(str(db))
    conn.execute("UPDATE mart_build_provenance SET dbt_invocation_id = 'inv-2', built_at = TIMESTAMPTZ '2026-11-08 12:00:00+00'")
    conn.close()
    _remark(tmp_path, db, bronze)
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



# ─── Freshness gate ───────────────────────────────────────────────────────────

def _flags(db, out, bronze, *extra):
    return ["--db", str(db), "--out", str(out), "--table", "race_to_track", "--bronze-dir", str(bronze), *extra]


def _manifest(out: Path) -> dict:
    import json

    return json.loads((out / "_manifest.json").read_text())


def _write_manifest(out: Path, m: dict) -> None:
    import json

    (out / "_manifest.json").write_text(json.dumps(m))


def test_export_refuses_missing_marker(tmp_path):
    db = _tiny_db(tmp_path / "tiny.duckdb")
    bronze = tmp_path / "bronze"
    write_bronze_run(bronze, RUN1)
    out = tmp_path / "out"
    r = _run(*_flags(db, out, bronze))
    assert r.returncode == 1, r.stdout + r.stderr
    assert f"ERROR: no build marker at {bf.marker_path(db.resolve())}; the warehouse has no recorded full build. " \
           "Run: make dbt-dev-full" in r.stdout
    assert not (out / "_manifest.json").exists()


def test_export_refuses_stale_bronze(tmp_path):
    db, bronze = _fresh(tmp_path)
    write_bronze_run(bronze, "20261110T000000Z")
    out = tmp_path / "out"
    r = _run(*_flags(db, out, bronze))
    assert r.returncode == 1, r.stdout + r.stderr
    assert f"ERROR: warehouse was built from bronze run {RUN2} but the latest bronze run is 20261110T000000Z. " \
           "Run: make dbt-dev-full" in r.stdout
    assert not (out / "_manifest.json").exists()


def test_export_fresh_marker_writes_four_provenance_keys(tmp_path):
    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    r = _run(*_flags(db, out, bronze))
    assert r.returncode == 0, r.stdout + r.stderr
    prov = _manifest(out)["provenance"]
    assert prov["bronze_run_id"] == RUN2
    assert prov["build_id"] == "inv-1"
    assert prov["build_is_full"] is True
    assert prov["dbt_node_count"] == 4


def test_check_passes_fresh_export(tmp_path):
    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    assert _run(*_flags(db, out, bronze)).returncode == 0
    r = _run(*_flags(db, out, bronze, "--check"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "No drift" in r.stdout and "STALE EXPORT" not in r.stdout and "MISMATCH" not in r.stdout


def test_check_fails_when_manifest_lacks_bronze_run_id(tmp_path):
    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    assert _run(*_flags(db, out, bronze)).returncode == 0
    m = _manifest(out)
    del m["provenance"]["bronze_run_id"]
    _write_manifest(out, m)
    r = _run(*_flags(db, out, bronze, "--check"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "STALE EXPORT: manifest provenance.bronze_run_id is missing (hand-edited or exported before the " \
           "freshness gate). Run: make app-data" in r.stdout


def test_check_fails_when_manifest_bronze_run_is_older(tmp_path):
    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    assert _run(*_flags(db, out, bronze)).returncode == 0
    m = _manifest(out)
    m["provenance"]["bronze_run_id"] = RUN1
    _write_manifest(out, m)
    r = _run(*_flags(db, out, bronze, "--check"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert f"STALE EXPORT: manifest bronze_run_id {RUN1} is older than latest bronze run {RUN2}. " \
           "Run: make dbt-dev-full app-data" in r.stdout


def test_check_fails_on_build_id_mismatch(tmp_path):
    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    assert _run(*_flags(db, out, bronze)).returncode == 0
    m = _manifest(out)
    m["provenance"]["build_id"] = "inv-old"
    _write_manifest(out, m)
    r = _run(*_flags(db, out, bronze, "--check"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "STALE EXPORT: manifest build_id inv-old does not match the warehouse build marker inv-1. " \
           "Run: make app-data" in r.stdout


def test_check_detects_row_count_mismatch(tmp_path):
    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    assert _run(*_flags(db, out, bronze)).returncode == 0
    m = _manifest(out)
    m["tables"][0]["rows"] += 1
    _write_manifest(out, m)
    r = _run(*_flags(db, out, bronze, "--check"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "MANIFEST/FILE MISMATCH: race_to_track rows differs from files on disk. Run: make app-data" in r.stdout


def test_check_detects_hash_mismatch(tmp_path):
    db, bronze = _fresh(tmp_path)
    out = tmp_path / "out"
    assert _run(*_flags(db, out, bronze)).returncode == 0
    # change the file on disk, not the manifest
    pq = out / "dimensions" / "race_to_track.parquet"
    conn = duckdb.connect()
    conn.execute(f"COPY (SELECT race_id, 'zzz' AS track_id FROM read_parquet('{pq}')) TO '{pq}' (FORMAT PARQUET)")
    conn.close()
    r = _run(*_flags(db, out, bronze, "--check"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "MANIFEST/FILE MISMATCH: race_to_track hash differs from files on disk. Run: make app-data" in r.stdout


def test_provenance_carries_acknowledged_gaps_and_fresh_check_passes(tmp_path):
    import json

    db, bronze = _fresh(tmp_path)
    # the latest run now holds the approved 2018 R14 italian_grand_prix error (ingestion/known_gaps.txt)
    write_bronze_run(bronze, "20261103T000000Z", rows=[
        {"season": 2018, "round_number": 14, "race_slug": "italian_grand_prix", "status": "error",
         "row_count": 0, "dq_passed": False}])
    _remark(tmp_path, db, bronze)
    out = tmp_path / "out"
    flags = ["--db", str(db), "--out", str(out), "--table", "race_to_track", "--bronze-dir", str(bronze)]
    r = _run(*flags)
    assert r.returncode == 0, r.stdout + r.stderr
    prov = json.loads((out / "_manifest.json").read_text())["provenance"]
    assert prov["source_coverage"] == "acknowledged_gaps_present"
    assert [(g["season"], g["round_number"], g["session_type"], g["race_slug"], g["status"], g["source"])
            for g in prov["acknowledged_gaps"]] == \
        [(2018, 14, "R", "italian_grand_prix", "error", "ingestion/known_gaps.txt")]
    assert prov["acknowledged_gaps"][0]["reason"]
    r = _run(*flags, "--check")
    assert r.returncode == 0, r.stdout + r.stderr
