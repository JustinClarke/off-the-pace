"""
WC-10e input/output guards: the 2024-25 seal, the run ledger with its OUTCOME DECODED line, and the loaders.

Rules come from the signed discovery registration, wi/WC-10-discovery-preregistration-DRAFT.md (commit 6fd0330,
SHA-256 4d679bf6..., DD-WC20). Section numbers (§) point into it. Nothing here fits anything.

  - §4 seal: `check_seasons` / `guard_path` refuse any season outside {2022, 2023} with SealError, BEFORE a file is
    opened. The loaders also check the decoded `season` column. The data gate's byte hashing of 2024-25 files
    (data_gate.py) is the only other contact with those files and decodes no column.
  - §0a ledger: `Ledger` appends to `_evidence/WC-10-discovery-<date>/PROVENANCE.txt`. Order enforced: START ->
    GATE (pass/fail) -> RUN START -> (first outcome column decode) OUTCOME DECODED -> OUTCOME-DERIVED WRITTEN
    (the run is COMPLETED). `load_outcomes` refuses unless the current start holds a passing gate line and
    RUN START, and writes OUTCOME DECODED before it decodes the first outcome column.
  - §0a restart rule: `restart_decision` (pure) and `Ledger.begin`. Infrastructure cause = exit by signal
    (status 128 + n) or OSError ENOSPC / EIO; any other exception is not.
  - §0a error rule: `safe_exception_line` gives type, file and line only, never the message or arguments.
  - Preflight: `Ledger.run_start` refuses RUN START (PreflightError) while any design_a.OPEN_CHOICES value is
    None or differs from the owner's ruling (design_a.preflight).
  - Amendments: B1_* and B2_* name the committed amendments. run_wc10 real mode refuses before anything is read
    unless the B1 and B2 SHA-256 are supplied, match the committed files (and the values recorded here), and an
    SG1-SG7 pass record exists (run_wc10.check_prerequisites); RUN START then records them (`extra`).

Columns. `OUTCOME_COLUMNS` is the §0a list. `OUTCOME_EQUIVALENT_COLUMNS` adds `seg_start_t` and `seg_end_t`:
they are not on the §0a list, but seg_end_t - seg_start_t is the segment time, so this module treats them as
outcome columns (loaded only after RUN START, and their decode writes OUTCOME DECODED). See the WC-10e report.
"""

from __future__ import annotations

import datetime as dt
import errno
import os
import re
import sys
import traceback
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from tasks.wake_calibration import data_gate as G

REPO = Path(__file__).resolve().parents[3]
WC = REPO / "_roadmap" / "_wake-calibration"
DEFAULT_PASS_DIR = WC / "_artifacts" / "WC-03-run" / "pass-table"
DEFAULT_SIDECAR_DIR = WC / "_artifacts" / "WC-10" / "sidecar"
DEFAULT_BRONZE = REPO / "data" / "bronze"

REGISTRATION = "wi/WC-10-discovery-preregistration-DRAFT.md"
REGISTRATION_COMMIT = "6fd03302c83cb8a23e080e7ab59fee599644761c"
REGISTRATION_SHA256 = "4d679bf6c94b12cf186776467478400c1feef89930be87d3fe36be49f1e8d248"

# Amendment B1 (twelve open choices; committed b89e54c, DD-WC22) and amendment B2 (tyre_life, DD-WC23). B2_SHA256
# is recorded here once the owner has committed B2 alone and given its hash; until then it is None and the supplied
# --b2-sha256 is checked against the committed file only.
B1_PATH = "wi/WC-10-amendment-B1-open-choices-DRAFT.md"
B1_COMMIT = "b89e54c"
B1_SHA256 = "c9566233bb25dcf078a8cc336682b289ec2d7494cfe6fb7189662d3c56b7b500"
B2_PATH = "wi/WC-10-amendment-B2-tyre-life-DRAFT.md"
B2_SHA256: str | None = None
SG_CHECKS = ("SG1", "SG2", "SG3", "SG4", "SG5", "SG6", "SG7")  # §17: all must PASS before RUN START

DISCOVERY_SEASONS = (2022, 2023)  # §4
SEALED_SEASONS = (2024, 2025)  # §4: no outcome column decoded until DD-WC21 is resolved

