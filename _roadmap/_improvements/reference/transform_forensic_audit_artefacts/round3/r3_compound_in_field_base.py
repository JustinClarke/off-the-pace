"""R3 F38: the field base is fuel-neutral but NOT compound-neutral, so every residual
carries minus the field's average compound cost.

Defect. int_field_pace_curve.sql:43-62,77-103 builds base_track_pace_s as the smoothed,
trimmed field mean of weight_corrected_lap_time (lap time with the car's OWN fuel
removed, int_lap_fuel_state.sql:95-96). Fuel is therefore handled consistently: the base
holds no fuel, and int_lap_residual_decomposed.sql:300,311 subtracts the lap's own absolute
fuel cost. The compound cost is not: the base still contains the field's tyre state
(grip_peak + wear + cliff ramp of every eligible car at that lap), and
int_lap_residual_decomposed.sql:199,300,311 subtracts the lap's own ABSOLUTE
compound_component_s (= int_compound_cliff_predicted.expected_compound_pace_s). So
    residual = (lap - fuel - own_cc - ...) - [compound-neutral base + field_cc(lap)]
i.e. every residual carries -field_cc(race, lap), a common-mode term that tracks the
field's tyre cycle (it falls when the field pits onto fresh tyres).

Oracle. Part 1 rebuilds int_field_pace_curve from its compiled production SQL, carrying
the eligible cars' own expected_compound_pace_s through the SAME eligibility, the SAME
10-90% trim and the SAME +/-2-lap smoothing; the rebuilt base must match the table
exactly. By linearity base = neutral_base + field_cc exactly on that trim set. Part 3
rebuilds next_5_lap_cumulative_jump_s and laps_until_cliff_class from the residual the
way the mart does (round-2 method; reproduction must be exact), then again with the
residual measured against a compound-neutral base, two ways: (A) add field_cc back on
the production trim set; (B) re-build the base from compound-corrected laps
(weight_corrected - own cc, re-ranked and re-trimmed), the exact analogue of how fuel is
handled. Per-stint drift is re-fitted in each arm.

DEFECT PRESENT while: int_field_pace_curve averages a lap time that still contains the
compound cost AND int_lap_residual_decomposed subtracts the lap's absolute
compound_component_s.
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show, REPO  # noqa: E402

c = con()
src = open(glob.glob(str(REPO / 'transform/target/compiled/*/models/intermediate/int_field_pace_curve.sql'))[0]).read()


def rep(s, a, b):
    assert s.count(a) == 1, (a, s.count(a))
    return s.replace(a, b)


CC_JOIN = ('    LEFT JOIN "dev"."main"."int_compound_cliff_predicted" AS ccp ON ccp.lap_id = f.lap_id\n')
# Arm A: carry own cc through the production trim set.
a = rep(src, "        f.weight_corrected_lap_time\n    FROM fuel_state AS f\n",
        "        f.weight_corrected_lap_time,\n        ccp.expected_compound_pace_s AS cc\n    FROM fuel_state AS f\n" + CC_JOIN)
a = rep(a, "            AS field_pace_trimmed_mean_s\n    FROM eligible_ranked",
        "            AS field_pace_trimmed_mean_s,\n"
        "        AVG(cc) FILTER (WHERE pct_rank BETWEEN 0.10 AND 0.90) AS field_cc_trimmed\n    FROM eligible_ranked")
a = rep(a, "        ) AS field_pace_smoothed_s\n    FROM trimmed",
        "        ) AS field_pace_smoothed_s,\n        AVG(field_cc_trimmed) OVER (PARTITION BY race_year, race_id ORDER BY lap_number"
        " ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING) AS field_cc_smoothed\n    FROM trimmed")
a = rep(a, "    field_pace_smoothed_s,\n    eligible_lap_count < 5",
        "    field_pace_smoothed_s,\n    field_cc_smoothed,\n    eligible_lap_count < 5")
c.execute("create temp table fpc_a as " + a)
# Arm B: base built from compound-corrected laps (re-ranked, re-trimmed) -- how fuel is handled.
b = rep(src, "        f.weight_corrected_lap_time\n    FROM fuel_state AS f\n",
        "        f.weight_corrected_lap_time - ccp.expected_compound_pace_s AS weight_corrected_lap_time\n"
        "    FROM fuel_state AS f\n" + CC_JOIN)
c.execute("create temp table fpc_b as " + b)

show(c, """select count(*) n_race_laps,
  max(abs(t.field_pace_smoothed_s - a.field_pace_smoothed_s)) rebuild_max_abs_err,
  round(avg(a.field_cc_smoothed), 3) mean_field_cc_s, round(stddev(a.field_cc_smoothed), 3) sd_field_cc_s,
  round(avg(a.field_pace_smoothed_s - b.field_pace_smoothed_s), 3) mean_base_minus_neutral_base_B
