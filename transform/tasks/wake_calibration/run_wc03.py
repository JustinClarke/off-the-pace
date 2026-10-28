"""
WC-03 / WC-04 real run: the one run of the pre-registration (§0), in the registered order.

    cd transform && python -m tasks.wake_calibration.run_wc03 \\
        --scratch-db <scratch folder>/dev.duckdb --pass-table-dir <scratch pass-table folder> \\
        --evidence-dir ../_roadmap/_wake-calibration/_evidence/WC-04-<date> --owner-yes

THIS HAS NOT BEEN RUN ON REAL DATA. It is tested on synthetic inputs only (tests/test_run_wc03.py).

It refuses to start unless all of these hold:
  - the pre-registration and every amendment in AMENDMENTS is committed, unchanged against HEAD, and its
    SHA-256 is recorded on WC-03 in status/build-log.json (BUILD-ORDER rule 4; `prereg.sha256` and
    `amendments[*].sha256`) and matches the file;
  - --owner-yes is given (rule 3: the owner's yes to the run itself);
  - --scratch-db is a file named dev.duckdb outside data/ (rule 5; §2d), opened read_only;
  - the evidence folder holds no result from an earlier start (§0: one run, no reruns).

Order (§12a): G1 (the committed synthetic suite; a failure refuses the run before any data is read) -> G3 (checks 1 and 4 before anything is read from the warehouse, then the yardstick panel is
built by the wrapper and checks 2-3) -> G2 (WC-01 count files byte for byte) -> prepare passes, G6 joins, G4
leakage (asserted inside the fits) -> curves, θ_now, scored set, contest -> G5, G7, W1-W3 -> verdict ->
SCORECARD.md (Table 1). Then, report-only (Table 2, §12b; never a verdict input, each step logged and, if it
cannot be computed, shown as "—" with the reason): §12b counts, coverage and contest per team, mixed stints
and gains, under attack, the §11 pit-stop figure (pitstop.py), the older-car run (decision record L6), the
sensitivity runs (sensitivity.py). SCORECARD.md is then rewritten with Table 2 and, when W1 holds but not in
a sensitivity run, a line saying so right after the first two lines (§12b). If G3 fails the run stops before anything is fitted, writes the registered first line and
nothing else. The pass table is rebuilt beforehand with the committed builder into --pass-table-dir:

    python -m tasks.wake_calibration.build_pass_table --out <scratch pass-table folder> --workers 6

B = 1,000 and seed 20261027 are not options (§8c).
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import numpy as np
import pandas as pd

from tasks.wake_calibration import contest as C
from tasks.wake_calibration import estimator as E
from tasks.wake_calibration import report as RP

REPO = Path(__file__).resolve().parents[3]
WC = REPO / "_roadmap/_wake-calibration"
BUILD_LOG = WC / "status/build-log.json"
PREREG = "wi/WC-03-preregistration-DRAFT.md"
AMENDMENTS = (
    "wi/WC-03-amendment-A1-circuit-bootstrap.md",
    "wi/WC-03-amendment-A2-no-reference-class.md",
    "wi/WC-03-amendment-A3-last-lap-exclusion.md",
    "wi/WC-03-amendment-A4-rulings.md",
)
# DRAFT amendment A5 (wi/WC-03-amendment-A5-fit-race-list-DRAFT.md): None = A4 ruling 4b as written. The owner
# sets "union" (option a) or "built" (option b) once A5 is decided, committed and its SHA-256 recorded; the
# CLI then also requires A5's digest (registration_problems). Not to be changed by an agent.
A5_DOC = "wi/WC-03-amendment-A5-fit-race-list-DRAFT.md"
A5_FIT_RACE_LIST: str | None = "union"
WAREHOUSE = REPO / "data/dev.duckdb"
BRONZE = REPO / "data/bronze"
D1_SCRIPT = REPO / "_roadmap/_fixes/_evidence/wi-12-2026-09-27/d1_build_panels_wi12.py"
WC01_EVIDENCE = WC / "_evidence/WC-01-2026-10-27"
G2_FILES = ("counts_by_season.csv", "passes_by_corner_class.csv", "exclusion_reasons_by_season.csv")

# G3 (§0, §12a), registered values.
G3_DB_SHA256 = "7173444b0745130769863c123fb5c04c7e5edd8be7a1fb2dbf614637d3214f9f"
G3_PANEL_ROWS = 135_841
G3_POOLED_SLOPE = 0.4777453471
G3_POOLED_TOL = 1e-9
G3_BRONZE_FILES = 1_214
G3_BRONZE_SHA256 = "aed1c27da1cc00fb80eea470bb0c5c4879ee09556c81ff35bc17ad4aff1690b4"
G3_BRONZE_GLOBS = (
    *[f"{t}/season=*/race=*/*.parquet" for t in ("laps", "race_control", "results", "weather", "telemetry")],
    "track_status/season=*/race=*/track_status.parquet",
    "circuit_info/season=*/race=*/*.parquet",
    "schedule/season=*/schedule.parquet",
)
G3_FAIL_LINE = "No verdict: G3 failed, the input data has changed since 2026-10-28"

STARTED, RESULTS, COMPLETED = "RUN START", "RESULT WRITING STARTED", "RUN COMPLETED"


class RefusedError(SystemExit):
    """The run refuses to start (nothing has been read from the warehouse or the pass table)."""


# --------------------------------------------------------------------------- guards


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_committed_unchanged(path: Path) -> bool:
    """True when the file is tracked and has no staged or unstaged change against HEAD."""
    rel = str(path.relative_to(REPO))
    tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", rel],
                             capture_output=True).returncode == 0
    clean = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", rel]).returncode == 0
    return tracked and clean


def registration_problems(build_log: Path = BUILD_LOG, wc_root: Path = WC,
                          committed: Callable[[Path], bool] = git_committed_unchanged) -> list[str]:
    """Every reason the registration is not ready for a real run (empty list = ready)."""
    log = json.loads(Path(build_log).read_text())
    item = next((i for i in log.get("items", []) if i.get("id") == "WC-03"), None)
    if item is None:
        return ["WC-03 not in the build log"]
    problems = []
    recorded = {PREREG: (item.get("prereg") or {}).get("sha256")}
    for a in item.get("amendments") or []:
        recorded[a.get("doc")] = a.get("sha256")
    docs = (PREREG, *AMENDMENTS, *((A5_DOC,) if A5_FIT_RACE_LIST is not None else ()))
    for doc in docs:
        path = Path(wc_root) / doc
        if not path.exists():
            problems.append(f"{doc}: missing")
            continue
        want = recorded.get(doc)
        if not want:
            problems.append(f"{doc}: no SHA-256 recorded on WC-03 in the build log")
        elif sha256_file(path) != want:
            problems.append(f"{doc}: file SHA-256 differs from the recorded one")
        if not committed(path):
            problems.append(f"{doc}: not committed, or changed against HEAD")
    return problems


def check_scratch_db(path: Path, warehouse: Path = WAREHOUSE) -> Path:
    p = Path(path).resolve()
    if p == Path(warehouse).resolve() or p.is_relative_to(Path(warehouse).resolve().parent):
        raise RefusedError(f"refused: {p} is the warehouse or inside data/; use a scratch copy (rule 5, §2d)")
    if p.name != "dev.duckdb":
        raise RefusedError("refused: the scratch copy must be named dev.duckdb (§2d)")
    if not p.is_file():
        raise RefusedError(f"refused: {p} does not exist")
    return p


def check_evidence_fresh(evidence: Path) -> None:
    prov = Path(evidence) / "PROVENANCE.txt"
    text = prov.read_text() if prov.exists() else ""
    if RESULTS in text or COMPLETED in text:
        raise RefusedError("refused: a result was already written in this evidence folder; n_runs = 1 is final (§0)")


EVIDENCE_ROOT = WC / "_evidence"
RUN_EVIDENCE_GLOBS = ("WC-03-*", "WC-04-*")


def check_no_result_anywhere(evidence_root: Path = EVIDENCE_ROOT) -> None:
    """§0 formal: a run is completed once any file under a WC-03 or WC-04 evidence folder holds a result. Refuse
    when the PROVENANCE.txt of any such folder (at any depth) records a result, whatever --evidence-dir is, so a
    second run cannot start under a new folder name (review D1)."""
    hits = []
    for pattern in RUN_EVIDENCE_GLOBS:
        for folder in sorted(Path(evidence_root).glob(pattern)):
            if not folder.is_dir():
                continue
            for prov in sorted(folder.rglob("PROVENANCE.txt")):
                text = prov.read_text(errors="replace")
                if RESULTS in text or COMPLETED in text:
                    hits.append(str(prov.relative_to(evidence_root)))
    if hits:
        raise RefusedError("refused: a WC-03/WC-04 result already exists (" + ", ".join(hits)
                           + "); n_runs = 1 is final (§0)")


# --------------------------------------------------------------------------- data sources


class Sources(Protocol):
    def db_sha256(self) -> str: ...
    def bronze_digest(self) -> tuple[int, str]: ...
    def yardstick(self) -> tuple[pd.DataFrame, int]: ...  # (panel, shipped calibration n)
    def panel_rows(self) -> int: ...
    def pooled_slope(self) -> float: ...
    def g2_mismatches(self) -> list[str]: ...
    def passes(self) -> pd.DataFrame: ...
    def calendar(self) -> dict: ...
    def race_circuit_map(self) -> dict: ...  # race_id -> §6 circuit key, every race in bronze laps (A5)
    def pits(self) -> pd.DataFrame: ...  # season, race_id, driver, lap, pit_in, pit_out (§11)
    def lap_info(self) -> pd.DataFrame: ...  # season, race_id, driver, lap, team, position (L5)


def bronze_digest(bronze: Path = BRONZE) -> tuple[int, str]:
    """G3 check 4: per file `<sha256>  <path relative to data/bronze>`, lines sorted bytewise by path, SHA-256
    of the text (each line newline-terminated, as `shasum` prints it)."""
    files = sorted({p for g in G3_BRONZE_GLOBS for p in glob.glob(str(Path(bronze) / g))})
    lines = [(os.path.relpath(p, bronze), sha256_file(Path(p))) for p in files]
    lines.sort(key=lambda x: x[0].encode())
    text = "".join(f"{h}  {rel}\n" for rel, h in lines)
    return len(lines), hashlib.sha256(text.encode()).hexdigest()


@dataclass
class ScratchSources:
    """The real sources. Every warehouse read is on the scratch copy, read_only; nothing is written to it.
    NOT RUN ON REAL DATA (synthetic tests replace this class)."""

    scratch_db: Path
    pass_dir: Path
    work_dir: Path  # scratch output (counts for G2)
    _panel: pd.DataFrame | None = None
    _shipped_n: int | None = None

    def db_sha256(self) -> str:
        return sha256_file(self.scratch_db)

    def bronze_digest(self) -> tuple[int, str]:
        return bronze_digest(BRONZE)

    def _panel_sql(self) -> str:
        spec = importlib.util.spec_from_file_location("d1_wi12", D1_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # top level defines constants and the SQL; main() is not called
        return mod.WI01_PANEL_SQL

    def yardstick(self) -> tuple[pd.DataFrame, int]:
        """§2d wrapper: WI01_PANEL_SQL on the scratch copy (cwd transform/ for the views' relative paths), plus
        the unfilled same-lap share and the shipped dirty_air_tax_s joined on lap_id (NULL stays NULL)."""
        if self._panel is None:
            import duckdb
            con = duckdb.connect(str(self.scratch_db), read_only=True)
            cwd = os.getcwd()
            os.chdir(REPO / "transform")
            try:
                panel = con.execute(self._panel_sql()).df()
                extra = con.execute(
                    "SELECT a.lap_id, a.dirty_air_share_lap AS dirty_air_share_lap_raw, t.dirty_air_tax_s "
                    "FROM int_lap_air_state a FULL OUTER JOIN int_dirty_air_tax_component t USING (lap_id)").df()
                shipped = con.execute(
                    """SELECT DISTINCT ROUND(500.0 * tax_calibration_confidence
                                             / (1.0 - tax_calibration_confidence)) AS n
                       FROM int_dirty_air_tax_component
                       WHERE dirty_air_intensity_lag1 > 0 AND dirty_air_tax_s BETWEEN 0 AND 5""").df()
            finally:
                os.chdir(cwd)
                con.close()
            if len(shipped) != 1:
                raise E.EstimatorError("shipped calibration n is not unique")
            if extra["lap_id"].duplicated().any():
                raise E.EstimatorError("more than one air-state / tax row per lap_id")
            panel = panel.merge(extra, on="lap_id", how="left")
            panel["dirty_air_share_lap"] = panel.pop("dirty_air_share_lap_raw")
            self._panel, self._shipped_n = panel, int(shipped["n"].iloc[0])
        return self._panel, self._shipped_n

    def panel_rows(self) -> int:
        """G3 check 2: the row count of the very panel yardstick() returns."""
        return len(self.yardstick()[0])

    def pooled_slope(self) -> float:
        """d1 Gate 1, computed exactly as d1 computes it (on the panel's own d_lag1)."""
        panel, _ = self.yardstick()
        x, y = panel["d_lag1"], panel["partial_residual_s"]
        return float(((x - x.mean()) * (y - y.mean())).mean() / x.var(ddof=0))

    def g2_mismatches(self) -> list[str]:
        out = Path(self.work_dir) / "g2_counts"
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(WC01_EVIDENCE / "counts.py"), str(self.pass_dir), str(out)], check=True)
        return [f for f in G2_FILES
                if not (out / f).exists() or (out / f).read_bytes() != (WC01_EVIDENCE / f).read_bytes()]

    def passes(self) -> pd.DataFrame:
        files = sorted(glob.glob(str(Path(self.pass_dir) / "pass_table_*.parquet")))
        return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

    def calendar(self) -> dict:
        from tasks.wake_calibration import build_pass_table as bpt
        return bpt.race_calendar(BRONZE)

    def race_circuit_map(self) -> dict:
        return race_circuit_map(BRONZE, self.calendar())

    def pits(self) -> pd.DataFrame:
        from tasks.wake_calibration import pitstop as P
        return P.pit_laps_from_bronze(BRONZE, range(2018, 2026))

    def lap_info(self) -> pd.DataFrame:
        from tasks.wake_calibration import report as RP
        return RP.lap_info_from_bronze(BRONZE, range(2018, 2026))


