"""R2-D: int_lap_fuel_state implies a starting fuel load above the FIA race-fuel maximum.

initial_fuel_kg = race_lap_count x dim_circuits.fuel_consumption_rate_kg_per_lap
(int_lap_fuel_state.sql:58). The seed rate is hand-set per event slug with no
constraint against race length. Independent bound: FIA Technical Regulations race
fuel maximum 105 kg (2018), 110 kg (2019 onward). Fuel at lap 1 is reconstructed
from the first valid lap: fuel(lap) = initial - rate x (lap - 1).

DEFECT PRESENT while: n_over_max > 0.
"""
from _db import con, show

c = con()
show(c, r"""
with r as (
  select f.race_year, f.race_id, max(f.fuel_mass_kg + d.fuel_consumption_rate_kg_per_lap * (f.lap_number - 1)) initial_kg,
         any_value(d.fuel_consumption_rate_kg_per_lap) rate, max(f.lap_number) laps
  from int_lap_fuel_state f join race_to_track rt using (race_id)
  join dim_circuits d on d.circuit_key = rt.track_id group by all)
select race_year, count(*) races,
  count(*) filter (where initial_kg > case when race_year = 2018 then 105 else 110 end) n_over_max,
  round(median(initial_kg), 1) median_initial_kg, round(max(initial_kg), 1) max_initial_kg
from r group by rollup(race_year) order by 1 nulls last""", "races whose modelled starting fuel exceeds the regulatory maximum")
show(c, r"""
with r as (
  select f.race_year, f.race_id, rt.track_id, max(f.fuel_mass_kg + d.fuel_consumption_rate_kg_per_lap * (f.lap_number - 1)) initial_kg,
         any_value(d.fuel_consumption_rate_kg_per_lap) rate, max(f.lap_number) laps
  from int_lap_fuel_state f join race_to_track rt using (race_id)
  join dim_circuits d on d.circuit_key = rt.track_id group by all)
select * from r order by initial_kg desc limit 12""", "worst races")
