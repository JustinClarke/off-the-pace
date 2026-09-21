-- Enforce the 2018 compound_code NULL rule: Pirelli's relative compound naming
-- began in 2019, and stg_tyre_allocations sourcing covers 2019-2024 only, so
-- every 2018 row must carry NULL.
-- Filed under 08p.

SELECT
    COUNT(*) as rows_with_non_null_2018_compound_code
FROM {{ ref('int_stint_geometry') }}
WHERE race_year = 2018
  AND compound_code IS NOT NULL
HAVING COUNT(*) > 0