def race_circuit_map(bronze: Path, calendar: dict) -> dict:
    """race_id -> §6 circuit key for every race folder in bronze laps (built or not), via the race calendar
    (DRAFT A5: a race with panel laps but no pass table still needs its circuit). Reads one column per file."""
    out = {}
    for f in sorted(glob.glob(str(Path(bronze) / "laps/season=*/race=*/*.parquet"))):
        if "session=" in f:
            continue
        season = int(Path(f).parent.parent.name.split("=")[1])
        slug = Path(f).parent.name.split("=", 1)[1]
        ids = pd.read_parquet(f, columns=["race_id"])["race_id"].dropna().astype(str).unique()
        if (season, slug) in calendar:
            for rid in ids:
                out[rid] = str(calendar[(season, slug)][0])
    return out


def fit_race_preflight(pass_dir: Path) -> dict[str, tuple[list[str], list[str]]]:
    """Before any warehouse read or gate: per era, the built fit-season races and those with a fit pass before the
    ±2 s loss trim (reverted from review D3, so no loss column is read here). Only race ids are returned.
    Under A4 ruling 4b as written a built race with no fit pass makes the run stop after G3; main() refuses
    instead (draft A5)."""
    cols = ["season", "race_id", "segment_basis", "reason", "clear_ahead", "gap_s", "ref_status", "tag"]
    files = sorted(glob.glob(str(Path(pass_dir) / "pass_table_*.parquet")))
    p = pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True)
    return _fit_race_lists(p)


