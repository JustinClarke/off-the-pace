"""Freshness gate: marker writer (after dbt) and validator (before export). No dbt, no real data."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pandas as pd
import pytest

import build_freshness as bf

NODES = {
    "model.p.a": ("model", {"enabled": True}),
    "seed.p.s": ("seed", {"enabled": True}),
    "test.p.t_err": ("test", {"enabled": True, "severity": "ERROR"}),
    "test.p.t_warn": ("test", {"enabled": True, "severity": "warn"}),
    "analysis.p.x": ("analysis", {"enabled": True}),
    "model.p.disabled": ("model", {"enabled": False}),
}
REQUIRED_IDS = ["model.p.a", "seed.p.s", "test.p.t_err", "test.p.t_warn"]


# ─── Fixtures / helpers (also imported by test_export_app_data.py) ────────────

def make_warehouse(path: Path, build_id: str = "inv-1", relations: tuple[str, ...] = bf.REQUIRED_RELATIONS) -> Path:
    conn = duckdb.connect(str(path))
    for r in relations:
        if r == "mart_build_provenance":
            conn.execute(f"CREATE TABLE {r} AS SELECT '{build_id}' AS dbt_invocation_id")
        else:
            conn.execute(f"CREATE TABLE {r} AS SELECT 1 AS x")
    conn.close()
    return path


ROW_DEFAULTS = {"season": 2030, "round_number": 1, "session_type": "R", "race_slug": "slug_0",
                "status": "ok", "row_count": 10, "dq_passed": True}


def write_laps(bronze: Path, season: int, session_type: str, slug: str, n: int) -> Path:
    path = bf.laps_artifact_path(bronze, season, session_type, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"lap": list(range(n))}).to_parquet(path)
    return path


def write_bronze_run(bronze: Path, run_id: str, statuses=("ok", "ok"), row_run_id: str | None = None,
                     rows: list[dict] | None = None) -> Path:
    """A fake manifest. Default: one distinct 10-lap session per status, ok ones with a matching laps parquet.
    `rows` gives full control (dicts overriding ROW_DEFAULTS); no laps parquet is written for those."""
    mdir = bronze / "manifests"
    mdir.mkdir(parents=True, exist_ok=True)
    f = mdir / f"run_{run_id}.parquet"
    if rows is None:
        rows = [{"round_number": i + 1, "race_slug": f"slug_{i}", "status": s} for i, s in enumerate(statuses)]
        for r in rows:
            if r["status"] == "ok":
                write_laps(bronze, 2030, "R", r["race_slug"], 10)
    full = [{**ROW_DEFAULTS, **r, "run_id": row_run_id or run_id} for r in rows]
    cols = ["run_id", *ROW_DEFAULTS]
    df = pd.DataFrame(full, columns=cols) if full else pd.DataFrame({c: pd.Series(dtype="object") for c in cols})
    df.to_parquet(f)
    return f


GAP_ITALIAN = "2018 R italian_grand_prix | round=14 | status=error | FastF1 IndexError in __fix_tyre_info"
GAP_BAHRAIN = "2026 R bahrain_grand_prix | round=16 | status=thin | laps.TyreLife 87% non-null, below the 90% bar"
GAP_MONACO = "2026 R monaco_grand_prix | round=6 | status=skip | merged telemetry covers 8.8% of laps"


def write_gaps(path: Path, *lines: str) -> Path:
    path.write_text("# test known gaps\n\n" + "\n".join(lines) + "\n")
    return path


def write_artifacts(
    target_dir: Path,
    *,
    build_id: str = "inv-1",
    manifest_id: str | None = None,
    started: datetime | None = None,
    which: str = "build",
    select=None,
    statuses: dict | None = None,
    drop: tuple[str, ...] = (),
    target: str = "dev",
) -> datetime:
    target_dir.mkdir(parents=True, exist_ok=True)
    started = started or (datetime.now(timezone.utc) + timedelta(seconds=30))
    ts = started.isoformat().replace("+00:00", "Z")
    statuses = statuses or {}
    results = []
    for uid in REQUIRED_IDS:
        if uid in drop:
            continue
        default = "pass" if uid.startswith("test.") else "success"
        results.append({"unique_id": uid, "status": statuses.get(uid, default)})
    rr = {
        "metadata": {"invocation_id": build_id, "invocation_started_at": ts, "dbt_version": "1.12.6"},
        "args": {
            "which": which, "select": select or [], "exclude": [], "selector": None, "resource_types": [],
            "exclude_resource_types": [], "target": target,
            "invocation_command": "dbt build --target dev" + (f" --select {select[0]}" if select else ""),
        },
        "results": results,
    }
    mf = {
        "metadata": {"invocation_id": manifest_id or build_id, "invocation_started_at": ts},
        "nodes": {uid: {"resource_type": rt, "config": cfg} for uid, (rt, cfg) in NODES.items()},
    }
    (target_dir / "run_results.json").write_text(json.dumps(rr))
    (target_dir / "manifest.json").write_text(json.dumps(mf))
    return started


def make_valid_marker(db: Path, bronze: Path, work: Path, build_id: str | None = None) -> dict:
    """Run the real writer against fake dbt artifacts. build_id defaults to the warehouse's provenance row."""
    if build_id is None:
        c = duckdb.connect(str(db), read_only=True)
        build_id = c.execute("SELECT dbt_invocation_id FROM mart_build_provenance").fetchone()[0]
        c.close()
    write_artifacts(work / "target", build_id=build_id)
    return bf.write_marker(db, bronze, work / "target")


