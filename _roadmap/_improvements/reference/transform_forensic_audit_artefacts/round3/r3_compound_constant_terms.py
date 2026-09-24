"""R3 F42: expected_compound_pace_s adds a unitless grip multiplier as seconds (ordered
backwards), and its temperature term compares track-surface to tyre-carcass temperature.

Defect (a), grip. int_compound_cliff_predicted.sql:194 adds COALESCE(compound_grip_peak, 0)
to expected_compound_pace_s. grip_peak is a hand-set, unitless ratio
(fit_compound_cliff.py:57-71 COMPOUND_DEFAULTS: HARD 0.97, MEDIUM 1.00, SOFT 1.03,
SUPERSOFT 1.05, ULTRASOFT 1.07, HYPERSOFT 1.09; copied into every cell at :308, never
fitted). Added to a pace in seconds it charges every lap ~1 s, and charges a SOFTER tyre
MORE (1.03 > 0.97), the opposite of the grip it names. It flows into compound_component_s
(int_lap_residual_decomposed.sql:199) and into int_synthetic_teammate.sql's cross-compound
adjustment (teammate_pace_adjusted_s = tm_time + (ego_cc - tm_cc)), where an ego on the
softer tyre gets his teammate's time made SLOWER by the grip difference.

Defect (b), temperature. int_compound_cliff_predicted.sql:108-116:
ambient_temp_delta = clamp(track_temp_c - compound_optimal_temp_low, 0, 30), and the
column enters expected_compound_pace_s as 0.005 * delta (:202). track_temp_c is the
track SURFACE (stg_weather, 13.8-57.5 C); compound_optimal_temp_low is the tyre
operating window (76-82 C for slicks, fit_compound_cliff.py:73-84). The difference is
negative on every slick lap, so the term is 0 exactly where a seed cell exists and fires
only on INTER/WET and on no-cell rows (where the NULL low bound COALESCEs to 20 C) --
round 2 F34's "0.050-0.060, the temperature term alone".

Oracle: the seed itself (one value per compound) and stg_weather's range.

DEFECT PRESENT while: compound_grip_peak is added to expected_compound_pace_s, or the
temperature term compares track temperature with the tyre operating window.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show  # noqa: E402

c = con()
show(c, """select compound_code, count(distinct compound_grip_peak) n_distinct_grip, min(compound_grip_peak) grip_peak,
   min(compound_optimal_temp_low) opt_low_c from dim_compounds_season group by 1 order by grip_peak""",
     "seed: one hand-set grip_peak and operating-window floor per compound")
show(c, """select round(min(track_temp_c),1) min_c, round(quantile_cont(track_temp_c, 0.99),1) p99_c, round(max(track_temp_c),1) max_c from stg_weather""",
     "stg_weather track temperature (surface)")
show(c, """
select r.compound, count(*) n_spine, round(avg(s.compound_grip_peak), 2) grip_s_charged,
  round(avg(r.compound_component_s), 3) mean_compound_component_s,
  round(avg(s.compound_grip_peak) / nullif(avg(r.compound_component_s), 0), 3) grip_share,
  round(avg(case when c.ambient_temp_delta > 0 then 1.0 else 0 end), 3) share_temp_term_nonzero
from int_lap_residual_decomposed r join int_compound_cliff_predicted c using (lap_id)
left join race_to_track rt on rt.race_id = r.race_id
left join dim_compounds_season s on s.circuit_key = rt.track_id and s.season = r.race_year and s.compound_code = r.compound
group by 1 order by 2 desc""", "spine: grip charged in seconds; how often the temperature term is non-zero")
show(c, """
select case when s.compound_code is null then 'no seed cell' else 'seed cell' end cell,
  case when r.compound in ('INTERMEDIATE','WET') then 'inter/wet' else 'slick' end tyre,
  count(*) n, round(avg(case when c.ambient_temp_delta > 0 then 1.0 else 0 end), 3) share_temp_nonzero
from int_lap_residual_decomposed r join int_compound_cliff_predicted c using (lap_id)
left join race_to_track rt on rt.race_id = r.race_id
left join dim_compounds_season s on s.circuit_key = rt.track_id and s.season = r.race_year and s.compound_code = r.compound
where r.compound is not null group by all order by 1, 2""", "temperature term fires only where there is no cell or the tyre is wet")
show(c, """
with st as (select t.*, e.compound ego_c, m.compound tm_c from int_synthetic_teammate t
  join int_lap_residual_decomposed e on e.race_year = t.race_year and e.race_id = t.race_id and e.driver_id = t.ego_driver_id and e.lap_number = t.lap_number
  join int_lap_residual_decomposed m on m.race_year = t.race_year and m.race_id = t.race_id and m.driver_id = t.teammate_driver_id and m.lap_number = t.lap_number),
g as (select st.*, ge.compound_grip_peak ge, gt.compound_grip_peak gt from st
  left join race_to_track rt on rt.race_id = st.race_id
  left join dim_compounds_season ge on ge.circuit_key = rt.track_id and ge.season = st.race_year and ge.compound_code = st.ego_c
  left join dim_compounds_season gt on gt.circuit_key = rt.track_id and gt.season = st.race_year and gt.compound_code = st.tm_c)
select count(*) pair_laps, count(*) filter (where ego_c <> tm_c) cross_compound_pair_laps,
  round(avg(abs(ge - gt)) filter (where ego_c <> tm_c), 3) mean_abs_grip_term_s,
  count(*) filter (where ego_c <> tm_c and ge > gt) ego_softer_credited_for_it
from g""", "Synthetic teammate: the grip term in cross-compound adjustments (sign: a softer ego makes the teammate slower)")
