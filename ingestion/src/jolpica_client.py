"""
JolpicaClient   reference-data client for official standings and classified pit stops.

Ergast (https://ergast.com) shut down after the 2024 season. Jolpica
(https://api.jolpi.ca) is its drop-in successor with an Ergast-compatible JSON
schema, so the flattening logic here doubles as an Ergast client if ever needed.

Scope (ingestion-v0.2 step 9): driver standings, constructor standings, and
classified pit stops → `data/bronze/reference/jolpica/`. This is *reference*
data, not timing data: it never feeds the live path, only historical marts.

Politeness: Jolpica publishes a sustained limit of ~4 req/s and a burst cap.
Every request goes through `_get`, which sleeps `min_interval_s` between calls
and retries with exponential backoff, mirroring `F1ApiClient.get_live_lap`.
"""

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
JOLPICA_DIR = PROJECT_ROOT / "data" / "bronze" / "reference" / "jolpica"

BASE_URL = "https://api.jolpi.ca/ergast/f1"
# Ergast caps page size at 100; Jolpica keeps the same ceiling.
PAGE_LIMIT = 100


class JolpicaClient:
    """Ergast-compatible REST client for standings and pit stops."""

    def __init__(self, base_url: str = BASE_URL, min_interval_s: float = 0.30):
        self.base_url = base_url.rstrip("/")
        self.min_interval_s = min_interval_s
        self._last_request_at = 0.0

    # ------------------------------------------------------------------
    # HTTP   politely rate-limited, paginated, retried
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_s:
            time.sleep(self.min_interval_s - elapsed)
        self._last_request_at = time.monotonic()

    def _get(self, path: str, max_attempts: int = 4) -> dict[str, Any]:
        """
        GET `{base_url}/{path}.json`, returning the parsed `MRData` envelope.

        Retries up to max_attempts with exponential backoff (1s, 2s, 4s). A 429
        honours the `Retry-After` header when present. Raises the last exception
        if every attempt fails.
        """
        url = f"{self.base_url}/{path.strip('/')}.json"
        last_exc: Optional[Exception] = None
        for attempt in range(max_attempts):
            self._throttle()
            try:
                resp = requests.get(
                    url,
                    params={"limit": PAGE_LIMIT, "offset": 0},
                    timeout=15,
                )
                resp.raise_for_status()
                return resp.json()["MRData"]
            except requests.HTTPError as exc:
                last_exc = exc
                status = exc.response.status_code if exc.response is not None else None
                if status == 429 and attempt < max_attempts - 1:
                    retry_after = float(exc.response.headers.get("Retry-After", 2 ** attempt))
                    logger.warning(f"  429 from Jolpica   backing off {retry_after:.0f}s")
                    time.sleep(retry_after)
                    continue
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    logger.warning(f"  Attempt {attempt + 1}/{max_attempts} failed: {exc}")
                    time.sleep(2 ** attempt)
        logger.error(f"Jolpica GET failed after {max_attempts} attempts: {url}")
        raise last_exc

    def _get_paginated(self, path: str) -> list[dict[str, Any]]:
        """
        Fetch every page for an endpoint, returning the list of `MRData`
        envelopes. Most standings/pit-stop queries fit one page, but a full
        season's pit stops can exceed 100 rows.
        """
        first = self._get(path)
        total = int(first.get("total", 0))
        envelopes = [first]
        offset = PAGE_LIMIT
        while offset < total:
            url = f"{self.base_url}/{path.strip('/')}.json"
            self._throttle()
            resp = requests.get(url, params={"limit": PAGE_LIMIT, "offset": offset}, timeout=15)
            resp.raise_for_status()
            envelopes.append(resp.json()["MRData"])
            offset += PAGE_LIMIT
        return envelopes

    # ------------------------------------------------------------------
    # Endpoint accessors   each returns a flat snake_case DataFrame
    # ------------------------------------------------------------------

    def get_driver_standings(self, season: int, round_num: Optional[int] = None) -> pd.DataFrame:
        """Driver championship standings for a season (optionally after a round)."""
        path = f"{season}/{round_num}/driverStandings" if round_num else f"{season}/driverStandings"
        return _flatten_standings(self._get(path), kind="driver", season=season)

    def get_constructor_standings(self, season: int, round_num: Optional[int] = None) -> pd.DataFrame:
        """Constructor championship standings for a season (optionally after a round)."""
        path = (
            f"{season}/{round_num}/constructorStandings"
            if round_num
            else f"{season}/constructorStandings"
        )
        return _flatten_standings(self._get(path), kind="constructor", season=season)

    def get_pit_stops(self, season: int, round_num: int) -> pd.DataFrame:
        """Classified pit stops for one race (driver, lap, stop number, duration)."""
        envelopes = self._get_paginated(f"{season}/{round_num}/pitstops")
        frames = [_flatten_pit_stops(env, season=season, round_num=round_num) for env in envelopes]
        frames = [f for f in frames if not f.empty]
        return pd.concat(frames, ignore_index=True) if frames else _empty_pit_stops()


# ----------------------------------------------------------------------
# Flatteners   Ergast nests deeply; bronze wants one tidy row per entity
# ----------------------------------------------------------------------

