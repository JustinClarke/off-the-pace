#!/usr/bin/env python3
"""Monitor a running ingestion log for failures and completion.

Stdlib-only Python port of monitor_ingest.sh tails a log file written by
`ingestion/src/ingest.py` and exits as soon as the run fails or completes, so it
can gate long backfills without a human watching the terminal.

Usage:
    python src/ingest.py --start-season 2018 --end-season 2024 --session R > ingest.log 2>&1 &
    python ingestion/scripts/monitor_ingest.py ingest.log

    # or via the Makefile:
    make monitor-ingest LOG=ingest.log

Exit codes:
    0  ingestion completed successfully ("=== COMPLETE:" seen)
    1  a real failure was detected (DQ fail, process error, OOM, disk full, killed)

FastF1 DEBUG-level noise (debug tracebacks, etc.) is ignored.
"""
import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

POLL_INTERVAL_S = 10

# Real failures worth aborting on mirrors monitor_ingest.sh.
FAILURE_RE = re.compile(
    r"\[DQ FAIL\]| ERROR | CRITICAL |ProcessRuntimeError|MemoryError|OSError.*disk|killed by|Killed"
)
COMPLETE_RE = re.compile(r"=== COMPLETE:")
PROGRESS_RE = re.compile(r"\[OK\]|\[PULL\]")


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def monitor(log_path: Path, poll_interval: int = POLL_INTERVAL_S) -> int:
    print(f"Monitoring: {log_path}")
    print(f"Polling every {poll_interval}s for failures or completion...\n", flush=True)

    pos = 0
    while True:
        if not log_path.exists():
            print(f"[{_ts()}] Waiting for ingestion output...", flush=True)
            time.sleep(poll_interval)
            continue

        size = log_path.stat().st_size
        if size > pos:
            with log_path.open("r", errors="replace") as fh:
                fh.seek(pos)
                new_text = fh.read()
                pos = fh.tell()

            failures = [ln for ln in new_text.splitlines() if FAILURE_RE.search(ln)]
            if failures:
                print("\n❌ FAILURE DETECTED in ingestion:")
                for ln in failures:
                    print(ln)
                print("\nRecent context:")
                _print_tail(log_path, 30)
                return 1

            if COMPLETE_RE.search(new_text):
                print("\n✅ Ingestion completed successfully!")
                _print_tail(log_path, 5)
                return 0

            progress = [ln for ln in new_text.splitlines() if PROGRESS_RE.search(ln)]
            if progress:
                print(f"[{_ts()}] {progress[-1].strip()}", flush=True)

        time.sleep(poll_interval)


def _print_tail(log_path: Path, n: int) -> None:
    lines = log_path.read_text(errors="replace").splitlines()
    for ln in lines[-n:]:
        print(ln)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log_file", type=Path, help="Path to the ingestion log to watch")
    parser.add_argument(
        "--poll-interval", type=int, default=POLL_INTERVAL_S, help=f"Seconds between checks (default: {POLL_INTERVAL_S})"
    )
    args = parser.parse_args()
    try:
        return monitor(args.log_file, args.poll_interval)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
