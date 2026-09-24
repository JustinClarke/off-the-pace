"""R2-H: Quali-vs-Race page subtracts two skills with OPPOSITE sign conventions.

app/src/features/quali-vs-race-skill/queries.ts:
    delta_s = AVG(q.quali_skill_session_avg_s) - AVG(f.driver_skill_proxy_mean_s)
quali_skill_session_avg_s: residual vs field model, negative = faster (int_qualifying_decomposed).
driver_skill_proxy_mean_s: fct_driver_skill_features.sql:13-14 "positive = ego faster than
    synthetic teammate".
methodology.tsx says both are "negative = faster". The warehouse's own quali_vs_race_skill_delta_s
uses the race RESIDUAL (same convention) and is not what the page reads.
Also: the join is at quali LAP grain, so every per-driver average is weighted by push-lap count.

Part 1 proves the sign (proxy vs residual correlate negatively). Part 2 re-runs the page's query
per season and compares its ranking with a sign-consistent delta (quali - race residual).

DEFECT PRESENT while: corr_residual_vs_proxy < 0 and the page still reads the proxy.
"""
from _db import con, show

c = con()
show(c, r"""select round(corr(driver_residual_mean_s, driver_skill_proxy_mean_s), 3) corr_residual_vs_proxy
from fct_driver_skill_features""", "Part 1: residual (neg = faster) vs proxy")
c.execute(r"""
create temp table page as
select q.race_year, q.driver_id,
  avg(q.quali_skill_session_avg_s) - avg(f.driver_skill_proxy_mean_s) page_delta,
  avg(q.quali_skill_session_avg_s) - avg(f.driver_residual_mean_s) consistent_delta,
  count(distinct q.race_id) n_races
from int_qualifying_decomposed q join fct_driver_skill_features f
  on q.driver_id = f.driver_id and q.race_id = f.race_id
where q.session_type = 'Q' and q.dnq_flag is not true and q.quali_traffic_flag is not true
group by all having count(distinct q.race_id) >= 3""")
show(c, r"""
select race_year, count(*) drivers,
  round(corr(rank_page, rank_cons), 3) spearman_page_vs_consistent,
  count(*) filter (where sign(page_delta) <> sign(consistent_delta)) sign_flips
from (select *, rank() over (partition by race_year order by page_delta) rank_page,
             rank() over (partition by race_year order by consistent_delta) rank_cons from page)
group by 1 order by 1""", "Part 2: page ranking vs sign-consistent ranking, per season")