def a5_refusal(lists: dict, a5: str | None) -> None:
    """Refuse before any warehouse read when, under A4 ruling 4b as written (a5 None), a built main-era fit
    race has no fit-eligible pass: the run would otherwise stop after G3 has been written (one run, no
    verdict). Conservative: the panel may lack that race too, but that cannot be known before G3."""
    built, contributing = lists["main"]
    if a5 is None and built != contributing:
        raise RefusedError("refused before any data is read from the warehouse: built 2022-2024 race(s) "
                           f"{sorted(set(built) - set(contributing))} have no fit-eligible pass, so under A4 "
                           "ruling 4b the run would stop after G3 (one run, no verdict). The owner decides "
                           "draft amendment A5 first.")


def _fit_race_lists(p: pd.DataFrame) -> dict[str, tuple[list[str], list[str]]]:
    gap = p["gap_s"].to_numpy(dtype=float)
    fit = ((p["segment_basis"] == E.BRAKING_BASIS) & p["reason"].isna() & ~p["clear_ahead"].astype(bool)
           & (p["ref_status"] == "measured") & ~E.is_yielding(p["tag"]) & np.isfinite(gap) & (gap >= 0)
           & (gap < E.FOLLOW_MAX_GAP_S))
    out = {}
    for era, spec in E.ERAS.items():
        in_era = p["season"].astype(int).isin(spec["fit"])
        out[era] = (sorted(p.loc[in_era, "race_id"].astype(str).unique()),
                    sorted(p.loc[in_era & fit, "race_id"].astype(str).unique()))
    return out


