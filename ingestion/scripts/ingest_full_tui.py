#!/usr/bin/env python3
"""Interactive terminal view for `make ingest-full`.

Runs ingestion/scripts/ingest_full.sh and shows what it is doing: the phase, the
season being pulled, how many sessions were written, rate-limit waits, the known
gaps and any problems. Ctrl+C stops it cleanly. Running `make ingest-full` again
resumes, because finished sessions are skipped.

With no interactive terminal (cron, CI, a pipe) it prints the script's output
unchanged, and it never prompts. `rich` draws the screen when it is installed;
without it the output is plain text.

Environment: INGEST_PLAIN=1 forces plain output. PYTHON picks the interpreter.
"""
from __future__ import annotations

import collections
import os
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ingestion" / "scripts" / "ingest_full.sh"
KNOWN_GAPS = ROOT / "ingestion" / "known_gaps.txt"
RATE_WINDOW_S = 3600

PHASE_RE = re.compile(r"^=== \d{4}-\d\d-\d\d \d\d:\d\d:\d\d\s+(.*)$")
SEASON_RE = re.compile(r"=== Season (\d{4}) ===")
SEASON_DONE_RE = re.compile(r"Season (\d{4}) complete\s+R: (\d+) ok.*?Q: (\d+) ok")
OK_RE = re.compile(r"\[OK\]\s+([RQ])\s+(\d{4}) Rd(\d+) (\S+)")
WAIT_RE = re.compile(r"\[RATE LIMIT\].*?wait (\d+)/(\d+) this run")
PROBLEM_RE = re.compile(r"\[(ERR|THIN|DQ FAIL)\]|\bFAILED\b|NEEDS ATTENTION|\| ERROR \|")


@dataclass
class RunState:
    phase: str = "starting"
    season: str = "-"
    seasons_done: list[str] = field(default_factory=list)
    ok: dict[str, int] = field(default_factory=lambda: {"R": 0, "Q": 0})
    waits: int = 0
    wait_cap: int = 24
    wait_started: float | None = None
    problems: collections.deque = field(default_factory=lambda: collections.deque(maxlen=6))
    recent: collections.deque = field(default_factory=lambda: collections.deque(maxlen=8))
    result: str | None = None  # the script's final line once it has one


def apply_line(state: RunState, line: str, now: float | None = None) -> None:
    """Update the state from one line of ingest_full.sh / ingest.py output."""
    text = line.rstrip("\n")
    now = time.time() if now is None else now

    m = PHASE_RE.match(text)
    if m:
        state.phase = m.group(1)
        if state.phase.startswith("DONE") or "FAILED after" in state.phase:
            state.result = state.phase
    m = SEASON_RE.search(text)
    if m:
        state.season = m.group(1)
    m = SEASON_DONE_RE.search(text)
    if m and m.group(1) not in state.seasons_done:
        state.seasons_done.append(m.group(1))
    m = OK_RE.search(text)
    if m:
        state.ok[m.group(1)] += 1
    m = WAIT_RE.search(text)
    if m:
        state.waits, state.wait_cap = int(m.group(1)), int(m.group(2))
        state.wait_started = now

    is_script_line = "__main__" in text or text.startswith("===") or "[dry run]" in text
    if not is_script_line:
        return
    if PROBLEM_RE.search(text) and "NOTES" not in text:
        state.problems.append(text.strip()[:200])
    state.recent.append(text.strip()[:200])


def load_known_gaps(path: Path = KNOWN_GAPS) -> list[str]:
    if not path.exists():
        return []
    lines = (ln.strip() for ln in path.read_text().splitlines())
    return [ln for ln in lines if ln and not ln.startswith("#")]


def _fmt(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def render(state: RunState, gaps: list[str], started: float):
    """Build the dashboard (needs rich)."""
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("Phase", state.phase)
    done = ", ".join(state.seasons_done) or "none yet"
    grid.add_row("Season", f"{state.season}   (finished: {done})")
    grid.add_row("Written this run", f"races {state.ok['R']}   qualifying {state.ok['Q']}")
    if state.wait_started and time.time() - state.wait_started < RATE_WINDOW_S:
        left = RATE_WINDOW_S - (time.time() - state.wait_started)
        grid.add_row("Rate limit", f"FastF1 hourly cap: resuming in {_fmt(left)} "
                                   f"(wait {state.waits}/{state.wait_cap})")
    elif state.waits:
        grid.add_row("Rate limit", f"waits so far {state.waits}/{state.wait_cap}")
    grid.add_row("Elapsed", _fmt(time.time() - started))
    if state.result:
        grid.add_row("Result", state.result)

    return Group(
        Panel(grid, title="Bronze full ingest 2018-2026", border_style="cyan"),
        Panel(Text("\n".join(gaps) or "none"), title="Known gaps (recorded, not blocking)"),
        Panel(Text("\n".join(state.problems) or "none"), title="Problems", border_style="yellow"),
        Panel(Text("\n".join(state.recent) or "waiting for output..."), title="Recent"),
    )


def _confirm(gaps: list[str]) -> bool:
    print("Full Bronze ingest, 2018-2026: races and qualifying with telemetry, plus Jolpica.")
    print("FastF1 allows 500 calls an hour, so this takes many hours. It is safe to stop")
    print("(Ctrl+C) and resume later: finished sessions are skipped.")
    print(f"Known gaps that will be recorded, not blocking: {len(gaps)}")
    answer = input("Press Enter to start, or type q to quit: ").strip().lower()
    return answer != "q"


def _reader(proc: subprocess.Popen, out: queue.Queue) -> None:
    for line in proc.stdout:
        out.put(line)
    out.put(None)


def main(argv: list[str]) -> int:
    interactive = (sys.stdin.isatty() and sys.stdout.isatty()
                   and os.environ.get("INGEST_PLAIN") != "1")
    gaps = load_known_gaps()
    if interactive and "--yes" not in argv and not _confirm(gaps):
        print("Not started.")
        return 0

    rich_ok = interactive
    if rich_ok:
        try:
            from rich.console import Console
            from rich.live import Live
        except ImportError:
            rich_ok = False

    env = {**os.environ, "PYTHON": os.environ.get("PYTHON", "./.venv/bin/python")}
    proc = subprocess.Popen(["bash", str(SCRIPT)], cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1, env=env)
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=_reader, args=(proc, lines), daemon=True).start()

    state = RunState()
    started = time.time()
    finished = False
    try:
        if rich_ok:
            console = Console()
            with Live(render(state, gaps, started), console=console,
                      refresh_per_second=4, transient=False) as live:
                while not finished:
                    try:
                        line = lines.get(timeout=0.25)
                    except queue.Empty:
                        line = ""
                    if line is None:
                        finished = True
                    elif line:
                        apply_line(state, line)
                    live.update(render(state, gaps, started))
        else:
            while True:
                line = lines.get()
                if line is None:
                    break
                print(line, end="", flush=True)
                apply_line(state, line)
    except KeyboardInterrupt:
        print("\nStopping. Run `make ingest-full` again to resume (finished sessions are skipped).")
        proc.terminate()

    rc = proc.wait()
    if state.result and state.result.startswith("DONE"):
        print(f"\n{state.result}")
    elif rc != 0:
        print(f"\nStopped with exit code {rc}. Run `make ingest-full` again to resume; "
              f"finished sessions are skipped.")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
