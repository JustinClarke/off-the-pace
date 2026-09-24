"""R3 F45: the era offset is estimated on a teammate-relative rating, is dominated by one
driver's change of teammate, and reverses the between-era gap it claims to remove.

Defect. int_era_normalized_driver_rating.sql:46-122 takes 20 "bridge" drivers (>= 8
races each side of 2022), averages each one's pre-2022 minus post-2022 shrunk rating,
and subtracts the mean (-0.1153 s) from EVERY pre-2022 driver-season (:144-151). The
rating is driver_skill_loro_s -- the driver against his own teammate (F40) -- so a car
era cannot move it; what moves a bridge driver's number is who his teammate was. The
offset is applied unconditionally (only n >= 3 is checked, :120), with t = -1.5. The
Era Translator says "Ratings from 2018 are directly comparable to ratings from 2024"
(app/src/features/era-translator/methodology.tsx:6-8); the timeline says the offset
removes the 2022 regulation shift (era-ratings-timeline/methodology.tsx:18-22).

Oracle. The level the pages call the field average: each era's mean rating. If an era
shift existed in this metric, the field means would differ across 2022 by about the
offset. Part 1 shows the offset's robustness; Part 2 the field-mean gap before and after.

DEFECT PRESENT while: an unconditional bridge-driver offset is subtracted from a
teammate-relative rating.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show  # noqa: E402

c = con()
show(c, "select distinct era_shift_global_s, era_shift_se_s, n_bridge_drivers, low_anchor_sample_flag from int_era_normalized_driver_rating",
     "the applied offset")
show(c, """
with b as (select driver_id, avg(shrunk_residual_s) filter (where season < 2022)
                          - avg(shrunk_residual_s) filter (where season >= 2022) shift
  from int_era_normalized_driver_rating where bridge_driver_anchor_flag group by 1),
loo as (select b1.driver_id, (select avg(shift) from b b2 where b2.driver_id <> b1.driver_id) off_without from b b1)
select round(avg(shift), 4) mean_shift, round(median(shift), 4) median_shift,
  round(avg(shift) / (stddev(shift) / sqrt(count(*))), 2) t_stat,
  (select round(min(off_without), 4) from loo) leave_one_out_min, (select round(max(off_without), 4) from loo) leave_one_out_max,
  (select driver_id from loo order by off_without desc limit 1) most_influential,
  (select round(shift, 3) from b order by shift limit 1) its_shift
from b""", "Part 1: robustness of the bridge-driver mean")
show(c, """
with f as (select season < 2022 pre, avg(shrunk_residual_s) m_unadj, avg(era_adjusted_rating) m_adj
  from int_era_normalized_driver_rating group by 1)
select round(max(m_unadj) filter (where pre) - max(m_unadj) filter (where not pre), 4) field_gap_pre_minus_post_before,
       round(max(m_adj) filter (where pre) - max(m_adj) filter (where not pre), 4) field_gap_pre_minus_post_after
from f""", "Part 2: the between-era gap in field-mean rating, before and after the offset")
show(c, """select season, count(*) n, round(avg(shrunk_residual_s), 3) field_mean_unadjusted, round(avg(era_adjusted_rating), 3) field_mean_adjusted
 from int_era_normalized_driver_rating group by 1 order by 1""", "Part 2b: field means by season (no step at 2022 before adjustment; a +0.115 s step after)")
