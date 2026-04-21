import pytest
import pandas as pd
import fastf1
from api_client import F1ApiClient

@pytest.mark.integration
def test_fastf1_live_schedule_connectivity():
    """Verify that FastF1 can successfully query the live API for a season schedule."""
    # We fetch a recent schedule to ensure connection works
    schedule = fastf1.get_event_schedule(2024, backend="fastf1")
    assert isinstance(schedule, pd.DataFrame)
    assert not schedule.empty
    assert "RoundNumber" in schedule.columns
    assert "EventName" in schedule.columns

@pytest.mark.integration
def test_api_client_session_loading():
    """Verify that the F1ApiClient can load a session using the real API (uses cache)."""
    client = F1ApiClient()
    # Load a session that was likely already cached or is extremely small/fast
    # 2021 Round 1 is Bahrain. We just loaded it, so it's in the cache.
    session = client.get_session(2021, 1, 'R')
    assert session is not None
    assert session.event is not None
    assert session.event['EventName'] == 'Bahrain Grand Prix'
    
    # Verify that laps can be extracted from the loaded session
    laps = client.get_laps(session)
    assert isinstance(laps, pd.DataFrame)
    assert not laps.empty
    assert "LapNumber" in laps.columns
    assert "DriverNumber" in laps.columns
