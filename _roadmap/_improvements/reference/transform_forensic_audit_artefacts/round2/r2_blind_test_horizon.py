"""R2-I: Blind-Test Scoreboard plots a 5-lap prediction against a 1-lap actual.

ml/src/predict.py: predicted_degradation_jump_s = p50 of degradation_regressor_p50, whose target
is S.DEGRADATION_TARGET = next_5_lap_cumulative_jump_s (5-lap cumulative, detrended, +-50 s clip).
app/src/features/blind-test-scoreboard/queries.ts: actual_degradation_jump_s =
f.next_lap_degradation_jump_s (legacy 1-lap, NOT detrended, +-10 s clip); transform.ts:92-97
plots x = actual, y = predicted with the p10-p90 band.

Scored against data/marts/mart_degradation_predictions.parquet (the shipped v14 scores).
DEFECT PRESENT while: the page reads next_lap_degradation_jump_s.
"""
from _db import REPO, con, show

c = con()
c.execute(f"create temp view p as select * from read_parquet('{REPO}/data/marts/mart_degradation_predictions.parquet')")
show(c, r"""
select p.model_version, count(*) n_rows_on_page,
  round(avg(abs(p.predicted_degradation_jump_s - f.next_lap_degradation_jump_s)), 3) mae_vs_page_actual_1lap,
  round(avg(abs(p.predicted_degradation_jump_s - f.next_5_lap_cumulative_jump_s)), 3) mae_vs_trained_target_5lap,
  round(avg(case when f.next_lap_degradation_jump_s between p.predicted_degradation_jump_p10_s
                  and p.predicted_degradation_jump_p90_s then 1.0 else 0 end), 3) band_coverage_page,
  round(avg(case when f.next_5_lap_cumulative_jump_s between p.predicted_degradation_jump_p10_s
                  and p.predicted_degradation_jump_p90_s then 1.0 else 0 end), 3) band_coverage_true_target,
  round(stddev(f.next_lap_degradation_jump_s), 3) sd_page_actual,
  round(stddev(f.next_5_lap_cumulative_jump_s), 3) sd_trained_target
from p join fct_cliff_prediction_features f using (lap_id)
where f.next_lap_degradation_jump_s is not null and f.laps_until_cliff_class is not null
  and f.next_5_lap_cumulative_jump_s is not null
group by 1""", "page's actual (1-lap) vs the model's trained target (5-lap), same rows")
