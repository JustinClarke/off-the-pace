"""R2-B: rubber_component_s and ambient_component_s are subtracted twice.

Algebra (exact in the build): int_track_evolution decomposes the SAME curve the
residual is measured against:
    base_track_pace_s = field_pace_smoothed_s
                      = race_mean + rubber_component_s + ambient_component_s + unexplained_residual_s
so pace_delta_s = lap_time_s - base_track_pace_s has already removed rubber and ambient,
and int_lap_residual_decomposed.sql:301-313 subtracts them a second time.

Part 1 proves the identity. Part 2 rebuilds next_5_lap_cumulative_jump_s from the
residual exactly as the mart does (reproduction must be exact), then again with the
second subtraction removed (residual + rubber + ambient where a track-evolution row
exists), re-fitting the per-stint drift the way int_lap_residual_stint_detrend does.

DEFECT PRESENT while: identity error ~0 AND the decomposition still subtracts both terms.
"""
from _db import con, show

c = con()
show(c, r"""
with rm as (select race_year, race_id, avg(track_state_index_s) mean_pace
            from int_track_evolution group by all)
select count(*) n_spine_laps_with_evolution_row,
  max(abs(r.base_track_pace_s - (rm.mean_pace + e.rubber_component_s
      + e.ambient_component_s + e.unexplained_residual_s))) max_abs_identity_error,
  round(avg(abs(e.rubber_component_s)), 4) mean_abs_rubber,
  round(avg(abs(e.ambient_component_s)), 4) mean_abs_ambient,
  round(quantile_cont(abs(e.ambient_component_s), 0.9), 4) p90_abs_ambient,
  round(max(abs(e.ambient_component_s)), 4) max_abs_ambient
from int_lap_residual_decomposed r
join int_track_evolution e using (race_year, race_id, lap_number)
join rm using (race_year, race_id)""", "Part 1: base_track_pace_s == race mean + rubber + ambient + unexplained")

LABEL = r"""
with src as (
  select r.lap_id, r.stint_id, r.lap_in_stint, r.cliff_onset_passed,
         r.driver_skill_residual_s
           + case when {fix} and e.race_id is not null
                  then e.rubber_component_s + e.ambient_component_s else 0 end as res
  from int_lap_residual_decomposed r
  left join int_track_evolution e using (race_year, race_id, lap_number)),
drift as (
  select stint_id, case when count(*) >= 3 then coalesce(regr_slope(res, lap_in_stint), 0.0) else 0.0 end d
  from src where cliff_onset_passed = false group by stint_id),
b as (select s.*, coalesce(d.d, 0.0) d from src s left join drift d using (stint_id))
select lap_id,
  case when lead(lap_in_stint, 5) over w = lap_in_stint + 5 then greatest(least(
      lead(res,1) over w + lead(res,2) over w + lead(res,3) over w + lead(res,4) over w
    + lead(res,5) over w - 5*res - 15*d, 50.0), -50.0) end as y
from b window w as (partition by stint_id order by lap_in_stint)"""

c.execute(f"create temp table y0 as {LABEL.format(fix='false')}")
c.execute(f"create temp table y1 as {LABEL.format(fix='true')}")
show(c, r"""
select count(*) n_labelled_eligible,
  max(abs(f.next_5_lap_cumulative_jump_s - y0.y)) reproduction_max_abs_err,
  round(avg(abs(y1.y - y0.y)), 4) mean_abs_label_shift_s,
  round(quantile_cont(abs(y1.y - y0.y), 0.5), 4) median_abs_shift_s,
  round(quantile_cont(abs(y1.y - y0.y), 0.9), 4) p90_abs_shift_s,
  round(avg(case when abs(y1.y - y0.y) > 0.05 then 1.0 else 0 end), 4) share_moved_gt_50ms,
  round(avg(case when abs(y1.y - y0.y) > 0.25 then 1.0 else 0 end), 4) share_moved_gt_250ms,
  round(stddev(f.next_5_lap_cumulative_jump_s), 3) label_sd,
  round(corr(y1.y, y0.y), 5) corr_fixed_vs_built
from fct_cliff_prediction_features f join y0 using (lap_id) join y1 using (lap_id)
where f.is_training_eligible and f.next_5_lap_cumulative_jump_s is not null""",
     "Part 2: label with the second subtraction removed vs as built (eligible labelled rows)")
show(c, r"""
select f.race_year, count(*) n, round(avg(abs(y1.y - y0.y)), 4) mean_abs_shift,
  round(avg(case when abs(y1.y - y0.y) > 0.25 then 1.0 else 0 end), 4) share_gt_250ms
from fct_cliff_prediction_features f join y0 using (lap_id) join y1 using (lap_id)
where f.is_training_eligible and f.next_5_lap_cumulative_jump_s is not null
group by 1 order by 1""", "Part 2 by season")

CLIFF = r"""
with src as (
  select r.lap_id, r.stint_id, r.lap_in_stint, r.cliff_onset_passed,
         r.driver_skill_residual_s
           + case when {fix} and e.race_id is not null
                  then e.rubber_component_s + e.ambient_component_s else 0 end as res
  from int_lap_residual_decomposed r
  left join int_track_evolution e using (race_year, race_id, lap_number)),
drift as (
  select stint_id, case when count(*) >= 3 then coalesce(regr_slope(res, lap_in_stint), 0.0) else 0.0 end d
  from src where cliff_onset_passed = false group by stint_id),
b as (select s.*, coalesce(d.d, 0.0) d from src s left join drift d using (stint_id)),
h as (select stint_id, max(lap_in_stint) last_lis from b group by 1),
scan as (select a.lap_id, min(f.lap_in_stint - a.lap_in_stint) k from b a join b f
  on a.stint_id = f.stint_id and a.lap_in_stint < f.lap_in_stint
  and (f.res - a.res - (f.lap_in_stint - a.lap_in_stint) * a.d) > 1.0 group by 1)
select b.lap_id, case when h.last_lis <= b.lap_in_stint then null
  when scan.k <= 2 then '0_to_2' when scan.k <= 5 then '3_to_5'
  when scan.k is not null then '6_plus' else 'none_in_stint' end cls
from b left join scan using (lap_id) left join h using (stint_id)"""
c.execute(f"create temp table k0 as {CLIFF.format(fix='false')}")
c.execute(f"create temp table k1 as {CLIFF.format(fix='true')}")
show(c, r"""
select count(*) n_cliff_labelled_eligible,
  count(*) filter (where f.laps_until_cliff_class is distinct from k0.cls) reproduction_mismatch,
  count(*) filter (where k1.cls is distinct from k0.cls) class_flips,
  round(avg(case when k1.cls is distinct from k0.cls then 1.0 else 0 end), 4) share_flipped
from fct_cliff_prediction_features f join k0 using (lap_id) join k1 using (lap_id)
where f.is_training_eligible and f.laps_until_cliff_class is not null""",
     "Part 3: cliff class with the second subtraction removed")
show(c, r"""
select k0.cls built, k1.cls fixed, count(*) n
from fct_cliff_prediction_features f join k0 using (lap_id) join k1 using (lap_id)
where f.is_training_eligible and f.laps_until_cliff_class is not null
group by all order by 1, 2""", "Part 3 transition matrix")
