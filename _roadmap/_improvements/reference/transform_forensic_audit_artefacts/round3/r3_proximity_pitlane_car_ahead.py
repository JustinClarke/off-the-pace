"""R3 F43: int_lap_proximity counts a car in the pit lane as "the car ahead" of a car on track.

Defect. int_lap_proximity.sql:65-99 builds one crossing per (driver, lap, 1%-bin) from
stg_telemetry_position and :122-155 orders EVERY crossing of a bin by session clock, so
the previous crossing is "the car ahead". Nothing removes crossings made while a car is
in the pit lane. A car entering/leaving the pits crosses the pit-straight bins at pit-lane
speed, and the next car on track crossing the same bin a fraction of a second later is
recorded as sitting within 1 s of it. stg_telemetry_position.sql:20-25 says pit-lane
samples are kept precisely so the proximity model can "exclude them downstream with a
reason rather than silently"; no such exclusion exists.

Oracle. stg_pits carries pit_in_time_s / pit_out_time_s on the same session clock as the
position channel. Part 1 rebuilds int_lap_proximity from its compiled production SQL
(must reproduce exactly). Part 2 re-runs it with crossings made between a car's
pit-in and pit-out time removed from the ordering (a missing pit_out -- retired in the
pit lane -- is bounded at pit_in + 120 s), so the car ahead is the previous car ON TRACK.

DEFECT PRESENT while: training-eligible laps exist whose gap_ahead_min_s is set by a car
that was between its pit-in and pit-out time.
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show, REPO  # noqa: E402

c = con()
src = open(glob.glob(str(REPO / 'transform/target/compiled/*/models/intermediate/int_lap_proximity.sql'))[0]).read()
assert src.count("    FROM crossings\n") == 1 and src.count("neighbours AS (") == 1

c.execute("create temp table prox_rebuild as " + src)
show(c, """
select count(*) n,
  count(*) filter (where p.share_lap_within_1s is distinct from r.share_lap_within_1s) d_share1,
  count(*) filter (where p.gap_ahead_min_s is distinct from r.gap_ahead_min_s) d_gapmin,
  count(*) filter (where p.time_within_1s is distinct from r.time_within_1s) d_time1
from int_lap_proximity p join prox_rebuild r using (lap_id)""", "Part 1: compiled production SQL reproduces int_lap_proximity")

PIT = """pit_windows AS (
    SELECT race_id, driver_id, pit_in_time_s,
           COALESCE(pit_out_time_s, pit_in_time_s + 120.0) AS pit_out_time_s
    FROM "dev"."main"."stg_pits" WHERE pit_in_time_s IS NOT NULL
),
crossings_flagged AS (
    SELECT c.*, EXISTS (SELECT 1 FROM pit_windows w WHERE w.race_id = c.race_id AND w.driver_id = c.driver_id
        AND c.crossing_time_s BETWEEN w.pit_in_time_s AND w.pit_out_time_s) AS in_pit_lane
    FROM crossings c
),
crossings_on_track AS (SELECT * EXCLUDE (in_pit_lane) FROM crossings_flagged WHERE NOT in_pit_lane),
neighbours AS ("""
cf = src.replace("neighbours AS (", PIT, 1).replace("    FROM crossings\n", "    FROM crossings_on_track\n", 1)
c.execute("create temp table prox_on_track as " + cf)

flag = src.replace("neighbours AS (", PIT, 1).replace("    FROM crossings\n", "    FROM crossings_flagged\n", 1)
flag = flag.replace("LAG(driver_id) OVER w AS ahead_driver_id,",
                    "LAG(driver_id) OVER w AS ahead_driver_id, LAG(in_pit_lane) OVER w AS ahead_in_pit,", 1)
nb = flag[:flag.index("gaps AS (")].rstrip().rstrip(',') + (
    "\nSELECT in_pit_lane, ahead_in_pit, ahead_driver_id, driver_id, crossing_time_s - ahead_crossing_s AS gap FROM neighbours")
c.execute("create temp table nb as " + nb)
show(c, """
select count(*) crossings, count(*) filter (where in_pit_lane) crossings_in_pit_lane,
  count(*) filter (where ahead_driver_id <> driver_id and gap < 1.0) within_1s,
  count(*) filter (where ahead_driver_id <> driver_id and gap < 1.0 and ahead_in_pit and not in_pit_lane) within_1s_of_a_pit_lane_car
from nb""", "Part 2a: crossing level")
show(c, """
with e as (select lap_id, race_year from fct_cliff_prediction_features where is_training_eligible)
select e.race_year, count(*) n_eligible,
  count(*) filter (where p.gap_ahead_min_s is distinct from f.gap_ahead_min_s) gap_min_changed,
  count(*) filter (where p.share_lap_within_1s > 0 and f.share_lap_within_1s = 0) within1s_only_from_pit_lane,
  round(avg(abs(p.share_lap_within_1s - f.share_lap_within_1s)), 5) mean_abs_d_share1
from e join int_lap_proximity p using (lap_id) join prox_on_track f using (lap_id)
group by rollup(1) order by 1""", "Part 2b: training-eligible laps, built vs pit-lane crossings removed")
show(c, """
with e as (select lap_id from fct_cliff_prediction_features where is_training_eligible)
select count(*) n_changed, round(median(p.gap_ahead_min_s), 3) median_built_s, round(median(f.gap_ahead_min_s), 3) median_on_track_s,
  round(median(f.gap_ahead_min_s - p.gap_ahead_min_s), 3) median_shift_s, round(quantile_cont(f.gap_ahead_min_s - p.gap_ahead_min_s, 0.9), 3) p90_shift_s,
  count(*) filter (where p.gap_ahead_min_s < 1 and f.gap_ahead_min_s >= 1) crosses_1s_threshold
from e join int_lap_proximity p using (lap_id) join prox_on_track f using (lap_id)
where p.gap_ahead_min_s is distinct from f.gap_ahead_min_s""", "Part 2c: gap_ahead_min_s on the changed laps (a contract feature, all five families)")
