-- int_constructor_pace_index has been superseded and removed; int_constructor_structural_pace
-- is its race-grain (not lap-grain) replacement, so lap-by-lap confidence monotonicity no
-- longer applies as a concept. CI bounds on the structural pace coefficient are validated
-- instead by the dbt_expectations.expect_column_pair_values_A_to_be_greater_than_B test in
-- schema.yml.
{{ config(tags=['placeholder']) }}
SELECT 1 WHERE FALSE