def _flatten_standings(mrdata: dict[str, Any], kind: str, season: int) -> pd.DataFrame:
    lists = mrdata.get("StandingsTable", {}).get("StandingsLists", [])
    if not lists:
        return pd.DataFrame()
    standings_list = lists[0]
    round_num = standings_list.get("round")
    rows: list[dict[str, Any]] = []

    if kind == "driver":
        for s in standings_list.get("DriverStandings", []):
            driver = s.get("Driver", {})
            constructors = s.get("Constructors", [{}])
            rows.append({
                "season":           season,
                "round":            int(round_num) if round_num else None,
                "position":         _to_int(s.get("position")),
                "position_text":    s.get("positionText"),
                "points":           _to_float(s.get("points")),
                "wins":             _to_int(s.get("wins")),
                "driver_id":        driver.get("driverId"),
                "driver_number":    _to_int(driver.get("permanentNumber")),
                "driver_code":      driver.get("code"),
                "given_name":       driver.get("givenName"),
                "family_name":      driver.get("familyName"),
                "constructor_id":   constructors[0].get("constructorId") if constructors else None,
                "constructor_name": constructors[0].get("name") if constructors else None,
            })
    else:  # constructor
        for s in standings_list.get("ConstructorStandings", []):
            constructor = s.get("Constructor", {})
            rows.append({
                "season":           season,
                "round":            int(round_num) if round_num else None,
                "position":         _to_int(s.get("position")),
                "position_text":    s.get("positionText"),
                "points":           _to_float(s.get("points")),
                "wins":             _to_int(s.get("wins")),
                "constructor_id":   constructor.get("constructorId"),
                "constructor_name": constructor.get("name"),
                "nationality":      constructor.get("nationality"),
            })

    return pd.DataFrame(rows)


def _flatten_pit_stops(mrdata: dict[str, Any], season: int, round_num: int) -> pd.DataFrame:
    races = mrdata.get("RaceTable", {}).get("Races", [])
    if not races:
        return _empty_pit_stops()
    race = races[0]
    rows = [{
        "season":      season,
        "round":       round_num,
        "race_name":   race.get("raceName"),
        "driver_id":   p.get("driverId"),
        "stop":        _to_int(p.get("stop")),
        "lap":         _to_int(p.get("lap")),
        "time_of_day": p.get("time"),
        "duration_s":  _to_float(p.get("duration")),
    } for p in race.get("PitStops", [])]
    return pd.DataFrame(rows) if rows else _empty_pit_stops()


def _empty_pit_stops() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "season", "round", "race_name", "driver_id",
        "stop", "lap", "time_of_day", "duration_s",
    ])


def _to_int(v: Any) -> Optional[int]:
    try:
        return int(v) if v is not None and v != "" else None
    except (ValueError, TypeError):
        return None


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None and v != "" else None
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------
# Writers   hive-partitioned bronze, snappy parquet (matches ingest.py)
# ----------------------------------------------------------------------

def write_driver_standings(df: pd.DataFrame, season: int, round_num: Optional[int] = None) -> Path:
    sub = JOLPICA_DIR / "driver_standings" / f"season={season}"
    if round_num:
        sub = sub / f"round={round_num}"
    os.makedirs(sub, exist_ok=True)
    path = sub / "driver_standings.parquet"
    df.to_parquet(path, index=False, compression="snappy")
    logger.info(f"  driver_standings → {path} ({len(df)} rows)")
    return path


def write_constructor_standings(df: pd.DataFrame, season: int, round_num: Optional[int] = None) -> Path:
    sub = JOLPICA_DIR / "constructor_standings" / f"season={season}"
    if round_num:
        sub = sub / f"round={round_num}"
    os.makedirs(sub, exist_ok=True)
    path = sub / "constructor_standings.parquet"
    df.to_parquet(path, index=False, compression="snappy")
    logger.info(f"  constructor_standings → {path} ({len(df)} rows)")
    return path


def write_pit_stops(df: pd.DataFrame, season: int, round_num: int) -> Path:
    sub = JOLPICA_DIR / "pit_stops" / f"season={season}" / f"round={round_num}"
    os.makedirs(sub, exist_ok=True)
    path = sub / "pit_stops.parquet"
    df.to_parquet(path, index=False, compression="snappy")
    logger.info(f"  pit_stops → {path} ({len(df)} rows)")
    return path


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def ingest_season(client: JolpicaClient, season: int, n_rounds: int) -> None:
    """End-of-season standings + per-round pit stops for one season."""
    logger.info(f"Jolpica: season {season} ({n_rounds} rounds)")
    write_driver_standings(client.get_driver_standings(season), season)
    write_constructor_standings(client.get_constructor_standings(season), season)
    for rnd in range(1, n_rounds + 1):
        try:
            stops = client.get_pit_stops(season, rnd)
            if not stops.empty:
                write_pit_stops(stops, season, rnd)
            else:
                logger.warning(f"  No pit stops for {season} Rd{rnd} (skipping)")
        except Exception as exc:
            logger.warning(f"  Pit stops failed {season} Rd{rnd}: {exc}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Jolpica reference-data ingest (standings, pit stops)")
    p.add_argument("--start-season", type=int, default=2018)
    p.add_argument("--end-season", type=int, default=2024)
    p.add_argument("--rounds", type=int, default=24, help="Max rounds to probe per season")
    p.add_argument("--min-interval", type=float, default=0.30, help="Seconds between requests")
    return p


def main(argv: Optional[list[str]] = None) -> None:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    client = JolpicaClient(min_interval_s=args.min_interval)
    for season in range(args.start_season, args.end_season + 1):
        ingest_season(client, season, args.rounds)


if __name__ == "__main__":
    main()
