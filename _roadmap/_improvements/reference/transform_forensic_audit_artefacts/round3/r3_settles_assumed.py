"""R3: settles items rounds 1 and 2 left Assumed. Not a finding by itself; each part names
the Assumed line it closes and prints the measurement that closes it.

A. Round 1 Assumed: "F1 perturbs anomaly_class and therefore eligibility."
   Rebuild int_lap_anomaly_flags from compiled production SQL (exact), then again with the
   residual NULL where base_track_pace_s is NULL (F1's fix), and apply the mart's
   eligibility rule (fct_cliff_prediction_features.sql:912-916).
B. Round 2 Assumed: "the ghost-car recombination is unaffected by F22 (the double term
   cancels)." -- predicted - actual is exactly the host-minus-ego constructor terms plus
   the two interactions (see also r3_hidden_performance_claims).
C. Round 2 Assumed: "That F1 perturbs constructor structural pace materially."
   int_constructor_structural_pace.sql:92 uses the same COALESCE; rebuild with the
   fabricated laps excluded.
D. Round 2 Assumed: "That the 8 never-raced dim_circuits rows feed nothing but the home
   count." The Degradation Simulator's circuit picker selects FROM dim_circuits
   (app/src/features/degradation-simulator/queries.ts:140-151).
E. Round 1 Assumed: "That shrinkage floors bind for reserve drivers (5.2)."
F. Brief item: the 2 race-depth lap files with no telemetry file, and what their laps get
   (this is round 1 F12's population).
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show, REPO  # noqa: E402

c = con()


def compiled(name):
    return open(glob.glob(str(REPO / f'transform/target/compiled/*/models/intermediate/{name}.sql'))[0]).read()


# A
src = compiled('int_lap_anomaly_flags')
c.execute("create temp table an0 as " + src)
a = "        driver_skill_residual_s,\n        track_unexplained_s,\n"
assert src.count(a) == 1
c.execute("create temp table an1 as " + src.replace(
    a, "        CASE WHEN base_track_pace_s IS NULL THEN NULL ELSE driver_skill_residual_s END AS driver_skill_residual_s,\n"
       "        track_unexplained_s,\n", 1))
show(c, """select count(*) n, count(*) filter (where a.anomaly_class is distinct from b.anomaly_class) mismatches
 from int_lap_anomaly_flags a join an0 b using (lap_id)""", "A1: rebuild reproduces int_lap_anomaly_flags")
show(c, """select a.anomaly_class built, b.anomaly_class with_f1_fixed, count(*) n from an0 a join an1 b using (lap_id)
 where a.anomaly_class is distinct from b.anomaly_class group by all order by 3 desc""", "A2: class changes")
show(c, """
with m as (select f.lap_id, f.age_in_stint, f.is_training_eligible e0, f.next_5_lap_cumulative_jump_s y, r.base_track_pace_s b
  from fct_cliff_prediction_features f join int_lap_residual_decomposed r using (lap_id)),
x as (select m.*, coalesce(m.age_in_stint > 3 and coalesce(an1.anomaly_class, 'normal') not in ('mistake', 'conditions'), false) e1
  from m join an1 using (lap_id))
select count(*) filter (where e0) eligible_built, count(*) filter (where e1) eligible_f1_fixed,
  count(*) filter (where e0 <> e1) flips, count(*) filter (where e0 <> e1 and b is not null) flips_on_measured_laps,
  count(*) filter (where e0 <> e1 and b is not null and y is not null) flips_measured_with_label
from x""", "A3: training eligibility flips")

# B
show(c, """
with ego as (select race_year, race_id, constructor_id, constructor_structural_pace_s s from int_constructor_structural_pace),
ei as (select race_year, race_id, constructor_id, circuit_constructor_interaction_s i from int_circuit_x_constructor_interaction)
select count(*) ghost_laps, max(abs(g.predicted_lap_time_s - g.actual_lap_time_s
      - (g.host_constructor_pace_s + g.circuit_interaction_s - coalesce(e.s, 0) - coalesce(ei.i, 0))
      - g.deg_interaction_s - g.cliff_interaction_s)) max_abs_err
