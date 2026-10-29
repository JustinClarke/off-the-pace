"""Synthetic tests for the real-run CLI (run_wc03.py). Nothing here opens data/dev.duckdb, a scratch copy of it,
the bronze files or a pass table on disk: the data sources are replaced by a synthetic stand-in, and the
bronze-hash recipe is checked on a temporary folder of made-up files."""

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tasks.wake_calibration import contest as C
from tasks.wake_calibration import run_wc03 as R
from tasks.wake_calibration.tests.test_contest import world


class FakeSources:
    """Synthetic stand-in for ScratchSources. G3 values default to the registered ones (the synthetic panel is
    far smaller than 135,841 rows, so its row count and pooled slope are reported, not computed)."""

    def __init__(self, sha=R.G3_DB_SHA256, bronze=(R.G3_BRONZE_FILES, R.G3_BRONZE_SHA256), rows=R.G3_PANEL_ROWS,
                 slope=R.G3_POOLED_SLOPE, g2=(), seed=21, races_per_season=2, n_drivers=4):
        self.sha, self.bronze, self.rows, self.slope, self.g2 = sha, bronze, rows, slope, list(g2)
        self.prepared, self.panel, self.cal, _ = world(seed=seed, races_per_season=races_per_season,
                                                       n_drivers=n_drivers)
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

    def race_circuit_map(self):
        ids = {f"{s}_{r}": c for (s, r), (c, _) in self.cal.items()}
        return ids

    def pits(self):
        k = self.prepared[["season", "race_id", "driver", "lap"]].drop_duplicates()
        return k.assign(pit_in=False, pit_out=False)

    def lap_info(self):
        k = self.prepared[["season", "race_id", "driver", "lap"]].drop_duplicates()
        return k.assign(team=k["driver"].map(lambda d: "T" + str(int(d[1:]) // 2)), position=2.0)


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


def _registration(tmp_path, record=True, tamper=None, with_a5=True):
    """A temporary copy of the registration: the pre-registration, A1-A4 and (with_a5) A5, each hashed and,
    when record, its SHA-256 recorded on WC-03 in a temporary build log."""
    wc = tmp_path / "wc"
    (wc / "wi").mkdir(parents=True)
    amendments = (*R.AMENDMENTS, *((R.A5_DOC,) if with_a5 else ()))
    shas = {}
    for doc in (R.PREREG, *amendments):
        (wc / doc).write_text(f"text of {doc}\n")
        shas[doc] = hashlib.sha256((wc / doc).read_bytes()).hexdigest()
    item = {"id": "WC-03", "prereg": {"sha256": shas[R.PREREG]}}
    if record:
        item["amendments"] = [{"doc": d, "sha256": shas[d], "commit": "abc"} for d in amendments]
    if tamper:
        (wc / tamper).write_text("edited after hashing\n")
    log = tmp_path / "build-log.json"
    log.write_text(json.dumps({"items": [item]}))
    return log, wc


def test_registration_ready_only_when_every_amendment_is_hashed_committed_and_unchanged(tmp_path):
    assert R.A5_FIT_RACE_LIST is not None  # A5 decided (DD-WC14), so A5 is part of the registration
    all_amendments = (*R.AMENDMENTS, R.A5_DOC)
    log, wc = _registration(tmp_path)
    assert R.registration_problems(log, wc, committed=lambda p: True) == []
    for doc in all_amendments:  # each amendment, A5 included, refuses when not committed
        name = Path(doc).name
        probs = R.registration_problems(log, wc, committed=lambda p, n=name: p.name != n)
        assert len(probs) == 1 and doc in probs[0] and "not committed" in probs[0]
    log, wc = _registration(tmp_path / "b", record=False)
    probs = R.registration_problems(log, wc, committed=lambda p: True)
    assert len(probs) == len(all_amendments) and all("no SHA-256 recorded" in p for p in probs)
    for i, doc in enumerate(all_amendments):  # each amendment, A5 included, refuses when changed after hashing
        log, wc = _registration(tmp_path / f"c{i}", tamper=doc)
        probs = R.registration_problems(log, wc, committed=lambda p: True)
        assert len(probs) == 1 and doc in probs[0] and "differs" in probs[0]
    log, wc = _registration(tmp_path / "d")
    (wc / R.A5_DOC).unlink()
    probs = R.registration_problems(log, wc, committed=lambda p: True)
    assert probs == [f"{R.A5_DOC}: missing"]


def test_the_repository_registration_is_ready_today(tmp_path, monkeypatch):
    """Reads only the build log and the wi/ files: the pre-registration and A1-A5 are committed, unchanged and
    their SHA-256 recorded on WC-03 (A5 at 71cf22b, DD-WC14), so the registration check passes and the CLI gets
    past it to the next refusal (the scratch copy does not exist). A not-ready registration, from a temporary
    copy, still makes the CLI refuse at the registration check."""
    assert R.registration_problems() == []
    argv = ["--scratch-db", "/nonexistent/dev.duckdb", "--pass-table-dir", "/nonexistent",
            "--evidence-dir", "/nonexistent", "--owner-yes", "--check-only"]
    with pytest.raises(R.RefusedError) as e:
        R.main(argv)
    assert "registration is not ready" not in str(e.value) and "does not exist" in str(e.value)
    real = R.registration_problems
    log, wc = _registration(tmp_path, record=False)
    monkeypatch.setattr(R, "registration_problems", lambda: real(log, wc, committed=lambda p: True))
    with pytest.raises(R.RefusedError) as e:
        R.main(argv)
    assert "registration is not ready" in str(e.value) and R.A5_DOC in str(e.value)


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


def test_bronze_digest_hashes_an_nfd_name_as_its_nfc_form(tmp_path, monkeypatch):
    """Draft amendment A6: a file whose name glob returns in NFD (combining tilde) hashes as its NFC name."""
    import unicodedata
    nfc = unicodedata.normalize("NFC", "são_paulo_grand_prix")
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    content = b"laps content"
    rel_nfc = f"laps/season=2021/race={nfc}/laps.parquet"
    want_text = f"{hashlib.sha256(content).hexdigest()}  {rel_nfc}\n"
    want = hashlib.sha256(want_text.encode()).hexdigest()
    for name in (nfd, nfc):
        b = tmp_path / ("bronze_" + ("nfd" if name == nfd else "nfc"))
        f = b / f"laps/season=2021/race={name}/laps.parquet"
        f.parent.mkdir(parents=True)
        f.write_bytes(content)
        assert R.bronze_digest(b) == (1, want)
    # Independent of what the file system stores: an NFD path from glob is normalised before hashing.
    real = R.glob.glob
    monkeypatch.setattr(R.glob, "glob", lambda pattern: [unicodedata.normalize("NFD", p) for p in real(pattern)])
    assert R.bronze_digest(tmp_path / "bronze_nfd") == (1, want)


# ---------------------------------------------------------------- Table 2 and draft amendment A5 (decision records L4-L7)


@pytest.fixture
def judged_classes(monkeypatch):
    """As world() does: the synthetic car ahead is redrawn at every corner, so the class rule calls nearly
    every following pass racecraft and the dirty-air curve has empty bins (G7). Assign held up / dirty air at
    random among following passes with a measured reference, so the run reaches the contest."""
    from tasks.wake_calibration import estimator as E
    original = E.prepare_passes

    def prepare(passes, calendar, half_window=4):
        out = original(passes, calendar, half_window)
        rng = np.random.default_rng(0)
        j = out["pass_class"].notna() & (out["ref_status"] == "measured")
        out.loc[j, "pass_class"] = np.where(rng.random(int(j.sum())) < 0.5, E.HELD_UP, E.DIRTY_AIR)
        return out

    monkeypatch.setattr(E, "prepare_passes", prepare)


def test_full_synthetic_run_writes_table_2_after_table_1(tmp_path, judged_classes):
    ev = tmp_path / "ev"
    res = R.run_pipeline(FakeSources(seed=14, races_per_season=3, n_drivers=6), ev, n_draws=4, synthetic=True)
    assert res.contest is not None  # a world large enough for every bin: the contest and its context run
    card = (ev / "SCORECARD.md").read_text()
    lines = card.splitlines()
    assert lines[0] == res.verdict_line and lines[2] == C.WITHIN_STINT_LINE
    assert card.index("Table 1") < card.index("Table 2")
    t2 = card[card.index("Table 2"):]
    for item in ("pit-stop figure", "older cars", "sensitivity, reference window ±2 laps",
                 "sensitivity, without 2024 Las Vegas", "coverage 2025", "under-attack difference",
                 "mixed_stints", "reference-fit diagnostic"):
        assert item in t2, item
    body = t2.split("\n", 1)[1]  # the title says "never pass or fail"; the rows must not
    for word in (" pass ", " fail ", " passed ", " failed "):
        assert word not in body.lower().replace("|", " ")
    for f in ("counts_no_car_ahead.csv", "counts_no_reference.csv", "coverage_per_team.csv"):
        assert (ev / f).exists(), f
    prov = (ev / "PROVENANCE.txt").read_text()
    assert "VERDICT WRITTEN" in prov and prov.index("VERDICT WRITTEN") < prov.index(R.COMPLETED)


def test_a_failing_table_2_step_is_a_dash_and_the_verdict_stands(tmp_path):
    class NoPits(FakeSources):
        def pits(self):
            raise OSError("bronze laps unreadable")

    ev = tmp_path / "ev"
    res = R.run_pipeline(NoPits(), ev, n_draws=3, synthetic=True)
    card = (ev / "SCORECARD.md").read_text()
    assert card.splitlines()[0] == res.verdict_line
    assert "| bronze pit laps | — (not computed: OSError) |" in card
    assert "TABLE 2 bronze pit laps: not computed" in (ev / "PROVENANCE.txt").read_text()


def _wet_race_sources():
    """A fit race whose passes are all excluded (as 2022 Japan, 2024 São Paulo), with panel laps."""
    src = FakeSources(seed=14, races_per_season=3, n_drivers=6)
    wet = sorted(src.raw.loc[src.raw["season"] == 2023, "race_id"].unique())[0]
    src.raw = src.raw.copy()
    src.raw.loc[src.raw["race_id"] == wet, "reason"] = "wet"
    return src, wet


def test_a4_4b_as_written_stops_before_any_curve_when_a_fit_race_has_no_fit_pass(tmp_path):
    src, wet = _wet_race_sources()
    ev = tmp_path / "ev"
    assert R.run_pipeline(src, ev, n_draws=3, synthetic=True) is None
    first = (ev / "SCORECARD.md").read_text().splitlines()[0]
    assert first.startswith(C.VERDICT_TEXT[C.NO_VERDICT]) and wet in first and "A5" in first
    assert not (ev / "main_curve.csv").exists()


def test_a5_union_runs_with_a_fit_race_that_has_no_fit_pass(tmp_path, judged_classes):
    src, wet = _wet_race_sources()
    res = R.run_pipeline(src, tmp_path / "ev", n_draws=3, synthetic=True, a5="union")
    assert res is not None and wet in res.plan.fit_races
    assert res.contest is not None and np.isfinite(res.contest.theta_draws).all()


def test_a5_refusal_before_the_warehouse_only_while_a5_is_undecided(monkeypatch):
    ok = {"main": (["a", "b"], ["a", "b"]), "older": (["c"], [])}
    bad = {"main": (["a", "b"], ["a"]), "older": (["c"], ["c"])}
    R.a5_refusal(ok, None)  # the older era never refuses the run: it is report-only
    with pytest.raises(R.RefusedError):
        R.a5_refusal(bad, None)
    R.a5_refusal(bad, "union")
    assert R.A5_FIT_RACE_LIST == "union"  # the owner's decision, DD-WC14 option (a)
    R.a5_refusal(bad, R.A5_FIT_RACE_LIST)  # as main() calls it: the decided A5 does not refuse
    monkeypatch.setattr(R, "A5_FIT_RACE_LIST", None)  # undecided A5 still refuses, as main() calls it
    with pytest.raises(R.RefusedError):
        R.a5_refusal(bad, R.A5_FIT_RACE_LIST)


def test_fit_race_lists_use_structural_columns_and_find_the_race_with_no_fit_pass():
    src, wet = _wet_race_sources()
    lists = R._fit_race_lists(src.raw)
    built, contributing = lists["main"]
    assert wet in built and wet not in contributing


def test_registration_requires_a5_once_it_is_switched_on(tmp_path, monkeypatch):
    log, wc = _registration(tmp_path, with_a5=False)  # a registration with A1-A4 only
    monkeypatch.setattr(R, "A5_FIT_RACE_LIST", None)
    assert R.registration_problems(log, wc, committed=lambda p: True) == []
    for a5 in ("union", "built"):
        monkeypatch.setattr(R, "A5_FIT_RACE_LIST", a5)
        probs = R.registration_problems(log, wc, committed=lambda p: True)
        assert probs == [f"{R.A5_DOC}: missing"]
    monkeypatch.undo()
    assert R.A5_FIT_RACE_LIST == "union"  # as decided: A5 is required with no monkeypatch
    probs = R.registration_problems(log, wc, committed=lambda p: True)
    assert probs == [f"{R.A5_DOC}: missing"]


def _relabel(frame, cols, old="2025", new="2021"):
    out = frame.copy()
    for c in cols:
        if c in out:
            out[c] = out[c].astype(str).str.replace(old, new, regex=False)
    return out


class OlderSources(FakeSources):
    """Main world (2022-2024 fit, 2025 held out) plus an older world (2018-2020 fit, 2021 held out)."""

    def __init__(self):
        super().__init__(seed=14, races_per_season=3, n_drivers=6)
        op, opan, ocal, _ = world(seed=15, seasons=(2018, 2019, 2020), races_per_season=3, n_drivers=6)
        op = _relabel(op, ["race_id", "race", "race_key", "corner_key"])
        op["season"] = op["season"].replace(2025, 2021)
        opan = _relabel(opan, ["race_id", "lap_id", "stint_id"])
        opan["race_year"] = opan["race_year"].replace(2025, 2021)
        self.prepared = pd.concat([self.prepared, op], ignore_index=True)
        self.panel = pd.concat([self.panel, opan], ignore_index=True)
        self.cal = {**self.cal, **{((2021 if s == 2025 else s), r.replace("2025", "2021")): v
                                   for (s, r), v in ocal.items()}}
        self.raw = self.prepared[[c for c in self.raw.columns]]


def test_the_older_car_run_is_wired_in_after_the_main_scorecard_and_never_decides(tmp_path, judged_classes):
    ev = tmp_path / "ev"
    res = R.run_pipeline(OlderSources(), ev, n_draws=3, synthetic=True)
    assert res.era == "main"
    assert (ev / "older_curve.csv").exists() and (ev / "older_class_curve_dirty_air.csv").exists()
    card = (ev / "SCORECARD.md").read_text()
    assert card.splitlines()[0] == res.verdict_line  # the older result never changes the first line
    t2 = card[card.index("Table 2"):]
    assert "older cars (2018-2020 fit, 2021 scored; never decides the verdict): W1" in t2
    assert "older curve, 2018-2021: pit-stop figure" in t2
    oc = pd.read_csv(ev / "older_curve.csv")
    assert len(oc) == 24
    prov = (ev / "PROVENANCE.txt").read_text()
    assert prov.index("VERDICT WRITTEN") < prov.index("TABLE 2 older cars: done")


# ---------------------------------------------------------------- review fixes D1-D3 (Opus review, 2026-10-28)


def _prov(folder: Path, *lines: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "PROVENANCE.txt").write_text("".join(f"t {x}\n" for x in lines))


def test_d1_a_result_in_any_wc03_or_wc04_folder_refuses_a_new_run(tmp_path):
    root = tmp_path / "_evidence"
    _prov(root / "WC-04-2026-10-29", R.STARTED)  # started, nothing seen: a restart is allowed
    _prov(root / "WC-02-2026-10-27", R.STARTED, R.RESULTS)  # not a WC-03/WC-04 folder
    R.check_no_result_anywhere(root)
    _prov(root / "WC-03-2026-10-30" / "sub", R.STARTED, R.RESULTS)  # nested PROVENANCE counts too
    with pytest.raises(R.RefusedError, match="WC-03-2026-10-30"):
        R.check_no_result_anywhere(root)
    root2 = tmp_path / "_evidence2"
    _prov(root2 / "WC-04-a", R.STARTED, R.RESULTS, R.COMPLETED)
    with pytest.raises(R.RefusedError):
        R.check_no_result_anywhere(root2)


def test_d1_main_refuses_a_second_run_under_a_new_evidence_folder(tmp_path, monkeypatch):
    root = tmp_path / "_evidence"
    _prov(root / "WC-04-2026-10-29", R.STARTED, R.RESULTS, R.COMPLETED)
    monkeypatch.setattr(R, "EVIDENCE_ROOT", root)
    monkeypatch.setattr(R, "registration_problems", lambda *a, **k: [])
    db = tmp_path / "scratch" / "dev.duckdb"
    db.parent.mkdir()
    db.write_bytes(b"")  # an empty stand-in; main refuses before reading it
    preflight = []
    monkeypatch.setattr(R, "fit_race_preflight", lambda d: preflight.append(d))
    with pytest.raises(R.RefusedError, match="already exists"):
        R.main(["--scratch-db", str(db), "--pass-table-dir", str(tmp_path / "pt"),
                "--evidence-dir", str(root / "WC-04-2026-10-30"), "--owner-yes", "--check-only"])
    assert preflight == []  # refused before the pass table is read


def test_d1_a_real_call_of_run_pipeline_also_checks_every_folder(tmp_path, monkeypatch):
    root = tmp_path / "_evidence"
    _prov(root / "WC-03-x", R.STARTED, R.RESULTS)
    monkeypatch.setattr(R, "EVIDENCE_ROOT", root)
    src = FakeSources()
    with pytest.raises(R.RefusedError):
        R.run_pipeline(src, root / "WC-04-new")  # synthetic False: B and seed as registered
    assert src.read == []


def test_d2_an_error_after_g3_is_a_recorded_no_verdict_and_spends_the_run(tmp_path):
    class Broken(FakeSources):
        def passes(self):
            raise RuntimeError("pass table unreadable")

    ev = tmp_path / "ev"
    assert R.run_pipeline(Broken(), ev, n_draws=3, synthetic=True) is None
    first = (ev / "SCORECARD.md").read_text().splitlines()[0]
    assert first.startswith(C.VERDICT_TEXT[C.NO_VERDICT])
    assert "the run stopped with an error" in first and "RuntimeError: pass table unreadable" in first
    prov = (ev / "PROVENANCE.txt").read_text()
    assert prov.index(R.RESULTS) < prov.index("ERROR after") < prov.index(R.COMPLETED)
    assert "Traceback" in prov
    with pytest.raises(R.RefusedError):  # §0: spent, never repeated
        R.check_evidence_fresh(ev)


def test_d2_a5_incomplete_fit_race_list_is_recorded_as_no_verdict(tmp_path):
    src, wet = _wet_race_sources()
    full = src.race_circuit_map()
    src.race_circuit_map = lambda: {k: v for k, v in full.items() if k != wet}  # the calendar lacks one race
    ev = tmp_path / "ev"
    assert R.run_pipeline(src, ev, n_draws=3, synthetic=True, a5="union") is None
    first = (ev / "SCORECARD.md").read_text().splitlines()[0]
    assert first.startswith(C.VERDICT_TEXT[C.NO_VERDICT]) and R.FIT_RACE_LIST_CAUSE in first and wet in first
    assert not (ev / "main_curve.csv").exists()
    assert f"{R.COMPLETED}: no verdict ({R.FIT_RACE_LIST_CAUSE})" in (ev / "PROVENANCE.txt").read_text()


def test_d2_an_older_era_fit_race_list_problem_stays_in_table_2(tmp_path, judged_classes):
    src = OlderSources()
    full = FakeSources.race_circuit_map(src)
    older_race = sorted(r for r in full if r.startswith("2019_"))[0]
    src.race_circuit_map = lambda: {k: v for k, v in full.items() if k != older_race}
    ev = tmp_path / "ev"
    res = R.run_pipeline(src, ev, n_draws=3, synthetic=True, a5="union")
    assert res is not None
    card = (ev / "SCORECARD.md").read_text()
    assert card.splitlines()[0] == res.verdict_line
    assert R.FIT_RACE_LIST_CAUSE in card[card.index("Table 2"):]


def test_d2_an_error_assembling_table_2_keeps_the_verdict(tmp_path, monkeypatch):
    def boom(rows):
        raise ValueError("table 2 text")

    monkeypatch.setattr(R.RP, "table2_text", boom)
    ev = tmp_path / "ev"
    res = R.run_pipeline(FakeSources(), ev, n_draws=3, synthetic=True)
    assert res is not None
    assert (ev / "SCORECARD.md").read_text().splitlines()[0] == res.verdict_line
    prov = (ev / "PROVENANCE.txt").read_text()
    assert "TABLE 2 assembly: not computed (ValueError: table 2 text)" in prov
    assert f"{R.COMPLETED}: verdict {res.verdict_code}" in prov


def test_verdict_line_names_the_w_checks_not_run():
    code, line = C.verdict([C.Check("G7", False, "", "main/slow: point empty bins [7]")], None, None, None)
    assert code == C.NO_VERDICT and "a W check" not in line
    assert line.endswith("G7 failed: main/slow: point empty bins [7]; W1, W2, W3 not run")
    code, line = C.verdict([], C.Check("W1", True, "", ""), C.Check("W2", None, "", "", "undefined in a draw"),
                           C.Check("W3", True, "", ""))
    assert code == C.NO_VERDICT and line.endswith("W2 not assessable: undefined in a draw")
