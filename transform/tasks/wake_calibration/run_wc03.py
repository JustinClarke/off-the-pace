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
SCORECARD.md. If G3 fails the run stops before anything is fitted, writes the registered first line and
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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import numpy as np
import pandas as pd

from tasks.wake_calibration import contest as C
from tasks.wake_calibration import estimator as E

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
    for doc in (PREREG, *AMENDMENTS):
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
                 synthetic: bool = False, g1_summary: str = "synthetic call: G1 not run here") -> C.EraResult | None:
    """The registered order. Returns the main-era result, or None when G3 or G2 stopped the run."""
    if not synthetic and (n_draws != E.N_BOOT or seed != E.SEED):
        raise RefusedError("refused: B and the seed are fixed (§8c)")
    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    check_evidence_fresh(evidence)
    _log(evidence, f"{STARTED}: n_draws {n_draws}, seed {seed}, synthetic {synthetic}, python {sys.version.split()[0]}")
    g3 = g3_checks(src)
    _log(evidence, RESULTS)
    _log(evidence, "G3: " + "; ".join(f"{c.name} {'pass' if c.passed else 'FAIL'} ({c.value})" for c in g3))
    if not all(c.passed for c in g3):
        bad = "; ".join(f"{c.name}: {c.value}" for c in g3 if not c.passed)
        (evidence / "SCORECARD.md").write_text(f"{G3_FAIL_LINE} ({bad}).\n\nThe flat penalty stays. "
                                               "Nothing was fitted or scored. The owner is told before anything else.\n")
        _log(evidence, f"{COMPLETED}: G3 failed; nothing fitted or scored")
        return None
    g2_bad = src.g2_mismatches()
    g2 = C.Check("G2", not g2_bad, "WC-01 count files reproduce byte for byte", ", ".join(g2_bad) or "all identical")
    _log(evidence, f"G2: {'pass' if g2.passed else 'FAIL'} ({g2.value})")
    if not g2.passed:
        (evidence / "SCORECARD.md").write_text(f"{C.VERDICT_TEXT[C.NO_VERDICT]} G2 failed: {g2.value}.\n")
        _log(evidence, f"{COMPLETED}: G2 failed; nothing fitted or scored")
        return None
    panel, _ = src.yardstick()
    prepared = E.prepare_passes(src.passes(), src.calendar())
    held = E.ERAS["main"]["held_out"]
    g6, g6_counts = g6_joins(panel, prepared, held)
    g1 = C.Check("G1", True, "synthetic tests committed and passing before the run", g1_summary)
    g4 = C.Check("G4", True, "no held-out row in any fit (asserted in code; a leak raises)", "asserted")
    held_races = sorted(panel.loc[panel["race_year"].astype(int) == held, "race_id"].astype(str).unique())
    result = C.run_era(prepared, panel, held_races, "main", n_draws=n_draws, seed=seed,
                       setup_checks=[g1, g2, *g3, g4, g6])
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
    (evidence / "SCORECARD.md").write_text(C.scorecard(result))
    _log(evidence, f"G6 counts: {json.dumps(g6_counts)}")
    _log(evidence, f"{COMPLETED}: verdict {result.verdict_code}")
    return result


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
    if args.check_only:
        print("checks passed; no data read")
        return 0
    ok, tail = run_g1_tests()  # before any data is read; a failure is a refusal, not a result
    if not ok:
        raise RefusedError(f"refused: G1 synthetic tests do not pass ({tail})")
    src = ScratchSources(db, args.pass_table_dir, db.parent)
    result = run_pipeline(src, args.evidence_dir, g1_summary=f"pytest: {tail}")
    print((Path(args.evidence_dir) / "SCORECARD.md").read_text().splitlines()[0])
    return 0 if result is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
