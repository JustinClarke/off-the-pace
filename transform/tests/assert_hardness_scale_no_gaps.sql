-- WI-17 (compound_hardness_scale, W50 seed rewrite). Every (compound, era) pair the warehouse
-- actually assigns must resolve a hardness rank -- a LEFT JOIN that matches nothing reads
-- identically to a fully-covered scale unless something asserts the positive case (the same
-- lesson assert_stint_geometry_2018_compound_code_null.sql's rule 2 encodes for the C-code join
-- itself).
--
-- 2018 identity is the lap's own compound name (compound_in_stint): 2018 laps carry absolute
-- names, and compound_code is NULL for all of 2018 by construction (08p) -- WI-17 takes 2018
-- identity from the lap name, never from tyre_allocations' 2018 rows (there are none, post W50).
-- 2019+ identity is compound_code (C1-C5; tyre_allocations does not carry C6, so a C6 gap can
-- only appear once a future season nominates it -- compound_hardness_scale already carries a
-- C6/2022+ row so that day resolves without a seed edit).
--
-- INTERMEDIATE/WET are not slicks and are out of scope for an ordinal hardness scale, matching
-- int_stint_geometry's own compound_code rule (Cinturato wets are not on the C-scale at all).

WITH warehouse_pairs AS (
    SELECT DISTINCT
        CASE WHEN race_year = 2018 THEN compound_in_stint ELSE compound_code END AS compound_code,
        CASE
            WHEN race_year = 2018 THEN '2018'
            WHEN race_year BETWEEN 2019 AND 2021 THEN '2019-21'
            ELSE '2022+'
        END AS era
    FROM {{ ref('int_stint_geometry') }}
    WHERE
        compound_in_stint NOT IN ('INTERMEDIATE', 'WET')
        AND (
            (race_year = 2018 AND compound_in_stint IS NOT NULL)
            OR (race_year != 2018 AND compound_code IS NOT NULL)
        )
)

SELECT
    w.compound_code,
    w.era
FROM warehouse_pairs AS w
LEFT JOIN {{ ref('compound_hardness_scale') }} AS s
    ON
        w.compound_code = s.compound_code
        AND w.era = s.era
WHERE s.compound_code IS NULL
