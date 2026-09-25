import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _network_disabled(*args, **kwargs):
    raise RuntimeError("FastF1 network access is disabled in offline unit tests")


@pytest.fixture(autouse=True)
def _isolate_bronze_and_network(request, tmp_path, monkeypatch):
    """Offline tests never touch data/bronze or the FastF1 network.

    Every ingest.py output directory is pointed at a per-test tmp bronze root,
    and FastF1's schedule/session entry points raise. Before this guard,
    ingest_season() tests fetched the real 2024 schedule and wrote it to
    data/bronze/schedule/. Tests marked `integration` are left alone.
    """
    if request.node.get_closest_marker("integration"):
        yield
        return
    import ingest
    for name, path in ingest._bronze_paths(tmp_path / "bronze").items():
        monkeypatch.setattr(ingest, name, path)
    monkeypatch.setattr(ingest.fastf1, "get_event_schedule", _network_disabled)
    monkeypatch.setattr(ingest.fastf1, "get_session", _network_disabled)
    yield