@pytest.fixture
def env(tmp_path):
    db = make_warehouse(tmp_path / "w.duckdb")
    bronze = tmp_path / "bronze"
    write_bronze_run(bronze, "20261101T000000Z")
    write_bronze_run(bronze, "20261102T000000Z")
    return db, bronze, tmp_path


def _has(problems, fragment):
    return any(fragment in p for p in problems)


def _edit_marker(db: Path, **changes):
    mp = bf.marker_path(db)
    m = json.loads(mp.read_text())
    m.update(changes)
    mp.write_text(json.dumps(m))


# ─── Bronze ───────────────────────────────────────────────────────────────────

def test_latest_bronze_run_is_max_filename(env):
    _, bronze, _ = env
    write_bronze_run(bronze, "20261030T000000Z")  # created last, sorts first
    (bronze / "manifests" / "notes.parquet").write_bytes(b"x")  # not a run file
    assert bf.latest_bronze_run(bronze) == "20261102T000000Z"


def test_bronze_run_id_mismatch_is_corrupt(env):
    _, bronze, _ = env
    write_bronze_run(bronze, "20261103T000000Z", row_run_id="20261101T000000Z")
    info, problems = bf.check_bronze(bronze)
    assert _has(problems, "ERROR: bronze manifest run_20261103T000000Z.parquet run_id 20261101T000000Z "
                          "does not match its filename")


def test_incomplete_latest_bronze_run_fails(env):
    _, bronze, _ = env
    write_bronze_run(bronze, "20261103T000000Z", statuses=("ok", "thin", "skip", "error", "error"))
    _, problems = bf.check_bronze(bronze)
    assert _has(problems, "ERROR: bronze run 20261103T000000Z is incomplete:")
    assert _has(problems, "error=2, ok=1, skip=1, thin=1")
    assert _has(problems, "Fix bronze ingestion before building.")


def test_empty_latest_bronze_run_fails(env):
    _, bronze, _ = env
    write_bronze_run(bronze, "20261103T000000Z", statuses=())
    _, problems = bf.check_bronze(bronze)
    assert _has(problems, "is incomplete: no rows")


def test_no_bronze_manifests_fails_closed(tmp_path):
    _, problems = bf.check_bronze(tmp_path / "nothing")
    assert problems == [f"ERROR: no bronze run manifests under {tmp_path / 'nothing' / 'manifests'}"]


# ─── validate() ───────────────────────────────────────────────────────────────

def test_fresh_full_build_passes_and_returns_ids(env):
    db, bronze, work = env
    make_valid_marker(db, bronze, work)
    v = bf.validate(db, bronze)
    assert v.problems == []
    assert v.bronze_run_id == "20261102T000000Z"
    assert v.build_id == "inv-1"
    assert v.marker["is_full"] is True and v.marker["dbt_node_count"] == 4
    assert v.marker["dbt_nodes_expected"] == 4  # disabled model and analysis are not required


def test_marker_path_convention(tmp_path):
    assert bf.marker_path(tmp_path / "x.duckdb") == tmp_path / "x.duckdb.build.json"


def test_missing_marker_fails(env):
    db, bronze, _ = env
    v = bf.validate(db, bronze)
    assert f"ERROR: no build marker at {bf.marker_path(db)}; the warehouse has no recorded full build. " \
           "Run: make dbt-dev-full" in v.problems


@pytest.mark.parametrize("content", ["not json", "[]", json.dumps({"schema": 2}), json.dumps({"schema": 1})])
def test_unreadable_or_bad_schema_marker_fails(env, content):
    db, bronze, _ = env
    bf.marker_path(db).write_text(content)
    v = bf.validate(db, bronze)
    assert f"ERROR: build marker {bf.marker_path(db)} is unreadable or has unsupported schema. " \
           "Run: make dbt-dev-full" in v.problems


def test_stale_bronze_fails(env):
    db, bronze, work = env
    make_valid_marker(db, bronze, work)
    write_bronze_run(bronze, "20261110T000000Z")
    v = bf.validate(db, bronze)
    assert "ERROR: warehouse was built from bronze run 20261102T000000Z but the latest bronze run is " \
           "20261110T000000Z. Run: make dbt-dev-full" in v.problems


def test_partial_marker_fails(env):
    db, bronze, work = env
    make_valid_marker(db, bronze, work)
    _edit_marker(db, is_full=False, dbt_command="dbt build --select a")
    v = bf.validate(db, bronze)
    assert "ERROR: warehouse was built by a partial dbt run (dbt build --select a); app-data needs a full " \
           "build. Run: make dbt-dev-full" in v.problems


