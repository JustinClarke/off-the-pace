-- Qualifying constructor pace model: constructor pace coefficient for
-- qualifying sessions.
-- Mirrors int_constructor_structural_pace but fit on qualifying laps only.
-- The qualifying-mode constructor coefficient reflects high-power/low-fuel trim
-- and is expected to differ from the race coefficient.
--
-- Identification: same within-constructor between-driver logic as
-- int_constructor_structural_pace.
-- Two teammates share the car   common pace deviation from the segment median
-- is the constructor effect.
--
-- Baseline is per Q1/Q2/Q3 segment, over push laps only (see
-- int_qualifying_push_laps). Both halves of that matter: the session median
-- used to be taken over every lap flagged valid, ~30% of which were cool-down
-- laps more than 107% off the session best, and it pooled three segments run on
-- a track that gains ~1s of grip between them.
--
-- Composition caveat: Q2 and Q3 are progressively self-selected fields, so a
-- fast constructor's delta to its own segment's median compresses as the field
-- narrows. Deltas are therefore re-centred within each segment before they are
-- aggregated to the constructor, which removes the level shift; the residual
-- compression is second-order and not corrected here.
--
-- Output grain: one row per (race_year, race_id, constructor_id).
-- PK: constructor_race_id (surrogate).

{{ config(materialized='table', tags=['simulation', 'qualifying']) }}

WITH push_laps AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        constructor_id,
        quali_segment,
        lap_time_s,
        driver_segment_best_s
    FROM {{ ref('int_qualifying_push_laps') }}
    WHERE is_push_lap = TRUE AND lap_time_s IS NOT NULL
),

-- Segment-level median push lap: the field-pace baseline this model measures
-- against.
segment_pace AS (
    SELECT
        race_year,
        race_id,
        quali_segment,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lap_time_s)
            AS segment_median_s
    FROM push_laps
    GROUP BY race_year, race_id, quali_segment
),

-- One observation per driver × segment: the driver's best push lap there.
clean_quali AS (
    SELECT
        p.race_year,
        p.race_id,
        p.quali_segment,
        p.driver_id,
        p.constructor_id,
        p.lap_time_s,
        p.lap_time_s - sp.segment_median_s AS raw_pace_delta_s
    FROM push_laps AS p
    INNER JOIN segment_pace AS sp
        ON
            p.race_year = sp.race_year
            AND p.race_id = sp.race_id
            AND p.quali_segment = sp.quali_segment
    WHERE
        sp.segment_median_s IS NOT NULL
        AND p.lap_time_s = p.driver_segment_best_s
),

-- Re-centre within the segment so Q1, Q2 and Q3 observations are on a common
-- scale before they are pooled per constructor.
segment_centre AS (
    SELECT
        race_year,
        race_id,
        quali_segment,
        AVG(raw_pace_delta_s) AS segment_avg_pace_delta
    FROM clean_quali
    GROUP BY race_year, race_id, quali_segment
),

centred AS (
    SELECT
        c.race_year,
        c.race_id,
        c.driver_id,
        c.constructor_id,
        c.raw_pace_delta_s - sc.segment_avg_pace_delta AS pace_delta_s
    FROM clean_quali AS c
    INNER JOIN segment_centre AS sc
        ON
            c.race_year = sc.race_year
            AND c.race_id = sc.race_id
            AND c.quali_segment = sc.quali_segment
),

constructor_agg AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pace_delta_s)
            AS median_pace_delta,
        STDDEV_POP(pace_delta_s) AS stddev_pace_delta,
        COUNT(*) AS n_obs,
        COUNT(DISTINCT driver_id) AS n_drivers
    FROM centred
    GROUP BY race_year, race_id, constructor_id
    HAVING COUNT(*) >= 1
),

race_mean AS (
    SELECT
        race_year,
        race_id,
        AVG(median_pace_delta) AS race_avg_pace_delta
    FROM constructor_agg
    GROUP BY race_year, race_id
)

SELECT
    CONCAT(
        CAST(ca.race_year AS VARCHAR), '_',
        ca.race_id, '_',
        ca.constructor_id, '_Q'
    ) AS constructor_race_id,
    ca.race_year,
    ca.race_id,
    ca.constructor_id,
    -- Re-centred: constructor pace relative to session average.
    ca.median_pace_delta
    - rm.race_avg_pace_delta AS constructor_structural_pace_s,
    COALESCE(
        ca.stddev_pace_delta / SQRT(CAST(ca.n_obs AS DOUBLE)),
        0.0
    ) AS constructor_structural_pace_se_s,
    COALESCE(
        (ca.median_pace_delta - rm.race_avg_pace_delta)
        - 1.96 * (ca.stddev_pace_delta / SQRT(CAST(ca.n_obs AS DOUBLE))),
        ca.median_pace_delta - rm.race_avg_pace_delta
    ) AS constructor_structural_pace_ci_low_s,
    COALESCE(
        (ca.median_pace_delta - rm.race_avg_pace_delta)
        + 1.96 * (ca.stddev_pace_delta / SQRT(CAST(ca.n_obs AS DOUBLE))),
        ca.median_pace_delta - rm.race_avg_pace_delta
    ) AS constructor_structural_pace_ci_high_s,
    ca.n_obs AS panel_observations_n,
    CAST(CURRENT_TIMESTAMP AS VARCHAR) AS fit_timestamp
FROM constructor_agg AS ca
INNER JOIN race_mean AS rm
    ON ca.race_year = rm.race_year AND ca.race_id = rm.race_id
ORDER BY ca.race_year DESC, ca.race_id ASC, ca.constructor_id ASC
