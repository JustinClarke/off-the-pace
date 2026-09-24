"""Round-1 F1 'Assumed' -> measured: do fabricated pace_delta_s = 0 laps survive the clean-lap filter
of fct_driver_skill_features (driver_residual_mean_s / _stddev_s, read by the Driver Consistency page)?

Filter (fct_driver_skill_features.sql:66-70): correction_weight = 1.0 AND anomaly_class NOT IN
('mistake','conditions') AND is_rain_lap = FALSE.
Part 2 recomputes each driver-race mean/stddev without the fabricated laps and reports the shift.
"""
from _db import con, show

c = con()
c.execute(r"""
create temp table clean as
select r.race_year, r.race_id, r.driver_id, r.driver_skill_residual_s res, r.base_track_pace_s is null fabricated
from int_lap_residual_decomposed r join int_lap_anomaly_flags a using (lap_id)
where r.correction_weight = 1.0 and a.anomaly_class not in ('mistake','conditions') and a.is_rain_lap = false""")
show(c, r"""
select count(*) clean_laps, count(*) filter (where fabricated) fabricated_clean_laps,
  round(avg(case when fabricated then 1.0 else 0 end), 4) share_fabricated,
  count(distinct (race_year, race_id, driver_id)) filter (where fabricated) driver_races_touched,
  (select count(*) from fct_driver_skill_features) driver_races
from clean""", "Part 1: fabricated laps inside the app's clean-lap filter")
show(c, r"""
with a as (select race_year, race_id, driver_id, avg(res) m_all, stddev(res) s_all,
             avg(res) filter (where not fabricated) m_meas, stddev(res) filter (where not fabricated) s_meas
           from clean group by all)
select round(avg(abs(m_all - m_meas)), 4) mean_abs_shift_in_mean_s, round(max(abs(m_all - m_meas)), 3) max_shift_mean_s,
  round(avg(s_all - s_meas), 4) mean_stddev_inflation_s, round(max(s_all - s_meas), 3) max_stddev_inflation_s
from a where m_meas is not null""", "Part 2: per driver-race mean and stddev, with vs without fabricated laps")