# --------------------------------------------------------------------------- the run


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _log(evidence: Path, line: str) -> None:
    with open(Path(evidence) / "PROVENANCE.txt", "a") as f:
        f.write(f"{_now()} {line}\n")


def g3_checks(src: Sources) -> list[C.Check]:
    """§12a G3, in order. Checks 1 and 4 read no warehouse table; the panel is built only after they pass."""
    out = []
    sha = src.db_sha256()
    out.append(C.Check("G3.1", sha == G3_DB_SHA256, "scratch dev.duckdb SHA-256", sha))
    n_files, digest = src.bronze_digest()
    out.append(C.Check("G3.4", n_files == G3_BRONZE_FILES and digest == G3_BRONZE_SHA256,
                       "bronze inputs: 1,214 files, combined SHA-256", f"{n_files} files, {digest}"))
    if not all(c.passed for c in out):
        return out
    _, shipped_n = src.yardstick()
    rows = src.panel_rows()
    out.append(C.Check("G3.2", rows == G3_PANEL_ROWS and shipped_n == G3_PANEL_ROWS,
                       "panel rows and shipped calibration n = 135,841", f"rows {rows}, shipped n {shipped_n}"))
    slope = src.pooled_slope()
    out.append(C.Check("G3.3", abs(slope - G3_POOLED_SLOPE) <= G3_POOLED_TOL,
                       "pooled-slope fingerprint 0.4777453471 ± 1e-9", f"{slope:.10f}"))
    return out


