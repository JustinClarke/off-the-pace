"""R3 F48: dirty-air share is not monotone in the gap -- the closest followers are coded
"no dirty air" whenever DRS opened anywhere in S2.

Defect. int_lap_air_state.sql:116-125 classifies each relative-distance third. In S2 a
median gap < 1.0 s with DRS active on any sample (:110 MAX over the sector) becomes
'drs_train'; a median gap of 1.0-1.5 s becomes 'dirty_air'. dirty_air_share_lap (:144-152)
is 1 only for 'dirty_air', so a car sitting 0.4 s behind through S2 with DRS open scores 0
while a car 1.3 s behind scores 1. dirty_air_share_lap is a contract feature (all five
families) and, lagged one lap, it is the treatment in theta_air
(int_dirty_air_tax_component.sql:101-109,195-206) -- so the tightest followers sit in the
CONTROL group of the regression that prices dirty air into the label, and the lap after
them is billed 0 s.

Oracle. The sector medians the model itself computes. Part 1 rebuilds the S2 rows from
the compiled production SQL; Part 2 counts how sub-1 s S2 laps are coded; Part 3 re-runs
the compiled theta_air SQL with S2 < 1.0 s coded as dirty air (drs_train kept for S1/S3),
on the as-built panel and on the measured-laps panel (round 2 F23a's fix).

DEFECT PRESENT while: an S2 median gap < 1.0 s with DRS active yields dirty_air_share_lap = 0.
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show, REPO  # noqa: E402

c = con()
air = open(glob.glob(str(REPO / 'transform/target/compiled/*/models/intermediate/int_lap_air_state.sql'))[0]).read()
tax = open(glob.glob(str(REPO / 'transform/target/compiled/*/models/intermediate/int_dirty_air_tax_component.sql'))[0]).read()
body = air[:air.index("-- Aggregate to lap level")].rstrip().rstrip(',')
c.execute("create temp table s2 as " + body +
          "\nSELECT race_year, race_id, driver_id, lap_number, gap_median_s, drs_active, sector_air_state FROM sector_classified WHERE sector = 2")
show(c, """
with e as (select race_year, race_id, driver_id, lap_number from fct_cliff_prediction_features where is_training_eligible)
select count(*) eligible_laps_with_s2,
  count(*) filter (where s.gap_median_s < 1.0) s2_median_gap_under_1s,
  count(*) filter (where s.gap_median_s < 1.0 and s.sector_air_state = 'drs_train') coded_drs_train_share_0,
  count(*) filter (where s.gap_median_s >= 1.0 and s.gap_median_s < 1.5) s2_gap_1_to_1_5s_all_coded_dirty,
  round(avg(case when s.sector_air_state = 'drs_train' then 1.0 else 0 end) filter (where s.gap_median_s < 1.0), 3) share_of_sub_1s_coded_clean
from e join s2 s using (race_year, race_id, driver_id, lap_number)""", "Part 2: how S2 laps are coded (training-eligible)")

a = "            WHEN gap_median_s < 1.0 AND drs_active = 1 THEN 'drs_train'"
assert air.count(a) == 1
c.execute("create temp table air0 as " + air)
c.execute("create temp table air1 as " + air.replace(
    a, "            WHEN gap_median_s < 1.0 AND drs_active = 1 AND sector != 2 THEN 'drs_train'", 1))
show(c, "select count(*) n, count(*) filter (where a.dirty_air_share_lap is distinct from b.dirty_air_share_lap) mismatches from int_lap_air_state a join air0 b using (lap_id)",
     "Part 1: compiled production SQL reproduces int_lap_air_state")
show(c, """select count(*) filter (where f.is_training_eligible) eligible,
  count(*) filter (where f.is_training_eligible and a.dirty_air_share_lap <> b.dirty_air_share_lap) eligible_share_changes
 from fct_cliff_prediction_features f join air0 a using (lap_id) join air1 b using (lap_id)""",
     "Part 2b: training rows whose dirty_air_share_lap changes when S2 < 1 s counts as dirty air")

ref = '"dev"."main"."int_lap_air_state"'
assert tax.count(ref) == 1
c.execute("""create temp table measured as select f.lap_id from int_lap_fuel_state f
  join int_field_pace_curve fp using (race_year, race_id, lap_number) where fp.field_pace_smoothed_s is not null""")


def theta(air_tbl, measured_only):
    t = tax.replace(ref, air_tbl, 1)
    if measured_only:
        t = t.replace("    WHERE partial_residual_s IS NOT NULL\n",
                      "    WHERE partial_residual_s IS NOT NULL AND lap_id IN (SELECT lap_id FROM measured)\n", 1)
        t = t.replace("        race_year,\n        race_id,\n        driver_id,\n        lap_in_stint,\n        partial_residual_s,\n"
                      "        dirty_air_share_lag1\n    FROM panel",
                      "        lap_id,\n        race_year,\n        race_id,\n        driver_id,\n        lap_in_stint,\n"
                      "        partial_residual_s,\n        dirty_air_share_lag1\n    FROM panel", 1)
    return c.execute(f"""select distinct round(dirty_air_tax_s / dirty_air_intensity_lag1, 6) from ({t})
                         where dirty_air_intensity_lag1 > 0 and dirty_air_tax_s > 0 and dirty_air_tax_s < 5""").fetchall()[0][0]


print("\n## Part 3: theta_air (s per lap behind a car) under each coding")
print(f"as built panel,   S2 DRS coded clean : {theta('air0', False)}   (shipped value 0.152123)")
print(f"as built panel,   S2 < 1 s = dirty   : {theta('air1', False)}")
print(f"measured laps,    S2 DRS coded clean : {theta('air0', True)}   (round 2 F23a: 0.415821)")
print(f"measured laps,    S2 < 1 s = dirty   : {theta('air1', True)}")
