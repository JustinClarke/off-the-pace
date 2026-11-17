#!/usr/bin/env python3
"""
Write-once lock for the Bronze Parquet layer.

  manifest  - SHA-256 of every file under a bronze root, written to MANIFEST.json
  lock      - writes the manifest, then sets the macOS user-immutable flag (uchg)
              on every file and directory, so writes fail until unlock
  unlock    - clears uchg (only for a deliberate rebuild into a new run folder)
  verify    - re-hashes every file and compares with MANIFEST.json; exit 1 on
              any added, removed or changed file

Immutability is enforced by the flag; verify catches a change even if the flag
was cleared. Run verify before any dbt or app build reads bronze.

Usage:
  python bronze_lock.py manifest <bronze_root>
  python bronze_lock.py lock     <bronze_root>
  python bronze_lock.py unlock   <bronze_root>
  python bronze_lock.py verify   <bronze_root>
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

MANIFEST_NAME = "MANIFEST.json"
CHUNK = 1 << 20


def _files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.name == MANIFEST_NAME and p.parent == root:
                continue
            yield p


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def build_manifest(root: Path) -> dict:
    entries = {}
    for p in _files(root):
        rel = p.relative_to(root).as_posix()
        entries[rel] = {"sha256": _sha256(p), "bytes": p.stat().st_size}
    return {"root": root.name, "file_count": len(entries), "files": entries}


def write_manifest(root: Path) -> Path:
    out = root / MANIFEST_NAME
    out.write_text(json.dumps(build_manifest(root), indent=2, sort_keys=True))
    return out


def _chflags(root: Path, flag: str) -> None:
    # chflags -R handles files and directories; uchg = user immutable (owner can clear).
    # macOS only. Elsewhere the immutable flag is skipped: the manifest still gives
    # tamper detection through verify(), which is the check that matters.
    if sys.platform != "darwin":
        print(f"[bronze_lock] immutable flag skipped on {sys.platform} (macOS only); "
              f"manifest and verify still apply")
        return
    subprocess.run(["chflags", "-R", flag, str(root)], check=True)


def lock(root: Path) -> None:
    write_manifest(root)
    _chflags(root, "uchg")


def unlock(root: Path) -> None:
    _chflags(root, "nouchg")


def verify(root: Path) -> tuple[bool, list[str]]:
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.exists():
        return False, ["no MANIFEST.json"]
    expected = json.loads(manifest_path.read_text())["files"]
    actual = build_manifest(root)["files"]
    problems = []
    for rel in sorted(set(expected) - set(actual)):
        problems.append(f"missing: {rel}")
    for rel in sorted(set(actual) - set(expected)):
        problems.append(f"added: {rel}")
    for rel in sorted(set(expected) & set(actual)):
        if expected[rel]["sha256"] != actual[rel]["sha256"]:
            problems.append(f"changed: {rel}")
    return not problems, problems


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in {"manifest", "lock", "unlock", "verify"}:
        print(__doc__)
        return 2
    cmd, root = argv[1], Path(argv[2]).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    if cmd == "manifest":
        print(write_manifest(root))
    elif cmd == "lock":
        lock(root)
        print(f"locked {root}")
    elif cmd == "unlock":
        unlock(root)
        print(f"unlocked {root}")
    else:
        ok, problems = verify(root)
        if ok:
            print(f"OK {root}")
            return 0
        for p in problems:
            print(p)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