# §0a: outcome columns.
OUTCOME_COLUMNS = frozenset({
    "seg_time_s", "min_speed_kph", "delta_time_s", "ref_time_s", "apex_kph",  # pass table
    "exit_speed_kph", "coast_time_s", "partial_throttle_share",  # sidecar
    "LapTime", "Sector1Time", "Sector2Time", "Sector3Time",  # bronze laps
    "speed_kph", "throttle_pct",  # bronze telemetry
})
# Not on the §0a list, but their difference is the segment time (see module docstring).
OUTCOME_EQUIVALENT_COLUMNS = frozenset({"seg_start_t", "seg_end_t"})
GUARDED_COLUMNS = OUTCOME_COLUMNS | OUTCOME_EQUIVALENT_COLUMNS

# §2: the columns read. Structure = no guarded column; readable before RUN START (the synthetic SG checks run
# on the real 2022-23 structure with synthetic outcomes, §17).
PASS_STRUCTURE_COLUMNS = [
    "season", "race_id", "race", "driver", "lap", "stint", "compound", "tyre_life", "corner_id", "corner_number",
    "corner_class", "segment_basis", "leader", "leader_lap", "gap_s", "clear_ahead", "behind_1s", "tag", "reason",
]
PASS_OUTCOME_COLUMNS = ["seg_start_t", "seg_end_t", "seg_time_s", "min_speed_kph"]
SIDECAR_KEY = ["season", "race_id", "driver", "lap", "corner_id"]
SIDECAR_STRUCTURE_COLUMNS = SIDECAR_KEY + [
    "exit_bracket_m", "throttle_n", "drs_open_approach", "prev_lap_gap_s", "prev_lap_clear_ahead", "prev_lap_reason",
]
SIDECAR_OUTCOME_COLUMNS = ["exit_speed_kph", "coast_time_s", "partial_throttle_share"]
LAPS_STRUCTURE_COLUMNS = ["race_id", "Driver", "LapNumber", "Team"]
LAPS_OUTCOME_COLUMNS = ["LapTime"]

# Ledger events (§0a).
EV_START, EV_GATE, EV_RUN_START = "START", "GATE", "RUN START"
EV_OPENED, EV_DECODED, EV_WRITTEN = "OPENED", "OUTCOME DECODED", "OUTCOME-DERIVED WRITTEN"
EV_ERROR, EV_EXIT = "ERROR", "EXIT"
INFRA_ERRNOS = (errno.ENOSPC, errno.EIO)


class SealError(RuntimeError):
    """A season outside 2022-23 was asked for (§4). Raised before any file is opened."""


class LedgerError(RuntimeError):
    """The §0a order was broken (an outcome load before RUN START, RUN START without a passing gate, ...)."""


class RestartRefused(LedgerError):
    """§0a: the run is COMPLETED, or a restart after OUTCOME DECODED does not meet the rule."""


class PreflightError(LedgerError):
    """RUN START refused: an open choice of design A is not set to the owner's ruling."""


# --------------------------------------------------------------------------- the seal (§4)


def check_seasons(seasons) -> tuple[int, ...]:
    """§4: refuse any season outside {2022, 2023}. Returns the seasons as ints. Raises SealError."""
    out = tuple(int(s) for s in seasons)
    bad = sorted({s for s in out if s not in DISCOVERY_SEASONS})
    if bad:
        raise SealError(f"season(s) {bad} refused: WC-10e reads 2022-23 only (registration §4)")
    if not out:
        raise SealError("no season given")
    return out


_SEASON_RE = (re.compile(r"season=(\d{4})"), re.compile(r"_(\d{4})\.parquet$"))


def season_of_path(path) -> int | None:
    """The season a parquet path names (`season=YYYY` folder or `*_YYYY.parquet`); None if it names none."""
    text = unicodedata.normalize("NFC", str(path))
    for rx in _SEASON_RE:
        m = rx.search(text)
        if m:
            return int(m.group(1))
    return None


def guard_path(path) -> Path:
    """§4: refuse a file unless its path names a discovery season. A path naming no season is refused too."""
    s = season_of_path(path)
    if s is None:
        raise SealError(f"refused: {path} names no season, so the seal cannot be checked")
    check_seasons([s])
    return Path(path)


def check_season_column(frame: pd.DataFrame, path) -> None:
    if "season" in frame.columns:
        found = sorted(set(pd.to_numeric(frame["season"]).astype(int).unique()))
        bad = [s for s in found if s not in DISCOVERY_SEASONS]
        if bad:
            raise SealError(f"{path} holds season rows {bad}")


# --------------------------------------------------------------------------- errors (§0a)


