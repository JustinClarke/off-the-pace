-- Layer 04: Track evolution decomposition: a linear pace trend and an ambient
-- component. rubber_component_s is the historical column name; it is a linear
-- pace trend, not a measurement of rubber.
-- track_state_index = field_pace_smoothed_s (the fuel- and compound-neutral
--   field base from int_field_pace_curve).
-- rubber_component_s: OLS straight-line fit of track_state_index vs. lap_number
--   per race, with the slope capped at <= 0 (a positive raw slope is published
--   as 0.0, status CLAMPED_POSITIVE). The fit is linear, not monotone-in-shape
--   and not a rubber model: it absorbs anything that moves field pace steadily.
-- ambient_component_s: residual after the trend, fitted by simple OLS on
--   track_temp_c ONLY, within race. humidity_pct is carried as a column but is
--   not in the fit. Where a race has no usable track-temperature fit the
--   component is 0.0 (the ambient zero-fill), not a measured zero.
-- rain_state / rainfall_flag are carried from int_lap_rain_state (the weather
--   observation alone, independent of whether the lap has a pace cell here).
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

-- One weather reading per lap, from int_lap_rain_state (race-lap grain, one
-- deterministic stg_weather pick per lap, independent of the pace reference).
-- The rain state is no longer decided here: this model only carries it.
weather_per_lap AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        track_temp_c,
        humidity_pct,
        rainfall_flag,
        rain_state
    FROM {{ ref('int_lap_rain_state') }}
),

combined AS (
    SELECT
        p.race_year,
        p.race_id,
        p.lap_number,
        p.field_pace_smoothed_s,
        w.track_temp_c,
        w.humidity_pct,
        w.rainfall_flag,
        -- A missing weather reading is NO_WEATHER, never DRY.
        COALESCE(w.rain_state, 'NO_WEATHER') AS rain_state
    FROM pace AS p
    LEFT JOIN weather_per_lap AS w
        ON
            p.race_year = w.race_year
            AND p.race_id = w.race_id
            AND p.lap_number = w.lap_number
),

-- Pre-compute per-race means to avoid nested window functions.
-- Fit cells are the non-thin rows that carry a field-pace base. Every row of
-- `pace` already passed NOT low_sample_flag, and a non-thin cell always has a
-- base, so today every row is a fit cell; the NOT NULL guard makes the fit
-- population explicit rather than leaning on AVG/SUM skipping NULLs.
race_means AS (
    SELECT
        race_year,
        race_id,
        AVG(lap_number) AS mean_lap,
        AVG(field_pace_smoothed_s) AS mean_pace,
        COUNT(*) AS rubber_fit_lap_count
    FROM combined
    WHERE field_pace_smoothed_s IS NOT NULL
    GROUP BY race_year, race_id
),

-- Linear rubber fit per race: OLS slope of field_pace vs lap_number.
-- rubber_slope_raw_s_per_lap is the unclamped slope (NULL when the race has
-- fewer than 2 distinct fit laps, SUM of squares 0). The published slope
-- clamps it to <= 0 (pace only improves with rubber) with an explicit CASE:
-- a NULL raw slope stays NULL. LEAST() would ignore the NULL and return 0.0,
-- publishing a fabricated "no rubber" for a race that was never measured.
race_slope AS (
    SELECT
        c.race_year,
        c.race_id,
        rm.mean_lap,
        rm.mean_pace,
        MAX(rm.rubber_fit_lap_count) AS rubber_fit_lap_count,
        SUM(
            (c.lap_number - rm.mean_lap)
            * (c.field_pace_smoothed_s - rm.mean_pace)
        )
        / NULLIF(SUM(POWER(c.lap_number - rm.mean_lap, 2)), 0)
            AS rubber_slope_raw_s_per_lap
    FROM combined AS c
    INNER JOIN
        race_means AS rm
        ON c.race_year = rm.race_year AND c.race_id = rm.race_id
    WHERE c.field_pace_smoothed_s IS NOT NULL
    GROUP BY c.race_year, c.race_id, rm.mean_lap, rm.mean_pace
),

