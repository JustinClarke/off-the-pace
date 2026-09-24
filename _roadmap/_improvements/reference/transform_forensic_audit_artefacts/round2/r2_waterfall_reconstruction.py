"""R2-M: Lap Waterfall / Race Lost reconstruct the observed pace delta with an extra term.

app/src/features/lap-waterfall/queries.ts and race-lost/queries.ts:
    pace_delta_s := AVG(total_explained_s) + AVG(driver_skill_residual_s) + AVG(track_unexplained_s)
But int_lap_residual_decomposed.sql:306-315 defines driver_skill_residual_s = pace_delta_s - total_explained_s
(track_unexplained_s is 'informational', never subtracted). So the true identity is
    pace_delta_s = total_explained_s + driver_skill_residual_s
and the page's "observed delta" is off by track_unexplained_s. The rubber and ambient bars the page
draws are, per R2-B, not contained in pace_delta_s at all.

DEFECT PRESENT while: the page adds track_unexplained_s.
"""
from _db import con, show

c = con()
show(c, r"""
select count(*) laps,
  max(abs(pace_delta_s - (total_explained_s + driver_skill_residual_s))) max_err_true_identity,
  round(avg(abs(track_unexplained_s)), 4) mean_abs_page_error_per_lap,
  round(quantile_cont(abs(track_unexplained_s), 0.9), 4) p90_abs_page_error
from int_lap_residual_decomposed where track_unexplained_s is not null""", "per lap")
show(c, r"""
with d as (
  select race_year, race_id, driver_id,
    avg(total_explained_s) + avg(driver_skill_residual_s) + avg(track_unexplained_s) page_delta,
    avg(total_explained_s) + avg(driver_skill_residual_s) true_delta
  from fct_lap_residuals where not is_major_outlier_lap and fuel_component_s is not null group by all)
select count(*) driver_races, round(avg(abs(page_delta - true_delta)), 4) mean_abs_err_s,
  round(max(abs(page_delta - true_delta)), 3) max_abs_err_s
from d""", "per driver-race, as the page aggregates it")