def safe_exception_line(exc: BaseException) -> str:
    """§0a: type, file and line of the innermost frame only; never the message or arguments."""
    tb = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ is not None else []
    if tb:
        frame = tb[-1]
        return f"type={type(exc).__name__} file={os.path.basename(frame.filename)} line={frame.lineno}"
    return f"type={type(exc).__name__} file=? line=?"


def is_infrastructure_cause(exit_status: int | None = None, exc: BaseException | None = None) -> bool:
    """§0a: exit by a signal (status 128 + n, OOM killer included), or OSError with errno ENOSPC or EIO.
    Any other Python exception is not an infrastructure cause."""
    if exit_status is not None and int(exit_status) > 128:
        return True
    if exc is not None and isinstance(exc, OSError) and exc.errno in INFRA_ERRNOS:
        return True
    return False


# --------------------------------------------------------------------------- the ledger (§0a)


@dataclass
class StartRecord:
    """One start of the run, as parsed from the ledger."""

    number: int
    code: str = ""
    inputs: str = ""
    gate: bool | None = None  # None = no gate line yet
    run_start: bool = False
    decoded: bool = False
    written: bool = False
    exited: bool = False
    cause: str = ""  # "infrastructure" / "other" / "" (no EXIT line: the process ended without writing one)
    events: list[str] = field(default_factory=list)

    @property
    def state(self) -> str:
        return G.run_state(bool(self.gate), self.written)


def restart_decision(prior: list[StartRecord], code: str, inputs: str, prior_exit_status: int | None = None
                     ) -> tuple[bool, str]:
    """§0a restart rule, pure. Returns (allowed, reason).

    - Any earlier start that wrote an outcome-derived number: COMPLETED, never rerun under this registration.
    - The last start decoded an outcome column but wrote nothing: allowed only with byte-identical code and
      inputs, and only for an infrastructure cause (recorded on its EXIT line, or, when it has no EXIT line
      because the process was killed, `prior_exit_status` > 128 supplied by the operator).
    - Otherwise (gate failure, or a crash before the first decode): restartable.
    """
    if any(s.written for s in prior):
        return False, "COMPLETED: an outcome-derived number was written; no rerun under this registration (§0a)"
    if not prior:
        return True, "first start"
    last = prior[-1]
    if not last.decoded:
        return True, "restartable: nothing outcome-derived written and no outcome column decoded"
    if (last.code, last.inputs) != (code, inputs):
        return False, "code or inputs changed after OUTCOME DECODED: post-hoc amendment required (§0a)"
    infra = last.cause == "infrastructure" or (not last.exited and is_infrastructure_cause(prior_exit_status))
    if not infra:
        return False, "the start after OUTCOME DECODED did not end by an infrastructure cause (§0a)"
    return True, "restart after OUTCOME DECODED: byte-identical code and inputs, infrastructure cause"


