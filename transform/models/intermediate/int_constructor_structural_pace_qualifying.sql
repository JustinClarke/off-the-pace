-- Qualifying constructor pace model: Constructor pace coefficient for qualifying sessions.
-- Mirrors int_constructor_structural_pace (#6) but fit on qualifying laps only.
-- The qualifying-mode constructor coefficient reflects high-power/low-fuel trim
-- and is expected to differ from the race coefficient.
--
-- Identification: same within-constructor between-driver logic as #6.
-- Two teammates share the car common pace deviation from the session median
-- is the constructor effect.
--
-- Output grain: one row per (race_year, race_id, constructor_id).
-- PK: constructor_race_id (surrogate).

{{ config(materialized='table', tags=['simulation', 'qualifying']) }}

WITH field_pace AS (
    -- Session-level median lap time per (race, constructor, session)
    -- Used as the baseline equivalent to field_pace_curve for race sessions.
    SELECT
        race_year,
        race_id,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lap_time_s)
            FILTER (WHERE is_valid_lap = TRUE AND lap_time_s IS NOT NULL)
            AS session_median_s
    FROM {{ ref('stg_laps_qualifying') }}
    GROUP BY race_year, race_id
),

clean_quali AS (
    SELECT
        q.lap_id,
        q.race_year,
        q.race_id,
        q.driver_id,
        q.constructor_id,
        q.lap_time_s,
        -- Pace delta vs session median (analogous to pace_delta_s in race model)
        q.lap_time_s-fp.session_median_s  AS pace_delta_s
    FROM {{ ref('stg_laps_qualifying') }} q
    JOIN field_pace fp
        ON q.race_year = fp.race_year
        AND q.race_id  = fp.race_id
    WHERE q.is_valid_lap = TRUE
      AND q.lap_time_s IS NOT NULL
      AND fp.session_median_s IS NOT NULL
      -- Only best lap per driver per session to reduce noise from scrubbed laps
      AND q.is_personal_best = TRUE
),

constructor_agg AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pace_delta_s) AS median_pace_delta,
        STDDEV_POP(pace_delta_s)                                   AS stddev_pace_delta,
        COUNT(*)                                                   AS n_obs,
        COUNT(DISTINCT driver_id)                                  AS n_drivers
    FROM clean_quali
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
    )                                                              AS constructor_race_id,
    ca.race_year,
    ca.race_id,
    ca.constructor_id,
    -- Re-centred: constructor pace relative to session average.
    ca.median_pace_delta-rm.race_avg_pace_delta                  AS constructor_structural_pace_s,
    COALESCE(
        ca.stddev_pace_delta / SQRT(CAST(ca.n_obs AS DOUBLE)),
        0.0
    )                                                              AS constructor_structural_pace_se_s,
    COALESCE(
        (ca.median_pace_delta-rm.race_avg_pace_delta)
           -1.96 * (ca.stddev_pace_delta / SQRT(CAST(ca.n_obs AS DOUBLE))),
        ca.median_pace_delta-rm.race_avg_pace_delta
    )                                                              AS constructor_structural_pace_ci_low_s,
    COALESCE(
        (ca.median_pace_delta-rm.race_avg_pace_delta)
            + 1.96 * (ca.stddev_pace_delta / SQRT(CAST(ca.n_obs AS DOUBLE))),
        ca.median_pace_delta-rm.race_avg_pace_delta
    )                                                              AS constructor_structural_pace_ci_high_s,
    ca.n_obs                                                       AS panel_observations_n,
    CAST(CURRENT_TIMESTAMP AS VARCHAR)                             AS fit_timestamp
FROM constructor_agg ca
JOIN race_mean rm USING (race_year, race_id)
ORDER BY ca.race_year DESC, ca.race_id, ca.constructor_id
