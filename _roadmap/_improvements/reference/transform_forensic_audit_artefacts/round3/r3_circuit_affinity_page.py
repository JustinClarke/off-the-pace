"""R3 F44: Driver Circuit Affinity paints the driver's absolute rating at a circuit as
"faster/slower than the driver's own average there", so every cell is green.

Defect. int_driver_circuit_affinity.sql:65-76,107-113 shrinks each (driver, circuit) mean
of driver_skill_loro_s toward the driver's global mean; shrunk_affinity_s is therefore a
LEVEL (the driver's rating at that circuit), not a deviation from his own mean. The
page reads it raw (app/src/features/driver-circuit-affinity/queries.ts:28-37) and colours
it on a zero-centred diverging scale (transform.ts:52; ui/charts/Heatmap.tsx:89-95;
page.tsx:27 green when value < 0), while methodology.tsx:7-9,15-16 and page.tsx:60 say
"relative to their own season-average pace" / "Green = faster than the driver's own
global average at that circuit". The model header (:21-22) says the same thing the page
does. Because driver_skill_loro_s averages -0.92 s (F40), every cell is negative.

Oracle. The relative quantity the page describes: shrunk_affinity_s minus the driver's
own global mean (the model's own prior mean, recomputed from int_driver_race_skill_loro).

DEFECT PRESENT while: the page colours shrunk_affinity_s itself rather than its
deviation from the driver's global mean.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show  # noqa: E402

c = con()
show(c, """
with g as (select driver_id, avg(driver_skill_loro_s) gm from int_driver_race_skill_loro
           where driver_skill_loro_s is not null and circuit_key is not null group by 1),
a as (select a.*, g.gm from int_driver_circuit_affinity a join g using (driver_id) where a.n_obs >= 2)
select count(*) cells_on_page, count(distinct driver_id) drivers,
  round(avg(case when shrunk_affinity_s < 0 then 1.0 else 0 end), 3) share_green_as_drawn,
  round(avg(case when shrunk_affinity_s - gm < 0 then 1.0 else 0 end), 3) share_green_relative_to_own_mean,
  round(avg(shrunk_affinity_s), 3) mean_value_drawn_s, round(avg(shrunk_affinity_s - gm), 3) mean_relative_s
from a""", "page population (n_obs >= 2, queries.ts:36)")
show(c, """
with g as (select driver_id, avg(driver_skill_loro_s) gm from int_driver_race_skill_loro
           where driver_skill_loro_s is not null and circuit_key is not null group by 1),
a as (select a.driver_id, count(*) cells, count(*) filter (where shrunk_affinity_s < 0) green,
   count(*) filter (where shrunk_affinity_s - g.gm < 0) green_rel
  from int_driver_circuit_affinity a join g using (driver_id) where a.n_obs >= 2 group by 1)
select count(*) drivers, count(*) filter (where green = cells) drivers_all_green_as_drawn,
  count(*) filter (where green_rel = cells) drivers_all_green_relative from a""", "per driver row of the heatmap")
show(c, "select max(race_year) max_season_in_source from int_driver_race_skill_loro",
     "methodology.tsx:27 says 'All seasons 2018-2024'")