class Ledger:
    """Append-only run ledger, `<evidence>/PROVENANCE.txt` (§0a). Every line: `<UTC time>  <EVENT>  <detail>`.
    A line never carries an outcome value (callers pass names, paths, digests and states only)."""

    def __init__(self, evidence_dir: Path):
        self.dir = Path(evidence_dir)
        self.path = self.dir / "PROVENANCE.txt"

    # -- reading
    def starts(self) -> list[StartRecord]:
        if not self.path.is_file():
            return []
        out: list[StartRecord] = []
        for raw in self.path.read_text().splitlines():
            parts = raw.split("  ", 2)
            if len(parts) < 2:
                continue
            ev, detail = parts[1], (parts[2] if len(parts) > 2 else "")
            if ev == EV_START:
                kv = dict(x.split("=", 1) for x in detail.split() if "=" in x)
                out.append(StartRecord(number=len(out) + 1, code=kv.get("code", ""), inputs=kv.get("inputs", "")))
            if not out:
                continue
            s = out[-1]
            s.events.append(ev)
            if ev == EV_GATE:
                s.gate = detail.startswith("PASS")
            elif ev == EV_RUN_START:
                s.run_start = True
            elif ev == EV_DECODED:
                s.decoded = True
            elif ev == EV_WRITTEN:
                s.written = True
            elif ev == EV_EXIT:
                s.exited = True
                kv = dict(x.split("=", 1) for x in detail.split() if "=" in x)
                s.cause = kv.get("cause", "other")
        return out

    def current(self) -> StartRecord:
        s = self.starts()
        if not s:
            raise LedgerError("no START in the ledger")
        return s[-1]

    # -- writing
    def _write(self, event: str, detail: str = "") -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with open(self.path, "a") as f:
            f.write(f"{now}  {event}  {detail}".rstrip() + "\n")

    def begin(self, reason: str, code: str, inputs: str, prior_exit_status: int | None = None) -> StartRecord:
        """New start. Refuses (RestartRefused) per `restart_decision`. Logs time, reason and digests."""
        prior = self.starts()
        ok, why = restart_decision(prior, code, inputs, prior_exit_status)
        if prior and not prior[-1].exited and prior_exit_status is not None:
            self._write(EV_EXIT, f"start={prior[-1].number} recorded_later exit_status={int(prior_exit_status)} "
                                 f"cause={'infrastructure' if is_infrastructure_cause(prior_exit_status) else 'other'}")
        if not ok:
            raise RestartRefused(why)
        reason = " ".join(str(reason).split())
        self._write(EV_START, f"n={len(prior) + 1} code={code} inputs={inputs} decision={why!r} reason={reason!r}")
        return self.current()

    def gate(self, ok: bool, lines: list[str]) -> None:
        """Gate result lines (data_gate.run_checks). A failure also writes EXIT FAILED_RESTARTABLE."""
        cur = self.current()
        if cur.gate is not None:
            raise LedgerError("gate already run in this start")
        for line in lines:
            self._write("GATE-LINE", line)
        self._write(EV_GATE, "PASS" if ok else "FAIL")
        if not ok:
            self.exit(cause="gate")

    def run_start(self, extra: str = "") -> None:
        """RUN START after a passing gate and the preflight. `extra` (names and digests only: amendment hashes,
        SG record digest) is appended to the line."""
        cur = self.current()
        if cur.gate is not True:
            raise LedgerError("RUN START refused: no passing gate line in this start (§0a)")
        if cur.run_start:
            raise LedgerError("RUN START already written in this start")
        from tasks.wake_calibration import design_a as A  # lazy: design_a imports this module

        try:
            A.preflight()
        except A.OpenChoicesUnset as exc:
            raise PreflightError(str(exc)) from exc
        extra = " ".join(str(extra).split())
        self._write(EV_RUN_START, f"registration_sha256={REGISTRATION_SHA256}" + (f" {extra}" if extra else ""))

    def require_run_start(self) -> StartRecord:
        cur = self.current()
        if cur.gate is not True or not cur.run_start:
            raise LedgerError("outcome load refused: the ledger holds no passing gate and RUN START for this start")
        if cur.exited:
            raise LedgerError("outcome load refused: this start has exited")
        return cur

    def opened(self, path, columns) -> None:
        self._write(EV_OPENED, f"{unicodedata.normalize('NFC', str(path))} columns={','.join(columns)}")

    def outcome_decoded(self, column: str, path) -> None:
        """Written once per start, before the first outcome column is decoded."""
        cur = self.require_run_start()
        if not cur.decoded:
            self._write(EV_DECODED, f"first={column} file={unicodedata.normalize('NFC', str(path))}")

    def outcome_written(self, where: str) -> None:
        """The run COMPLETES here (§0a): call before the first outcome-derived number reaches any file or stream."""
        cur = self.require_run_start()
        if not cur.written:
            self._write(EV_WRITTEN, f"first_destination={where}")

    def error(self, exc: BaseException) -> None:
        self._write(EV_ERROR, safe_exception_line(exc))

    def exit(self, cause: str = "", exc: BaseException | None = None) -> str:
        cur = self.current()
        if cause in ("", None):
            cause = "infrastructure" if is_infrastructure_cause(exc=exc) else ("other" if exc else "none")
        state = cur.state
        self._write(EV_EXIT, f"state={state} cause={cause} outcome_written={cur.written}")
        return state


def guarded_main(fn, ledger: Ledger) -> int:
    """§0a entry-point wrapper: run fn(); on any exception write only its type, file and line to the ledger and to
    stderr (never the message or arguments), record the exit and return 1."""
    try:
        fn()
    except BaseException as exc:  # noqa: BLE001 - §0a: every exception is caught
        line = safe_exception_line(exc)
        try:
            ledger.error(exc)
            ledger.exit(exc=exc)
        finally:
            print(f"ERROR {line}", file=sys.stderr)
        return 1
    ledger.exit()
    return 0


# --------------------------------------------------------------------------- loaders


def _read(path: Path, columns: list[str], ledger: Ledger | None, opened: list | None) -> pd.DataFrame:
    guard_path(path)
    if ledger is not None:
        ledger.opened(path, columns)
    if opened is not None:
        opened.append((unicodedata.normalize("NFC", str(path)), tuple(columns)))
    frame = pq.read_table(path, columns=columns).to_pandas()
    check_season_column(frame, path)
    return frame


