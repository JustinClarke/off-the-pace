-- Weather snapshot nearest to each lap start.
-- Joins bronze weather samples (≈1Hz) to laps on lap_start_time_s using
-- ASOF semantics: for each lap we take the weather sample with the largest
-- session_time_s that is still ≤ lap_start_time_s (i.e. current conditions
-- at the moment the lap begins). Falls back to the first available sample
-- for laps that start before the first weather reading.
--
-- WET CONDITIONS (WI-05, F26). `rainfall_flag` is the wet-conditions flag
-- every consumer filters on (anomaly_class 'conditions', the clean panels,
-- the wet-race pages). It is NOT bronze Rainfall any more. Bronze Rainfall
-- alone was wrong in both directions: 2018 Spain and 2019 Monaco read 83%
-- "raining" with nobody on intermediates at 52% humidity, while both Turkish
-- GPs (2020, 2021) ran ~100% on inters/wets with Rainfall never set --
-- Rainfall means precipitation now, and a track stays wet after it stops. Tyre
-- choice alone is no fix either: it is a strategy call, not a sensor, and a
-- field can sit on inters through a dry-but-humid stretch. So the flag needs the
-- field's tyres AND a physical wet signal. Three independent measurements of the
-- same lap each cast a vote:
--   1. rainfall_flag_bronze   bronze Rainfall (precipitation sensor)
--   2. humidity_pct >= var('wet_humidity_min_pct')   (air moisture)
--   3. field_wet_tyre_share >= var('wet_field_tyre_share_min')
--      (the running field's collective call on the track: a majority, so one
--      team's gamble cannot move it)
-- RULE: a lap is wet only when the tyre vote is 1 AND (rain vote is 1 OR
-- humidity vote is 1). Tyres alone never decide wet. Consequence, by design: a
-- lap where at least half the field is on wets but Rainfall is unset and
-- humidity is below the threshold stays DRY.
-- NULL SIGNALS ABSTAIN; they are not zero votes. When the field tyre share is
-- NULL (no car on the lap has a recorded compound, e.g. 2021 round 12) the tyres
-- cannot be asked, so the lap falls back to the majority of the remaining
-- available signals (rain and humidity), with bronze Rainfall breaking a tie.
-- A NULL rain or humidity vote just does not support wet. wet_signal_votes counts
-- the signals that voted wet and wet_signal_available how many had a value.
--
-- STALE SAMPLES: weather_sample_age_s is lap start minus the weather sample time.
-- weather_sample_stale marks samples older than var('wet_stale_sample_s') (120 s).
-- It is a flag only; the vote is not changed by it. rain_signal_disagreement marks every lap
-- where bronze Rainfall and the vote differ, so the correction stays
-- auditable. The field share reads bronze compound straight from stg_laps: it
-- is a field-wide aggregate, not one car's stint alignment, so
-- stg_lap_tyre_qa's per-car quarantine does not apply to it.
{{ config(materialized='view') }}

WITH weather_raw AS (
    SELECT
        CAST(season AS INTEGER) AS race_year,
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(session_time_s AS DOUBLE) AS session_time_s,
        CAST(ambient_temp_c AS DOUBLE) AS ambient_temp_c,
        CAST(track_temp_c AS DOUBLE) AS track_temp_c,
        CAST(rainfall_flag AS BOOLEAN) AS rainfall_flag,
        CAST(humidity_pct AS DOUBLE) AS humidity_pct,
        CAST(wind_speed_ms AS DOUBLE) AS wind_speed_ms,
        CAST(wind_direction AS INTEGER) AS wind_direction,
        -- Station pressure, 100% non-null in bronze across all seasons.
        -- Staged for completeness of the weather contract, not as a model
        -- input: air density derived from it was measured as a degradation
        -- feature and rejected (-0.33% / +0.70%, inside harness noise --
        -- see ml/src/schema.py).
        CAST(pressure_hpa AS DOUBLE) AS pressure_hpa
    FROM {{ source('bronze_f1', 'raw_weather') }}
),

laps AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_start_time_s
    FROM {{ ref('stg_laps') }}
    WHERE lap_start_time_s IS NOT NULL
),

-- For each lap, pick the weather sample immediately preceding or at lap start.
-- Using a lateral/window approach: rank weather samples per race that are
-- ≤ lap_start_time_s, take the closest one (MAX session_time_s ≤ lap_start).
lap_weather AS (
    SELECT
        l.lap_id,
        l.race_year,
        l.race_id,
        l.driver_id,
        l.lap_number,
        l.lap_start_time_s,
        -- Pick weather sample closest to (and not after) lap start
        MAX(w.session_time_s) AS matched_session_time_s
    FROM laps AS l
    INNER JOIN weather_raw AS w
        ON
            l.race_year = w.race_year
            AND l.race_id = w.race_id
            AND l.lap_start_time_s >= w.session_time_s
    GROUP BY
        l.lap_id,
        l.race_year,
        l.race_id,
        l.driver_id,
        l.lap_number,
        l.lap_start_time_s
),

