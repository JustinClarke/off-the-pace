-- Regression for the non-estimable evidence used by
-- assert_isolation_sign_convention. Reads the real model output; no rows are
-- fabricated.
WITH iso AS (
    SELECT car_term_source, car_iso_s
    FROM {{ ref('int_constructor_car_fe_isolation') }}
)

-- Vacuity guard: the relation must have at least one row.
SELECT 'relation_empty' AS failure, 0 AS n_bad
WHERE NOT EXISTS (SELECT 1 FROM iso)

UNION ALL

SELECT 'row_not_not_estimated' AS failure, COUNT(*) AS n_bad
FROM iso
WHERE car_term_source IS NULL OR car_term_source <> 'not_estimated'
HAVING COUNT(*) > 0

UNION ALL

SELECT 'car_iso_s_non_null' AS failure, COUNT(*) AS n_bad
FROM iso
WHERE car_iso_s IS NOT NULL
HAVING COUNT(*) > 0