def test_failed_marker_fails(env):
    db, bronze, work = env
    make_valid_marker(db, bronze, work)
    _edit_marker(db, n_error=2, n_skipped=3, success=False)
    v = bf.validate(db, bronze)
    assert "ERROR: the last full build recorded 2 errors and 3 skipped nodes; app-data refuses to export. " \
           "Fix and run: make dbt-dev-full" in v.problems


def test_missing_required_relation_fails(env, tmp_path):
    _, bronze, work = env
    db = make_warehouse(tmp_path / "w2.duckdb", relations=("mart_build_provenance", "fct_lap_residuals"))
    make_valid_marker(db, bronze, work)
    v = bf.validate(db, bronze)
    assert f"ERROR: warehouse {db} is missing required relations: dim_drivers, race_to_track. " \
           "Run: make dbt-dev-full" in v.problems


def test_warehouse_modified_after_build_fails(env):
    db, bronze, work = env
    make_valid_marker(db, bronze, work)
    st = db.stat()
    os.utime(db, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    v = bf.validate(db, bronze)
    assert "ERROR: warehouse changed after build inv-1 (size or mtime differs from the marker); " \
           "rebuild with: make dbt-dev-full" in v.problems


def test_build_id_mismatch_with_provenance_table_fails(env):
    db, bronze, work = env
    make_valid_marker(db, bronze, work)
    _edit_marker(db, build_id="inv-other")
    v = bf.validate(db, bronze)
    assert "ERROR: marker build_id inv-other does not match mart_build_provenance.dbt_invocation_id inv-1; " \
           "rebuild with: make dbt-dev-full" in v.problems


def test_validate_fails_closed_on_exception(tmp_path):
    v = bf.validate(tmp_path / "does-not-exist.duckdb", tmp_path)
    assert v.problems and v.marker is None


# ─── Writer ───────────────────────────────────────────────────────────────────

def _write(env, **artifact_kwargs):
    db, bronze, work = env
    write_artifacts(work / "target", **artifact_kwargs)
    return bf.write_marker(db, bronze, work / "target")


def _refused(env, fragment, **artifact_kwargs):
    db, _, _ = env
    bf.marker_path(db).write_text("{}")  # an old marker must not survive a refused write
    with pytest.raises(bf.BuildFreshnessError) as ei:
        _write(env, **artifact_kwargs)
    assert _has(ei.value.problems, fragment), ei.value.problems
    assert not bf.marker_path(db).exists()


def test_writer_writes_full_marker(env):
    m = _write(env)
    db = env[0]
    assert json.loads(bf.marker_path(db).read_text()) == m
    assert m["schema"] == 1 and m["is_full"] and m["success"] and m["build_id"] == "inv-1"
    assert m["n_error"] == 0 and m["n_skipped"] == 0 and m["warn_tests"] == []
    assert m["bronze_run_id"] == "20261102T000000Z" and m["bronze_manifest_count"] == 2
    assert len(m["bronze_latest_manifest_sha256"]) == 64 and m["bronze_manifest_status_ok"] is True
    assert m["warehouse"]["size"] == db.stat().st_size and m["warehouse"]["mtime_ns"] == db.stat().st_mtime_ns
    assert not list(db.parent.glob("*.tmp"))


def test_writer_refuses_select(env):
    _refused(env, "ERROR: warehouse was built by a partial dbt run (dbt build --target dev --select a)",
             select=["a"])


def test_writer_refuses_non_build_command(env):
    _refused(env, "partial dbt run", which="run")


def test_writer_refuses_wrong_target(env):
    _refused(env, "partial dbt run", target="ci")


def test_writer_refuses_node_missing_from_results(env):
    _refused(env, "1 enabled nodes in manifest.json are missing from run_results.json", drop=("test.p.t_err",))


def test_writer_refuses_invocation_mismatch(env):
    _refused(env, "run_results.json invocation inv-1 differs from manifest.json invocation inv-2",
             manifest_id="inv-2")


def test_writer_refuses_bronze_changed_during_build(env):
    _, bronze, _ = env
    started = datetime.now(timezone.utc) + timedelta(seconds=30)
    newest = bf.list_bronze_runs(bronze)[-1]
    later = (started + timedelta(seconds=10)).timestamp()
    os.utime(newest, (later, later))
    _refused(env, "ERROR: bronze manifests changed during the dbt build; not writing a marker. Re-run the build.",
             started=started)


def test_writer_refuses_wal(env):
    db, _, _ = env
    Path(str(db) + ".wal").write_bytes(b"x")
    _refused(env, f"ERROR: {db.resolve()}.wal exists; checkpoint or remove it before building.")


def test_writer_refuses_skipped_required_node(env):
    _refused(env, "recorded 0 errors and 1 skipped nodes", statuses={"model.p.a": "skipped"})


def test_writer_refuses_error_node(env):
    _refused(env, "recorded 1 errors and 0 skipped nodes", statuses={"test.p.t_err": "fail"})


def test_writer_refuses_warn_on_error_severity_test(env):
    _refused(env, "recorded 1 errors", statuses={"test.p.t_err": "warn"})


def test_writer_allows_warn_on_warn_severity_test_and_surfaces_it(env, capsys):
    m = _write(env, statuses={"test.p.t_warn": "warn"})
    assert m["warn_tests"] == ["test.p.t_warn"] and m["n_warn"] == 1 and m["n_error"] == 0
    db, bronze, _ = env
    assert bf.validate(db, bronze).problems == []
    # the CLI prints it
    write_artifacts(env[2] / "target", statuses={"test.p.t_warn": "warn"})
    rc = bf.main(["write", "--db", str(db), "--bronze-dir", str(bronze), "--target-dir", str(env[2] / "target")])
    assert rc == 0
    assert "test.p.t_warn" in capsys.readouterr().out


def test_writer_refuses_provenance_binding_mismatch(env):
    _refused(env, "ERROR: marker build_id inv-9 does not match mart_build_provenance.dbt_invocation_id inv-1",
             build_id="inv-9")


def test_writer_refuses_incomplete_bronze(env):
    _, bronze, _ = env
    write_bronze_run(bronze, "20261103T000000Z", statuses=("ok", "thin"))
    _refused(env, "ERROR: bronze run 20261103T000000Z is incomplete:")


def test_writer_refuses_unreadable_artifacts(env):
    db, bronze, work = env
    with pytest.raises(bf.BuildFreshnessError) as ei:
        bf.write_marker(db, bronze, work / "no-target")
    assert _has(ei.value.problems, "cannot read dbt artifacts")
    assert not bf.marker_path(db).exists()


def test_cli_write_failure_exit_code_and_no_marker(env, capsys):
    db, bronze, work = env
    write_artifacts(work / "target", select=["a"])
    rc = bf.main(["write", "--db", str(db), "--bronze-dir", str(bronze), "--target-dir", str(work / "target")])
    assert rc == 1
    assert "partial dbt run" in capsys.readouterr().out
    assert not bf.marker_path(db).exists()


# ─── invalidate ───────────────────────────────────────────────────────────────

def test_invalidate_removes_marker_and_missing_is_not_an_error(env):
    db, bronze, work = env
    make_valid_marker(db, bronze, work)
    assert bf.marker_path(db).exists()
    assert bf.invalidate(db) is True
    assert not bf.marker_path(db).exists()
    assert bf.invalidate(db) is False
    assert bf.main(["invalidate", "--db", str(db)]) == 0


# ─── Acceptance: skips, approved known gaps, unapproved known gaps ────────────

PRIOR, LATEST = "20261101T000000Z", "20261102T000000Z"
SKIP_ROW = {"status": "skip", "row_count": 0, "dq_passed": False}  # a skip row carries no counts of its own


def _accept_env(tmp_path, latest_rows, prior_rows=(), gaps=(), laps=True):
    """Bronze with an earlier run (prior_rows, laps parquets written for ok ones) and a latest run."""
    bronze = tmp_path / "b"
    for r in prior_rows:
        if laps and r.get("status", "ok") == "ok" and r.get("row_count", 10) > 0:
            write_laps(bronze, r.get("season", 2030), r.get("session_type", "R"), r["race_slug"], r.get("row_count", 10))
    if prior_rows:
        write_bronze_run(bronze, PRIOR, rows=list(prior_rows))
    write_bronze_run(bronze, LATEST, rows=list(latest_rows))
    return bronze, write_gaps(tmp_path / "gaps.txt", *gaps)


def _check(tmp_path, latest_rows, prior_rows=(), gaps=(), laps=True):
    bronze, gp = _accept_env(tmp_path, latest_rows, prior_rows, gaps, laps)
    return bf.check_bronze(bronze, gp)


def _skip(slug="s1", rnd=1, **kw):
    return {"round_number": rnd, "race_slug": slug, **SKIP_ROW, **kw}


def _prior(slug="s1", rnd=1, **kw):
    return {"round_number": rnd, "race_slug": slug, "status": "ok", **kw}


def test_accepted_skip_when_prior_ok_exists(tmp_path):
    info, problems = _check(tmp_path, [_skip()], [_prior()])
    assert problems == [] and info["n_skip_accepted"] == 1 and info["n_ok"] == 0


def test_all_384_verified_skips_are_accepted(tmp_path):
    n = 384
    prior = [_prior(f"s{i}", i + 1, row_count=5 + i % 7) for i in range(n)]
    latest = [_skip(f"s{i}", i + 1) for i in range(n)]
    info, problems = _check(tmp_path, latest, prior)
    assert problems == []
    assert info["n_skip_accepted"] == 384 and info["n_ok"] == 0 and info["acknowledged_gaps"] == []
    assert info["status_ok"] is True


def test_skip_without_prior_ok_blocks(tmp_path):
    _, problems = _check(tmp_path, [_skip()], [_prior(status="error", row_count=0)])
    assert _has(problems, "2030 R1 s1 status=skip is not an accepted skip: no earlier manifest entry with status ok")


def test_skip_with_no_earlier_run_at_all_blocks(tmp_path):
    _, problems = _check(tmp_path, [_skip()])
    assert _has(problems, "no earlier manifest entry with status ok")


def test_skip_prior_ok_only_in_the_same_latest_run_does_not_count(tmp_path):
    _, problems = _check(tmp_path, [_skip(), {"round_number": 1, "race_slug": "s1", "status": "ok"}])
    assert _has(problems, "no earlier manifest entry with status ok")


def test_skip_prior_dq_failed_blocks(tmp_path):
    _, problems = _check(tmp_path, [_skip()], [_prior(dq_passed=False)])
    assert _has(problems, "has dq_passed=False")


def test_skip_prior_row_count_zero_blocks(tmp_path):
    _, problems = _check(tmp_path, [_skip()], [_prior(row_count=0)])
    assert _has(problems, "has row_count=0")


def test_skip_missing_laps_parquet_blocks(tmp_path):
    _, problems = _check(tmp_path, [_skip()], [_prior()], laps=False)
    assert _has(problems, "the laps parquet is missing (laps/season=2030/race=s1/2030_s1_laps.parquet)")


def test_skip_mismatched_row_count_blocks(tmp_path):
    bronze, gp = _accept_env(tmp_path, [_skip()], [_prior(row_count=10)])
    write_laps(bronze, 2030, "R", "s1", 9)
    _, problems = bf.check_bronze(bronze, gp)
    assert _has(problems, "the laps parquet has 9 rows but the manifest row_count is 10")


def test_quali_skip_uses_the_quali_path(tmp_path):
    prior = _prior(session_type="Q")
    latest = _skip(session_type="Q")
    info, problems = _check(tmp_path, [latest], [prior])
    assert problems == [] and info["n_skip_accepted"] == 1
    assert (tmp_path / "b/laps/season=2030/race=s1/session=Q/2030_s1_quali_laps.parquet").is_file()


def test_ok_row_needs_matching_laps_artifact(tmp_path):
    bronze, gp = _accept_env(tmp_path, [{"race_slug": "s1", "status": "ok", "row_count": 10}])
    _, problems = bf.check_bronze(bronze, gp)
    assert _has(problems, "status=ok but the laps parquet is missing")
    write_laps(bronze, 2030, "R", "s1", 11)
    _, problems = bf.check_bronze(bronze, gp)
    assert _has(problems, "status=ok but the laps parquet has 11 rows but the manifest row_count is 10")
    write_laps(bronze, 2030, "R", "s1", 10)
    info, problems = bf.check_bronze(bronze, gp)
    assert problems == [] and info["n_ok"] == 1


def test_approved_italian_error_is_acknowledged_not_ok(tmp_path):
    row = {"round_number": 14, "season": 2018, "race_slug": "italian_grand_prix", "status": "error",
           "row_count": 0, "dq_passed": False}
    info, problems = _check(tmp_path, [row], gaps=[GAP_ITALIAN])
    assert problems == []
    assert info["n_ok"] == 0 and info["n_skip_accepted"] == 0
    assert info["acknowledged_gaps"] == [{
        "season": 2018, "round_number": 14, "session_type": "R", "race_slug": "italian_grand_prix",
        "status": "error", "reason": "FastF1 IndexError in __fix_tyre_info", "source": "ingestion/known_gaps.txt"}]


def test_approved_bahrain_thin_is_acknowledged_not_ok(tmp_path):
    row = {"round_number": 16, "season": 2026, "race_slug": "bahrain_grand_prix", "status": "thin", "row_count": 1145}
    info, problems = _check(tmp_path, [row], gaps=[GAP_BAHRAIN])
    assert problems == [] and info["n_ok"] == 0
    assert [(g["season"], g["round_number"], g["status"]) for g in info["acknowledged_gaps"]] == [(2026, 16, "thin")]


def test_wrong_round_same_slug_blocks(tmp_path):
    row = {"round_number": 15, "season": 2018, "race_slug": "italian_grand_prix", "status": "error"}
    info, problems = _check(tmp_path, [row], gaps=[GAP_ITALIAN])
    assert _has(problems, "matches a ingestion/known_gaps.txt entry only by season, session and slug, not round")
    assert info["acknowledged_gaps"] == []


def test_wrong_slug_same_round_blocks(tmp_path):
    row = {"round_number": 14, "season": 2018, "race_slug": "other_grand_prix", "status": "error"}
    info, problems = _check(tmp_path, [row], gaps=[GAP_ITALIAN])
    assert _has(problems, "2018 R14 other_grand_prix status=error is not ok and is not an approved known gap")
    assert info["acknowledged_gaps"] == []


def test_wrong_season_blocks(tmp_path):
    row = {"round_number": 14, "season": 2019, "race_slug": "italian_grand_prix", "status": "error"}
    _, problems = _check(tmp_path, [row], gaps=[GAP_ITALIAN])
    assert _has(problems, "2019 R14 italian_grand_prix status=error is not ok and is not an approved known gap")


def test_wrong_session_type_blocks(tmp_path):
    row = {"round_number": 14, "season": 2018, "session_type": "Q", "race_slug": "italian_grand_prix",
           "status": "error"}
    _, problems = _check(tmp_path, [row], gaps=[GAP_ITALIAN])
    assert _has(problems, "2018 Q14 italian_grand_prix status=error is not ok and is not an approved known gap")


def test_wrong_status_for_approved_gap_blocks(tmp_path):
    row = {"round_number": 14, "season": 2018, "race_slug": "italian_grand_prix", "status": "thin"}
    info, problems = _check(tmp_path, [row], gaps=[GAP_ITALIAN])
    assert _has(problems, "status=thin but the approved known gap expects status=error")
    assert info["acknowledged_gaps"] == []


def test_entry_not_on_the_allow_list_is_unapproved_even_if_it_matches(tmp_path):
    # the file says italian is "thin": that exact tuple is not on the allow-list
    gap = "2018 R italian_grand_prix | round=14 | status=thin | wrongly recorded"
    row = {"round_number": 14, "season": 2018, "race_slug": "italian_grand_prix", "status": "thin"}
    _, problems = _check(tmp_path, [row], gaps=[gap])
    assert _has(problems, "is an unapproved known gap")


def test_unacknowledged_error_thin_and_unknown_status_block(tmp_path):
    rows = [{"round_number": 1, "race_slug": "a", "status": "error"},
            {"round_number": 2, "race_slug": "b", "status": "thin"},
            {"round_number": 3, "race_slug": "c", "status": "weird"},
            {"round_number": 4, "race_slug": "d", "status": None}]
    _, problems = _check(tmp_path, rows)
    assert _has(problems, "2030 R1 a status=error is not ok and is not an approved known gap")
    assert _has(problems, "2030 R2 b status=thin is not ok and is not an approved known gap")
    assert _has(problems, "2030 R3 c has unknown status 'weird'")
    assert _has(problems, "2030 R4 d has unknown status None")
    assert _has(problems, "ERROR: bronze run 20261102T000000Z is incomplete: 4 of 4 rows are not accepted")


MONACO_PRIOR = {"season": 2026, "round_number": 6, "race_slug": "monaco_grand_prix", "row_count": 1452}
MONACO_SKIP = {"season": 2026, "round_number": 6, "race_slug": "monaco_grand_prix", **SKIP_ROW}


def test_monaco_shaped_documented_verified_skip_passes(tmp_path):
    info, problems = _check(tmp_path, [MONACO_SKIP], [MONACO_PRIOR], gaps=[GAP_MONACO])
    assert problems == [] and info["status_ok"] is True
    assert info["n_skip_accepted"] == 1 and info["n_ok"] == 0 and info["acknowledged_gaps"] == []


def test_monaco_is_not_on_the_allow_list():
    assert not any(g[3] == "monaco_grand_prix" for g in bf.APPROVED_GAPS)


@pytest.mark.parametrize("prior_kw, fragment", [
    ({"status": "error", "row_count": 0}, "no earlier manifest entry with status ok"),
    ({"dq_passed": False}, "dq_passed=False"),
    ({"row_count": 0}, "row_count=0"),
])
def test_documented_skip_with_failed_prior_check_blocks(tmp_path, prior_kw, fragment):
    info, problems = _check(tmp_path, [MONACO_SKIP], [{**MONACO_PRIOR, **prior_kw}], gaps=[GAP_MONACO])
    assert _has(problems, f"2026 R6 monaco_grand_prix status=skip is not an accepted skip: ") and _has(problems, fragment)
    assert info["n_skip_accepted"] == 0


def test_documented_skip_with_missing_laps_blocks(tmp_path):
    _, problems = _check(tmp_path, [MONACO_SKIP], [MONACO_PRIOR], gaps=[GAP_MONACO], laps=False)
    assert _has(problems, "monaco_grand_prix status=skip is not an accepted skip: the laps parquet is missing")


def test_documented_skip_with_count_mismatch_blocks(tmp_path):
    bronze, gp = _accept_env(tmp_path, [MONACO_SKIP], [MONACO_PRIOR], [GAP_MONACO])
    write_laps(bronze, 2026, "R", "monaco_grand_prix", 1451)
    _, problems = bf.check_bronze(bronze, gp)
    assert _has(problems, "the laps parquet has 1451 rows but the manifest row_count is 1452")


def test_unapproved_documented_error_blocks(tmp_path):
    gap = "2030 R a | round=1 | status=error | documented only"
    row = {"round_number": 1, "race_slug": "a", "status": "error"}
    info, problems = _check(tmp_path, [row], gaps=[gap])
    assert _has(problems, "2030 R1 a status=error is an unapproved known gap")
    assert info["acknowledged_gaps"] == []


def test_unapproved_documented_thin_blocks(tmp_path):
    gap = "2030 R a | round=1 | status=thin | documented only"
    row = {"round_number": 1, "race_slug": "a", "status": "thin"}
    info, problems = _check(tmp_path, [row], gaps=[gap])
    assert _has(problems, "2030 R1 a status=thin is an unapproved known gap")
    assert info["acknowledged_gaps"] == []


def test_documented_ok_row_passes_when_it_verifies(tmp_path):
    gap = "2030 R a | round=1 | status=ok | documented only"
    bronze, gp = _accept_env(tmp_path, [{"round_number": 1, "race_slug": "a", "status": "ok", "row_count": 10}],
                             gaps=[gap])
    write_laps(bronze, 2030, "R", "a", 10)
    info, problems = bf.check_bronze(bronze, gp)
    assert problems == [] and info["n_ok"] == 1


def test_known_gap_not_in_latest_run_does_not_block(tmp_path):
    info, problems = _check(tmp_path, [_skip()], [_prior()], gaps=[GAP_MONACO, GAP_ITALIAN, GAP_BAHRAIN])
    assert problems == []


# ─── known_gaps.txt parsing ───────────────────────────────────────────────────

@pytest.mark.parametrize("line", [
    "2018 R italian_grand_prix",                                          # old format, no round/status/reason
    "2018 R italian_grand_prix | round=14 | status=error",                # no reason field
    "2018 R italian_grand_prix | round=14 | status=error |",              # empty reason
    "2018 R italian_grand_prix | round=14 | status=error |    ",         # blank reason
    "2018 R italian_grand_prix | 14 | status=error | why",                # round not round=N
    "2018 R italian_grand_prix | round=x | status=error | why",
    "2018 R italian_grand_prix | round=14 | status=broken | why",        # unknown status
    "2018 X italian_grand_prix | round=14 | status=error | why",         # unknown session type
    "20x8 R italian_grand_prix | round=14 | status=error | why",
    "2018 R Italian GP | round=14 | status=error | why",
    "2018 R | round=14 | status=error | why",
])
def test_malformed_known_gaps_line_is_refused(tmp_path, line):
    gp = write_gaps(tmp_path / "g.txt", GAP_ITALIAN, line)
    with pytest.raises(bf.BuildFreshnessError) as ei:
        bf.parse_known_gaps(gp)
    assert _has(ei.value.problems, "ingestion/known_gaps.txt line 4 is malformed") or \
        _has(ei.value.problems, "line 4 is malformed")


def test_empty_reason_is_refused_with_clear_message(tmp_path):
    gp = write_gaps(tmp_path / "g.txt", "2018 R italian_grand_prix | round=14 | status=error |")
    with pytest.raises(bf.BuildFreshnessError) as ei:
        bf.parse_known_gaps(gp)
    assert _has(ei.value.problems, "the reason is empty")


def test_duplicate_and_missing_known_gaps_are_refused(tmp_path):
    with pytest.raises(bf.BuildFreshnessError) as ei:
        bf.parse_known_gaps(write_gaps(tmp_path / "g.txt", GAP_ITALIAN, GAP_ITALIAN))
    assert _has(ei.value.problems, "duplicate entry")
    with pytest.raises(bf.BuildFreshnessError):
        bf.parse_known_gaps(tmp_path / "missing.txt")


def test_reason_may_contain_pipes_and_comments_are_ignored(tmp_path):
    gp = write_gaps(tmp_path / "g.txt", "# c", "2018 R italian_grand_prix | round=14 | status=error | a | b")
    (g,) = bf.parse_known_gaps(gp)
    assert g.reason == "a | b" and g.round_number == 14


def test_malformed_known_gaps_blocks_the_bronze_check(tmp_path):
    row = {"round_number": 1, "race_slug": "a", "status": "ok"}
    bronze, _ = _accept_env(tmp_path, [row])
    write_laps(bronze, 2030, "R", "a", 10)
    gp = write_gaps(tmp_path / "bad.txt", "2018 R italian_grand_prix")
    _, problems = bf.check_bronze(bronze, gp)
    assert _has(problems, "is malformed")


def test_repo_known_gaps_file_parses_with_the_documented_entries():
    gaps = {(g.season, g.session_type, g.round_number, g.race_slug, g.expected_status): g
            for g in bf.parse_known_gaps(bf.KNOWN_GAPS_FILE)}
    assert set(gaps) == {(2018, "R", 14, "italian_grand_prix", "error"),
                         (2026, "R", 16, "bahrain_grand_prix", "thin"),
                         (2026, "R", 6, "monaco_grand_prix", "skip")}
    assert all(g.reason for g in gaps.values())
    assert set(bf.APPROVED_GAPS) == {(2018, "R", 14, "italian_grand_prix", "error"),
                                     (2026, "R", 16, "bahrain_grand_prix", "thin")}


# ─── Writer: acknowledged gaps, source coverage, lock ─────────────────────────

def _gap_writer_env(env, gaps):
    db, bronze, work = env
    rows = [{"season": 2018, "round_number": 14, "race_slug": "italian_grand_prix", "status": "error",
             "row_count": 0, "dq_passed": False},
            {"round_number": 1, "race_slug": "a", "status": "ok"}]
    write_bronze_run(bronze, "20261103T000000Z", rows=rows)
    write_laps(bronze, 2030, "R", "a", 10)
    write_artifacts(work / "target")
    return bf.write_marker(db, bronze, work / "target", known_gaps_path=write_gaps(work / "g.txt", *gaps))


def test_marker_records_acknowledged_gaps_and_source_coverage(env):
    m = _gap_writer_env(env, [GAP_ITALIAN])
    assert m["source_coverage"] == "acknowledged_gaps_present"
    assert m["n_acknowledged_gaps"] == 1 and m["n_sessions_ok"] == 1
    assert m["acknowledged_gaps"][0]["race_slug"] == "italian_grand_prix"
    assert m["acknowledged_gaps"][0]["source"] == "ingestion/known_gaps.txt"
    db = env[0]
    assert json.loads(bf.marker_path(db).read_text())["acknowledged_gaps"] == m["acknowledged_gaps"]


def test_cli_prints_source_coverage_and_known_gap_line(env, capsys):
    db, bronze, work = env
    rows = [{"season": 2018, "round_number": 14, "race_slug": "italian_grand_prix", "status": "error",
             "row_count": 0, "dq_passed": False}]
    write_bronze_run(bronze, "20261103T000000Z", rows=rows)
    write_artifacts(work / "target")
    gp = write_gaps(work / "g.txt", GAP_ITALIAN)
    rc = bf.main(["write", "--db", str(db), "--bronze-dir", str(bronze), "--target-dir", str(work / "target"),
                  "--known-gaps", str(gp)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "source_coverage=acknowledged_gaps_present" in out
    assert "KNOWN GAP (acknowledged, not complete coverage): 2018 R14 italian_grand_prix status=error: " \
           "FastF1 IndexError in __fix_tyre_info" in out


def test_marker_without_gaps_is_complete(env):
    m = _write(env)
    assert m["source_coverage"] == "complete" and m["acknowledged_gaps"] == [] and m["n_acknowledged_gaps"] == 0
    assert m["n_sessions_ok"] == 2


def test_writer_accepts_documented_verified_skip_in_latest_run(env):
    db, bronze, work = env
    write_bronze_run(bronze, "20261103T000000Z", rows=[
        {"season": 2026, "round_number": 6, "race_slug": "monaco_grand_prix", **SKIP_ROW}])
    write_bronze_run(bronze, "20261102T120000Z", rows=[
        {"season": 2026, "round_number": 6, "race_slug": "monaco_grand_prix", "row_count": 1452}])
    write_laps(bronze, 2026, "R", "monaco_grand_prix", 1452)
    write_artifacts(work / "target")
    m = bf.write_marker(db, bronze, work / "target", known_gaps_path=write_gaps(work / "g.txt", GAP_MONACO))
    assert m["n_acknowledged_gaps"] == 0 and m["source_coverage"] == "complete"


def test_writer_refuses_unapproved_known_gap_error_in_latest_run(env):
    db, bronze, work = env
    write_bronze_run(bronze, "20261103T000000Z", rows=[
        {"season": 2026, "round_number": 6, "race_slug": "monaco_grand_prix", "status": "error"}])
    write_artifacts(work / "target")
    gap = "2026 R monaco_grand_prix | round=6 | status=error | documented only"
    with pytest.raises(bf.BuildFreshnessError) as ei:
        bf.write_marker(db, bronze, work / "target", known_gaps_path=write_gaps(work / "g.txt", gap))
    assert _has(ei.value.problems, "2026 R6 monaco_grand_prix status=error is an unapproved known gap")
    assert not bf.marker_path(db).exists()


def test_writer_refuses_when_bronze_lock_verify_fails(env, monkeypatch):
    monkeypatch.setattr(bf, "_bronze_lock_verify", lambda d: ["changed: laps/x.parquet"])
    _refused(env, "ERROR: bronze_lock verify failed for")


def test_bronze_lock_verify_is_real_and_read_only(tmp_path, monkeypatch):
    monkeypatch.undo()  # drop the autouse stub: exercise the real bronze_lock.verify
    bronze = tmp_path / "bronze"
    (bronze / "laps").mkdir(parents=True)
    f = bronze / "laps" / "x.parquet"
    f.write_bytes(b"abc")
    assert bf._bronze_lock_verify(bronze) == ["no MANIFEST.json"]
    spec = bf.importlib.util.spec_from_file_location("bl", bf.BRONZE_LOCK_PY)
    mod = bf.importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.write_manifest(bronze)
    assert bf._bronze_lock_verify(bronze) == []
    before = {p: p.stat().st_mtime_ns for p in bronze.rglob("*") if p.is_file()}
    assert bf._bronze_lock_verify(bronze) == []
    assert {p: p.stat().st_mtime_ns for p in bronze.rglob("*") if p.is_file()} == before
    f.write_bytes(b"abd")
    assert bf._bronze_lock_verify(bronze) == ["changed: laps/x.parquet"]


def test_marker_missing_new_keys_is_unsupported(env):
    db, bronze, work = env
    make_valid_marker(db, bronze, work)
    mp = bf.marker_path(db)
    m = json.loads(mp.read_text())
    del m["source_coverage"]
    mp.write_text(json.dumps(m))
    assert any("unreadable or has unsupported schema" in p for p in bf.validate(db, bronze).problems)
