-- T39 (F49, WI-15b). Every declared degradation_source class has rows, and
-- surface_bulk_ratio is normalised, in both places it is built.
--
-- Before F49 the ratio was surface/(surface+bulk). Both loads sum the same
-- non-negative push_residual series and no surface weight exceeds the bulk
-- weight at the same lag, so surface <= bulk always and the ratio could not
-- pass 0.5. 'surface_driven' needed > 0.65 and had 0 of 41,437 laps. Dividing
-- each load by its own weight sum makes a steady push read 0.5, but the ceiling
-- is still bulk_sum/(surface_sum+bulk_sum) = 0.606, so the class was removed
-- rather than left in place, dead.
--   1. empty_class: a class in the list below has no rows. The list must
--      match the accepted_values test on degradation_source in
--      intermediate/schema.yml: accepted_values stops undeclared classes
--      appearing, this stops declared ones being dead. Restoring
--      'surface_driven' in both fails here.
--   2. *_ratio_not_normalised: the ratio never exceeds 0.5 (unnormalised, the
--      exact ceiling is 0.5; normalised, it reaches 0.606 whenever all of a
--      lap's push is on that lap). Checked in the fan model and in the contract
--      mart, which carry separate copies of the expression.
{{ config(severity='error') }}

WITH declared AS (
    SELECT 'bulk_driven' AS class_name
    UNION ALL
    SELECT 'mixed' AS class_name
),

observed AS (
    SELECT
        degradation_source AS class_name,
        COUNT(*) AS n_laps
    FROM {{ ref('int_tyre_surface_vs_bulk_decoupling') }}
    GROUP BY 1
)

SELECT
    'empty_class' AS check_name,
    d.class_name AS detail,
    COALESCE(o.n_laps, 0) AS measured
FROM declared AS d
LEFT JOIN observed AS o ON d.class_name = o.class_name
WHERE COALESCE(o.n_laps, 0) = 0

UNION ALL

SELECT
    'decoupling_ratio_not_normalised' AS check_name,
    'max surface_bulk_ratio' AS detail,
    MAX(surface_bulk_ratio) AS measured
FROM {{ ref('int_tyre_surface_vs_bulk_decoupling') }}
HAVING MAX(surface_bulk_ratio) <= 0.5

UNION ALL

SELECT
    'mart_ratio_not_normalised' AS check_name,
    'max surface_bulk_ratio' AS detail,
    MAX(surface_bulk_ratio) AS measured
FROM {{ ref('fct_cliff_prediction_features') }}
HAVING MAX(surface_bulk_ratio) <= 0.5
