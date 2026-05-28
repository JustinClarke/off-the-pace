import subprocess
from pathlib import Path

from sybil import Sybil
from sybil.parsers.markdown import CodeBlockParser

_ROOT = Path(__file__).parent.parent


def _run_bash(example):
    result = subprocess.run(
        ["bash", "-c", example.parsed],
        capture_output=True,
        text=True,
        cwd=_ROOT,
    )
    if result.returncode != 0:
        raise ValueError(
            f"bash snippet failed (exit {result.returncode}):\n{result.stderr}"
        )


pytest_collect_file = Sybil(
    parsers=[CodeBlockParser("bash", evaluator=_run_bash)],
    patterns=["*.md"],
).pytest()
