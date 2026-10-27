-- OUT: 04b_beta_band_agreement
-- Would the position-channel gap put the pair in the same design-note beta
-- band (<0.5, 0.5-1, 1-1.5, 1.5-2, 2-3, >=3 s) as the timing feed? S1+S2,
-- green, same filters as gap_eval. By timing band and era.
WITH b AS (
    SELECT *,
        CASE WHEN gap_timing_s < 0.5 THEN 0 WHEN gap_timing_s < 1 THEN 1 WHEN gap_timing_s < 1.5 THEN 2
             WHEN gap_timing_s < 2 THEN 3 WHEN gap_timing_s < 3 THEN 4 ELSE 5 END AS kb_t,
        CASE WHEN gap_pos_s < 0.5 THEN 0 WHEN gap_pos_s < 1 THEN 1 WHEN gap_pos_s < 1.5 THEN 2
             WHEN gap_pos_s < 2 THEN 3 WHEN gap_pos_s < 3 THEN 4 ELSE 5 END AS kb_p,
        CASE WHEN race_year <= 2021 THEN '2018-2021' ELSE '2022-2025' END AS era
    FROM gap_eval WHERE line IN ('s1', 's2')
)
SELECT era, kb_t AS timing_beta_band, COUNT(*) AS n_pairs,
       ROUND(AVG(CASE WHEN kb_p = kb_t THEN 1.0 ELSE 0 END), 4) AS share_same_band,
       ROUND(AVG(CASE WHEN ABS(kb_p - kb_t) <= 1 THEN 1.0 ELSE 0 END), 4) AS share_within_one_band
FROM b WHERE kb_t <= 4 GROUP BY ROLLUP(1, 2) ORDER BY 1, 2
;;
-- OUT: 04b_noise_by_era_and_bracket
-- Is the disagreement spread tied to the position cadence? median |diff| by era
-- and by the bracketing sample spacing at the line (own car).
SELECT CASE WHEN race_year <= 2019 THEN '2018-19 (0.30 s grid)' WHEN race_year <= 2021 THEN '2020-21 (0.22 s grid)'
            ELSE '2022-25 (jittered, median 0.24 s)' END AS cadence,
       CASE WHEN bracket_dt < 0.2 THEN 'a: <0.20' WHEN bracket_dt < 0.26 THEN 'b: 0.20-0.26'
            WHEN bracket_dt < 0.32 THEN 'c: 0.26-0.32' ELSE 'd: >=0.32' END AS own_bracket_dt,
       COUNT(*) AS n_pairs, ROUND(MEDIAN(ABS(disagreement_s)), 4) AS median_abs_diff_s,
       ROUND(QUANTILE_CONT(ABS(disagreement_s), 0.9), 4) AS p90_abs
FROM gap_eval WHERE line IN ('s1', 's2') AND gap_timing_s < 2
GROUP BY 1, 2 ORDER BY 1, 2