def g6_joins(panel: pd.DataFrame, passes: pd.DataFrame, season: int) -> tuple[C.Check, dict]:
    """§2f: every joined pass row's lap_id cross-check holds; unjoined counts reported."""
    keys = C.panel_lap_keys(panel[panel["race_year"].astype(int) == season]).assign(
        lap_id=panel.loc[panel["race_year"].astype(int) == season, "lap_id"].astype(str).to_numpy())
    pk = passes.loc[passes["season"].astype(int) == season, E.PASS_KEY].drop_duplicates()
    pk = pk.assign(season=pk["season"].astype(int), race_id=pk["race_id"].astype(str),
                   driver=pk["driver"].astype(str), lap=pk["lap"].astype(int))
    j = pk.merge(keys, on=E.PASS_KEY, how="outer", indicator=True)
    both = j[j["_merge"] == "both"]
    expect = (both["season"].astype(str) + "_" + both["race_id"] + "_" + both["driver"] + "_"
              + both["lap"].astype(str))
    bad = int((expect != both["lap_id"]).sum())
    counts = {"laps_with_passes_no_panel_row": int((j["_merge"] == "left_only").sum()),
              "panel_laps_no_passes": int((j["_merge"] == "right_only").sum()), "lap_id_mismatches": bad}
    return C.Check("G6", bad == 0, "lap_id cross-check on every joined row (§2f)", json.dumps(counts)), counts


def run_g1_tests() -> tuple[bool, str]:
    """G1: the committed synthetic suite, run before any data is read. Returns (passed, pytest's last line)."""
    env = {**os.environ, "PYTHONPATH": str(REPO / "transform")}
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           str(Path(__file__).resolve().parent / "tests")], capture_output=True, text=True, env=env)
    tail = (proc.stdout.strip().splitlines() or ["no output"])[-1]
    return proc.returncode == 0, tail


def run_pipeline(src: Sources, evidence: Path, n_draws: int = E.N_BOOT, seed: int = E.SEED,
                 synthetic: bool = False, g1_summary: str = "synthetic call: G1 not run here",
                 a5: str | None = None) -> C.EraResult | None:
    """The registered order. Returns the main-era result, or None when G3, G2, the A4 4b guard or an error after
    G3 stopped the run (each recorded as no verdict with its cause; review D2)."""
    if not synthetic and (n_draws != E.N_BOOT or seed != E.SEED):
        raise RefusedError("refused: B and the seed are fixed (§8c)")
    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    check_evidence_fresh(evidence)
    if not synthetic:
        check_no_result_anywhere(EVIDENCE_ROOT)
    _log(evidence, f"{STARTED}: n_draws {n_draws}, seed {seed}, synthetic {synthetic}, python {sys.version.split()[0]}")
    g3 = g3_checks(src)  # an error here is before RESULTS: nothing was seen, a restart is allowed (§0)
    _log(evidence, RESULTS)
    _log(evidence, "G3: " + "; ".join(f"{c.name} {'pass' if c.passed else 'FAIL'} ({c.value})" for c in g3))
    if not all(c.passed for c in g3):
        bad = "; ".join(f"{c.name}: {c.value}" for c in g3 if not c.passed)
        (evidence / "SCORECARD.md").write_text(f"{G3_FAIL_LINE} ({bad}).\n\nThe flat penalty stays. "
                                               "Nothing was fitted or scored. The owner is told before anything else.\n")
        _log(evidence, f"{COMPLETED}: G3 failed; nothing fitted or scored")
        return None
    # Review D2: from here on the run is spent (§0). Any error up to the verdict is recorded as no verdict, with
    # its cause, on the scorecard's first line and in PROVENANCE.txt; it is never left as a bare crash.
    try:
        stage = _through_verdict(src, evidence, g3, n_draws, seed, g1_summary, a5)
    except Exception as exc:  # noqa: BLE001 - recorded, never swallowed silently
        _record_error_no_verdict(evidence, exc)
        return None
    if stage is None:
        return None
    result, ctx = stage
    # After the verdict line is written, an error while assembling Table 2 keeps the Table 1 scorecard and the
    # verdict (Table 2 never decides it); it is logged and the run is completed.
    try:
        first, rows = table2(src, evidence, *ctx, n_draws, seed)
        t1 = C.scorecard(result).splitlines()
        card = t1[:4] + first + ([""] if first else []) + t1[4:]
        (evidence / "SCORECARD.md").write_text("\n".join(card) + "\n" + RP.table2_text(rows))
    except Exception as exc:  # noqa: BLE001
        _log(evidence, f"TABLE 2 assembly: not computed ({type(exc).__name__}: {str(exc)[:300]}); "
                       "SCORECARD.md keeps Table 1 and the verdict")
        for tb_line in traceback.format_exc().rstrip().splitlines():
            _log(evidence, f"  | {tb_line}")
    _log(evidence, f"{COMPLETED}: verdict {result.verdict_code}")
    return result