race_slope_published AS (
    SELECT
        *,
        CASE
            WHEN rubber_slope_raw_s_per_lap IS NULL THEN NULL
            ELSE LEAST(rubber_slope_raw_s_per_lap, 0.0)
        END AS rubber_slope_s_per_lap
    FROM race_slope
),

-- Grain stays one row per combined (race, lap): LEFT JOIN so a lap is never
-- dropped because its race has no fit. Components are NULL, never 0.0, where
-- the slope or the lap's own base is missing.
with_rubber AS (
    SELECT
        c.*,
        rs.rubber_slope_raw_s_per_lap,
        rs.rubber_slope_s_per_lap,
        COALESCE(rs.rubber_fit_lap_count, 0) AS rubber_fit_lap_count,
        rs.mean_lap,
        rs.mean_pace,
        CASE
            WHEN c.field_pace_smoothed_s IS NULL THEN 'NO_FIELD_BASE'
            WHEN rs.rubber_slope_raw_s_per_lap IS NULL THEN 'INSUFFICIENT_LAPS'
            WHEN rs.rubber_slope_raw_s_per_lap > 0 THEN 'CLAMPED_POSITIVE'
            ELSE 'MEASURED'
        END AS rubber_status,
        -- rubber_component: linear trend removed from mean (monotone
        -- decreasing)
        CASE
            WHEN c.field_pace_smoothed_s IS NULL THEN NULL
            ELSE rs.rubber_slope_s_per_lap * (c.lap_number - rs.mean_lap)
        END AS rubber_component_s,
        CASE
            WHEN c.field_pace_smoothed_s IS NULL THEN NULL
            ELSE
                c.field_pace_smoothed_s
                - (
                    rs.mean_pace
                    + rs.rubber_slope_s_per_lap * (c.lap_number - rs.mean_lap)
                )
        END AS track_state_residual_s
    FROM combined AS c
    LEFT JOIN race_slope_published AS rs
        ON c.race_year = rs.race_year AND c.race_id = rs.race_id
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
        SUM((r.track_temp_c - tm.mean_track_temp) * r.track_state_residual_s)
        / NULLIF(SUM(POWER(r.track_temp_c - tm.mean_track_temp, 2)), 0)
            AS ambient_slope_s_per_c
    FROM with_rubber AS r
    INNER JOIN
        temp_means AS tm
        ON r.race_year = tm.race_year AND r.race_id = tm.race_id
    WHERE r.track_temp_c IS NOT NULL
    GROUP BY r.race_year, r.race_id, tm.mean_track_temp
)

SELECT
    r.race_year,
    r.race_id,
    r.lap_number,
    r.field_pace_smoothed_s AS track_state_index_s,
    r.rubber_component_s,
    -- ambient_component: weather-correlated fraction of the residual
    COALESCE(
        a.ambient_slope_s_per_c * (r.track_temp_c - a.mean_track_temp),
        0.0
    ) AS ambient_component_s,
    -- pure residual after both components removed (unexplained variation)
    r.track_state_residual_s
    - COALESCE(
        a.ambient_slope_s_per_c * (r.track_temp_c - a.mean_track_temp), 0.0
    )
        AS unexplained_residual_s,
    r.track_temp_c,
    r.humidity_pct,
    r.rainfall_flag,
    r.rain_state,
    r.rubber_slope_raw_s_per_lap,
    r.rubber_slope_s_per_lap,
    r.rubber_fit_lap_count,
    r.rubber_status
FROM with_rubber AS r
LEFT JOIN ambient_slope AS a
    ON r.race_year = a.race_year AND r.race_id = a.race_id
ORDER BY r.race_year, r.race_id, r.lap_number
