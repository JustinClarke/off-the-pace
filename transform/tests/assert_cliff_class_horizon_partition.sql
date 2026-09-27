-- laps_until_cliff_class must partition the remaining-stint horizon exactly as
-- its class names read. Prior to 2026-08 it did not: the label tested a fixed
-- set of LEAD offsets ({1,2} -> 0_to_2, {3,5} -> 3_to_5, {6} -> 6_plus), so
-- offset 4 was never tested and nothing past 6 was. That made `6_plus` mean
-- "exactly 6" and pushed every cliff 4 or 7+ laps out into 'none_in_stint' --
-- 9,405 training rows on the wrong side of a class boundary, and a `6_plus`
-- class the classifier could not learn (final-fold F1 0.058).
--
-- WI-01/F1 (2026-09-27): driver_skill_residual_s can now be NULL (a lap the
-- field curve has no measured base for, rather than a fabricated 0). Two
-- additions to the re-derivation below, mirroring the mart's own fix: (a) a
-- lap whose OWN residual is unmeasured has no honest starting point to scan
-- from -> NULL; (b) a lap sitting on or before the nearest later unmeasured
-- lap in the stint might hide a real crossing the scan can't see past ->
-- NULL, not 'none_in_stint'.
--
-- The scan below is an independent re-derivation of the first crossing lap. It
-- does not reuse the mart's CTEs, so it fails if the mart's definition drifts
-- back to a fixed offset set, changes the 1.0s threshold, drops the
-- k x drift detrending, or regresses the NULL-propagation above.
WITH residuals AS (
    SELECT
        r.lap_id,
        r.stint_id,
        r.lap_in_stint,
        r.driver_skill_residual_s,
        COALESCE(d.drift_s_per_lap, 0.0) AS drift_s_per_lap
    FROM {{ ref('int_lap_residual_decomposed') }} AS r
    LEFT JOIN {{ ref('int_lap_residual_stint_detrend') }} AS d
        ON r.stint_id = d.stint_id
),

horizon AS (
    SELECT
        stint_id,
        MAX(lap_in_stint) AS last_lap_in_stint
    FROM residuals
    GROUP BY stint_id
),

first_crossing AS (
    SELECT
        a.lap_id,
        MIN(f.lap_in_stint - a.lap_in_stint) AS laps_until_cliff
    FROM residuals AS a
    INNER JOIN residuals AS f
        ON
            a.stint_id = f.stint_id
            AND a.lap_in_stint < f.lap_in_stint
            AND (
                f.driver_skill_residual_s
                - a.driver_skill_residual_s
                - (f.lap_in_stint - a.lap_in_stint) * a.drift_s_per_lap
            ) > 1.0
    GROUP BY a.lap_id
),

nearest_unknown AS (
    SELECT
        a.lap_id,
        MIN(g.lap_in_stint - a.lap_in_stint) AS nearest_unknown_gap
    FROM residuals AS a
    INNER JOIN residuals AS g
        ON
            a.stint_id = g.stint_id
            AND a.lap_in_stint < g.lap_in_stint
            AND g.driver_skill_residual_s IS NULL
    GROUP BY a.lap_id
),

expected AS (
    SELECT
        r.lap_id,
        fc.laps_until_cliff,
        CASE
            WHEN r.driver_skill_residual_s IS NULL THEN NULL
            WHEN h.last_lap_in_stint <= r.lap_in_stint THEN NULL
            WHEN
                fc.laps_until_cliff <= 2
                AND (ug.nearest_unknown_gap IS NULL OR ug.nearest_unknown_gap > fc.laps_until_cliff)
                THEN '0_to_2'
            WHEN
                fc.laps_until_cliff <= 5
                AND (ug.nearest_unknown_gap IS NULL OR ug.nearest_unknown_gap > fc.laps_until_cliff)
                THEN '3_to_5'
            WHEN
                fc.laps_until_cliff IS NOT NULL
                AND (ug.nearest_unknown_gap IS NULL OR ug.nearest_unknown_gap > fc.laps_until_cliff)
                THEN '6_plus'
            WHEN ug.nearest_unknown_gap IS NOT NULL THEN NULL
            ELSE 'none_in_stint'
        END AS expected_class
    FROM residuals AS r
    INNER JOIN horizon AS h ON r.stint_id = h.stint_id
    LEFT JOIN first_crossing AS fc ON r.lap_id = fc.lap_id
    LEFT JOIN nearest_unknown AS ug ON r.lap_id = ug.lap_id
)

SELECT
    m.lap_id,
    e.laps_until_cliff,
    m.laps_until_cliff_class AS actual_class,
    e.expected_class
FROM {{ ref('fct_cliff_prediction_features') }} AS m
INNER JOIN expected AS e ON m.lap_id = e.lap_id
WHERE m.laps_until_cliff_class IS DISTINCT FROM e.expected_class
