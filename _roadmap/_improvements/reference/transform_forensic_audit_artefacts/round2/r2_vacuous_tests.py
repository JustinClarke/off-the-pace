"""R2-L: dbt singular tests that cannot fail, or cannot see the defect they are named for.

Each block states the test, why it cannot fail, and (where possible) runs its own logic against
the defect it was written to catch. A green suite count includes all of these.

DEFECT PRESENT while: any block below still reports its 'cannot fail' condition.
"""
import pathlib
import re

from _db import REPO, con, show

tests = REPO / "transform" / "tests"
print("## 1. Placeholders: body is `SELECT 1 WHERE FALSE` (always 0 rows, counted as PASS)")
for p in sorted(tests.glob("*.sql")):
    if re.search(r"SELECT\s+1\s+WHERE\s+FALSE", p.read_text(), re.I):
        print("  ", p.name)

print("\n## 2. Pass by construction")
m = (REPO / "transform/models/intermediate/int_dirty_air_tax_component.sql").read_text()
print("  assert_aero_penalty_negative: WHERE dirty_air_tax_s < 0, but the model clamps the tax:",
      "'THEN 0.0' clamp present =", "* COALESCE(wl.dirty_air_share_lag1, 0.0) < 0\n                THEN 0.0" in m,
      "-> an inverted (negative) theta zeroes every tax and the test still passes")
e = (REPO / "transform/models/intermediate/int_track_evolution.sql").read_text()
print("  assert_track_evolution_monotone: rubber = LEAST(slope, 0.0) * (lap - mean_lap); clamp present =",
      "0.0\n        ) AS rubber_slope_s_per_lap" in e, "-> monotone non-increasing by construction")

c = con()
print("\n## 3. Named for a defect they cannot see")
show(c, r"""
with ranked as (
  select driver_id, stint_id, lap_number, age_in_stint, race_id,
    row_number() over (partition by driver_id, stint_id order by lap_number) rnk
  from int_lap_residual_decomposed where stint_id is not null)
select r1.race_id, count(*) test_failures_in_race
from ranked r1 join ranked r2 on r1.driver_id = r2.driver_id and r1.stint_id = r2.stint_id and r1.rnk = r2.rnk + 1
where r1.age_in_stint <= r2.age_in_stint and r1.race_id in ('2018_3','2022_11','2025_6')
group by 1""", "assert_stint_boundaries_correct ('laps assigned to wrong stint near pit stops') on the three "
     "races where stint numbering ignores the pit stops (R2-E): empty result = test passes")
show(c, r"""
select f.race_id, count(*) rows_with_no_seed_cell,
  count(*) filter (where p.expected_compound_pace_s in (0.0, 0.5)) rows_the_test_flags,
  round(min(p.expected_compound_pace_s), 4) min_pace, round(max(p.expected_compound_pace_s), 4) max_pace
from fct_cliff_prediction_features f join int_compound_cliff_predicted p using (lap_id)
where f.race_year = 2025 and f.compound_cliff_onset_laps is null and f.compound not in ('INTERMEDIATE','WET')
group by 1 order by 1""", "assert_cliff_predictions_valid ('seed parameters failed to join') vs round-1 F7 rows, "
     "where the seed did fail to join: default is temperature term only, never exactly 0 or 0.5")