-- For laps before first weather sample, fall back to minimum session_time_s
lap_weather_fallback AS (
    SELECT
        l.lap_id,
        l.race_year,
        l.race_id,
        l.driver_id,
        l.lap_number,
        l.lap_start_time_s,
        MIN(w.session_time_s) AS matched_session_time_s
    FROM laps AS l
    INNER JOIN weather_raw AS w
        ON
            l.race_year = w.race_year
            AND l.race_id = w.race_id
    WHERE
        NOT EXISTS (
            SELECT 1 FROM weather_raw AS w2
            WHERE
                w2.race_year = l.race_year
                AND w2.race_id = l.race_id
                AND w2.session_time_s <= l.lap_start_time_s
        )
    GROUP BY
        l.lap_id,
        l.race_year,
        l.race_id,
        l.driver_id,
        l.lap_number,
        l.lap_start_time_s
),

combined_matches AS (
    SELECT * FROM lap_weather
    UNION ALL
    SELECT * FROM lap_weather_fallback
),

-- Share of the cars that have a recorded compound on this lap that are on
-- INTERMEDIATE or WET tyres. One row per race-lap.
field_tyres AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        AVG(
            CASE WHEN compound IN ('INTERMEDIATE', 'WET') THEN 1.0 ELSE 0.0 END
        ) AS field_wet_tyre_share
    FROM {{ ref('stg_laps') }}
    WHERE compound IS NOT NULL
    GROUP BY race_year, race_id, lap_number
),

matched AS (
    SELECT
        m.lap_id,
        m.race_year,
        m.race_id,
        m.driver_id,
        m.lap_number,
        w.session_time_s AS weather_session_time_s,
        w.ambient_temp_c,
        w.track_temp_c,
        w.rainfall_flag AS rainfall_flag_bronze,
        w.humidity_pct,
        w.wind_speed_ms,
        w.wind_direction,
        w.pressure_hpa,
        ft.field_wet_tyre_share,
        m.lap_start_time_s,
        m.lap_start_time_s - w.session_time_s AS weather_sample_age_s,
        -- One vote per signal. A NULL signal abstains (NULL, no evidence); it is
        -- never counted as a vote either way.
        CASE
            WHEN w.rainfall_flag IS NULL THEN NULL
            WHEN w.rainfall_flag THEN 1
            ELSE 0
        END AS vote_rain,
        CASE
            WHEN w.humidity_pct IS NULL THEN NULL
            WHEN w.humidity_pct >= {{ var('wet_humidity_min_pct') }} THEN 1
            ELSE 0
        END AS vote_humidity,
        CASE
            WHEN ft.field_wet_tyre_share IS NULL THEN NULL
            WHEN ft.field_wet_tyre_share >= {{ var('wet_field_tyre_share_min') }} THEN 1
            ELSE 0
        END AS vote_tyres
    FROM combined_matches AS m
    INNER JOIN weather_raw AS w
        ON
            m.race_year = w.race_year
            AND m.race_id = w.race_id
            AND m.matched_session_time_s = w.session_time_s
    LEFT JOIN field_tyres AS ft
        ON
            m.race_year = ft.race_year
            AND m.race_id = ft.race_id
            AND m.lap_number = ft.lap_number
),

voted AS (
    SELECT
        *,
        COALESCE(vote_rain, 0) + COALESCE(vote_humidity, 0) + COALESCE(vote_tyres, 0)
            AS wet_signal_votes,
        (vote_rain IS NOT NULL)::INTEGER
        + (vote_humidity IS NOT NULL)::INTEGER
        + (vote_tyres IS NOT NULL)::INTEGER AS wet_signal_available,
        weather_sample_age_s > {{ var('wet_stale_sample_s') }} AS weather_sample_stale
    FROM matched
),

-- Wet verdict (header). Tyres present: wet only with tyre vote 1 AND (rain OR
-- humidity vote 1). Tyre share NULL: majority of the available rain/humidity
-- votes, a tie broken by bronze Rainfall (the only sensor of precipitation).
decided AS (
    SELECT
        *,
        CASE
            WHEN vote_tyres IS NULL THEN
                CASE
                    WHEN 2 * wet_signal_votes > wet_signal_available THEN TRUE
                    WHEN 2 * wet_signal_votes = wet_signal_available
                        THEN COALESCE(vote_rain = 1, FALSE)
                    ELSE FALSE
                END
            ELSE vote_tyres = 1
                AND (COALESCE(vote_rain, 0) = 1 OR COALESCE(vote_humidity, 0) = 1)
        END AS wet_decision
    FROM voted
)

SELECT
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    weather_session_time_s,
    ambient_temp_c,
    track_temp_c,
    -- The wet-conditions flag (header): tyres AND (rain OR humidity).
    wet_decision AS rainfall_flag,
    humidity_pct,
    wind_speed_ms,
    wind_direction,
    pressure_hpa,
    rainfall_flag_bronze,
    field_wet_tyre_share,
    wet_signal_votes,
    wet_signal_available,
    weather_sample_age_s,
    weather_sample_stale,
    COALESCE(rainfall_flag_bronze, FALSE) <> wet_decision AS rain_signal_disagreement
FROM decided
