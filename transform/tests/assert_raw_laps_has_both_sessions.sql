-- Assert that both stg_laps (race) and stg_laps_qualifying exist and have data
-- Test passes when both models contain rows

SELECT 1
WHERE
    (SELECT COUNT(*) FROM {{ ref('stg_laps') }}) = 0
    OR (SELECT COUNT(*) FROM {{ ref('stg_laps_qualifying') }}) = 0
