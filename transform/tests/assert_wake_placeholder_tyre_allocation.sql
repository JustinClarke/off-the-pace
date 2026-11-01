-- WC-16: the placeholder's C-number tyre allocation (seeds/wake_placeholder_tyre_allocation.csv).
-- Returns offending rows:
--   * a c_number race whose trio is not in hardness order (hard_c < medium_c < soft_c by C-number);
--   * a named_2018 race whose trio is not in hardness order on compound_hardness_scale (2018 ranks);
--   * a c_number race whose MEDIUM has no medium_shift row in wake_placeholder_c_number_factor
--     (C1 or C6 as medium: fails loudly rather than silently falling back);
--   * a step row missing for -2..2, or a missing bound.
WITH a AS (
    SELECT * FROM {{ ref('wake_placeholder_tyre_allocation') }}
),

r AS (
    SELECT * FROM {{ ref('wake_placeholder_c_number_factor') }}
),

h AS (
    SELECT CAST(compound_code AS VARCHAR) AS compound_code, hardness_rank
    FROM {{ ref('compound_hardness_scale') }}
    WHERE CAST(era AS VARCHAR) = '2018'
),

steps AS (
    SELECT CAST(s AS VARCHAR) AS param FROM range(-2, 3) AS t (s)
    UNION ALL SELECT 'min'
    UNION ALL SELECT 'max'
)

SELECT race_id, 'c_number trio not in hardness order' AS problem
FROM a
WHERE compound_scale = 'c_number'
    AND NOT (CAST(SUBSTR(hard_c, 2) AS INTEGER) < CAST(SUBSTR(medium_c, 2) AS INTEGER)
        AND CAST(SUBSTR(medium_c, 2) AS INTEGER) < CAST(SUBSTR(soft_c, 2) AS INTEGER))
UNION ALL
SELECT a.race_id, 'named_2018 trio not in hardness order'
FROM a
LEFT JOIN h AS hh ON a.hard_name = hh.compound_code
LEFT JOIN h AS hm ON a.medium_name = hm.compound_code
LEFT JOIN h AS hs ON a.soft_name = hs.compound_code
WHERE a.compound_scale = 'named_2018'
    AND NOT (hh.hardness_rank < hm.hardness_rank AND hm.hardness_rank < hs.hardness_rank)
UNION ALL
SELECT a.race_id, 'race medium has no medium_shift row (C1 or C6 as medium?)'
FROM a
LEFT JOIN r ON r.param_kind = 'medium_shift' AND r.param = a.medium_c
WHERE a.compound_scale = 'c_number' AND r.value IS NULL
UNION ALL
SELECT s.param, 'missing step or bound row'
FROM steps AS s
LEFT JOIN r ON r.param = s.param AND r.param_kind IN ('step', 'bound')
WHERE r.value IS NULL
