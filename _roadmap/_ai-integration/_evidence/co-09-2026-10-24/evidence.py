"""CO-09 evidence: before (HEAD code) vs after (re-keyed) on scratch copies. Read-only."""
import duckdb, sys, json
S, OUT = sys.argv[1], sys.argv[2]
c = duckdb.connect()
c.execute(f"ATTACH '{S}/before/dev.duckdb' AS b (READ_ONLY)")
c.execute(f"ATTACH '{S}/dev.duckdb' AS a (READ_ONLY)")
out = {}
def q(name, sql):
    df = c.sql(sql).df(); out[name] = df
    df.to_csv(f"{OUT}/{name}.csv", index=False); return df

q("per_season_stints", """
WITH bb AS (SELECT race_year, COUNT(*) n_before,
   COUNT(*) FILTER (WHERE stint_end_cause='green_pit') green_b, COUNT(*) FILTER (WHERE stint_end_cause='sc_pit') sc_b,
   COUNT(*) FILTER (WHERE stint_end_cause='vsc_pit') vsc_b, COUNT(*) FILTER (WHERE stint_end_cause='red') red_b,
   COUNT(*) FILTER (WHERE stint_end_cause='race_end') race_end_b, COUNT(*) FILTER (WHERE stint_end_cause='retirement') ret_b,
   COUNT(*) FILTER (WHERE is_censored_stint) censored_b
   FROM b.int_stint_end_regime GROUP BY 1),
aa AS (SELECT race_year, COUNT(*) n_after,
   COUNT(*) FILTER (WHERE stint_end_cause='green_pit') green_a, COUNT(*) FILTER (WHERE stint_end_cause='sc_pit') sc_a,
   COUNT(*) FILTER (WHERE stint_end_cause='vsc_pit') vsc_a, COUNT(*) FILTER (WHERE stint_end_cause='red') red_a,
   COUNT(*) FILTER (WHERE stint_end_cause='race_end') race_end_a, COUNT(*) FILTER (WHERE stint_end_cause='retirement') ret_a,
   COUNT(*) FILTER (WHERE is_censored_stint) final_runs_a,
   COUNT(*) FILTER (WHERE is_stint_life_censored) life_censored_a,
   COUNT(*) FILTER (WHERE reached_flag) flag_1_a, COUNT(*) FILTER (WHERE NOT reached_flag) flag_0_a,
   COUNT(*) FILTER (WHERE reached_flag IS NULL) flag_censored_a
   FROM a.int_stint_end_regime GROUP BY 1)
SELECT bb.race_year, n_before, n_after, n_after-n_before AS d_stints,
  sc_b, sc_a, red_b, red_a, green_b, green_a, vsc_b, vsc_a, race_end_b, race_end_a, ret_b, ret_a,
  censored_b, final_runs_a, life_censored_a, flag_1_a, flag_0_a, flag_censored_a
FROM bb JOIN aa USING (race_year) ORDER BY 1""")

# map each before-stint to its after-run via laps
q("joined_runs_by_race", """
WITH m AS (SELECT DISTINCT bg.race_year, bg.race_id, bg.driver_id, bg.stint_id AS old_id, ag.stint_id AS new_id
  FROM b.int_stint_geometry bg JOIN a.int_stint_geometry ag USING (lap_id)),
runs AS (SELECT race_year, race_id, driver_id, new_id, COUNT(*) n_frag FROM m GROUP BY ALL HAVING COUNT(*) > 1),
er AS (SELECT stint_id, end_regime FROM b.int_stint_end_regime)
SELECT r.race_year, r.race_id, COUNT(*) AS runs_joined, SUM(n_frag-1) AS stints_removed,
  COUNT(DISTINCT driver_id) AS drivers
FROM runs r GROUP BY 1,2 ORDER BY 1,2""")

q("joined_boundaries_by_regime", """
WITH m AS (SELECT DISTINCT bg.race_year, bg.stint_id AS old_id, ag.stint_id AS new_id
  FROM b.int_stint_geometry bg JOIN a.int_stint_geometry ag USING (lap_id)),
absorbed AS (SELECT m.race_year, e.end_regime FROM m JOIN b.int_stint_end_regime e ON e.stint_id = m.old_id
  JOIN a.int_stint_end_regime x ON x.stint_id = m.new_id
  WHERE e.end_lap_number < x.end_lap_number)
SELECT race_year, end_regime AS boundary_regime, COUNT(*) n FROM absorbed GROUP BY ALL ORDER BY 1,2""")

