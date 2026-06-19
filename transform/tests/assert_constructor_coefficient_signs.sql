-- Constructor structural pace is centred on the field, so in every season at least
-- one constructor must be genuinely faster than the field average (point estimate < 0)
-- AND identified with a non-degenerate CI. This fails if a whole season collapses to
-- "nobody faster than field" or to unidentified (CI low == CI high) estimates, which
-- would signal the HDFE fit silently produced no usable signal.
WITH per_season AS (
    SELECT
        race_year,
        MIN(constructor_structural_pace_s)                              AS best_pace_s,
        SUM(CASE WHEN constructor_structural_pace_ci_low_s
                      < constructor_structural_pace_ci_high_s
                 THEN 1 ELSE 0 END)                                     AS identified_n
    FROM {{ ref('int_constructor_structural_pace') }}
    GROUP BY race_year
)

SELECT *
FROM per_season
WHERE best_pace_s >= 0
   OR identified_n = 0
