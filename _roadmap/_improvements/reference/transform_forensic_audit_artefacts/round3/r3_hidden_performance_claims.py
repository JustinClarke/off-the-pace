"""R3 F46: Hidden Performance states an identity its data fails on 93% of rows, and the
ghost-race rank key contradicts its own header and its own test.

Defect (a). app/src/features/hidden-performance/methodology.tsx:21-24: "when the host
constructor equals the driver's own team, predicted finish equals actual finish -- any
deviation from zero in that case signals a data issue." In fct_ghost_race_finish a
scenario puts EVERY driver in the host car (fct_ghost_race_finish.sql:230-233 ranks all
drivers of one host scenario), so in the self scenario the ego keeps his own pace but
the other 19 cars are transplanted; the rank is an equal-car rank, not the result.
methodology.tsx:9-10 also says the ranking is "by predicted cumulative race time";
the mart ranks by mean lap (fct_ghost_race_finish.sql:5-9,230-233).

Defect (b). predicted_finish_position ranks on predicted_mean_lap_s, which includes the
fuel term (fct_ghost_car_pace.sql:323-333). fct_ghost_car_pace.sql:335-352 builds a
fuel-adjusted twin "so ranking by pace isn't biased by which lap window (heavy vs.
light fuel) a driver happened to run", fct_ghost_race_finish.sql:167-169 calls that twin
"the ranking key", and assert_ghost_self_scenario_rank.sql validates the twin -- but the
published rank never uses it.

Also verified here (round-2 Assumed): the ghost recombination is an identity --
predicted = actual + (host - ego constructor terms) + deg/cliff interactions to 6e-14 --
so F1, F22 and F35's level terms cancel in every swap.

DEFECT PRESENT while: (a) the methodology text states the self-scenario identity; (b)
predicted_finish_position is ranked on predicted_mean_lap_s.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show  # noqa: E402

c = con()
show(c, """
with ego as (select race_year, race_id, constructor_id, constructor_structural_pace_s s from int_constructor_structural_pace),
ei as (select race_year, race_id, constructor_id, circuit_constructor_interaction_s i from int_circuit_x_constructor_interaction)
select count(*) ghost_laps,
  max(abs(g.predicted_lap_time_s - g.actual_lap_time_s
      - (g.host_constructor_pace_s + g.circuit_interaction_s - coalesce(e.s, 0) - coalesce(ei.i, 0))
      - g.deg_interaction_s - g.cliff_interaction_s)) max_abs_identity_err
from fct_ghost_car_pace g
left join ego e on e.race_year = g.race_year and e.race_id = g.race_id and e.constructor_id = g.ego_constructor_id
left join ei on ei.race_year = g.race_year and ei.race_id = g.race_id and ei.constructor_id = g.ego_constructor_id""",
     "context: ghost pace = actual + (host - ego constructor) + deg/cliff interaction, exactly")
show(c, """
select count(*) self_rows_on_page, count(*) filter (where delta_vs_actual_position = 0) delta_zero,
  round(avg(case when delta_vs_actual_position <> 0 then 1.0 else 0 end), 3) share_violating_stated_identity,
  round(avg(abs(delta_vs_actual_position)), 2) mean_abs_delta_places, count(*) filter (where abs(delta_vs_actual_position) >= 3) off_by_3plus
from fct_ghost_race_finish where is_self_scenario and actual_finish_position is not null
  and avg_recombination_confidence >= 0.3 and not is_short_run""",
     "(a) self-scenario rows the page shows (queries.ts:79-83 filters)")
show(c, """
with r as (select *, rank() over (partition by race_year, race_id, host_constructor_id order by predicted_mean_residual_pace_s) rk_fuel_adj
  from fct_ghost_race_finish)
select count(*) scenario_rows, count(*) filter (where rk_fuel_adj <> predicted_finish_position) rank_differs,
  count(*) filter (where abs(rk_fuel_adj - predicted_finish_position) >= 3) differs_3plus,
  count(*) filter (where avg_recombination_confidence >= 0.3 and not is_short_run and delta_vs_actual_position is not null
                   and abs(rk_fuel_adj - predicted_finish_position) >= 3) page_rows_differ_3plus
from r""", "(b) published rank (fuel-inclusive mean) vs the declared ranking key (fuel-adjusted mean)")
show(c, """
with s as (select g.race_year, g.race_id, g.ego_driver_id, g.predicted_mean_lap_s, g.predicted_mean_residual_pace_s, r.finish_position
  from fct_ghost_race_finish g join stg_results r on r.race_year = g.race_year and r.race_id = g.race_id and r.driver_id = g.ego_driver_id
  where g.is_self_scenario and r.is_classified and r.finish_position is not null),
rk as (select *, rank() over (partition by race_year, race_id order by predicted_mean_lap_s) a,
   rank() over (partition by race_year, race_id order by predicted_mean_residual_pace_s) b,
   rank() over (partition by race_year, race_id order by finish_position) o from s),
per as (select corr(a, o) rho_published_key, corr(b, o) rho_declared_key from rk group by race_year, race_id)
select count(*) races, round(avg(rho_published_key), 3) mean_rho_published_key, round(avg(rho_declared_key), 3) mean_rho_declared_key
from per""", "(b) assert_ghost_self_scenario_rank's statistic under each key: the test passes either way, so it cannot tell them apart")
