-- laps_until_cliff_class must partition the remaining-stint horizon exactly as
-- its class names read. Prior to 2026-08 it did not: the label tested a fixed
-- set of LEAD offsets ({1,2} -> 0_to_2, {3,5} -> 3_to_5, {6} -> 6_plus), so
-- offset 4 was never tested and nothing past 6 was. That made `6_plus` mean
-- "exactly 6" and pushed every cliff 4 or 7+ laps out into 'none_in_stint' --
-- 9,405 training rows on the wrong side of a class boundary, and a `6_plus`
-- class the classifier could not learn (final-fold F1 0.058).
--
-- The scan below is an independent re-derivation of the first crossing lap. It
-- does not reuse the mart's CTEs, so it fails if the mart's definition drifts
-- back to a fixed offset set, changes the 1.0s threshold, or drops the
-- k x drift detrending.
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

expected AS (
    SELECT
        r.lap_id,
        fc.laps_until_cliff,
        CASE
            WHEN h.last_lap_in_stint <= r.lap_in_stint THEN NULL
            WHEN fc.laps_until_cliff <= 2 THEN '0_to_2'
            WHEN fc.laps_until_cliff <= 5 THEN '3_to_5'
            WHEN fc.laps_until_cliff IS NOT NULL THEN '6_plus'
            ELSE 'none_in_stint'
        END AS expected_class
    FROM residuals AS r
    INNER JOIN horizon AS h ON r.stint_id = h.stint_id
    LEFT JOIN first_crossing AS fc ON r.lap_id = fc.lap_id
)

SELECT
    m.lap_id,
    e.laps_until_cliff,
    m.laps_until_cliff_class AS actual_class,
    e.expected_class
FROM {{ ref('fct_cliff_prediction_features') }} AS m
INNER JOIN expected AS e ON m.lap_id = e.lap_id
WHERE m.laps_until_cliff_class IS DISTINCT FROM e.expected_class