from int_field_pace_curve t join fpc_a a using (race_year, race_id, lap_number)
join fpc_b b using (race_year, race_id, lap_number)""",
     "Part 1: production field base rebuilt exactly; the field-average compound cost inside it")
show(c, """with x as (select race_year, race_id, lap_number, field_cc_smoothed f,
   field_cc_smoothed - lag(field_cc_smoothed, 5) over (partition by race_year, race_id order by lap_number) d5 from fpc_a)
select round(avg(abs(d5)), 3) mean_abs_change_over_5_laps_s, round(quantile_cont(abs(d5), 0.9), 3) p90_s,
  round(max(abs(d5)), 3) max_s from x""", "Part 1b: how much field_cc moves across a 5-lap label window")

show(c, """
select count(*) spine_laps_with_base,
  round(avg(r.driver_skill_residual_s), 3) mean_residual_built_s,
  round(avg(r.driver_skill_residual_s + a.field_cc_smoothed), 3) mean_residual_neutral_A_s,
  round(avg(r.driver_skill_residual_s + (r.base_track_pace_s - b.field_pace_smoothed_s)), 3) mean_residual_neutral_B_s
from int_lap_residual_decomposed r join fpc_a a using (race_year, race_id, lap_number)
join fpc_b b using (race_year, race_id, lap_number) where r.base_track_pace_s is not null""",
     "Part 2: residual LEVEL (the app's skill numbers are ~2 s 'faster than the field' from this term alone)")
show(c, """select round(avg(compound_component_s), 3) waterfall_compound_bar_mean_s,
  round(avg(driver_skill_residual_s), 3) waterfall_skill_bar_mean_s,
  round(avg(case when driver_skill_residual_s < 0 then 1.0 else 0 end), 3) share_laps_skill_negative,
  (select round(avg(case when driver_residual_mean_s < 0 then 1.0 else 0 end), 3) from fct_driver_skill_features) share_driver_races_negative
from fct_lap_residuals""", "Part 2b: what the app tables show (fct_lap_residuals feeds Lap Waterfall / Race Lost; fct_driver_skill_features the skill pages)")

SRC = """
with src as (
  select r.lap_id, r.stint_id, r.lap_in_stint, r.cliff_onset_passed,
         r.driver_skill_residual_s + case when r.base_track_pace_s is null then 0
             when '{arm}' = 'A' then coalesce(a.field_cc_smoothed, 0)
             when '{arm}' = 'B' then coalesce(r.base_track_pace_s - b.field_pace_smoothed_s, 0)
             else 0 end as res
  from int_lap_residual_decomposed r
  left join fpc_a a using (race_year, race_id, lap_number)
  left join fpc_b b using (race_year, race_id, lap_number)),
drift as (
  select stint_id, case when count(*) >= 3 then coalesce(regr_slope(res, lap_in_stint), 0.0) else 0.0 end d
  from src where cliff_onset_passed = false group by stint_id),
bb as (select s.*, coalesce(d.d, 0.0) d from src s left join drift d using (stint_id))"""
LABEL = SRC + """
select lap_id,
  case when lead(lap_in_stint, 5) over w = lap_in_stint + 5 then greatest(least(
      lead(res,1) over w + lead(res,2) over w + lead(res,3) over w + lead(res,4) over w
    + lead(res,5) over w - 5*res - 15*d, 50.0), -50.0) end as y
