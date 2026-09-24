"""R3 F40: the equal-car rating compares a driver's 20th-percentile lap with his teammate's
MEDIAN lap, so every driver rates ~0.9 s "faster than the car" and the rating embeds
lap-time dispersion.

Defect. int_driver_race_skill_loro.sql:151-154 computes each driver's MEDIAN and P20
pace delta; :184-192 builds the car baseline as the mean of the OTHER same-car drivers'
MEDIANS; :218 subtracts it from the focal driver's P20:
    driver_skill_loro_s = P20(own) - median(teammate)
                        = [P20(own) - median(own)]  +  [median(own) - median(teammate)]
The first bracket is a pure spread term (always negative, larger in magnitude the more
a driver's laps scatter); only the second is a teammate comparison. The column feeds
int_driver_season_ratings (:28) -> int_era_normalized_driver_rating (Era Translator,
Era Ratings Timeline, Hidden Performance's driver_season_rating) and
int_driver_circuit_affinity (Driver Circuit Affinity). Those pages say
"negative = faster than the (era-normalised) field average".

Oracle. Part 1 rebuilds the model from compiled production SQL (exact) and splits the
rating into its two brackets. Part 2 uses the defining property of a teammate-relative
measure: two teammates' ratings must sum to ~0 (one cannot be faster than the other both
ways). Part 3 compares driver-season rankings against the symmetric statistic the
header's own "ceiling vs ceiling" intent implies: P20(own) - mean P20(teammates).

DEFECT PRESENT while: driver_skill_loro_s subtracts a teammate MEDIAN from the driver's P20.
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show, REPO  # noqa: E402

c = con()
src = open(glob.glob(str(REPO / 'transform/target/compiled/*/models/intermediate/int_driver_race_skill_loro.sql'))[0]).read()
c.execute("create temp table loro_rb as " + src)
show(c, """select count(*) n, max(abs(a.driver_skill_loro_s - b.driver_skill_loro_s)) max_abs_err
 from int_driver_race_skill_loro a join loro_rb b using (race_year, race_id, driver_id)""",
     "Part 1: compiled production SQL reproduces int_driver_race_skill_loro")
cut = src.index("-- Per (race, constructor): sum/count")
c.execute("create temp table dra as " + src[:cut].rstrip().rstrip(',') + "\nSELECT * FROM driver_race_agg")
show(c, """
with x as (select l.driver_skill_loro_s r, d.driver_p20_pace_delta_s - d.driver_median_pace_delta_s disp,
    d.driver_median_pace_delta_s - l.loro_car_baseline_s loc
  from int_driver_race_skill_loro l join dra d using (race_year, race_id, driver_id, constructor_id)
  where l.driver_skill_loro_s is not null)
select count(*) driver_races, round(avg(r), 3) mean_rating_s, round(avg(case when r < 0 then 1.0 else 0 end), 3) share_negative,
  round(avg(disp), 3) mean_spread_term_s, round(stddev(disp), 3) sd_spread_term_s,
  round(avg(loc), 3) mean_teammate_term_s, round(stddev(loc), 3) sd_teammate_term_s,
  round(corr(r, disp), 3) corr_rating_with_spread
from x""", "Part 1b: rating = spread term [P20 - own median] + teammate term [own median - teammate median]")
show(c, """
with p as (select race_year, race_id, constructor_id, sum(driver_skill_loro_s) s, bool_and(driver_skill_loro_s < 0) both_neg
  from int_driver_race_skill_loro where driver_skill_loro_s is not null group by 1, 2, 3 having count(*) = 2)
select count(*) two_driver_cars, round(avg(s), 3) mean_pair_sum_s, count(*) filter (where both_neg) both_rated_faster_than_each_other
from p""", "Part 2: a teammate-relative rating must sum to ~0 per pair")
show(c, """select count(*) driver_seasons_on_era_pages, round(avg(case when era_adjusted_rating < 0 then 1.0 else 0 end), 3) share_negative
 from int_era_normalized_driver_rating where n_races >= 5""", "Part 2b: Era Translator population (n_races >= 5): share shown as 'faster than the field average'")
show(c, """
with car as (select race_year, race_id, constructor_id, sum(driver_p20_pace_delta_s) sp, count(*) n from dra group by all),
sym as (select d.race_year, d.race_id, d.driver_id, d.driver_p20_pace_delta_s - (car.sp - d.driver_p20_pace_delta_s) / (car.n - 1) sym
  from dra d join car using (race_year, race_id, constructor_id) where car.n > 1),
s as (select l.driver_id, l.race_year, avg(l.driver_skill_loro_s) built, avg(sym.sym) sym
  from int_driver_race_skill_loro l join sym using (race_year, race_id, driver_id) group by 1, 2 having count(*) >= 5),
r as (select *, rank() over (partition by race_year order by built) rb, rank() over (partition by race_year order by sym) rs from s)
select race_year, count(*) drivers, round(corr(rb, rs), 3) spearman_built_vs_symmetric,
  count(*) filter (where abs(rb - rs) >= 3) moved_3plus_places, round(avg(built), 3) mean_built_s, round(avg(sym), 3) mean_symmetric_s
from r group by rollup(1) order by 1""", "Part 3: season rankings, as built vs symmetric ceiling (P20 vs teammates' P20)")
