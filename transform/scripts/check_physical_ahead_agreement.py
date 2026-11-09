"""Documented check (not a dbt test): sample-grain agreement of int_lap_physical_ahead's car ahead with the
production crossing-time car ahead (int_lap_proximity), per race. Gate: >= 94% on every race.

Why a script and not a dbt test: the validated statistic (experiments 26 and 27: 96-99%) compares each
position sample's physical car ahead with int_lap_proximity's PER-BIN car ahead. That per-bin table is the
`gaps`/`neighbours` CTE of int_lap_proximity and is not materialised, and int_lap_physical_ahead is lap grain.
The dbt test assert_physical_ahead_agrees_with_proximity runs a lap-grain proxy on existing tables instead
(warn only; see that file).

Population (as experiment 26 P1): samples whose physical class is 'same_lap' (so not lap 1, not side by side,
not overlapping, not lapped, not unknown) and whose crossing-time gap at the same (driver, lap, bin) is <= 3 s.

Run 2026-11-09, all 173 races, guard off: 170 rated, median 97.6%, range 80.3-99.7%. FAILS the gate on 8:
2023_13 (80.3%), 2018_4 (83.7%), 2020_1 (84.9%), 2021_2 (86.8%), 2019_18 (91.2%), 2025_12 (91.9%),
2022_11 (93.4%), 2023_21 (93.8%). Not explained by SC/VSC/red laps (green-flag-only agreement is similar).
Cause not established. Not measurable: 2018_1, 2018_2 (no position samples), 2021_12 (no clean lap).

Read-only: opens the warehouse with read_only=True and bronze parquet; writes nothing but the optional --out
JSON. usage (from transform/):
    ../.venv/bin/python scripts/check_physical_ahead_agreement.py [--races 2024_16,2019_15] [--out f.json]
"""
import argparse
import importlib.util
import json
import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location(
    'int_lap_physical_ahead', os.path.join(ROOT, 'models', 'intermediate', 'int_lap_physical_ahead.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

GATE = 0.94
MIN_N = 10000   # as the experiment 26 proposed test: fewer compared samples is not a rate

# int_lap_proximity's crossings -> pit filter -> neighbours, for one race (same SQL, minus the lap scalars).
CT_SQL = """
WITH pos AS (
    SELECT race_id, driver_id, lap_number, session_time_s,
           CAST(FLOOR(relative_distance * 100) AS INTEGER) AS track_bin
    FROM stg_telemetry_position WHERE race_id = $rid
), crossings AS (
    SELECT race_id, driver_id, lap_number, track_bin, MIN(session_time_s) AS crossing_time_s
    FROM pos GROUP BY 1, 2, 3, 4
), pit_windows AS (
    SELECT race_id, driver_id, pit_in_time_s,
           COALESCE(pit_out_time_s, pit_in_time_s + $open_s) AS pit_out_time_s
    FROM stg_pits WHERE pit_in_time_s IS NOT NULL AND race_id = $rid
), on_track AS (
    SELECT c.* FROM crossings c WHERE NOT EXISTS (
        SELECT 1 FROM pit_windows w WHERE w.race_id = c.race_id AND w.driver_id = c.driver_id
          AND c.crossing_time_s BETWEEN w.pit_in_time_s AND w.pit_out_time_s)
), nb AS (
    SELECT *, LAG(driver_id) OVER w AS a_drv, LAG(crossing_time_s) OVER w AS a_t
    FROM on_track WINDOW w AS (PARTITION BY race_id, track_bin ORDER BY crossing_time_s, driver_id)
)
SELECT driver_id, lap_number, track_bin, a_drv AS ct_driver_id, crossing_time_s - a_t AS ct_gap_s
FROM nb WHERE a_drv <> driver_id AND crossing_time_s - a_t <= $max_gap
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--warehouse', default=os.path.join(ROOT, '..', 'data', 'dev.duckdb'))
    ap.add_argument('--bronze', default=os.path.join(ROOT, '..', 'data', 'bronze'))
    ap.add_argument('--races', default='')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    wh = duckdb.connect(a.warehouse, read_only=True)
    os.chdir(ROOT)   # stg views resolve bronze paths relative to transform/
    races = a.races.split(',') if a.races else [r[0] for r in wh.sql(
        'SELECT DISTINCT race_id FROM int_lap_proximity ORDER BY 1').fetchall()]
    tel_glob = os.path.join(a.bronze, 'telemetry', '*', '*', '*.parquet')
    laps_glob = os.path.join(a.bronze, 'laps', '*', '*', '*.parquet')
    res, fails = {}, []
    for rid in races:
        tel = duckdb.sql(f"""SELECT SessionTime / 1e9 AS T, driver_id AS drv, CAST(lap_number AS INTEGER) AS lap,
                X, Y, LEAST(GREATEST(RelativeDistance, 0.0), 0.999999) AS rd
            FROM '{tel_glob}' WHERE Source = 'pos' AND race_id = '{rid}' AND RelativeDistance IS NOT NULL
            ORDER BY drv, T, "index" """).df()
        laps = duckdb.sql(f"SELECT * FROM '{laps_glob}' WHERE race_id = '{rid}'").df()
        smp = m.build_race_samples(tel, laps) if len(tel) and len(laps) else None
        if smp is None:
            res[rid] = dict(status='not_measurable'); continue
        smp = smp.merge(tel[['drv', 'lap', 'T', 'rd']].drop_duplicates(['drv', 'lap', 'T']),
                        left_on=['driver_id', 'lap_number', 'session_time_s'], right_on=['drv', 'lap', 'T'])
        smp['track_bin'] = (smp.rd * 100).astype(int)
        ct = wh.execute(CT_SQL, dict(rid=rid, open_s=120.0, max_gap=300.0)).df()
        j = smp[smp.sample_class == 'same_lap'].merge(ct, on=['driver_id', 'lap_number', 'track_bin'])
        j = j[j.ct_gap_s <= 3.0]
        agree = float((j.ahead_driver_id == j.ct_driver_id).mean()) if len(j) else None
        res[rid] = dict(n=int(len(j)), agreement=agree)
        if len(j) >= MIN_N and agree < GATE:
            fails.append(rid)
        print(rid, res[rid], flush=True)
    rated = [v['agreement'] for v in res.values() if v.get('n', 0) >= MIN_N]
    summary = dict(races=len(races), rated=len(rated), min=min(rated), max=max(rated),
                   failing=fails, not_measurable=[k for k, v in res.items() if v.get('status')],
                   below_min_n=[k for k, v in res.items() if 0 <= v.get('n', -1) < MIN_N])
    print(json.dumps(summary, indent=1))
    if a.out:
        json.dump(dict(summary=summary, races=res), open(a.out, 'w'), indent=1)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
