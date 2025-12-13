"""
RaceReplaySimulator   stream historical lap data to Fabric Eventstream.

Replays a saved Bronze parquet file as if it were a live race, emitting
OpenF1-compatible JSON payloads to Azure EventHub at configurable speed.

Future streaming integration component   not yet deployed. Requires EVENTSTREAM_CONNECTION_STRING
and EVENTHUB_NAME in .env.

Usage:
  python replay_simulator.py \\
    --parquet_path data/bronze/laps/season=2024/race=bahrain_grand_prix/2024_bahrain_grand_prix_laps.parquet \\
    --race_id 2024_1 \\
    --speed 10.0
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

try:
    from azure.eventhub import EventHubProducerClient, EventData
    _EVENTHUB_AVAILABLE = True
except ImportError:
    _EVENTHUB_AVAILABLE = False


class RaceReplaySimulator:
    """
    Streams historical lap data to Fabric Eventstream at configurable speed.

    Each lap is emitted as a JSON payload matching the OpenF1 live API schema,
    allowing downstream consumers to process historical replays identically to
    live data.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        eventhub_name: Optional[str] = None,
    ):
        self.connection_string = connection_string or os.getenv("EVENTSTREAM_CONNECTION_STRING")
        self.eventhub_name     = eventhub_name or os.getenv("EVENTHUB_NAME")
        self.producer = None

    def simulate_race(
        self,
        parquet_path: str,
        race_id: str,
        speed_multiplier: float = 10.0,
        dry_run: bool = False,
    ) -> int:
        """
        Replay historical laps as a live event stream.

        Args:
            parquet_path: Path to the Bronze laps parquet file
            race_id: Race identifier to filter (e.g. '2024_1')
            speed_multiplier: Replay speed   1.0 = real-time (~90s/lap), 10.0 = 10x
            dry_run: Print payloads without sending to Eventstream

        Returns:
            Number of laps emitted
        """
        if not Path(parquet_path).exists():
            raise FileNotFoundError(f"Parquet not found: {parquet_path}")

        # Only validate EventHub credentials if running live (not dry_run)
        if not dry_run:
            if not self.connection_string or not self.eventhub_name:
                raise ValueError(
                    "Set EVENTSTREAM_CONNECTION_STRING and EVENTHUB_NAME in .env "
                    "or pass as constructor arguments to run in live mode."
                )
            if _EVENTHUB_AVAILABLE and not self.producer:
                self.producer = EventHubProducerClient.from_connection_string(
                    conn_str=self.connection_string,
                    eventhub_name=self.eventhub_name,
                )

        laps = pd.read_parquet(parquet_path)
        race_laps = laps[laps['race_id'] == race_id].sort_values('LapNumber')

        if race_laps.empty:
            print(f"No laps found for race_id={race_id}")
            return 0

        mode = "DRY RUN" if dry_run else "LIVE"
        print(f"Simulating {race_id} at {speed_multiplier}x [{mode}]   {len(race_laps)} laps")

        sent = 0
        for _, lap in race_laps.iterrows():
            payload = self._build_payload(lap)

            if not dry_run and self.producer and _EVENTHUB_AVAILABLE:
                batch = self.producer.create_batch()
                batch.add(EventData(json.dumps(payload)))
                self.producer.send_batch(batch)

            print(f"  Lap {payload['lap_number']:3d} | Driver {payload['driver_id']:>2} | {payload['lap_time']:.3f}s")
            sent += 1
            time.sleep(90 / speed_multiplier)

        if self.producer and _EVENTHUB_AVAILABLE:
            self.producer.close()

        print(f"\nComplete   {sent} laps emitted")
        return sent

    @staticmethod
    def _build_payload(lap: pd.Series) -> dict:
        """
        Convert a lap row to an OpenF1-compatible JSON payload.

        LapTime is stored as nanoseconds (int64) in parquet. Convert to seconds.
        Falls back to timedelta.total_seconds() for older files.
        """
        lap_time = lap['LapTime']
        if hasattr(lap_time, 'total_seconds'):
            lap_time_s = lap_time.total_seconds()
        elif isinstance(lap_time, (int, float)):
            lap_time_s = float(lap_time) / 1e9
        else:
            lap_time_s = 0.0

        return {
            "driver_id":   str(int(lap['DriverNumber'])),
            "race_id":     str(lap['race_id']),
            "lap_number":  int(lap['LapNumber']),
            "lap_time":    round(lap_time_s, 3),
            "compound":    str(lap['Compound']),
            "tyre_life":   int(lap['TyreLife']),
            "ingested_at": pd.Timestamp.now().isoformat(),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay historical F1 race data as a live stream.")
    parser.add_argument("--parquet_path", required=True, help="Path to Bronze laps parquet file")
    parser.add_argument("--race_id",      required=True, help="Race ID to replay (e.g. 2024_1)")
    parser.add_argument("--speed",        type=float, default=10.0, help="Speed multiplier (default: 10.0)")
    parser.add_argument("--dry_run",      action="store_true", help="Print payloads without sending")
    args = parser.parse_args()

    simulator = RaceReplaySimulator()
    simulator.simulate_race(
        parquet_path=args.parquet_path,
        race_id=args.race_id,
        speed_multiplier=args.speed,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
