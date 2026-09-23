-- 08p. Pins the compound_code NULL rule in BOTH directions.
--
-- Rule 1 (the rule this test was created for): Pirelli's relative compound
-- naming began in 2019 and stg_tyre_allocations covers 2019-2024 only, so
-- every 2018 row must carry NULL. Guards against a silent back-fill.
--
-- Rule 2 (added 2026-09-22): every SLICK lap in 2019-2024 must resolve a
-- code. Rule 1 alone is satisfied VACUOUSLY by a column that is NULL
-- everywhere, which is exactly what shipped on 2026-09-21 - the join was
-- written across two disjoint `circuit_key` domains, matched zero rows, and
-- this test passed anyway. A LEFT JOIN that matches nothing is
-- indistinguishable from the CAST(NULL AS VARCHAR) it replaced unless
-- something asserts the positive case. INTERMEDIATE/WET are excluded:
-- Cinturato wets are not on the C1-C5 scale, so NULL is correct for them.

SELECT
    'rule_1_2018_must_be_null' AS violated_rule,
    COUNT(*) AS n_violating_rows
FROM {{ ref('int_stint_geometry') }}
WHERE
    race_year = 2018
    AND compound_code IS NOT NULL
HAVING COUNT(*) > 0

UNION ALL

SELECT
    'rule_2_2019plus_slicks_must_resolve' AS violated_rule,
    COUNT(*) AS n_violating_rows
FROM {{ ref('int_stint_geometry') }}
WHERE
    race_year >= 2019
    AND compound_in_stint IN ('HARD', 'MEDIUM', 'SOFT')
    AND compound_code IS NULL
HAVING COUNT(*) > 0
