"""Helper for the physical-ahead check scripts: an in-memory DuckDB with the two staging relations
(stg_physical_ahead_telemetry, stg_physical_ahead_laps) built straight from the bronze parquet and the seed CSV,
with the same SQL and column contract as the dbt views. Lets a script run races while the dbt warehouse file is
locked by a build. Differences from the dbt view: is_stg_valid_lap / compound_clean are recomputed here only for
the compound (NULL for None / nan / UNKNOWN / ''); is_stg_valid_lap is approximated from the raw columns
(timed, no pit, not deleted, accurate from 2019, no 4-7 in TrackStatus, lap > 1, not manually excluded) and is
used only by the 'stg_valid' rule probe. Read-only."""
import os

import duckdb

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRONZE = os.path.join(ROOT, 'data', 'bronze')
SEED = os.path.join(ROOT, 'transform', 'seeds', 'seed_manual_lap_exceptions.csv')


def open_staging(threads=2):
    c = duckdb.connect()
    c.execute(f'SET threads={threads}')
    c.execute(f"""CREATE VIEW stg_physical_ahead_telemetry AS
        SELECT CAST(season AS INTEGER) AS race_year, CAST(race_id AS VARCHAR) AS race_id,
               CAST(driver_id AS VARCHAR) AS driver_id, CAST(lap_number AS INTEGER) AS lap_number,
               SessionTime / 1e9 AS session_time_s, X AS x, Y AS y, "index" AS sample_index,
               COALESCE(X = 0 AND Y = 0, FALSE) AS is_zero_xy
        FROM read_parquet('{BRONZE}/telemetry/*/*/*.parquet', hive_partitioning=true) WHERE Source = 'pos'""")
    c.execute(f"""CREATE VIEW stg_physical_ahead_laps AS
        WITH l AS (SELECT * FROM read_parquet('{BRONZE}/laps/*/*/*.parquet', hive_partitioning=true)),
        x AS (SELECT * FROM read_csv('{SEED}', header=true) WHERE event_type = 'exclude')
        SELECT CAST(l.season AS INTEGER) AS race_year, CAST(l.race_id AS VARCHAR) AS race_id,
               CAST(l.Driver AS VARCHAR) AS driver_id, CAST(l.LapNumber AS INTEGER) AS lap_number,
               l.LapTime AS lap_time_ns, l.PitInTime AS pit_in_time_ns, l.PitOutTime AS pit_out_time_ns,
               l.Deleted AS deleted, l.Compound AS compound_raw, l.TrackStatus AS track_status,
               CASE WHEN UPPER(l.Compound) IN ('NONE','NAN','UNKNOWN','NULL','') THEN NULL
                    ELSE UPPER(l.Compound) END AS compound_clean,
               EXISTS (SELECT 1 FROM x WHERE x.race_year = CAST(l.season AS INTEGER)
                       AND x.race_id = CAST(l.race_id AS VARCHAR) AND x.driver_id = CAST(l.Driver AS VARCHAR)
                       AND x.lap_number = CAST(l.LapNumber AS INTEGER)) AS is_manual_excluded,
               COALESCE(l.LapTime > 0 AND l.PitInTime IS NULL AND l.PitOutTime IS NULL AND NOT l.Deleted
                        AND (l.IsAccurate OR l.season < 2019) AND NOT regexp_matches(l.TrackStatus, '.*[4567].*')
                        AND l.LapNumber > 1
                        AND NOT EXISTS (SELECT 1 FROM x WHERE x.race_year = CAST(l.season AS INTEGER)
                            AND x.race_id = CAST(l.race_id AS VARCHAR) AND x.driver_id = CAST(l.Driver AS VARCHAR)
                            AND x.lap_number = CAST(l.LapNumber AS INTEGER)), FALSE) AS is_stg_valid_lap
        FROM l""")
    return c
