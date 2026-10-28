"""Synthetic tests for the real-run CLI (run_wc03.py). Nothing here opens data/dev.duckdb, a scratch copy of it,
the bronze files or a pass table on disk: the data sources are replaced by a synthetic stand-in, and the
bronze-hash recipe is checked on a temporary folder of made-up files."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tasks.wake_calibration import contest as C
from tasks.wake_calibration import run_wc03 as R
from tasks.wake_calibration.tests.test_contest import world


class FakeSources:
    """Synthetic stand-in for ScratchSources. G3 values default to the registered ones (the synthetic panel is
    far smaller than 135,841 rows, so its row count and pooled slope are reported, not computed)."""

    def __init__(self, sha=R.G3_DB_SHA256, bronze=(R.G3_BRONZE_FILES, R.G3_BRONZE_SHA256), rows=R.G3_PANEL_ROWS,
                 slope=R.G3_POOLED_SLOPE, g2=(), seed=21):
        self.sha, self.bronze, self.rows, self.slope, self.g2 = sha, bronze, rows, slope, list(g2)
        self.prepared, self.panel, self.cal, _ = world(seed=seed, races_per_season=2, n_drivers=4)
        self.raw = self.prepared[[c for c in self.prepared.columns if c not in
                                  {"reason_wc03", "yielding", "circuit", "corner_key", "ref_spread_s",
                                   "leader_time_s", "racecraft", "pass_class", "under_attack", "gap_bin",
                                   "race_key"}]]
        self.read = []

    def db_sha256(self):
        self.read.append("sha")
        return self.sha

    def bronze_digest(self):
        self.read.append("bronze")
        return self.bronze

    def yardstick(self):
        self.read.append("panel")
        return self.panel, R.G3_PANEL_ROWS

    def panel_rows(self):
        return self.rows

    def pooled_slope(self):
        return self.slope

    def g2_mismatches(self):
        self.read.append("g2")
        return self.g2

    def passes(self):
        self.read.append("passes")
        return self.raw

    def calendar(self):
        return self.cal


# ---------------------------------------------------------------- refusals


def test_refuses_the_warehouse_and_anything_inside_data(tmp_path):
    with pytest.raises(R.RefusedError):
        R.check_scratch_db(R.WAREHOUSE)
    with pytest.raises(R.RefusedError):
        R.check_scratch_db(R.WAREHOUSE.parent / "scratch" / "dev.duckdb")
    other = tmp_path / "copy.duckdb"
    other.write_bytes(b"x")
    with pytest.raises(R.RefusedError):
        R.check_scratch_db(other)  # must be named dev.duckdb (§2d)
    good = tmp_path / "dev.duckdb"
    good.write_bytes(b"x")
    assert R.check_scratch_db(good) == good.resolve()


def _registration(tmp_path, record=True, tamper=None):
    wc = tmp_path / "wc"
    (wc / "wi").mkdir(parents=True)
    shas = {}
    for doc in (R.PREREG, *R.AMENDMENTS):
        (wc / doc).write_text(f"text of {doc}\n")
        shas[doc] = hashlib.sha256((wc / doc).read_bytes()).hexdigest()
    item = {"id": "WC-03", "prereg": {"sha256": shas[R.PREREG]}}
    if record:
        item["amendments"] = [{"doc": d, "sha256": shas[d], "commit": "abc"} for d in R.AMENDMENTS]
    if tamper:
        (wc / tamper).write_text("edited after hashing\n")
    log = tmp_path / "build-log.json"
    log.write_text(json.dumps({"items": [item]}))
    return log, wc


def test_registration_ready_only_when_every_amendment_is_hashed_committed_and_unchanged(tmp_path):
    log, wc = _registration(tmp_path)
    assert R.registration_problems(log, wc, committed=lambda p: True) == []
    probs = R.registration_problems(log, wc, committed=lambda p: "A4" not in p.name)
    assert len(probs) == 1 and "A4" in probs[0]
    log, wc = _registration(tmp_path / "b", record=False)
    assert len(R.registration_problems(log, wc, committed=lambda p: True)) == len(R.AMENDMENTS)
    log, wc = _registration(tmp_path / "c", tamper=R.AMENDMENTS[0])
    assert any("differs" in p for p in R.registration_problems(log, wc, committed=lambda p: True))


def test_the_repository_registration_is_not_ready_today():
    """Reads only the build log and the wi/ files: A1-A4 have no recorded SHA-256 and A4 is not committed, so
    the CLI must refuse. (When the owner records the digests this test is expected to need updating.)"""
    assert R.registration_problems() != []
    with pytest.raises(R.RefusedError):
        R.main(["--scratch-db", "/nonexistent/dev.duckdb", "--pass-table-dir", "/nonexistent",
                "--evidence-dir", "/nonexistent", "--owner-yes", "--check-only"])


def test_b_and_seed_are_fixed_outside_synthetic_tests(tmp_path):
    with pytest.raises(R.RefusedError):
        R.run_pipeline(FakeSources(), tmp_path / "ev", n_draws=10)


# ---------------------------------------------------------------- G3 first, then nothing else


def test_g3_failure_stops_before_anything_is_fitted_and_writes_the_registered_line(tmp_path):
    src = FakeSources(sha="0" * 64)
    out = R.run_pipeline(src, tmp_path / "ev", n_draws=3, synthetic=True)
    assert out is None
    card = (tmp_path / "ev" / "SCORECARD.md").read_text().splitlines()
    assert card[0].startswith(R.G3_FAIL_LINE)
    assert "panel" not in src.read and "passes" not in src.read and "g2" not in src.read
    assert not (tmp_path / "ev" / "main_curve.csv").exists()


def test_g3_checks_2_and_3_are_read_from_the_panel_only_after_1_and_4_pass(tmp_path):
    src = FakeSources(slope=R.G3_POOLED_SLOPE + 2e-9)
    assert R.run_pipeline(src, tmp_path / "ev", n_draws=3, synthetic=True) is None
    assert "G3.3" in (tmp_path / "ev" / "SCORECARD.md").read_text()
    src = FakeSources(bronze=(1213, R.G3_BRONZE_SHA256))
    assert R.run_pipeline(src, tmp_path / "ev2", n_draws=3, synthetic=True) is None
    assert "panel" not in src.read


def test_g2_failure_is_no_verdict_and_nothing_is_fitted(tmp_path):
    src = FakeSources(g2=["counts_by_season.csv"])
    assert R.run_pipeline(src, tmp_path / "ev", n_draws=3, synthetic=True) is None
    assert "G2 failed" in (tmp_path / "ev" / "SCORECARD.md").read_text()
    assert "passes" not in src.read


# ---------------------------------------------------------------- the whole order, synthetic, and no rerun


def test_full_synthetic_run_writes_the_evidence_and_refuses_a_second_start(tmp_path):
    ev = tmp_path / "ev"
    res = R.run_pipeline(FakeSources(), ev, n_draws=4, synthetic=True)
    assert res is not None
    for f in ("SCORECARD.md", "main_curve.csv", "class_curve_dirty_air.csv", "class_curve_held_up.csv",
              "PROVENANCE.txt"):
        assert (ev / f).exists(), f
    prov = (ev / "PROVENANCE.txt").read_text()
    assert R.STARTED in prov and R.RESULTS in prov and R.COMPLETED in prov
    names = [c.name for c in res.checks]
    assert names[:6] == ["G1", "G2", "G3.1", "G3.4", "G3.2", "G3.3"] and "G6" in names and "G7" in names
    assert next(c for c in res.checks if c.name == "G6").passed
    card = (ev / "SCORECARD.md").read_text().splitlines()
    assert card[0] == res.verdict_line and card[2] == C.WITHIN_STINT_LINE
    with pytest.raises(R.RefusedError):  # one run, no reruns (§0)
        R.run_pipeline(FakeSources(), ev, n_draws=4, synthetic=True)


def test_a_crash_before_any_result_may_be_restarted(tmp_path):
    ev = tmp_path / "ev"

    class Crash(FakeSources):
        def bronze_digest(self):
            raise RuntimeError("disk error")

    with pytest.raises(RuntimeError):
        R.run_pipeline(Crash(), ev, n_draws=3, synthetic=True)
    assert R.RESULTS not in (ev / "PROVENANCE.txt").read_text()
    R.check_evidence_fresh(ev)  # no refusal: nothing was seen


def test_g6_flags_a_lap_id_that_does_not_match_the_keys():
    src = FakeSources()
    panel = src.panel.copy()
    check, counts = R.g6_joins(panel, src.prepared, 2025)
    assert check.passed and counts["panel_laps_no_passes"] > 0  # lap 1 and the last lap have no passes
    i = panel.index[(panel["race_year"] == 2025) & (panel["lap_number"] == 5)][0]
    panel.loc[i, "lap_id"] = "wrong"
    check, counts = R.g6_joins(panel, src.prepared, 2025)
    assert not check.passed and counts["lap_id_mismatches"] == 1


# ---------------------------------------------------------------- G3 check 4 recipe


def test_bronze_digest_matches_the_registered_shell_recipe(tmp_path):
    b = tmp_path / "bronze"
    files = ["laps/season=2024/race=b/laps.parquet", "laps/season=2024/race=a/laps.parquet",
             "telemetry/season=2024/race=a/x.parquet", "track_status/season=2024/race=a/track_status.parquet",
             "schedule/season=2024/schedule.parquet", "circuit_info/season=2024/race=a/ci.parquet",
             "laps/season=2024/race=a/session=Q/q.parquet",  # deeper qualifying folder: not hashed
             "track_status/season=2024/race=a/other.parquet"]  # not track_status.parquet: not hashed
    for i, f in enumerate(files):
        (b / f).parent.mkdir(parents=True, exist_ok=True)
        (b / f).write_bytes(f"content {i}".encode())
    n, digest = R.bronze_digest(b)
    hashed = [f for f in files[:6]]
    lines = subprocess.run(["shasum", "-a", "256", *hashed], cwd=b, capture_output=True, text=True,
                           check=True).stdout
    sorted_text = subprocess.run(["sort", "-t", " ", "-k3"], input=lines, capture_output=True, text=True,
                                 env={"LC_ALL": "C"}, check=True).stdout
    want = hashlib.sha256(sorted_text.encode()).hexdigest()
    assert n == 6 and digest == want