FIT_RACE_LIST_CAUSE = "fit-race list incomplete"  # draft A5 "Order": the recorded no-verdict cause


def _record_error_no_verdict(evidence: Path, exc: Exception) -> None:
    """Review D2: an error after G3 was written is a no verdict with its cause (§0: the run is spent)."""
    cause = FIT_RACE_LIST_CAUSE if isinstance(exc, C.FitRaceListError) else "the run stopped with an error"
    line = (f"{C.VERDICT_TEXT[C.NO_VERDICT]} No verdict: {cause} ({type(exc).__name__}: {str(exc)[:300]}). "
            "The error came after G3 had been written, so under §0 this run is spent and is not repeated; "
            "nothing after the error is a result.")
    (evidence / "SCORECARD.md").write_text(line + "\n")
    _log(evidence, f"ERROR after {RESULTS}: {type(exc).__name__}: {str(exc)[:300]}")
    for tb_line in traceback.format_exc().rstrip().splitlines():
        _log(evidence, f"  | {tb_line}")
    _log(evidence, f"{COMPLETED}: no verdict ({cause})")


def _through_verdict(src: Sources, evidence: Path, g3: list, n_draws: int, seed: int, g1_summary: str,
                     a5: str | None):
    """G2 to the verdict line (the part of run_pipeline after G3). Returns None when G2 or the A4 4b guard
    stopped the run (already recorded), else (main-era result, the arguments table2 needs)."""
    g2_bad = src.g2_mismatches()
    g2 = C.Check("G2", not g2_bad, "WC-01 count files reproduce byte for byte", ", ".join(g2_bad) or "all identical")
    _log(evidence, f"G2: {'pass' if g2.passed else 'FAIL'} ({g2.value})")
    if not g2.passed:
        (evidence / "SCORECARD.md").write_text(f"{C.VERDICT_TEXT[C.NO_VERDICT]} G2 failed: {g2.value}.\n")
        _log(evidence, f"{COMPLETED}: G2 failed; nothing fitted or scored")
        return None
    panel, _ = src.yardstick()
    raw = src.passes()
    cal = src.calendar()
    prepared = E.prepare_passes(raw, cal)
    held = E.ERAS["main"]["held_out"]
    g6, g6_counts = g6_joins(panel, prepared, held)
    g1 = C.Check("G1", True, "synthetic tests committed and passing before the run", g1_summary)
    g4 = C.Check("G4", True, "no held-out row in any fit (asserted in code; a leak raises)", "asserted")
    held_races = sorted(panel.loc[panel["race_year"].astype(int) == held, "race_id"].astype(str).unique())
    lists = era_lists(src, prepared, panel, a5)
    if lists["main"][0] is None and lists["main"][2]:
        # A4 ruling 4b as written: the run stops before any curve or score. Recorded as no verdict.
        line = (f"{C.VERDICT_TEXT[C.NO_VERDICT]} Fit-race list: {lists['main'][2]} (A4 ruling 4b; "
                "see draft amendment A5). Nothing was fitted or scored.")
        (evidence / "SCORECARD.md").write_text(line + "\n")
        _log(evidence, f"{COMPLETED}: A4 4b fit-race lists differ; nothing fitted or scored")
        return None
    result = C.run_era(prepared, lists["main"][1], held_races, "main", n_draws=n_draws, seed=seed,
                       setup_checks=[g1, g2, *g3, g4, g6], fit_races=lists["main"][0],
                       race_circuit=lists["main"][3])
    result.main_table.to_csv(evidence / "main_curve.csv", index=False)
    result.dirty_table.to_csv(evidence / "class_curve_dirty_air.csv", index=False)
    result.held_up_table.to_csv(evidence / "class_curve_held_up.csv", index=False)
    if result.scored is not None:
        result.scored.drops.to_csv(evidence / "lap_drops.csv", index=False)
    if result.contest is not None:
        pd.DataFrame([{"set": s, **r} for s, r in result.contest.point.items()]).to_csv(
            evidence / "contest.csv", index=False)
        th = result.contest.theta_draws
        lo, hi = (np.percentile(th, E.CI_PERCENTILES) if np.isfinite(th).all() else (np.nan, np.nan))
        pd.DataFrame([{"theta_now": result.contest.theta_point, "ci_lower": lo, "ci_upper": hi,
                       "n_draws": len(th)}]).to_csv(evidence / "theta_now.csv", index=False)
    (evidence / "SCORECARD.md").write_text(C.scorecard(result))  # Table 1 first: a later crash cannot lose it
    _log(evidence, f"G6 counts: {json.dumps(g6_counts)}")
    _log(evidence, f"VERDICT WRITTEN: {result.verdict_code}")
    return result, (raw, cal, prepared, panel, result, lists, held_races, g1, g2, g3)


