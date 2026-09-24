"""R2-C: dirty_air_tax_s is only computed for the theta CALIBRATION population.

int_dirty_air_tax_component.sql: `with_tax` selects FROM `panel`, and `panel` keeps only
laps with correction_weight = 1.0 and rainfall FALSE (:167-171). That filter is right for
estimating theta and wrong for applying it: every other spine lap gets no row, and
int_lap_residual_decomposed.sql:229 COALESCEs the missing tax to 0.0. A downweighted lap
spent behind a car is billed 0 s of dirty air while an identical weight-1 lap is billed
theta x share.

Part 2: the theta calibration panel includes F1's fabricated laps
(pace_delta = 0 via COALESCE(field_pace, lap_time)); their partial residual is just -fuel.

DEFECT PRESENT while: n_should_be_taxed_but_zero > 0.
"""
from _db import con, show

c = con()
c.execute(r"""
create temp table lag as
select g.lap_id, lag(coalesce(a.dirty_air_share_lap, 0.0), 1, 0.0)
         over (partition by g.stint_id order by g.lap_in_stint) share_lag1
from int_stint_geometry g left join int_lap_air_state a using (lap_id)""")
show(c, r"""
select count(*) spine_laps_without_tax_row,
  count(*) filter (where l.share_lag1 > 0) n_should_be_taxed_but_zero,
  count(*) filter (where l.share_lag1 > 0 and f.is_training_eligible) of_which_training_eligible,
  round(avg(0.152123 * l.share_lag1) filter (where l.share_lag1 > 0), 4) mean_missing_tax_s_at_theta_built,
  round(max(0.152123 * l.share_lag1), 4) max_missing_tax_s
from int_lap_residual_decomposed r
left join int_dirty_air_tax_component d using (lap_id)
join lag l using (lap_id)
join fct_cliff_prediction_features f using (lap_id)
where d.lap_id is null""", "Part 1: spine laps with no tax row but a non-zero lagged dirty-air share")
show(c, r"""
select coalesce(e.correction_weight, -1) correction_weight, coalesce(t.rainfall_flag, false) rain, count(*) n
from int_lap_residual_decomposed r
left join int_dirty_air_tax_component d using (lap_id)
left join int_event_corrections e using (lap_id)
left join int_track_evolution t on t.race_year = r.race_year and t.race_id = r.race_id and t.lap_number = r.lap_number
where d.lap_id is null group by all order by n desc""", "Why no row (correction_weight, rain)")

show(c, r"""
with p as (
  select d.lap_id, l.share_lag1 x,
         (r.pace_delta_s - r.fuel_component_s) y, r.base_track_pace_s is null base_null
  from int_dirty_air_tax_component d join int_lap_residual_decomposed r using (lap_id)
  join lag l using (lap_id))
select count(*) n_panel, count(*) filter (where base_null) n_fabricated_base,
  round(covar_pop(y, x) / var_pop(x), 6) theta_as_built,
  round(covar_pop(y, x) filter (where not base_null) / var_pop(x) filter (where not base_null), 6) theta_excluding_fabricated
from p""", "Part 2: theta with F1's fabricated-base laps excluded from the calibration panel")

show(c, r"""
with p as (
  select l.share_lag1 x, (r.pace_delta_s - r.fuel_component_s) y, r.base_track_pace_s is null base_null,
         r.lap_number, r.race_year
  from int_dirty_air_tax_component d join int_lap_residual_decomposed r using (lap_id) join lag l using (lap_id))
select base_null, count(*) n, round(avg(x), 3) share_treated, round(avg(y), 3) mean_y,
  round(avg(y) filter (where x > 0) - avg(y) filter (where x = 0), 4) treated_minus_untreated
from p group by 1 order by 1""", "Part 2b: fabricated laps are y = -fuel (large negative) and disproportionately treated")
show(c, r"""
with p as (
  select l.share_lag1 x, (r.pace_delta_s - r.fuel_component_s) y, r.base_track_pace_s is null base_null, r.race_year
  from int_dirty_air_tax_component d join int_lap_residual_decomposed r using (lap_id) join lag l using (lap_id))
select race_year, round(covar_pop(y, x) / var_pop(x), 4) theta_built_by_season,
  round(covar_pop(y, x) filter (where not base_null) / var_pop(x) filter (where not base_null), 4) theta_measured_only
from p group by 1 order by 1""", "Part 2c: per-season (diagnostic; production theta is pooled, see round-1 F5)")