q("label_flips_lap_grain", """
WITH bl AS (SELECT g.lap_id, g.race_year, e.stint_end_cause cb, e.is_censored_stint cens_b,
     g.lap_in_stint lis_b, f.stint_length_laps len_b
   FROM b.int_stint_geometry g JOIN b.int_stint_end_regime e USING (stint_id) JOIN b.fct_stint_features f USING (stint_id)),
al AS (SELECT g.lap_id, e.stint_end_cause ca, e.is_stint_life_censored cens_a, e.reached_flag rf,
     g.lap_in_stint lis_a, f.stint_length_laps len_a
   FROM a.int_stint_geometry g JOIN a.int_stint_end_regime e USING (stint_id) JOIN a.fct_stint_features f USING (stint_id))
SELECT race_year, COUNT(*) laps,
  COUNT(*) FILTER (WHERE cb IS DISTINCT FROM ca) cause_changed,
  COUNT(*) FILTER (WHERE cb IN ('sc_pit','vsc_pit','red','green_pit') AND ca='race_end') pit_to_race_end,
  COUNT(*) FILTER (WHERE (len_b - lis_b) <> (len_a - lis_a)) remaining_life_changed,
  COUNT(*) FILTER (WHERE cens_b IS DISTINCT FROM cens_a) stint_life_censor_changed
FROM bl JOIN al USING (lap_id) GROUP BY 1 ORDER BY 1""")

q("lap_rows_per_season", """
SELECT race_year,
 (SELECT COUNT(*) FROM b.fct_cliff_prediction_features x WHERE x.race_year=t.race_year) mart_rows_before,
 (SELECT COUNT(*) FROM a.fct_cliff_prediction_features x WHERE x.race_year=t.race_year) mart_rows_after,
 (SELECT COUNT(*) FROM b.fct_cliff_prediction_features x WHERE x.race_year=t.race_year AND next_5_lap_cumulative_jump_s IS NOT NULL) n5_before,
 (SELECT COUNT(*) FROM a.fct_cliff_prediction_features x WHERE x.race_year=t.race_year AND next_5_lap_cumulative_jump_s IS NOT NULL) n5_after,
 (SELECT COUNT(*) FROM b.fct_cliff_prediction_features x WHERE x.race_year=t.race_year AND is_training_eligible) elig_before,
 (SELECT COUNT(*) FROM a.fct_cliff_prediction_features x WHERE x.race_year=t.race_year AND is_training_eligible) elig_after
FROM (SELECT DISTINCT race_year FROM a.fct_cliff_prediction_features) t ORDER BY 1""")

q("canada_2025", """
SELECT 'before' AS side, driver_id, stint_id, stint_number, end_lap_number, end_lap_in_stint, end_regime, stint_end_cause,
  is_censored_stint, NULL::BOOLEAN is_stint_life_censored, NULL::BOOLEAN reached_flag
FROM b.int_stint_end_regime WHERE race_id='2025_10'
UNION ALL
SELECT 'after', driver_id, stint_id, stint_number, end_lap_number, end_lap_in_stint, end_regime, stint_end_cause,
  is_censored_stint, is_stint_life_censored, reached_flag
FROM a.int_stint_end_regime WHERE race_id='2025_10'
ORDER BY driver_id, side DESC, stint_number""")

q("canada_2025_summary", """
SELECT 'before' side, stint_end_cause, COUNT(*) n, COUNT(*) FILTER (WHERE end_lap_in_stint=1) one_lap
FROM b.int_stint_end_regime WHERE race_id='2025_10' GROUP BY ALL
UNION ALL
SELECT 'after', stint_end_cause, COUNT(*), COUNT(*) FILTER (WHERE end_lap_in_stint=1)
FROM a.int_stint_end_regime WHERE race_id='2025_10' GROUP BY ALL ORDER BY 1 DESC, 2""")

q("unchanged_key_check", """
SELECT
 (SELECT COUNT(*) FROM b.int_stint_end_regime) stints_before,
 (SELECT COUNT(*) FROM a.int_stint_end_regime) stints_after,
 (SELECT COUNT(*) FROM a.int_stint_end_regime x WHERE x.stint_id IN (SELECT stint_id FROM b.int_stint_end_regime)) after_ids_present_before,
 (SELECT COUNT(*) FROM a.int_stint_geometry) laps_after, (SELECT COUNT(*) FROM b.int_stint_geometry) laps_before""")

for k, v in out.items():
    print(f"\n== {k}"); print(v.to_string(index=False))
