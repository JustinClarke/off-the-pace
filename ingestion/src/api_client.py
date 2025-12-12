"""
F1ApiClient   unified wrapper for FastF1 (historical) and OpenF1 (live) APIs.
"""

import fastf1
import pandas as pd
import requests
import time
from typing import Optional, Dict, Any
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent
cache_dir = project_root / 'data' / 'cache'


class F1ApiClient:
    """Unified wrapper for FastF1 (historical) and OpenF1 (live) APIs."""

    def __init__(self):
        os.makedirs(cache_dir, exist_ok=True)
        fastf1.Cache.enable_cache(str(cache_dir))

    def get_session(self, year: int, round_num: int, session_type: str = 'R') -> fastf1.core.Session:
        """
        Load and return a FastF1 session.

        Args:
            year: Season year (e.g. 2024)
            round_num: Round number   always use integer, not event name string
            session_type: 'R' race, 'Q' qualifying, 'FP1'/'FP2'/'FP3' practice

        Returns:
            Loaded FastF1 Session object
        """
        logger.info(f"Loading session: {year} Rd{round_num} [{session_type}]")
        session = fastf1.get_session(year, round_num, session_type)
        session.load()
        return session

    def get_laps(self, session: fastf1.core.Session) -> pd.DataFrame:
        """
        Extract laps from a FastF1 session and add race metadata.

        Column names are kept in FastF1's native PascalCase.
        Renaming to snake_case happens downstream in dbt stg_f1_laps.sql.

        Returns:
            DataFrame with FastF1 lap columns + race_id
        """
        df = pd.DataFrame(session.laps)
        df['race_id'] = f"{session.event['EventDate'].year}_{session.event['RoundNumber']}"
        logger.info(f"Extracted {len(df)} laps")
        return df

    def get_live_lap(self, driver_number: int, lap_number: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a lap from the OpenF1 live API with exponential backoff retry.

        Retry schedule: immediate → 2s → 4s (3 attempts total).

        Args:
            driver_number: FIA driver number (e.g. 44)
            lap_number: Lap number within the session

        Returns:
            Lap data dict, or None if unavailable after retries
        """
        url = f"https://api.openf1.org/v1/laps?driver_number={driver_number}&lap_number={lap_number}"

        for attempt in range(3):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                return data[0] if data else None
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/3 failed: {e}")
                time.sleep(2 ** attempt)

        logger.error(f"OpenF1 lap fetch failed after 3 attempts (driver={driver_number}, lap={lap_number})")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = F1ApiClient()
    session = client.get_session(2021, 1, 'R')
    laps = client.get_laps(session)
    logger.info(f"Retrieved {len(laps)} laps.")
