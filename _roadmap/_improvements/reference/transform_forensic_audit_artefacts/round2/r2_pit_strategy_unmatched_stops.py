"""R2-K: int_pit_strategy_value loses the pit stop of any stint whose last laps were not valid.

int_pit_strategy_value.sql:52-70 stint_meta keeps valid laps only, so stint_end_lap (:293) is the
last VALID lap. stint_actual_pit (:304-317) matches a stop only if pit_in_lap is within
[stint_start_lap, stint_end_lap + 1]. A stop taken under SC/VSC/red (whose run-in laps are not
valid) or after any invalid lap falls outside the window -> actual_pit_lap NULL -> verdict NULL
and opportunity_cost_s 0.0 (:406-409, :437) as if the stint never stopped.

App: pit-strategy/queries.ts orders stints by actual_pit_lap NULLS LAST and ends a NULL stint at
total_laps (= MAX valid lap), so the Gantt draws these stints to the flag and re-orders them.

Independent value: int_stint_end_regime.stint_end_cause (pit-ended causes) + stg_pits.
DEFECT PRESENT while: pit-ended stints with NULL actual_pit_lap > 0.
"""
from _db import con, show

c = con()
show(c, r"""
select e.stint_end_cause, count(*) stints,
  count(*) filter (where pv.actual_pit_lap is null) actual_pit_lap_null,
  round(avg(case when pv.actual_pit_lap is null then 1.0 else 0 end), 3) share_null,
  count(*) filter (where pv.actual_pit_lap is null and pv.strategy_verdict is null) verdict_null
from int_pit_strategy_value pv join int_stint_end_regime e using (stint_id)
group by 1 order by 2 desc""", "pit-ended stints that lost their stop")
show(c, r"""
select pv.stint_id, e.stint_end_cause, e.end_lap_number in_lap_per_regime,
  max(g.lap_number) filter (where g.is_valid_lap) last_valid_lap,
  (select list(p.pit_in_lap_number) from stg_pits p where p.race_id = pv.race_id and p.driver_id = pv.driver_id) driver_pit_laps
from int_pit_strategy_value pv join int_stint_end_regime e using (stint_id)
join int_stint_geometry g using (stint_id)
where pv.actual_pit_lap is null and e.stint_end_cause = 'sc_pit'
group by all order by 1 limit 8""", "examples: the in-lap sits beyond last valid lap + 1")
