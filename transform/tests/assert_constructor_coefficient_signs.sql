-- Constructor structural pace is centred on the field, so in every season at least
-- one constructor must be genuinely faster than the field average (point estimate < 0)
-- AND identified with a non-degenerate CI. This fails if a whole season collapses to
-- "nobody faster than field" or to unidentified (CI low == CI high) estimates, which
-- would signal the HDFE fit silently produced no usable signal.
--
-- Only seasons whose dry panel holds at least two constructors are asserted: a
-- single constructor is centred on itself (pace exactly 0), so "someone is faster
-- than the field" cannot hold by construction. That happens only when a season has
-- almost no dry running at all -- on the CI fixtures, whose 2024 season is the one
-- race 2024 São Paulo, run entirely on intermediates/wets. Until WI-05's F26 fix the
-- rain flag read 36% of that race as dry and fed it to this panel.
WITH per_season AS (
    SELECT
        race_year,
        MIN(constructor_structural_pace_s)                              AS best_pace_s,
        SUM(CASE WHEN constructor_structural_pace_ci_low_s
                      < constructor_structural_pace_ci_high_s
                 THEN 1 ELSE 0 END)                                     AS identified_n,
        COUNT(DISTINCT constructor_id)                                  AS constructors_n
    FROM {{ ref('int_constructor_structural_pace') }}
    GROUP BY race_year
)

SELECT *
FROM per_season
WHERE constructors_n >= 2
  AND (best_pace_s >= 0
   OR identified_n = 0)