def era_lists(src: Sources, prepared: pd.DataFrame, panel: pd.DataFrame, a5: str | None) -> dict:
    """Per era: (fit_races or None, the panel to use, problem text, race_circuit or None).

    a5 None (A4 ruling 4b as written): no explicit list; the problem text is set when the curve's fit races
    and θ_now's panel races differ, and the era is then not run. a5 "union" / "built" (DRAFT A5, once adopted):
    the explicit list from contest.fit_race_list; under "built" the panel's fit-season laps outside the list
    are left out of θ_now."""
    out = {}
    rc_all = None
    for era, spec in E.ERAS.items():
        if a5 is None:
            fit = E.fit_passes(prepared, era)
            curve_races = set(fit["race_key"].astype(str))
            theta_races = set(C.theta_fit_rows(panel, era)["race_id"].astype(str))
            prob = ""
            if curve_races != theta_races:
                prob = (f"θ_now panel races and curve fit races differ: panel only "
                        f"{sorted(theta_races - curve_races)[:6]}, curve only {sorted(curve_races - theta_races)[:6]}")
            out[era] = (None, panel, prob, None)
            continue
        rc_all = rc_all if rc_all is not None else src.race_circuit_map()
        try:
            races, rc = C.fit_race_list(prepared, panel, rc_all, era, a5)
        except C.FitRaceListError as exc:
            if era == "main":
                raise  # recorded by run_pipeline as "no verdict: fit-race list incomplete" (review D2)
            # The older-car run is report-only (Table 2): its incomplete list is shown there, never a verdict.
            out[era] = (None, panel, f"{FIT_RACE_LIST_CAUSE}: {exc}", None)
            continue
        pan = panel
        if a5 == "built":
            in_fit = pan["race_year"].astype(int).isin(spec["fit"])
            pan = pan[~in_fit | pan["race_id"].astype(str).isin(races)]
        out[era] = (races, pan, "", rc)
    return out