from bb window w as (partition by stint_id order by lap_in_stint)"""
CLIFF = SRC + """,
h as (select stint_id, max(lap_in_stint) last_lis from bb group by 1),
scan as (select x.lap_id, min(f.lap_in_stint - x.lap_in_stint) k from bb x join bb f
  on x.stint_id = f.stint_id and x.lap_in_stint < f.lap_in_stint
  and (f.res - x.res - (f.lap_in_stint - x.lap_in_stint) * x.d) > 1.0 group by 1)
select bb.lap_id, case when h.last_lis <= bb.lap_in_stint then null
  when scan.k <= 2 then '0_to_2' when scan.k <= 5 then '3_to_5'
  when scan.k is not null then '6_plus' else 'none_in_stint' end cls
from bb left join scan using (lap_id) left join h using (stint_id)"""
for arm in ("0", "A", "B"):
    c.execute(f"create temp table y{arm} as {LABEL.format(arm=arm)}")
    c.execute(f"create temp table k{arm} as {CLIFF.format(arm=arm)}")

for arm in ("A", "B"):
    show(c, f"""
select count(*) n_labelled_eligible,
  max(abs(f.next_5_lap_cumulative_jump_s - y0.y)) reproduction_max_abs_err,
  round(avg(abs(y{arm}.y - y0.y)), 4) mean_abs_label_shift_s,
  round(quantile_cont(abs(y{arm}.y - y0.y), 0.5), 4) median_abs_shift_s,
  round(quantile_cont(abs(y{arm}.y - y0.y), 0.9), 4) p90_abs_shift_s,
  round(avg(case when abs(y{arm}.y - y0.y) > 0.25 then 1.0 else 0 end), 4) share_moved_gt_250ms,
  round(stddev(f.next_5_lap_cumulative_jump_s), 3) label_sd,
  round(corr(y{arm}.y, y0.y), 4) corr_neutral_vs_built
from fct_cliff_prediction_features f join y0 using (lap_id) join y{arm} using (lap_id)
where f.is_training_eligible and f.next_5_lap_cumulative_jump_s is not null""",
         f"Part 3 ({arm}): 5-lap label, compound-neutral base vs as built (eligible labelled rows)")
    show(c, f"""
select count(*) n_cliff_labelled_eligible,
  count(*) filter (where f.laps_until_cliff_class is distinct from k0.cls) reproduction_mismatch,
  count(*) filter (where k{arm}.cls is distinct from k0.cls) class_flips,
  round(avg(case when k{arm}.cls is distinct from k0.cls then 1.0 else 0 end), 4) share_flipped
from fct_cliff_prediction_features f join k0 using (lap_id) join k{arm} using (lap_id)
where f.is_training_eligible and f.laps_until_cliff_class is not null""",
         f"Part 3 ({arm}): cliff class")

show(c, """
select f.race_year, count(*) n, round(avg(abs(yB.y - y0.y)), 3) mean_abs_shift_B,
  round(avg(case when abs(yB.y - y0.y) > 0.25 then 1.0 else 0 end), 3) share_gt_250ms
from fct_cliff_prediction_features f join y0 using (lap_id) join yB using (lap_id)
where f.is_training_eligible and f.next_5_lap_cumulative_jump_s is not null group by 1 order by 1""",
     "Part 3 by season (arm B)")
show(c, """
with w as (select a.race_year, a.race_id, a.lap_number,
    lead(a.field_cc_smoothed, 5) over (partition by a.race_year, a.race_id order by a.lap_number) - a.field_cc_smoothed d5
  from fpc_a a)
select case when w.d5 < -0.5 then 'a field cc falls >0.5 s (pit cycle)' when w.d5 > 0.5 then 'c rises >0.5 s'
            else 'b within +/-0.5 s' end window_kind,
  count(*) n, round(avg(abs(yB.y - y0.y)), 3) mean_abs_shift_B, round(avg(yB.y - y0.y), 3) mean_signed_shift_B
from fct_cliff_prediction_features f join y0 using (lap_id) join yB using (lap_id)
join w on w.race_year = f.race_year and w.race_id = f.race_id and w.lap_number = f.lap_number
where f.is_training_eligible and f.next_5_lap_cumulative_jump_s is not null group by 1 order by 1""",
     "Part 4: where the shift lives -- label windows that span the field's pit cycle")
