"""Puts scripts/ on sys.path so tests can import the scripts as modules."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_bronze_lock(monkeypatch):
    """Scratch bronze dirs carry no MANIFEST.json; the lock check is tested on its own (monkeypatch.undo())."""
    import build_freshness

    monkeypatch.setattr(build_freshness, "_bronze_lock_verify", lambda bronze_dir: [])