def table2(src, evidence, raw, cal, prepared, panel, result, lists, held_races, g1, g2, g3, n_draws, seed):
    """The report-only steps (§12b, §11, L5, L6, L4). Each is logged; one that cannot be computed is shown as
    "—" with the reason and the others go on. Returns (first lines for the scorecard, Table 2 rows)."""
    from tasks.wake_calibration import pitstop as P
    from tasks.wake_calibration import sensitivity as S
    rows: list[dict] = []
    first: list[str] = []
    held = E.ERAS["main"]["held_out"]

    def step(name, fn):
        try:
            out = fn()
            _log(evidence, f"TABLE 2 {name}: done")
            return out
        except Exception as exc:  # report-only: recorded, shown as "—", never silently dropped
            _log(evidence, f"TABLE 2 {name}: not computed ({type(exc).__name__}: {str(exc)[:200]})")
            rows.append({"item": name, "value": f"{RP.UNAVAILABLE} (not computed: {type(exc).__name__})"})
            return None

    lap_info = step("bronze lap info", src.lap_info)

    def counts():
        RP.no_car_ahead_counts(prepared, lap_info).to_csv(evidence / "counts_no_car_ahead.csv", index=False)
        E.no_reference_counts(prepared).to_csv(evidence / "counts_no_reference.csv", index=False)
        RP.class_bin_counts(prepared).to_csv(evidence / "counts_class_bin_season_race.csv", index=False)
        rows.append({"item": "counts (§12b)", "value": "counts_no_car_ahead.csv, counts_no_reference.csv, "
                     "counts_class_bin_season_race.csv, lap_drops.csv; G6 counts in PROVENANCE.txt"})
    step("counts", counts)

    def teams():
        tm = RP.team_map(lap_info)
        cov = RP.coverage_per_team(prepared, tm, None if result.scored is None else result.scored.laps)
        cov.to_csv(evidence / "coverage_per_team.csv", index=False)
        per = RP.contest_per_team(result, tm)
        per.to_csv(evidence / "contest_per_team.csv", index=False)
        rows.extend(RP.team_rows(cov, per, held))
    if lap_info is not None:
        step("coverage and contest per team", teams)
    step("contest context", lambda: rows.extend(RP.contest_context_rows(result)))
    step("under attack", lambda: rows.extend(RP.under_attack_rows(result.under_attack)))
    pits = step("bronze pit laps", src.pits)

    def pit(label, era_res, seasons, tag):
        if era_res is None or era_res.main_draws is None or (era_res.main_table["status"] != E.CURVE_OK).any():
            rows.append({"item": f"pit-stop figure, {label}", "value": f"{RP.UNAVAILABLE} (curve not estimable)"})
            return
        fig = P.pit_figure(prepared, pits, seasons, C.curve_array(era_res.main_table), era_res.main_draws,
                           n_draws=n_draws)
        fig.events.to_csv(evidence / f"pit_events_{tag}.csv", index=False)
        fig.drops.to_csv(evidence / f"pit_drops_{tag}.csv", index=False)
        rows.extend({"item": f"{label}: {r['item']}", "value": r["value"]} for r in fig.table2_rows())
    if pits is not None:
        step("pit-stop figure 2022-2025", lambda: pit("main curve, 2022-2025", result, (2022, 2023, 2024, 2025), "main"))
        step("pit-stop figure 2025", lambda: pit("main curve, 2025 only", result, (2025,), "2025"))

    def older():
        fr, pan, prob, rc = lists["older"]
        if fr is None and prob:
            rows.extend(RP.older_rows(None, f"fit-race list (A4 ruling 4b; see draft A5): {prob}"))
            return None
        oh = E.ERAS["older"]["held_out"]
        g6o, _ = g6_joins(pan, prepared, oh)
        g4o = C.Check("G4", True, "no 2021 row in the older fit (asserted in code)", "asserted")
        races = sorted(pan.loc[pan["race_year"].astype(int) == oh, "race_id"].astype(str).unique())
        res = C.run_era(prepared, pan, races, "older", n_draws=n_draws, seed=seed,
                        setup_checks=[g1, g2, *g3, g4o, g6o], fit_races=fr, race_circuit=rc)
        res.main_table.to_csv(evidence / "older_curve.csv", index=False)
        res.dirty_table.to_csv(evidence / "older_class_curve_dirty_air.csv", index=False)
        if res.contest is not None:
            pd.DataFrame([{"set": s, **r} for s, r in res.contest.point.items()]).to_csv(
                evidence / "older_contest.csv", index=False)
        rows.extend(RP.older_rows(res))
        return res
    old = step("older cars", older)
    if pits is not None and old is not None:
        step("pit-stop figure 2018-2021", lambda: pit("older curve, 2018-2021", old, (2018, 2019, 2020, 2021), "older"))

    def sens():
        fr, pan, _, rc = lists["main"]
        outs = S.run_variants(raw, prepared, pan, cal, held_races, n_draws=n_draws, seed=seed, fit_races=fr,
                              race_circuit=rc)
        rows.extend(S.table2_rows(outs))
        first.extend(S.first_lines(result, outs))
    step("sensitivity runs", sens)
    rows.append({"item": "reference-fit diagnostic (§2e, §12b)",
                 "value": "the procedure that produced 0.331 returns 0.305 (95 % interval 0.269 to 0.341, n 135,675) "
                          "on the 2026-10-28 data; diagnostic only, not the benchmark"})
    rows.append({"item": "minimum-speed agreement per corner class (WC-02, observation only)",
                 "value": "_evidence/WC-02-2026-10-27/check3_by_class.csv"})
    return first, rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch-db", type=Path, required=True)
    ap.add_argument("--pass-table-dir", type=Path, required=True)
    ap.add_argument("--evidence-dir", type=Path, required=True)
    ap.add_argument("--owner-yes", action="store_true", help="the owner has said yes to this run (rule 3)")
    ap.add_argument("--check-only", action="store_true", help="run the refusal checks only; read no data")
    args = ap.parse_args(argv)
    problems = registration_problems()
    if problems:
        raise RefusedError("refused: the registration is not ready (rule 4):\n  " + "\n  ".join(problems))
    if not args.owner_yes:
        raise RefusedError("refused: --owner-yes not given (rule 3)")
    db = check_scratch_db(args.scratch_db)
    if Path(args.pass_table_dir).resolve().is_relative_to(WAREHOUSE.parent.resolve()):
        raise RefusedError("refused: --pass-table-dir must not be inside data/")
    check_evidence_fresh(args.evidence_dir)
    check_no_result_anywhere(EVIDENCE_ROOT)  # review D1: every WC-03-* / WC-04-* folder, not only this one
    a5_refusal(fit_race_preflight(args.pass_table_dir), A5_FIT_RACE_LIST)
    if args.check_only:
        print("checks passed; no warehouse or bronze data read (pass-table structure only, for the A5 pre-flight)")
        return 0
    ok, tail = run_g1_tests()  # before any data is read; a failure is a refusal, not a result
    if not ok:
        raise RefusedError(f"refused: G1 synthetic tests do not pass ({tail})")
    src = ScratchSources(db, args.pass_table_dir, db.parent)
    result = run_pipeline(src, args.evidence_dir, g1_summary=f"pytest: {tail}", a5=A5_FIT_RACE_LIST)
    print((Path(args.evidence_dir) / "SCORECARD.md").read_text().splitlines()[0])
    return 0 if result is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