def _refuse_guarded(columns) -> None:
    bad = sorted(set(columns) & GUARDED_COLUMNS)
    if bad:
        raise LedgerError(f"structure loader refuses outcome column(s) {bad}")


def load_structure(pass_dir: Path = DEFAULT_PASS_DIR, sidecar_dir: Path = DEFAULT_SIDECAR_DIR,
                   seasons=DISCOVERY_SEASONS, ledger: Ledger | None = None, opened: list | None = None
                   ) -> pd.DataFrame:
    """Pass table structure columns joined 1:1 to the sidecar structure columns, 2022-23 only. No outcome column
    is decoded, so this needs no RUN START (the SG checks use it, §17)."""
    seasons = check_seasons(seasons)
    _refuse_guarded(PASS_STRUCTURE_COLUMNS + SIDECAR_STRUCTURE_COLUMNS)
    p = pd.concat([_read(Path(pass_dir) / f"pass_table_{s}.parquet", PASS_STRUCTURE_COLUMNS, ledger, opened)
                   for s in seasons], ignore_index=True)
    sc = pd.concat([_read(Path(sidecar_dir) / f"sidecar_{s}.parquet", SIDECAR_STRUCTURE_COLUMNS, ledger, opened)
                    for s in seasons], ignore_index=True)
    out = p.merge(sc, on=SIDECAR_KEY, how="left", validate="one_to_one")
    return out


def load_lap_structure(bronze: Path = DEFAULT_BRONZE, seasons=DISCOVERY_SEASONS, ledger: Ledger | None = None,
                       opened: list | None = None) -> pd.DataFrame:
    """Bronze laps structure (race_id, driver, lap, Team), 2022-23 only."""
    seasons = check_seasons(seasons)
    frames = []
    for s in seasons:
        for f in sorted(Path(bronze).glob(f"laps/season={s}/race=*/*.parquet")):
            frames.append(_read(f, LAPS_STRUCTURE_COLUMNS, ledger, opened))
    laps = pd.concat(frames, ignore_index=True)
    return laps.rename(columns={"Driver": "driver", "LapNumber": "lap", "Team": "team"})


def load_outcomes(ledger: Ledger, pass_dir: Path = DEFAULT_PASS_DIR, sidecar_dir: Path = DEFAULT_SIDECAR_DIR,
                  bronze: Path = DEFAULT_BRONZE, seasons=DISCOVERY_SEASONS) -> dict[str, pd.DataFrame]:
    """The outcome columns, keyed for joining: {"pass": key + seg_start_t, seg_end_t, seg_time_s, min_speed_kph;
    "sidecar": key + exit_speed_kph, coast_time_s, partial_throttle_share; "laps": race_id, driver, lap, LapTime
    (seconds)}. Refuses unless the ledger holds a passing gate and RUN START for this start; writes OUTCOME
    DECODED before the first decode. Seasons outside 2022-23 are refused before anything else."""
    seasons = check_seasons(seasons)
    ledger.require_run_start()
    out = {}
    key = SIDECAR_KEY
    frames = []
    for s in seasons:
        path = guard_path(Path(pass_dir) / f"pass_table_{s}.parquet")
        ledger.outcome_decoded(PASS_OUTCOME_COLUMNS[0], path)
        frames.append(_read(path, key + PASS_OUTCOME_COLUMNS, ledger, None))
    out["pass"] = pd.concat(frames, ignore_index=True)
    frames = []
    for s in seasons:
        path = guard_path(Path(sidecar_dir) / f"sidecar_{s}.parquet")
        ledger.outcome_decoded(SIDECAR_OUTCOME_COLUMNS[0], path)
        frames.append(_read(path, key + SIDECAR_OUTCOME_COLUMNS, ledger, None))
    out["sidecar"] = pd.concat(frames, ignore_index=True)
    frames = []
    for s in seasons:
        for f in sorted(Path(bronze).glob(f"laps/season={s}/race=*/*.parquet")):
            guard_path(f)
            ledger.outcome_decoded("LapTime", f)
            lap = _read(f, ["race_id", "Driver", "LapNumber", "LapTime"], ledger, None)
            frames.append(lap)
    laps = pd.concat(frames, ignore_index=True).rename(columns={"Driver": "driver", "LapNumber": "lap"})
    laps["lap_time_s"] = pd.to_timedelta(laps.pop("LapTime")).dt.total_seconds()
    out["laps"] = laps
    return out
