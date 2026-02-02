-- DEPRECATED (initial transform release, 2026-05-26).
-- int_constructor_pace_index superseded by int_constructor_structural_pace (#6); old model removed.
-- int_constructor_structural_pace is race-grain (not lap-grain), so lap-by-lap confidence
-- monotonicity no longer applies. CI bounds on the structural pace coefficient are validated
-- by the dbt_expectations.expect_column_pair_values_A_to_be_greater_than_B test in schema.yml.
SELECT 1 WHERE FALSE
