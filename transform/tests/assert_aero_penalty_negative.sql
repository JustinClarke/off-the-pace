-- Dirty-air tax must be a penalty, never a bonus: theta_air (the fitted coefficient
-- dirty_air_tax_s = CLAMP(theta_air * dirty_air_share_lag1, 0, 5.0) applies -- see
-- int_dirty_air_tax_component.sql "Part 2") must be >= 0. A negative theta_air would
-- mean following another car makes you FASTER -- the inverted-sign failure mode this
-- test is named for.
--
-- F34: the old body checked `dirty_air_tax_s < 0` -- the PUBLISHED column, which is
-- CLAMPed to [0, 5.0] in the model itself, so it can never be negative by construction.
-- That made the test unconditionally vacuous (0 rows, always) regardless of theta_air's
-- actual sign. This re-derives the PRE-CLAMP coefficient instead: theta_air is one
-- global number per build (F5), so it can be recovered exactly from any lap whose clamp
-- did not bind (0 < dirty_air_tax_s < 5.0) by dividing back out the lagged share that
-- produced it.
--
-- Two checks, because a single negative theta_air can hide from the first one: if it is
-- negative enough (or the clamp floor catches everything), EVERY positive-exposure lap
-- reads exactly 0.0 and there is no unclamped observation left to recover theta_air
-- from -- the second check exists so that degenerate case still fails loudly instead of
-- finding nothing to check and passing by omission.
SELECT
    'negative_theta_air_recovered' AS check_name,
    CAST(theta_air AS VARCHAR) AS detail
FROM (
    SELECT DISTINCT ROUND(dirty_air_tax_s / dirty_air_intensity_lag1, 6) AS theta_air
    FROM {{ ref('int_dirty_air_tax_component') }}
    WHERE
        dirty_air_intensity_lag1 > 0
        AND dirty_air_tax_s > 0.0
        AND dirty_air_tax_s < 5.0
) AS unclamped
WHERE theta_air < 0

UNION ALL

SELECT
    'positive_exposure_uniformly_zero' AS check_name,
    CAST(COUNT(*) AS VARCHAR) AS detail
FROM {{ ref('int_dirty_air_tax_component') }}
WHERE dirty_air_intensity_lag1 > 0
HAVING
    COUNT(*) > 0
    AND COUNT(*) FILTER (WHERE dirty_air_tax_s > 0.0) = 0
