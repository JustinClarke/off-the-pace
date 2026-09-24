"""R3 F47: push_residual reads fuel burn as "pushing".

Defect. int_lap_thermal_proxy.sql:46-49 takes raw stg_laps.lap_time_s, :87-99 builds an
expanding trailing median of the stint's earlier valid laps, and :106 sets
push_residual = baseline - lap_time. Earlier laps carried more fuel, so a lap is faster
than the median of its predecessors by roughly (laps since the median lap) x fuel gain
(~0.05 s/lap) with no change in driving. The header (:22-23) defines the sign as "faster
than the stint baseline = pushing harder = higher thermal input", and the two load
features (:118-150) accumulate only the positive part. The tree already carries a
fuel-corrected lap time (int_lap_fuel_state.weight_corrected_lap_time), and
int_field_pace_curve uses it for exactly this reason.

Oracle. Part 1 rebuilds int_lap_thermal_proxy from compiled production SQL (exact).
Part 2 re-runs it with the fuel-corrected lap time (invalid laps keep the raw time; they
never enter the baseline) and compares on training-eligible rows by stint position.

DEFECT PRESENT while: int_lap_thermal_proxy's push baseline and residual use a lap time
that still contains the fuel burn.
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show, REPO  # noqa: E402

c = con()
src = open(glob.glob(str(REPO / 'transform/target/compiled/*/models/intermediate/int_lap_thermal_proxy.sql'))[0]).read()
c.execute("create temp table tp0 as " + src)
show(c, """select count(*) n, count(*) filter (where a.cumulative_push_load_bulk is distinct from b.cumulative_push_load_bulk
   or a.push_residual is distinct from b.push_residual) mismatches
 from int_lap_thermal_proxy a join tp0 b using (lap_id)""", "Part 1: compiled production SQL reproduces int_lap_thermal_proxy")
a = "    SELECT lap_id, lap_time_s\n"
b = '    FROM "dev"."main"."stg_laps"\n),'
assert src.count(a) == 1 and src.count(b) == 1
cf = src.replace(a, "    SELECT l.lap_id, COALESCE(f.weight_corrected_lap_time, l.lap_time_s) AS lap_time_s\n", 1).replace(
    b, '    FROM "dev"."main"."stg_laps" l LEFT JOIN "dev"."main"."int_lap_fuel_state" f USING (lap_id)\n),', 1)
c.execute("create temp table tp1 as " + cf)
show(c, """
with m as (select f.lap_in_stint, a.push_residual p0, b.push_residual p1,
    a.cumulative_push_load_bulk l0, b.cumulative_push_load_bulk l1
  from fct_cliff_prediction_features f join tp0 a using (lap_id) join tp1 b using (lap_id)
  where f.is_training_eligible and a.push_residual is not null)
select case when lap_in_stint <= 5 then 'a 1-5' when lap_in_stint <= 10 then 'b 6-10'
            when lap_in_stint <= 20 then 'c 11-20' else 'd 21+' end lap_in_stint,
  count(*) n, round(avg(p0), 3) push_built_s, round(avg(p1), 3) push_fuel_corrected_s,
  round(avg(case when p0 > 0 then 1.0 else 0 end), 3) share_pushing_built,
  round(avg(case when p1 > 0 then 1.0 else 0 end), 3) share_pushing_fuel_corrected,
  round(avg(l0), 3) bulk_load_built, round(avg(l1), 3) bulk_load_fuel_corrected
from m group by rollup(1) order by 1""", "Part 2: training-eligible rows, raw vs fuel-corrected lap time")
