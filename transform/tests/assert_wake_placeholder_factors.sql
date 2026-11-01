-- WC-13: the placeholder's tyre and car multipliers. Returns offending laps.
--   * every (season, constructor_id) in the data has a constructor factor row
--     (a missing row would silently be neutral; the seed must be complete);
--   * a neutral fallback is always flagged, and a resolved lap never is;
--   * the per-lap loss is race x tyre x car held to the bounds, flagged when held;
--   * a constructor factor is 1.00 unless its row is public_concept;
--   * the tyre factor is ordered SOFT >= MEDIUM >= HARD within every race (WC-16: per race,
--     since the C-number factor varies by race);
--   * WC-16: a c_number lap's factor is clamp(step x medium shift) from
--     wake_placeholder_c_number_factor, in 0.90-1.17, with a C-number; a relative_class lap's
--     factor is the relative seed's; a 2019+ dry lap at a race with a trio is never relative_class.
WITH c AS (
    SELECT * FROM {{ ref('int_lap_wake_placeholder_cost') }}
),

order_check AS (
    SELECT
        race_id,
        MIN(CASE WHEN compound_class = 'SOFT' THEN compound_factor END) AS f_soft_min,
        MAX(CASE WHEN compound_class = 'MEDIUM' THEN compound_factor END) AS f_medium_max,
        MIN(CASE WHEN compound_class = 'MEDIUM' THEN compound_factor END) AS f_medium_min,
        MAX(CASE WHEN compound_class = 'HARD' THEN compound_factor END) AS f_hard_max
    FROM c
    WHERE compound_factor_scale <> 'neutral'
    GROUP BY race_id
),

c_rule AS (
    SELECT * FROM {{ ref('wake_placeholder_c_number_factor') }}
),

expected_c AS (
    SELECT
        c.lap_id,
        c.compound_factor,
        ROUND(LEAST(GREATEST(st.value * sh.value, b_min.value), b_max.value), 4) AS expected
    FROM c
    LEFT JOIN c_rule AS sh ON sh.param_kind = 'medium_shift' AND sh.param = c.race_medium_c
    LEFT JOIN c_rule AS st
        ON st.param_kind = 'step'
        AND st.param = CAST(GREATEST(LEAST(
            CAST(SUBSTR(c.tyre_c_number, 2) AS INTEGER) - CAST(SUBSTR(c.race_medium_c, 2) AS INTEGER),
            2), -2) AS VARCHAR)
    LEFT JOIN c_rule AS b_min ON b_min.param_kind = 'bound' AND b_min.param = 'min'
    LEFT JOIN c_rule AS b_max ON b_max.param_kind = 'bound' AND b_max.param = 'max'
    WHERE c.compound_factor_scale = 'c_number'
)

SELECT lap_id, 'no constructor row for a team in the data' AS problem
FROM c WHERE constructor_factor_source = 'neutral_no_constructor_row'
UNION ALL
SELECT lap_id, 'neutral fallback without a flag'
FROM c
WHERE (compound_factor_source IN ('neutral_missing_compound', 'neutral_unresolved_compound')
        OR constructor_factor_source IN ('neutral_missing_constructor', 'neutral_no_constructor_row'))
    AND factor_flag IS NULL
UNION ALL
SELECT lap_id, 'flag on a fully resolved lap'
FROM c
WHERE compound_factor_source NOT IN ('neutral_missing_compound', 'neutral_unresolved_compound')
    AND constructor_factor_source NOT IN ('neutral_missing_constructor', 'neutral_no_constructor_row')
    AND factor_flag IS NOT NULL
UNION ALL
SELECT lap_id, 'per-lap loss is not race x tyre x car within bounds'
FROM c
WHERE ABS(loss_s_per_lap_within_1s - ROUND(LEAST(GREATEST(
        race_loss_s_per_lap_within_1s * compound_factor * constructor_factor, 0.15), 0.55), 4)) > 1e-9
    OR (lap_loss_bounded <> (race_loss_s_per_lap_within_1s * compound_factor * constructor_factor < 0.15
        OR race_loss_s_per_lap_within_1s * compound_factor * constructor_factor > 0.55))
UNION ALL
SELECT lap_id, 'non-neutral car factor without public_concept'
FROM c WHERE constructor_factor <> 1.0 AND constructor_factor_source <> 'public_concept'
UNION ALL
SELECT lap_id, 'neutral or missing tyre class with a non-neutral factor'
FROM c
WHERE compound_factor_source NOT IN ('assumed_relative_label', 'assumed_race_order_2018', 'assumed_c_number')
    AND compound_factor <> 1.0
UNION ALL
SELECT race_id, 'tyre factor not ordered SOFT >= MEDIUM >= HARD in this race'
FROM order_check
WHERE f_soft_min < f_medium_max OR f_medium_min < f_hard_max
UNION ALL
SELECT lap_id, 'c_number tyre factor is not clamp(step x medium shift) from the seed'
FROM expected_c WHERE expected IS NULL OR ABS(compound_factor - expected) > 1e-9
UNION ALL
SELECT lap_id, 'c_number lap without a C-number, or tyre factor outside 0.90-1.17'
FROM c
WHERE compound_factor_scale = 'c_number'
    AND (tyre_c_number IS NULL OR race_medium_c IS NULL
        OR compound_factor < 0.90 OR compound_factor > 1.17 OR compound_factor_source <> 'assumed_c_number')
UNION ALL
SELECT c.lap_id, 'relative_class tyre factor differs from the relative seed'
FROM c
LEFT JOIN {{ ref('wake_placeholder_compound_factor') }} AS cf ON c.compound_class = cf.compound_class
WHERE c.compound_factor_scale = 'relative_class'
    AND (cf.factor IS NULL OR ABS(c.compound_factor - cf.factor) > 1e-9 OR c.tyre_c_number IS NOT NULL)
UNION ALL
SELECT c.lap_id, 'dry 2019+ lap at a race with a C-number trio not on the c_number scale'
FROM c
INNER JOIN {{ ref('wake_placeholder_tyre_allocation') }} AS a
    ON c.race_id = CAST(a.race_id AS VARCHAR) AND a.compound_scale = 'c_number'
WHERE c.compound_class IN ('SOFT', 'MEDIUM', 'HARD') AND c.compound_factor_scale <> 'c_number'
UNION ALL
SELECT lap_id, 'wet, intermediate or missing compound not neutral'
FROM c
WHERE (compound_class IN ('INTERMEDIATE', 'WET') OR compound_class IS NULL)
    AND (compound_factor <> 1.0 OR compound_factor_scale <> 'neutral')
