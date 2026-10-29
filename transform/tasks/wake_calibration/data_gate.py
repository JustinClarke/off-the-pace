"""WC-10 Stage 0 input data gate (WC-10c). Read-only: file bytes and path names only. No parquet column is
decoded, so no outcome column (segment time, minimum speed, delta time) is ever read.

Restart rule (plan section 9; registration text is WC-10d):
    A gate failure that has read no outcome column is restartable. A run "completes" only once an
    outcome-derived number has been written. `run_state()` is the pure function the run script uses:
    it returns COMPLETED only if an outcome number was written; a gate failure before that is
    RESTARTABLE; a gate failure after an outcome number was written is NOT restartable (the run is
    burned: it must be reported, not retried). This closes the trap that ended WC-03 (G3.4 digest
    mismatch caused by NFD path names).

The bronze digest reuses run_wc03.bronze_digest (NFC-normalised paths, uncommitted fix kept as is).
`digest_lines` is the same recipe over an arbitrary file set, for tests and for other scopes.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import os
import sys
import unicodedata
from pathlib import Path

from tasks.wake_calibration import run_wc03 as R

COMPLETED, RESTARTABLE, BURNED, RUNNING = "COMPLETED", "FAILED_RESTARTABLE", "FAILED_NOT_RESTARTABLE", "RUNNING"
DEFAULT_PASS_DIR = R.WC / "_artifacts/WC-03-run/pass-table"


def run_state(gate_ok: bool, outcome_number_written: bool) -> str:
    """Pure rule. A run completes only once an outcome-derived number is written (and the gate passed)."""
    if outcome_number_written:
        return COMPLETED if gate_ok else BURNED
    return RUNNING if gate_ok else RESTARTABLE


def is_restartable(gate_ok: bool, outcome_number_written: bool) -> bool:
    return run_state(gate_ok, outcome_number_written) == RESTARTABLE


def digest_lines(root: Path, files: list[Path]) -> tuple[int, str]:
    """Same recipe as run_wc03.bronze_digest: `<sha256>  <NFC path relative to root>` lines, sorted bytewise
    by path, newline-terminated; SHA-256 of the text. Independent of input order."""
    lines = [(unicodedata.normalize("NFC", os.path.relpath(p, root)), R.sha256_file(Path(p))) for p in files]
    lines.sort(key=lambda x: x[0].encode())
    text = "".join(f"{h}  {rel}\n" for rel, h in lines)
    return len(lines), hashlib.sha256(text.encode()).hexdigest()


def pass_table_digest(pass_dir: Path) -> tuple[int, str, dict[str, str]]:
    files = sorted(Path(pass_dir).glob("pass_table_*.parquet"))
    n, d = digest_lines(pass_dir, files)
    return n, d, {unicodedata.normalize("NFC", f.name): R.sha256_file(f) for f in files}


SCOPE_GLOBS = tuple(f"{t}/season=*/race=*/*.parquet" for t in ("laps", "telemetry", "weather"))


def scoped_bronze_digest(bronze: Path = R.BRONZE) -> tuple[int, str]:
    """WC-10 scope: laps, telemetry and weather only (paths and file bytes; no column is decoded)."""
    files = sorted({Path(p) for g in SCOPE_GLOBS for p in glob.glob(str(Path(bronze) / g))})
    return digest_lines(bronze, files)


def sha256sums_mismatches(pass_dir: Path, per_file: dict[str, str], prefix: str = "pass_table_") -> list[str]:
    """Compare per-file hashes with the SHA256SUMS in the folder (lines whose name starts with `prefix`).
    A missing SHA256SUMS file is reported as a mismatch of "SHA256SUMS"."""
    sums = Path(pass_dir) / "SHA256SUMS"
    if not sums.is_file():
        return ["SHA256SUMS"]
    want = {}
    for line in sums.read_text().splitlines():
        if line.strip():
            h, name = line.split(None, 1)
            if name.strip().startswith(prefix):
                want[unicodedata.normalize("NFC", name.strip().lstrip("*"))] = h
    bad = [k for k in sorted(set(want) | set(per_file)) if want.get(k) != per_file.get(k)]
    return bad


DEFAULT_SIDECAR_DIR = R.WC / "_artifacts/WC-10/sidecar"

# Registered digests (draft section 16). Changing one is a pre-result amendment, not an edit here.
EXPECTED = {
    "pass_table": (8, "188dac5e31279a4d4edf6629a095ac1dfb7511254e5a59d9ad0d619bd734dc24"),
    "scoped_bronze": (517, "80d9623bf0c0447bdb3ef642af0250f6eb70c00e254e039ac8bb81ffdd068b3d"),
    "sidecar": (8, "8595ce93ca6ff211551bce2546d6635078f0a2cb60dd92ee92f1917cf5ea9d91"),
    "full_bronze": (R.G3_BRONZE_FILES, R.G3_BRONZE_SHA256),
}


def sidecar_digest(sidecar_dir: Path) -> tuple[int, str, dict[str, str]]:
    files = sorted(Path(sidecar_dir).glob("sidecar_*.parquet"))
    n, d = digest_lines(sidecar_dir, files)
    return n, d, {unicodedata.normalize("NFC", f.name): R.sha256_file(f) for f in files}


def _verdict(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def check_folder(label: str, n: int, d: str, exp: tuple[int, str], bad: list[str] | None = None) -> tuple[bool, str]:
    ok = (n, d) == tuple(exp) and not bad
    extra = f"  per-file vs SHA256SUMS: {'MATCH' if not bad else 'MISMATCH ' + str(bad)}" if bad is not None else ""
    return ok, f"{label}: {_verdict(ok)}  files {n} (want {exp[0]})  digest {d} (want {exp[1]}){extra}"


def run_checks(bronze: Path, pass_dir: Path, sidecar_dir: Path, expected: dict | None = None) -> tuple[bool, list[str]]:
    """Checks 1-4, one line each. Returns (all_pass, lines). Reads file bytes and names only."""
    exp = {**EXPECTED, **(expected or {})}
    results = []
    pn, pd_, per = pass_table_digest(pass_dir)
    results.append(check_folder("check 1 pass table", pn, pd_, exp["pass_table"], sha256sums_mismatches(pass_dir, per, "pass_table_")))
    sn, sd = scoped_bronze_digest(bronze)
    results.append(check_folder("check 2 scoped bronze (laps+telemetry+weather)", sn, sd, exp["scoped_bronze"]))
    cn, cd, cper = sidecar_digest(sidecar_dir)
    results.append(check_folder("check 3 sidecar", cn, cd, exp["sidecar"], sha256sums_mismatches(sidecar_dir, cper, "sidecar_")))
    n, d = R.bronze_digest(bronze)
    results.append(check_folder("check 4 full bronze (run_wc03 file set)", n, d, exp["full_bronze"]))
    return all(r[0] for r in results), [r[1] for r in results]


def main(argv=None, expected: dict | None = None) -> int:
    ap = argparse.ArgumentParser(description="WC-10 input data gate, dry run (reads no outcome column).")
    ap.add_argument("--bronze", type=Path, default=R.BRONZE)
    ap.add_argument("--pass-table-dir", type=Path, default=DEFAULT_PASS_DIR)
    ap.add_argument("--sidecar-dir", type=Path, default=DEFAULT_SIDECAR_DIR)
    a = ap.parse_args(argv)
    ok, lines = run_checks(a.bronze, a.pass_table_dir, a.sidecar_dir, expected)
    for line in lines:
        print(line)
    print("outcome columns read: none (file bytes and path names only)")
    print(f"GATE: {_verdict(ok)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
