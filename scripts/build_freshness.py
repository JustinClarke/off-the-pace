"""
Freshness gate for the app-data pipeline.

A full dbt build writes a marker next to the warehouse (`<db>.build.json`); the
app export refuses to read a warehouse whose marker is missing, partial, failed,
stale against bronze, or older than the file on disk.

CLI (called from the Makefile dbt recipes):
  python scripts/build_freshness.py invalidate --db data/dev.duckdb
  python scripts/build_freshness.py write --db data/dev.duckdb [--target dev]
                                          [--bronze-dir data/bronze] [--target-dir transform/target]
                                          [--known-gaps ingestion/known_gaps.txt]

`invalidate` runs BEFORE dbt, `write` runs only after dbt exits 0. The writer also
deletes the old marker first, so a refused write never leaves a marker behind.
Every check fails closed: an exception while validating is reported as a problem.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
BRONZE_DIR = ROOT / "data" / "bronze"
DBT_TARGET_DIR = ROOT / "transform" / "target"

MARKER_SCHEMA = 1
RUN_FILE_RE = re.compile(r"^run_(\d{8}T\d{6}Z)\.parquet$")
OK_STATUSES = frozenset({"ok"})  # 'thin', 'skip', 'error' and anything else are not clearly successful
REQUIRED_RELATIONS = ("mart_build_provenance", "fct_lap_residuals", "dim_drivers", "race_to_track")
REQUIRED_NODE_TYPES = ("model", "seed", "test")
PASS_STATUSES = frozenset({"success", "pass"})
FAIL_STATUSES = frozenset({"error", "fail"})

REBUILD = "make dbt-dev-full"

KNOWN_GAPS_FILE = ROOT / "ingestion" / "known_gaps.txt"
KNOWN_GAPS_SOURCE = "ingestion/known_gaps.txt"
BRONZE_LOCK_PY = ROOT / "ingestion" / "src" / "bronze_lock.py"
GAP_STATUSES = frozenset({"ok", "thin", "skip", "error"})
SESSION_TYPES = frozenset({"R", "Q"})

# The only known gaps the freshness gate accepts: (season, session_type, round_number, race_slug,
# expected manifest status). Listing a session in known_gaps.txt documents it; only this list approves it.
# It applies only to the exceptional statuses 'error' and 'thin': any other listed error or thin session
# blocks. A session whose latest status is 'ok' or a verified 'skip' (Monaco 2026 R included) passes on its
# own checks, whether or not it is documented in known_gaps.txt.
APPROVED_GAPS = frozenset({
    (2018, "R", 14, "italian_grand_prix", "error"),
    (2026, "R", 16, "bahrain_grand_prix", "thin"),
})


class Validation(NamedTuple):
    problems: list[str]
    marker: dict | None  # the marker, only when problems is empty

    @property
    def bronze_run_id(self) -> str | None:
        return self.marker["bronze_run_id"] if self.marker else None

    @property
    def build_id(self) -> str | None:
        return self.marker["build_id"] if self.marker else None


class BuildFreshnessError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


# ─── Marker path ──────────────────────────────────────────────────────────────

def marker_path(db_path: Path | str) -> Path:
    p = Path(db_path)
    return p.with_name(p.name + ".build.json")


def invalidate(db_path: Path | str) -> bool:
    """Delete the marker. A missing marker is not an error. True if one was removed."""
    mp = marker_path(db_path)
    try:
        mp.unlink()
        return True
    except FileNotFoundError:
        return False


# ─── Bronze ───────────────────────────────────────────────────────────────────

def list_bronze_runs(bronze_dir: Path | str) -> list[Path]:
    mdir = Path(bronze_dir) / "manifests"
    if not mdir.is_dir():
        return []
    return sorted(p for p in mdir.iterdir() if p.is_file() and RUN_FILE_RE.match(p.name))


def latest_bronze_run(bronze_dir: Path | str) -> str | None:
    """Latest run id (lexicographic max of the filename stem), or None."""
    runs = list_bronze_runs(bronze_dir)
    return RUN_FILE_RE.match(runs[-1].name).group(1) if runs else None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class KnownGap(NamedTuple):
    season: int
    session_type: str
    round_number: int
    race_slug: str
    expected_status: str
    reason: str


_GAP_ROUND_RE = re.compile(r"^round=(\d+)$")
_GAP_STATUS_RE = re.compile(r"^status=(\w+)$")
_SLUG_RE = re.compile(r"^[a-z0-9_]+$")


def parse_known_gaps(path: Path | str = KNOWN_GAPS_FILE) -> list[KnownGap]:
    """Strictly parse `YEAR TYPE SLUG | round=N | status=S | reason`. Any malformed line refuses.

    Raises BuildFreshnessError. A missing or unreadable file also refuses (fail closed).
    """
    path = Path(path)
    try:
        text = path.read_text()
    except OSError as e:
        raise BuildFreshnessError([f"ERROR: cannot read {KNOWN_GAPS_SOURCE} at {path}: {e}"])
    gaps: list[KnownGap] = []
    problems: list[str] = []
    seen: set[tuple] = set()
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        where = f"ERROR: {KNOWN_GAPS_SOURCE} line {n} is malformed"
        parts = [p.strip() for p in line.split("|", 3)]
        if len(parts) != 4:
            problems.append(f"{where}: expected 'YEAR TYPE SLUG | round=N | status=S | reason': {line[:80]}")
            continue
        head, rnd, st, reason = parts
        fields = head.split()
        mr, ms = _GAP_ROUND_RE.match(rnd), _GAP_STATUS_RE.match(st)
        if (len(fields) != 3 or not fields[0].isdigit() or fields[1] not in SESSION_TYPES
                or not _SLUG_RE.match(fields[2]) or not mr or not ms or ms.group(1) not in GAP_STATUSES):
            problems.append(f"{where}: expected 'YEAR TYPE SLUG | round=N | status=S | reason' with TYPE R or Q "
                            f"and status ok, thin, skip or error: {line[:80]}")
            continue
        if not reason:
            problems.append(f"{where}: the reason is empty: {line[:80]}")
            continue
        g = KnownGap(int(fields[0]), fields[1], int(mr.group(1)), fields[2], ms.group(1), reason)
        key = (g.season, g.session_type, g.race_slug)
        if key in seen:
            problems.append(f"{where}: duplicate entry for {g.season} {g.session_type} {g.race_slug}")
            continue
        seen.add(key)
        gaps.append(g)
    if problems:
        raise BuildFreshnessError(problems)
    return gaps


def _label(season, session_type, round_number, slug) -> str:
    return f"{season} {session_type}{round_number} {slug}"


def laps_artifact_path(bronze_dir: Path | str, season: int, session_type: str, slug: str) -> Path:
    base = Path(bronze_dir) / "laps" / f"season={season}" / f"race={slug}"
    if session_type == "Q":
        return base / "session=Q" / f"{season}_{slug}_quali_laps.parquet"
    return base / f"{season}_{slug}_laps.parquet"


def _parquet_rows(path: Path) -> int:
    import pyarrow.parquet as pq

    return pq.ParquetFile(path).metadata.num_rows


def _artifact_problem(bronze_dir: Path, season, session_type, slug, expected_rows) -> str | None:
    """None when the laps parquet exists and its row count equals expected_rows."""
    p = laps_artifact_path(bronze_dir, season, session_type, slug)
    if not p.is_file():
        return f"the laps parquet is missing ({p.relative_to(bronze_dir)})"
    try:
        n = _parquet_rows(p)
    except Exception as e:  # noqa: BLE001 — unreadable artifact fails closed
        return f"the laps parquet is unreadable ({type(e).__name__}: {e})"
    if n != expected_rows:
        return f"the laps parquet has {n} rows but the manifest row_count is {expected_rows}"
    return None


_SESSION_COLS = ("season", "round_number", "session_type", "race_slug", "status", "row_count", "dq_passed")


def _prior_ok(runs: list[Path]) -> dict[tuple, dict]:
    """Latest status=ok manifest row per (season, round, session_type, slug) over the given (earlier) runs."""
    import duckdb

    out: dict[tuple, dict] = {}
    conn = duckdb.connect()
    try:
        for f in runs:  # ascending run order: a later ok overrides an earlier one
            try:
                rows = conn.execute(
                    "SELECT season, round_number, session_type, race_slug, row_count, dq_passed "
                    "FROM read_parquet(?) WHERE status = 'ok'", [str(f)]).fetchall()
            except Exception:  # noqa: BLE001 — an unreadable old run supplies no prior ok entry
                continue
            for s, r, t, slug, rc, dq in rows:
                out[(s, r, t, slug)] = {"run": RUN_FILE_RE.match(f.name).group(1), "row_count": rc, "dq_passed": dq}
    finally:
        conn.close()
    return out


def classify_sessions(rows: list[dict], gaps: list[KnownGap], bronze_dir: Path, prior: dict) -> dict:
    """Apply the acceptance rules to every row of the latest run.

    Returns {n_ok, n_skip_accepted, acknowledged_gaps, blocked: [message, ...]}.
    """
    n_ok = n_skip = 0
    acknowledged: list[dict] = []
    blocked: list[str] = []
    for row in rows:
        season, rnd, st, slug = (row.get(k) for k in ("season", "round_number", "session_type", "race_slug"))
        status, rc, dq = row.get("status"), row.get("row_count"), row.get("dq_passed")
        if None in (season, rnd, st, slug):
            blocked.append(f"  blocked: a manifest row has no season, round_number, session_type or race_slug "
                           f"(status={status})")
            continue
        label = _label(season, st, rnd, slug)
        if status == "ok":
            if not isinstance(rc, int) or rc <= 0:
                blocked.append(f"  blocked: {label} status=ok but row_count is {rc}")
                continue
            why = _artifact_problem(bronze_dir, season, st, slug, rc)
            if why:
                blocked.append(f"  blocked: {label} status=ok but {why}")
                continue
            n_ok += 1
        elif status == "skip":
            # A verified skip passes whether or not the session is documented in known_gaps.txt.
            p = prior.get((season, rnd, st, slug))
            why = None
            if p is None:
                why = "no earlier manifest entry with status ok exists for this session"
            elif p["dq_passed"] is not True:
                why = f"its earlier ok entry (run {p['run']}) has dq_passed={p['dq_passed']}"
            elif not isinstance(p["row_count"], int) or p["row_count"] <= 0:
                why = f"its earlier ok entry (run {p['run']}) has row_count={p['row_count']}"
            else:
                why = _artifact_problem(bronze_dir, season, st, slug, p["row_count"])
            if why:
                blocked.append(f"  blocked: {label} status=skip is not an accepted skip: {why}")
                continue
            n_skip += 1
        elif status in ("thin", "error"):
            # Only the exceptional statuses consult the known-gap documentation and APPROVED_GAPS.
            same = [g for g in gaps if (g.season, g.session_type, g.race_slug) == (season, st, slug)]
            exact = [g for g in same if g.round_number == rnd]
            if not same:
                blocked.append(f"  blocked: {label} status={status} is not ok and is not an approved known gap")
                continue
            if not exact:
                blocked.append(f"  blocked: {label} status={status} matches a {KNOWN_GAPS_SOURCE} entry only by "
                               f"season, session and slug, not round (entry round {same[0].round_number}); "
                               f"a known gap must match the round exactly")
                continue
            g = exact[0]
            if (g.season, g.session_type, g.round_number, g.race_slug, g.expected_status) not in APPROVED_GAPS:
                blocked.append(f"  blocked: {label} status={status} is an unapproved known gap: it is listed in "
                               f"{KNOWN_GAPS_SOURCE} (expected status {g.expected_status}) but is not an approved "
                               f"freshness exception; approve it separately or resolve it")
                continue
            if status != g.expected_status:
                blocked.append(f"  blocked: {label} status={status} but the approved known gap expects "
                               f"status={g.expected_status}")
                continue
            acknowledged.append({
                "season": season, "round_number": rnd, "session_type": st, "race_slug": slug,
                "status": status, "reason": g.reason, "source": KNOWN_GAPS_SOURCE,
            })
        else:
            blocked.append(f"  blocked: {label} has unknown status {status!r}")
    return {"n_ok": n_ok, "n_skip_accepted": n_skip, "acknowledged_gaps": acknowledged, "blocked": blocked}


def _bronze_lock_verify(bronze_dir: Path) -> list[str]:
    """Problems from bronze_lock verify (read-only re-hash against MANIFEST.json); empty when it passes."""
    spec = importlib.util.spec_from_file_location("_bronze_lock", BRONZE_LOCK_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ok, problems = mod.verify(Path(bronze_dir).resolve())
    return [] if ok else problems


def check_bronze(bronze_dir: Path | str, known_gaps_path: Path | str = KNOWN_GAPS_FILE) -> tuple[dict | None, list[str]]:
    """Validate the latest bronze run. Returns (info, problems); info is None when no run exists.

    Every latest-run session must be ok, an accepted skip or an approved known gap (classify_sessions).
    """
    bronze_dir = Path(bronze_dir)
    runs = list_bronze_runs(bronze_dir)
    if not runs:
        return None, [f"ERROR: no bronze run manifests under {bronze_dir / 'manifests'}"]
    latest = runs[-1]
    run_id = RUN_FILE_RE.match(latest.name).group(1)
    info = {
        "run_id": run_id,
        "file": latest,
        "count": len(runs),
        "sha256": None,
        "status_ok": False,
        "status_counts": {},
        "acknowledged_gaps": [],
        "n_ok": 0,
        "n_skip_accepted": 0,
    }
    problems: list[str] = []
    try:
        import duckdb

        info["sha256"] = _sha256_file(latest)
        conn = duckdb.connect()
        try:
            cur = conn.execute("SELECT * FROM read_parquet(?)", [str(latest)])
            names = [d[0] for d in cur.description]
            data = cur.fetchall()
        finally:
            conn.close()
        missing = [c for c in ("run_id", "status") if c not in names]
        if missing:
            raise ValueError(f"missing columns {', '.join(missing)}")
        rows = [dict(zip(names, r)) for r in data]
    except Exception as e:  # noqa: BLE001 — unreadable manifest = corrupt, fail closed
        return info, [f"ERROR: bronze run {run_id} is incomplete: manifest unreadable ({e}). "
                      "Fix bronze ingestion before building."]

    counts: dict[str, int] = {}
    bad_ids: set = set()
    for r in rows:
        status = r["status"]
        key = "NULL" if status is None else status
        counts[key] = counts.get(key, 0) + 1
        if r["run_id"] != run_id:
            bad_ids.add(r["run_id"])
    info["status_counts"] = counts
    for x in sorted(bad_ids, key=str):
        problems.append(f"ERROR: bronze manifest {latest.name} run_id {x} does not match its filename")
    details = []
    blocked: list[str] = []
    if not rows:
        details.append("no rows")
    else:
        absent = [c for c in _SESSION_COLS if c not in names]
        try:
            gaps = parse_known_gaps(known_gaps_path)
        except BuildFreshnessError as e:
            problems += e.problems
            gaps = None
        if absent:
            details.append(f"the manifest has no {', '.join(absent)} column(s)")
        elif gaps is not None:
            res = classify_sessions(rows, gaps, bronze_dir, _prior_ok(runs[:-1]))
            info.update(acknowledged_gaps=res["acknowledged_gaps"], n_ok=res["n_ok"],
                        n_skip_accepted=res["n_skip_accepted"])
            blocked = res["blocked"]
            if blocked:
                summary = ", ".join(f"{s}={n}" for s, n in sorted(counts.items()))
                details.append(f"{len(blocked)} of {len(rows)} rows are not accepted: not ok, not an accepted "
                               f"skip and not an approved known gap (status counts: {summary})")
    if details:
        problems.append(f"ERROR: bronze run {run_id} is incomplete: {'; '.join(details)}. "
                        "Fix bronze ingestion before building.")
    problems += blocked
    info["status_ok"] = not problems
    return info, problems


# ─── Warehouse helpers ────────────────────────────────────────────────────────

def _warehouse_stat(db_path: Path) -> dict:
    st = os.stat(db_path)
    return {"path": str(db_path), "size": st.st_size, "mtime_ns": st.st_mtime_ns}


def _db_relations_and_build_id(db_path: Path) -> tuple[set[str], list[str]]:
    import duckdb

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rels = {r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        ids: list[str] = []
        if "mart_build_provenance" in rels:
            ids = [r[0] for r in conn.execute("SELECT dbt_invocation_id FROM mart_build_provenance").fetchall()]
        return rels, ids
    finally:
        conn.close()


# ─── Export-side validation ───────────────────────────────────────────────────

_MARKER_KEYS = ("build_id", "is_full", "success", "n_error", "n_skipped", "dbt_command",
                "dbt_node_count", "bronze_run_id", "warehouse", "source_coverage", "acknowledged_gaps")


def _read_marker(mp: Path) -> dict | None:
    try:
        m = json.loads(mp.read_text())
        if not isinstance(m, dict) or m.get("schema") != MARKER_SCHEMA:
            return None
        if any(k not in m for k in _MARKER_KEYS):
            return None
        w = m["warehouse"]
        if not isinstance(w, dict) or "size" not in w or "mtime_ns" not in w:
            return None
        return m
    except Exception:  # noqa: BLE001
        return None


def validate(db_path: Path | str, bronze_dir: Path | str = BRONZE_DIR) -> Validation:
    """All the reasons the warehouse must not be exported. Empty problems = fresh full build."""
    db_path = Path(db_path)
    try:
        return _validate(db_path, Path(bronze_dir))
    except Exception as e:  # noqa: BLE001 — fail closed
        return Validation([f"ERROR: freshness validation failed unexpectedly: {type(e).__name__}: {e}"], None)


def _validate(db_path: Path, bronze_dir: Path) -> Validation:
    problems: list[str] = []
    mp = marker_path(db_path)

    binfo, bproblems = check_bronze(bronze_dir)

    if not mp.exists():
        problems.append(f"ERROR: no build marker at {mp}; the warehouse has no recorded full build. Run: {REBUILD}")
        return Validation(problems + bproblems, None)
    m = _read_marker(mp)
    if m is None:
        problems.append(f"ERROR: build marker {mp} is unreadable or has unsupported schema. Run: {REBUILD}")
        return Validation(problems + bproblems, None)

    if m["is_full"] is not True:
        problems.append(f"ERROR: warehouse was built by a partial dbt run ({m['dbt_command']}); "
                        f"app-data needs a full build. Run: {REBUILD}")
    elif m["success"] is not True or m["n_error"] or m["n_skipped"]:
        problems.append(f"ERROR: the last full build recorded {m['n_error']} errors and {m['n_skipped']} "
                        f"skipped nodes; app-data refuses to export. Fix and run: {REBUILD}")

    st = os.stat(db_path)
    if st.st_size != m["warehouse"]["size"] or st.st_mtime_ns != m["warehouse"]["mtime_ns"]:
        problems.append(f"ERROR: warehouse changed after build {m['build_id']} "
                        f"(size or mtime differs from the marker); rebuild with: {REBUILD}")

    rels, ids = _db_relations_and_build_id(db_path)
    missing = [r for r in REQUIRED_RELATIONS if r not in rels]
    if missing:
        problems.append(f"ERROR: warehouse {db_path} is missing required relations: {', '.join(missing)}. "
                        f"Run: {REBUILD}")
    elif len(ids) != 1 or ids[0] != m["build_id"]:
        got = ids[0] if len(ids) == 1 else f"<{len(ids)} rows>"
        problems.append(f"ERROR: marker build_id {m['build_id']} does not match "
                        f"mart_build_provenance.dbt_invocation_id {got}; rebuild with: {REBUILD}")

    problems += bproblems
    if binfo is not None and m["bronze_run_id"] != binfo["run_id"]:
        problems.append(f"ERROR: warehouse was built from bronze run {m['bronze_run_id']} "
                        f"but the latest bronze run is {binfo['run_id']}. Run: {REBUILD}")

    return Validation(problems, None if problems else m)


# ─── Writer ───────────────────────────────────────────────────────────────────

def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_marker(
    db_path: Path | str,
    bronze_dir: Path | str = BRONZE_DIR,
    target_dir: Path | str = DBT_TARGET_DIR,
    target: str = "dev",
    known_gaps_path: Path | str = KNOWN_GAPS_FILE,
) -> dict:
    """Validate the finished dbt invocation and write the marker atomically.

    Raises BuildFreshnessError (and leaves no marker) on any problem.
    """
    db_path = Path(db_path).resolve()
    bronze_dir = Path(bronze_dir)
    target_dir = Path(target_dir)
    invalidate(db_path)  # a refused write must never leave the old marker behind

    problems: list[str] = []

    wal = Path(str(db_path) + ".wal")
    if wal.exists():
        problems.append(f"ERROR: {db_path}.wal exists; checkpoint or remove it before building.")
    if not db_path.exists():
        raise BuildFreshnessError(problems + [f"ERROR: warehouse not found at {db_path}"])

    try:
        rr = _load_json(target_dir / "run_results.json")
        mf = _load_json(target_dir / "manifest.json")
        args = rr["args"]
        results = rr["results"]
        build_id = rr["metadata"]["invocation_id"]
        mf_id = mf["metadata"]["invocation_id"]
        started = _parse_ts(rr["metadata"].get("invocation_started_at") or mf["metadata"]["invocation_started_at"])
        dbt_version = rr["metadata"].get("dbt_version")
    except Exception as e:  # noqa: BLE001
        raise BuildFreshnessError(problems + [f"ERROR: cannot read dbt artifacts under {target_dir}: "
                                              f"{type(e).__name__}: {e}"])

    if build_id != mf_id:
        problems.append(f"ERROR: run_results.json invocation {build_id} differs from manifest.json "
                        f"invocation {mf_id}; not a single dbt invocation.")

    # Full-build definition
    command = args.get("invocation_command") or ""
    partial = []
    if args.get("which") != "build":
        partial.append(f"which={args.get('which')!r}")
    if args.get("select"):
        partial.append(f"select={args.get('select')}")
    if args.get("exclude"):
        partial.append(f"exclude={args.get('exclude')}")
    if args.get("selector"):
        partial.append(f"selector={args.get('selector')}")
    if args.get("resource_types"):
        partial.append(f"resource_types={args.get('resource_types')}")
    if args.get("exclude_resource_types"):
        partial.append(f"exclude_resource_types={args.get('exclude_resource_types')}")
    if args.get("target") != target:
        partial.append(f"target={args.get('target')!r} (expected {target!r})")
    if partial:
        problems.append(f"ERROR: warehouse was built by a partial dbt run ({command}); "
                        f"app-data needs a full build. Run: {REBUILD}")
        problems.append(f"  not a full build: {', '.join(partial)}")

    nodes = mf.get("nodes", {})
    expected = {
        uid for uid, n in nodes.items()
        if n.get("resource_type") in REQUIRED_NODE_TYPES and n.get("config", {}).get("enabled", True)
    }
    seen = {r["unique_id"] for r in results}
    absent = sorted(expected - seen)
    if absent:
        problems.append(f"ERROR: {len(absent)} enabled nodes in manifest.json are missing from run_results.json "
                        f"(first: {', '.join(absent[:3])}); the build did not cover the whole project.")

    n_error = n_skipped = n_warn = 0
    warn_tests: list[str] = []
    bad_warn: list[str] = []
    for r in results:
        uid, status = r["unique_id"], r["status"]
        if status in PASS_STATUSES:
            continue
        if status == "skipped":
            n_skipped += 1
        elif status == "warn":
            n_warn += 1
            node = nodes.get(uid, {})
            is_test = node.get("resource_type") == "test" or uid.startswith("test.")
            if is_test and str(node.get("config", {}).get("severity", "")).lower() == "warn":
                warn_tests.append(uid)
            else:
                n_error += 1
                bad_warn.append(uid)
        else:  # error, fail and any unknown status fail closed
            n_error += 1
    if n_error or n_skipped:
        problems.append(f"ERROR: the last full build recorded {n_error} errors and {n_skipped} skipped nodes; "
                        f"app-data refuses to export. Fix and run: {REBUILD}")
    if bad_warn:
        problems.append(f"  warn on tests not configured with severity warn: {', '.join(sorted(bad_warn)[:5])}")

    # Bronze
    binfo, bproblems = check_bronze(bronze_dir, known_gaps_path)
    problems += bproblems
    if binfo is not None:
        try:
            lock_problems = _bronze_lock_verify(bronze_dir)
        except Exception as e:  # noqa: BLE001 — a lock check that cannot run is a block
            lock_problems = [f"cannot run: {type(e).__name__}: {e}"]
        if lock_problems:
            problems.append(f"ERROR: bronze_lock verify failed for {bronze_dir} ({len(lock_problems)} problems, "
                            f"first: {'; '.join(lock_problems[:3])}). Bronze is not the locked, certified copy.")
        if latest_bronze_run(bronze_dir) != binfo["run_id"]:
            problems.append(f"ERROR: the latest bronze run changed during validation (was {binfo['run_id']}); "
                            "not writing a marker. Re-run the build.")
        start_ts = started.timestamp()
        if any(p.stat().st_mtime > start_ts for p in list_bronze_runs(bronze_dir)):
            problems.append("ERROR: bronze manifests changed during the dbt build; not writing a marker. "
                            "Re-run the build.")

    # Binding to the provenance table
    try:
        rels, ids = _db_relations_and_build_id(db_path)
        if "mart_build_provenance" not in rels:
            problems.append(f"ERROR: warehouse {db_path} is missing required relations: mart_build_provenance. "
                            f"Run: {REBUILD}")
        elif len(ids) != 1 or ids[0] != build_id:
            got = ids[0] if len(ids) == 1 else f"<{len(ids)} rows>"
            problems.append(f"ERROR: marker build_id {build_id} does not match "
                            f"mart_build_provenance.dbt_invocation_id {got}; rebuild with: {REBUILD}")
    except Exception as e:  # noqa: BLE001
        problems.append(f"ERROR: cannot read mart_build_provenance from {db_path}: {type(e).__name__}: {e}")

    if problems:
        raise BuildFreshnessError(problems)

    sha = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    marker = {
        "schema": MARKER_SCHEMA,
        "build_id": build_id,
        "built_at": started.astimezone(timezone.utc).isoformat(),
        "marker_written_at": datetime.now(timezone.utc).isoformat(),
        "target": args.get("target"),
        "select": args.get("select") or [],
        "exclude": args.get("exclude") or [],
        "selector": args.get("selector") or None,
        "dbt_command": command,
        "dbt_version": dbt_version,
        "dbt_node_count": len(results),
        "dbt_nodes_expected": len(expected),
        "is_full": True,
        "success": True,
        "n_error": n_error,
        "n_skipped": n_skipped,
        "n_warn": n_warn,
        "warn_tests": sorted(warn_tests),
        "bronze_run_id": binfo["run_id"],
        "bronze_manifest_count": binfo["count"],
        "bronze_latest_manifest_sha256": binfo["sha256"],
        "bronze_manifest_status_ok": binfo["status_ok"],
        "n_sessions_ok": binfo["n_ok"],
        "n_sessions_skip_accepted": binfo["n_skip_accepted"],
        "n_acknowledged_gaps": len(binfo["acknowledged_gaps"]),
        "acknowledged_gaps": binfo["acknowledged_gaps"],
        "source_coverage": "acknowledged_gaps_present" if binfo["acknowledged_gaps"] else "complete",
        "git_sha": sha.strip() if sha is not None else None,
        "git_dirty": bool(status.strip()) if status is not None else None,
        "warehouse": _warehouse_stat(db_path),
    }
    mp = marker_path(db_path)
    fd, tmp = tempfile.mkstemp(dir=mp.parent, prefix=mp.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(marker, f, indent=2)
        os.replace(tmp, mp)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return marker


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("invalidate", help="delete the build marker (run before dbt)")
    inv.add_argument("--db", type=Path, required=True)
    wr = sub.add_parser("write", help="validate the finished dbt build and write the marker (run after dbt)")
    wr.add_argument("--db", type=Path, required=True)
    wr.add_argument("--bronze-dir", type=Path, default=BRONZE_DIR)
    wr.add_argument("--target-dir", type=Path, default=DBT_TARGET_DIR)
    wr.add_argument("--target", default="dev")
    wr.add_argument("--known-gaps", type=Path, default=KNOWN_GAPS_FILE)
    args = ap.parse_args(argv)

    if args.cmd == "invalidate":
        removed = invalidate(args.db)
        print(f"  build marker {'removed' if removed else 'not present'}: {marker_path(args.db)}")
        return 0
    try:
        m = write_marker(args.db, args.bronze_dir, args.target_dir, args.target, args.known_gaps)
    except BuildFreshnessError as e:
        for p in e.problems:
            print(p)
        return 1
    print(f"  build marker written: {marker_path(args.db)} (build {m['build_id']}, bronze run {m['bronze_run_id']}, "
          f"{m['dbt_node_count']} nodes, source_coverage={m['source_coverage']})")
    for g in m["acknowledged_gaps"]:
        print(f"  KNOWN GAP (acknowledged, not complete coverage): {g['season']} {g['session_type']}"
              f"{g['round_number']} {g['race_slug']} status={g['status']}: {g['reason']}")
    if m["warn_tests"]:
        print(f"  WARN: {m['n_warn']} tests passed with severity warn:")
        for t in m["warn_tests"]:
            print(f"    {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
