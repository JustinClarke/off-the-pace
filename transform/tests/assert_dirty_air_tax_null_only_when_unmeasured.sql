-- CO-04 / FD6. int_dirty_air_tax_component's lagged share, and so the tax, is
-- NULL exactly when the previous lap of the stint (full lap sequence) has an
-- unmeasured air state (int_lap_air_state.dirty_air_share_lap NULL), and is
-- never NULL otherwise. Replaces the plain not_null the lag column carried
-- before FD6, which would now fail on the honest NULLs.
--
-- One row per failure:
--   'lag_null_but_previous_measured' -- NULL lag, previous lap measured (or
--     no previous lap in the stint, where the lag is 0.0 by definition).
--   'lag_set_but_previous_unmeasured' -- a lag value where the previous lap's
--     air state is unmeasured: an unknown priced as known.
--   'tax_null_mismatch' -- dirty_air_tax_s NULL where the lag is not, or the
--     reverse.
{{ config(severity='error') }}

WITH prev_air AS (
    SELECT
        g.lap_id,
        LAG(a.dirty_air_share_lap) OVER w AS prev_share,
        LAG(g.lap_id) OVER w AS prev_lap_id
    FROM {{ ref('int_stint_geometry') }} AS g
    LEFT JOIN {{ ref('int_lap_air_state') }} AS a ON g.lap_id = a.lap_id
    WINDOW w AS (PARTITION BY g.stint_id ORDER BY g.lap_in_stint)
),

checked AS (
    SELECT
        t.lap_id,
        t.dirty_air_intensity_lag1,
        t.dirty_air_tax_s,
        p.prev_lap_id,
        p.prev_lap_id IS NOT NULL AND p.prev_share IS NULL
            AS previous_unmeasured
    FROM {{ ref('int_dirty_air_tax_component') }} AS t
    INNER JOIN prev_air AS p ON t.lap_id = p.lap_id
)

SELECT
    'lag_null_but_previous_measured' AS failure,
    lap_id,
    dirty_air_intensity_lag1,
    dirty_air_tax_s
FROM checked
WHERE dirty_air_intensity_lag1 IS NULL AND NOT previous_unmeasured

UNION ALL

SELECT
    'lag_set_but_previous_unmeasured' AS failure,
    lap_id,
    dirty_air_intensity_lag1,
    dirty_air_tax_s
FROM checked
WHERE dirty_air_intensity_lag1 IS NOT NULL AND previous_unmeasured

UNION ALL

SELECT
    'tax_null_mismatch' AS failure,
    lap_id,
    dirty_air_intensity_lag1,
    dirty_air_tax_s
FROM checked
WHERE (dirty_air_tax_s IS NULL) != (dirty_air_intensity_lag1 IS NULL)