from fct_ghost_car_pace g
left join ego e on e.race_year = g.race_year and e.race_id = g.race_id and e.constructor_id = g.ego_constructor_id
left join ei on ei.race_year = g.race_year and ei.race_id = g.race_id and ei.constructor_id = g.ego_constructor_id""",
     "B: ghost recombination is an identity; F1/F22/F35 level terms cancel in every swap")

# C
src = compiled('int_constructor_structural_pace')
c.execute("create temp table cs0 as " + src)
a = "        - COALESCE(fp.field_pace_smoothed_s, f.lap_time_s) AS pace_delta_s,"
assert src.count(a) == 1
cf = src.replace(a, "        - fp.field_pace_smoothed_s AS pace_delta_s,", 1)
cf = cf.replace("        f.lap_time_s IS NOT NULL\n", "        f.lap_time_s IS NOT NULL AND fp.field_pace_smoothed_s IS NOT NULL\n", 1)
c.execute("create temp table cs1 as " + cf)
show(c, """select count(*) team_races, max(abs(a.constructor_structural_pace_s - b.constructor_structural_pace_s)) rebuild_err
 from int_constructor_structural_pace a join cs0 b using (constructor_race_id)""", "C1: rebuild reproduces int_constructor_structural_pace")
show(c, """select count(*) team_races, round(avg(abs(a.constructor_structural_pace_s - b.constructor_structural_pace_s)), 4) mean_abs_shift_s,
  round(quantile_cont(abs(a.constructor_structural_pace_s - b.constructor_structural_pace_s), 0.9), 4) p90_s,
  round(max(abs(a.constructor_structural_pace_s - b.constructor_structural_pace_s)), 3) max_s
 from cs0 a join cs1 b using (constructor_race_id)""", "C2: structural pace with F1's fabricated laps excluded (a per-race constant: cancels from the ML label)")

# D
show(c, """select count(distinct dc.circuit_id) picker_venues,
  count(distinct dc.circuit_id) filter (where not exists (select 1 from race_to_track rt join dim_circuits d2 on d2.circuit_key = rt.track_id
                                                            where d2.circuit_id = dc.circuit_id)) venues_never_raced
 from dim_circuits dc""", "D: Degradation Simulator circuit picker (GROUP BY circuit_id over dim_circuits)")
show(c, """select distinct dc.circuit_name from dim_circuits dc where not exists (select 1 from race_to_track rt join dim_circuits d2
  on d2.circuit_key = rt.track_id where d2.circuit_id = dc.circuit_id) order by 1""", "D2: the never-raced venues it offers")

# E
show(c, """
with n as (select driver_id, count(*) races from int_driver_race_skill_loro where driver_skill_loro_s is not null group by 1)
select case when races < 5 then 'a <5 races' when races < 20 then 'b 5-19' else 'c 20+' end driver_career_in_window,
  count(distinct s.driver_id) drivers,
  round(avg(abs(s.shrunk_residual_s - s.raw_residual_mean_s)), 3) season_rating_mean_abs_shrink_s,
  round(avg(s.rating_confidence), 3) season_rating_confidence
from int_driver_season_ratings s join n using (driver_id) group by 1 order by 1""",
     "E1: season ratings shrink toward the SEASON mean -- the floor binds hardest on reserves")
show(c, """
with n as (select driver_id, count(*) races from int_driver_race_skill_loro where driver_skill_loro_s is not null and circuit_key is not null group by 1)
select case when races < 5 then 'a <5 races' when races < 20 then 'b 5-19' else 'c 20+' end driver_career_in_window,
  count(*) cells, round(avg(abs(a.shrunk_affinity_s - a.raw_affinity_s)), 3) affinity_mean_abs_shrink_s,
  count(*) filter (where abs(a.shrunk_affinity_s - a.raw_affinity_s) < 1e-9) cells_not_shrunk_at_all
from int_driver_circuit_affinity a join n using (driver_id) group by 1 order by 1""",
     "E2: circuit affinity shrinks toward the DRIVER's own mean -- a reserve's level is never pulled to the field")

# F
show(c, """
with l as (select distinct season, race_id, regexp_extract(filename, 'race=([^/]+)', 1) slug
           from read_parquet('../data/bronze/laps/*/*/*.parquet', filename=true)),
t as (select distinct regexp_extract(filename, 'season=(\\d+)', 1)::int season, regexp_extract(filename, 'race=([^/]+)', 1) slug
      from glob('../data/bronze/telemetry/*/*/*.parquet') g(filename))
select l.season, l.race_id, l.slug from l left join t using (season, slug) where t.slug is null order by 1, 2""",
     "F1: race-depth lap files with no telemetry file")
show(c, """select race_id in ('2018_1','2018_2') no_telemetry_race, count(*) eligible_2018,
  round(avg(case when gap_ahead_min_s is null then 1.0 else 0 end), 3) share_gap_null,
  round(avg(dirty_air_share_lap), 3) mean_dirty_air_share, round(avg(share_lap_within_1s), 3) mean_share_within_1s,
  count(*) filter (where air_state_dominant = 'free_air') free_air_rows
 from fct_cliff_prediction_features where race_year = 2018 and is_training_eligible group by 1 order by 1""",
     "F2: what their laps get -- all free air, zero proximity (round 1 F12)")
