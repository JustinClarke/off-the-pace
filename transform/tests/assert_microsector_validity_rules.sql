-- DA-02 validity rules for int_microsector_proximity (design note section 1,
-- DD5). One row per failure.
--
--   'valid_row_unpriced'      a valid row (invalid_reason IS NULL) without a
--                             time, a car ahead, a gap or a gap_band
--   'invalid_row_priced'      an invalid row that still carries a gap_band
--   'unknown_ahead_has_gap'   no car ahead but a gap (unknown is NULL, never 0,
--                             the CO-04 rule)
--   'lapped_within_not_flagged'  a lapped car ahead within the window that is
--                             not 'lapped_ahead_within_window' (DD5)
--   'lapped_beyond_not_reference' a lapped car ahead at or beyond the window on
--                             an otherwise timed row that is not in the
--                             reference band (DD5: beyond 3 s the row is in
--                             the reference band whoever the car is)
--   'band_edge'               a gap_band that does not match the gap
--   'y_without_field'         y_s present with fewer than
--                             var('microsector_min_field_n') timed cars
--   'gate_a_season'           Gate A (DA-01): under 90% of a season's TIMING-
--                             valid rows are exposure-valid (dev 2026-10-24:
--                             95.1-98.3% per season; DA-01 measured 95.5-98.5%
--                             on green samples)
{{ config(severity='error') }}

SELECT
    'valid_row_unpriced' AS issue,
    microsector_id AS detail
FROM {{ ref('int_microsector_proximity') }}
WHERE
    invalid_reason IS NULL
    AND (
        time_s IS NULL
        OR ahead_driver_id IS NULL
        OR gap_ahead_s IS NULL
        OR gap_band IS NULL
    )

UNION ALL

SELECT
    'invalid_row_priced' AS issue,
    microsector_id AS detail
FROM {{ ref('int_microsector_proximity') }}
WHERE invalid_reason IS NOT NULL AND gap_band IS NOT NULL

UNION ALL

SELECT
    'unknown_ahead_has_gap' AS issue,
    microsector_id AS detail
FROM {{ ref('int_microsector_proximity') }}
WHERE ahead_driver_id IS NULL AND gap_ahead_s IS NOT NULL

UNION ALL

SELECT
    'lapped_within_not_flagged' AS issue,
    microsector_id AS detail
FROM {{ ref('int_microsector_proximity') }}
WHERE
    timing_invalid_reason IS NULL
    AND is_lapped_ahead
    AND gap_ahead_s < {{ var('microsector_lapped_ahead_window_s') }}
    AND invalid_reason IS DISTINCT FROM 'lapped_ahead_within_window'

UNION ALL

SELECT
    'lapped_beyond_not_reference' AS issue,
    microsector_id AS detail
FROM {{ ref('int_microsector_proximity') }}
WHERE
    timing_invalid_reason IS NULL
    AND is_lapped_ahead
    AND gap_ahead_s >= {{ var('microsector_lapped_ahead_window_s') }}
    AND gap_band IS DISTINCT FROM '5_gt3_reference'

UNION ALL

SELECT
    'band_edge' AS issue,
    microsector_id AS detail
FROM {{ ref('int_microsector_proximity') }}
WHERE
    gap_band IS NOT NULL
    AND gap_band IS DISTINCT FROM CASE
        WHEN gap_ahead_s < 0.5 THEN '0_lt0.5'
        WHEN gap_ahead_s < 1.0 THEN '1_0.5to1'
        WHEN gap_ahead_s < 1.5 THEN '2_1to1.5'
        WHEN gap_ahead_s < 2.0 THEN '3_1.5to2'
        WHEN gap_ahead_s < 3.0 THEN '4_2to3'
        ELSE '5_gt3_reference'
    END

UNION ALL

SELECT
    'y_without_field' AS issue,
    microsector_id AS detail
FROM {{ ref('int_microsector_proximity') }}
WHERE
    y_s IS NOT NULL
    AND field_n < {{ var('microsector_min_field_n') }}

UNION ALL

SELECT
    'gate_a_season' AS issue,
    CAST(race_year AS VARCHAR) AS detail
FROM {{ ref('int_microsector_proximity') }}
WHERE timing_invalid_reason IS NULL
GROUP BY race_year
HAVING
    COUNT(*) >= 1000
    AND AVG(CASE WHEN invalid_reason IS NULL THEN 1.0 ELSE 0.0 END) < 0.90
