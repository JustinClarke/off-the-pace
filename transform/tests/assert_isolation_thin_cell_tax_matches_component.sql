-- W10 / v17: the thin-cell dirty-air tax priced inside the isolation panel is the same
-- number the tax component would write.
--
-- int_driver_isolation_lap_panel prices a lap with no int_dirty_air_tax_component row
-- (a thin field-base cell) as theta_air x the previous lap's share, clamped to [0, 5],
-- by re-deriving the lag. This test applies the panel's pricing rule to the laps that
-- DO have a component row and requires it to reproduce the component's tax (tolerance
-- 1e-9 s), so the two copies of the rule cannot drift apart. It also pins:
--   * a repriced lap is never in 2018_1 or 2018_2 (no telemetry, 6% measured);
--   * a repriced lap's tax is never NULL and lies in [0, 5];
--   * the panel gained laps from this (vacuity guard: at least 1,000 repriced laps;
--     50 on the CI fixture, which measures 91).

WITH theta AS (
    SELECT CAST({{ var('theta_air_label_value') }} AS DOUBLE) AS theta_air
),

lagged AS (
    SELECT
        g.lap_id,
        LAG(a.dirty_air_share_lap, 1, 0.0) OVER (
            PARTITION BY g.stint_id
            ORDER BY g.lap_in_stint
        ) AS share_lag1
    FROM {{ ref('int_stint_geometry') }} AS g
    LEFT JOIN {{ ref('int_lap_air_state') }} AS a
        ON g.lap_id = a.lap_id
),

rule_vs_component AS (
    SELECT
        d.lap_id,
        d.dirty_air_tax_s AS component_tax_s,
        CASE
            WHEN t.theta_air * l.share_lag1 < 0 THEN 0.0
            WHEN t.theta_air * l.share_lag1 > 5.0 THEN 5.0
            ELSE t.theta_air * l.share_lag1
        END AS rule_tax_s
    FROM {{ ref('int_dirty_air_tax_component') }} AS d
    INNER JOIN lagged AS l
        ON d.lap_id = l.lap_id
    CROSS JOIN theta AS t
)

SELECT
    'panel pricing rule differs from the tax component' AS issue,
    lap_id,
    rule_tax_s - component_tax_s AS diff_s
FROM rule_vs_component
WHERE
    (component_tax_s IS NULL) <> (rule_tax_s IS NULL)
    OR ABS(rule_tax_s - component_tax_s) > 1e-9

UNION ALL

SELECT
    'repriced lap in a race without telemetry' AS issue,
    lap_id,
    dirty_air_tax_s AS diff_s
FROM {{ ref('int_driver_isolation_lap_panel') }}
WHERE is_thin_cell_tax AND race_id IN ('2018_1', '2018_2')

UNION ALL

SELECT
    'repriced lap with a NULL or out-of-range tax' AS issue,
    lap_id,
    dirty_air_tax_s AS diff_s
FROM {{ ref('int_driver_isolation_lap_panel') }}
WHERE
    is_thin_cell_tax
    AND (dirty_air_tax_s IS NULL OR dirty_air_tax_s < 0 OR dirty_air_tax_s > 5.0)

UNION ALL

SELECT
    'too few thin-cell laps repriced (vacuity guard)' AS issue,
    NULL AS lap_id,
    COUNT(*) AS diff_s
FROM {{ ref('int_driver_isolation_lap_panel') }}
WHERE is_thin_cell_tax
HAVING COUNT(*) < {{ 50 if target.name == 'ci' else 1000 }}
