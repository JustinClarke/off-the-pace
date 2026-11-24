{{ config(tags=['intermediate'], severity='error') }}
-- Task 2A. A lap whose compound cost is unknown (NULL expected_compound_pace_s:
-- no compound parameter cell, or unknown tyre age) must not enter the field pace
-- base. int_field_pace_curve drops it in its `eligible` CTE.
--
-- FIXTURE MIRROR, NOT THE FULL MODEL. int_field_pace_curve cannot be run in
-- isolation here (its eligible CTE joins fuel_state, geometry, air and
-- fastest-lap CTEs built from six upstream refs), so this test rebuilds the two
-- predicates of that CTE that concern the compound cost, copied from
-- int_field_pace_curve.sql, and evaluates them on synthetic laps:
--     LEFT JOIN compound AS c ON f.lap_id = c.lap_id          (compound CTE)
--     compound_corrected_lap_time = f.weight_corrected_lap_time
--                                   - c.expected_compound_pace_s   (no COALESCE)
--     WHERE f.weight_corrected_lap_time IS NOT NULL
--       AND c.expected_compound_pace_s IS NOT NULL
-- If either line changes in the model, change it here too. The pace itself comes
-- from the real compound_cliff_wear_s macro, the same expression
-- int_compound_cliff_predicted uses, so "missing cell -> NULL" is the real
-- behaviour and not an assumption. The all-model guard below
-- (assert_compound_wear_missing_cell_is_null) holds the macro; this one holds
-- the predicate.
--
-- Fixture laps, all at one (race, lap_number):
--   A_valid_priced     cell exists, age known       -> eligible
--   B_missing_cell     no cell (NULL), age known    -> NOT eligible
--   C_unknown_age      cell exists, age NULL        -> NOT eligible
-- Returns rows only on failure: (1) the eligible set is not exactly {A};
-- (2) A is missing from the base, or its corrected time is not wlt - pace;
-- (3) the field base (eligible count / mean corrected time) differs from A alone,
-- which is what happens if B enters as a free 0 s tyre (count 2, mean moved).
WITH laps AS (
    SELECT * FROM (VALUES
        -- lap_id,           weight_corrected_lap_time, gradient, severity, age, laps_past_cliff
        ('A_valid_priced',   90.0, CAST(0.10 AS DOUBLE), CAST(1.20 AS DOUBLE), CAST(10.0 AS DOUBLE), CAST(0.0 AS DOUBLE)),
        ('B_missing_cell',   88.0, CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), CAST(12.0 AS DOUBLE), CAST(0.0 AS DOUBLE)),
        ('C_unknown_age',    91.0, CAST(0.10 AS DOUBLE), CAST(1.20 AS DOUBLE), CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE))
    ) AS t (lap_id, weight_corrected_lap_time, wear_gradient, severity, age, laps_past_cliff)
),

-- the `compound` CTE of int_field_pace_curve (lap_id, expected_compound_pace_s),
-- priced by the real macro
compound AS (
    SELECT
        lap_id,
        {{ compound_cliff_wear_s('wear_gradient', 'severity', 'age', 'laps_past_cliff') }}
            AS expected_compound_pace_s
    FROM laps
),

-- the `eligible` CTE's compound predicates, verbatim
eligible AS (
    SELECT
        f.lap_id,
        f.weight_corrected_lap_time - c.expected_compound_pace_s
            AS compound_corrected_lap_time
    FROM laps AS f
    LEFT JOIN compound AS c ON f.lap_id = c.lap_id
    WHERE
        f.weight_corrected_lap_time IS NOT NULL
        AND c.expected_compound_pace_s IS NOT NULL
),

expected_pace_a AS (
    SELECT expected_compound_pace_s FROM compound WHERE lap_id = 'A_valid_priced'
),

base AS (
    SELECT
        COUNT(*) AS eligible_lap_count,
        AVG(compound_corrected_lap_time) AS base_mean_s,
        COUNT(*) FILTER (WHERE lap_id = 'A_valid_priced') AS a_in,
        COUNT(*) FILTER (WHERE lap_id = 'B_missing_cell') AS b_in,
        COUNT(*) FILTER (WHERE lap_id = 'C_unknown_age') AS c_in,
        MAX(compound_corrected_lap_time) FILTER (WHERE lap_id = 'A_valid_priced')
            AS a_corrected_s
    FROM eligible
)

SELECT
    b.eligible_lap_count,
    b.a_in,
    b.b_in,
    b.c_in,
    b.base_mean_s,
    b.a_corrected_s,
    e.expected_compound_pace_s AS a_pace_s
FROM base AS b
CROSS JOIN expected_pace_a AS e
WHERE
    -- exactly the valid priced lap is eligible
    b.eligible_lap_count != 1
    OR b.a_in != 1
    -- the missing-cell lap and the unknown-age lap cannot contribute
    OR b.b_in != 0
    OR b.c_in != 0
    -- the valid lap keeps its full compound correction (a priced pace, not NULL)
    OR e.expected_compound_pace_s IS NULL
    OR b.a_corrected_s IS NULL
    OR ABS(b.a_corrected_s - (90.0 - e.expected_compound_pace_s)) > 1e-9
    -- the field base is A alone
    OR ABS(b.base_mean_s - (90.0 - e.expected_compound_pace_s)) > 1e-9
