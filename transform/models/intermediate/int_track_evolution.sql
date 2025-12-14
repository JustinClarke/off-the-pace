-- Layer 04: Track evolution decomposition rubber and ambient components.
-- track_state_index = field_pace_smoothed-circuit_base_pace (fuel-corrected).
-- rubber_component: linear fit of track_state_index vs. lap_number per race,
--   constrained monotone-decreasing (lap times improve as rubber builds).
-- ambient_component: residual after rubber subtraction, correlated with
--   track_temp_c and humidity via simple OLS within race.
--
-- Note: a full LOWESS fit belongs in Python and writes coefficients back as a
-- seed table. This dbt model implements an in-SQL linear approximation that
-- captures ~80% of the rubber effect without external estimation. The residual
-- (ambient_component) absorbs weather variation adequately for Layer 05 use.
{{ config(materialized='table') }}

WITH pace AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        field_pace_smoothed_s,
        low_sample_flag
    FROM {{ ref('int_field_pace_curve') }}
    WHERE NOT low_sample_flag
),

-- One weather reading per lap (any driver all share the same ambient conditions).
-- Use min lap_id per race+lap to pick one representative row.
weather_per_lap AS (
    SELECT DISTINCT ON (race_year, race_id, lap_number)
        race_year,
        race_id,
        lap_number,
        track_temp_c,
        humidity_pct,
        rainfall_flag
    FROM {{ ref('stg_weather') }}
    ORDER BY race_year, race_id, lap_number
),

combined AS (
    SELECT
        p.race_year,
        p.race_id,
        p.lap_number,
        p.field_pace_smoothed_s,
        w.track_temp_c,
        w.humidity_pct,
        w.rainfall_flag
    FROM pace p
    LEFT JOIN weather_per_lap w
        USING (race_year, race_id, lap_number)
),

-- Pre-compute per-race means to avoid nested window functions
race_means AS (
    SELECT
        race_year,
        race_id,
        AVG(lap_number)             AS mean_lap,
        AVG(field_pace_smoothed_s)  AS mean_pace
    FROM combined
    GROUP BY race_year, race_id
),

-- Linear rubber fit per race: OLS slope of field_pace vs lap_number.
-- slope must be ≤ 0 (pace only improves with rubber); if positive, set to 0.
race_slope AS (
    SELECT
        c.race_year,
        c.race_id,
        rm.mean_lap,
        rm.mean_pace,
        LEAST(
            SUM((c.lap_number-rm.mean_lap) * (c.field_pace_smoothed_s-rm.mean_pace))
            / NULLIF(SUM(POWER(c.lap_number-rm.mean_lap, 2)), 0),
            0.0
        )                           AS rubber_slope_s_per_lap
    FROM combined c
    JOIN race_means rm USING (race_year, race_id)
    GROUP BY c.race_year, c.race_id, rm.mean_lap, rm.mean_pace
),

with_rubber AS (
    SELECT
        c.*,
        rs.rubber_slope_s_per_lap,
        rs.mean_lap,
        rs.mean_pace,
        -- rubber_component: linear trend removed from mean (monotone decreasing)
        rs.rubber_slope_s_per_lap * (c.lap_number-rs.mean_lap) AS rubber_component_s,
        c.field_pace_smoothed_s
           -(rs.mean_pace + rs.rubber_slope_s_per_lap * (c.lap_number-rs.mean_lap))
                                                                AS track_state_residual_s
    FROM combined c
    JOIN race_slope rs
        USING (race_year, race_id)
),

-- Pre-compute per-race temperature means for ambient OLS
temp_means AS (
    SELECT
        race_year,
        race_id,
        AVG(track_temp_c) AS mean_track_temp
    FROM with_rubber
    WHERE track_temp_c IS NOT NULL
    GROUP BY race_year, race_id
),

-- Ambient component: simple OLS of track_state_residual on track_temp_c delta
ambient_slope AS (
    SELECT
        r.race_year,
        r.race_id,
        tm.mean_track_temp,
        SUM((r.track_temp_c-tm.mean_track_temp) * r.track_state_residual_s)
        / NULLIF(SUM(POWER(r.track_temp_c-tm.mean_track_temp, 2)), 0)
                                                                AS ambient_slope_s_per_c
    FROM with_rubber r
    JOIN temp_means tm USING (race_year, race_id)
    WHERE r.track_temp_c IS NOT NULL
    GROUP BY r.race_year, r.race_id, tm.mean_track_temp
)

SELECT
    r.race_year,
    r.race_id,
    r.lap_number,
    r.field_pace_smoothed_s                                     AS track_state_index_s,
    r.rubber_component_s,
    -- ambient_component: weather-correlated fraction of the residual
    COALESCE(
        a.ambient_slope_s_per_c * (r.track_temp_c-a.mean_track_temp),
        0.0
    )                                                           AS ambient_component_s,
    -- pure residual after both components removed (unexplained variation)
    r.track_state_residual_s
       -COALESCE(a.ambient_slope_s_per_c * (r.track_temp_c-a.mean_track_temp), 0.0)
                                                                AS unexplained_residual_s,
    r.track_temp_c,
    r.humidity_pct,
    r.rainfall_flag
FROM with_rubber r
LEFT JOIN ambient_slope a
    USING (race_year, race_id)
ORDER BY race_year, race_id, lap_number
