"""R2-E: bronze Stint boundaries vs pit stops (independent: stg_pits' PitInTime, which round 1
matched 100% against Jolpica for 2019 and 2021-2025).

A stint boundary is a lap L where stint_number(L) differs from the previous lap's. A real tyre
change needs a pit in-lap at L-1 (or a red-flag stoppage, when tyres may be changed in the
pit lane under the flag). Reports, per race:
  boundaries_without_pit  -- stint increments with no in-lap on the previous lap and no red flag
  pits_without_boundary   -- an in-lap at L-1 but the stint does not increment at L
                             (drive-through / stop-go penalties legitimately land here)
Races where both are high have stint numbering misaligned with the car's actual stops.

DEFECT PRESENT while: any race has boundaries_without_pit >= 5.
"""
from _db import con, show

c = con()
c.execute(r"""
create temp table seq as
select g.race_year, g.race_id, g.driver_id, g.lap_number, g.stint_number, g.is_red_flag_lap,
  lag(g.stint_number) over w prev_stint,
  lag(g.is_pit_lap) over w prev_is_pit,
  lag(g.is_red_flag_lap) over w prev_red,
  exists (select 1 from stg_pits p where p.race_year = g.race_year and p.race_id = g.race_id
          and p.driver_id = g.driver_id and p.pit_in_lap_number = g.lap_number - 1) prev_is_in_lap
from int_stint_geometry g
window w as (partition by g.race_year, g.race_id, g.driver_id order by g.lap_number)""")
c.execute(r"""
create temp table per_race as
select race_year, race_id,
  count(*) filter (where prev_stint is not null and stint_number is not null and stint_number <> prev_stint
                   and not prev_is_in_lap and not coalesce(prev_red, false) and not is_red_flag_lap) boundaries_without_pit,
  count(*) filter (where prev_is_in_lap and stint_number is not distinct from prev_stint) pits_without_boundary,
  count(*) filter (where prev_is_in_lap) pit_stops
from seq group by all""")
show(c, r"""select * from per_race where boundaries_without_pit >= 3 order by boundaries_without_pit desc""",
     "races with >= 3 stint boundaries that have no pit stop behind them")
show(c, r"""select race_year, sum(pit_stops) pit_stops, sum(boundaries_without_pit) boundaries_without_pit,
  sum(pits_without_boundary) pits_without_boundary, count(*) filter (where boundaries_without_pit >= 5) races_ge5
from per_race group by rollup(1) order by 1 nulls last""", "by season")

show(c, r"""
with b as (select race_year, race_id, driver_id, lap_number boundary_lap from seq
           where prev_stint is not null and stint_number is not null and stint_number <> prev_stint),
p as (select race_year, race_id, driver_id, pit_in_lap_number from stg_pits),
m as (select b.race_id, b.driver_id, b.boundary_lap,
        (select min_by(b.boundary_lap - 1 - p.pit_in_lap_number, abs(b.boundary_lap - 1 - p.pit_in_lap_number))
         from p where p.race_year = b.race_year and p.race_id = b.race_id and p.driver_id = b.driver_id) offset_laps
      from b where b.race_id in ('2018_3', '2025_6', '2022_11', '2018_2', '2018_18', '2020_1', '2018_15'))
select race_id, offset_laps, count(*) n from m group by all order by race_id, n desc""",
     "offset (stint boundary lap - 1 - nearest in-lap) in the flagged races")
show(c, r"""
select f.race_id, count(*) spine_rows, count(*) filter (where f.is_training_eligible) eligible,
  count(*) filter (where f.is_training_eligible and f.next_5_lap_cumulative_jump_s is not null) labelled_p50
from fct_cliff_prediction_features f where f.race_id in ('2018_3', '2025_6', '2022_11') group by 1""",
     "ML rows in the three misaligned races")

# Tighter blast radius for the three misaligned races: rows whose bronze stint ordinal differs from the
# pit-derived ordinal (1 + in-laps strictly before this lap). Drive-through penalties also carry PitInTime,
# so this slightly over-counts wherever one occurred.
show(c, r"""
with g as (
  select g.lap_id, g.race_id, g.driver_id, g.lap_number, g.stint_number,
    dense_rank() over (partition by g.race_id, g.driver_id order by g.stint_number) bronze_ord,
    1 + (select count(*) from stg_pits p where p.race_id = g.race_id and p.driver_id = g.driver_id
         and p.pit_in_lap_number < g.lap_number) pit_ord
  from int_stint_geometry g where g.race_id in ('2018_3','2022_11','2025_6'))
select g.race_id, count(*) filter (where f.is_training_eligible) eligible_rows,
  count(*) filter (where f.is_training_eligible and (g.stint_number is null or g.bronze_ord <> g.pit_ord)) eligible_on_wrong_stint,
  count(*) filter (where f.is_training_eligible and f.next_5_lap_cumulative_jump_s is not null
                   and (g.stint_number is null or g.bronze_ord <> g.pit_ord)) labelled_on_wrong_stint
from g join fct_cliff_prediction_features f using (lap_id) group by 1 order by 1""",
     "eligible rows sitting on a stint that disagrees with the pit stops")
