-- Push-lap gate for qualifying, at lap grain.
--
-- stg_laps_qualifying.is_valid_lap removes out-laps and in-laps (both carry a
-- pit time), deleted laps and neutralised laps. It cannot remove the cool-down
-- lap *between* two push laps: a qualifying run is out-lap → push → cool-down →
-- push → in-lap, and the middle lap has no pit time, is not deleted and is
-- flagged accurate, so it passes every condition. Measured over the seven
-- staged seasons, ~30% of the laps the model treated as valid were more than
-- 107% off the session best   the classic cut for "this was not a serious lap".
-- Everything downstream (the field-pace baseline, the constructor coefficient,
-- the skill residual) was fit through that.
--
-- The gate is the 107% rule applied per segment rather than per session, which
-- is why this model sits on int_qualifying_segments: Q3 is both a faster track
-- and a self-selected top-10 field, so a session-wide cut is the wrong
-- reference for a Q1 lap. A driver's own best lap in a segment is always a push
-- lap, so no one with a valid lap drops out of the decomposition.
--
-- Output grain: lap_id   one row per qualifying lap (every lap, gated or not,
-- so consumers can filter rather than lose the row set).
-- PK: lap_id (FK to stg_laps_qualifying).

{{ config(materialized='table', tags=['simulation', 'qualifying']) }}

WITH laps AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        constructor_id,
        lap_number,
        lap_start_time_s,
        lap_time_s,
        tyre_life,
        compound,
        is_personal_best,
        is_valid_lap
    FROM {{ ref('stg_laps_qualifying') }}
),

segments AS (
    SELECT
        race_year,
        race_id,
        quali_segment,
        segment_index,
        window_start_s,
        window_end_s
    FROM {{ ref('int_qualifying_segments') }}
),

-- Window join on the session clock. A lap with no lap_start_time_s, or a
-- session with no status timeline in bronze, falls through to 'Q' = the whole
-- session unsegmented, which is exactly the pre-segment behaviour rather than a
-- dropped row.
assigned AS (
    SELECT
        l.*,
        COALESCE(s.quali_segment, 'Q') AS quali_segment,
        s.segment_index
    FROM laps AS l
    LEFT JOIN segments AS s
        ON
            l.race_year = s.race_year
            AND l.race_id = s.race_id
            AND (
                s.window_start_s IS NULL
                OR l.lap_start_time_s >= s.window_start_s
            )
            AND (
                s.window_end_s IS NULL
                OR l.lap_start_time_s < s.window_end_s
            )
),

segment_best AS (
    SELECT
        race_year,
        race_id,
        quali_segment,
        MIN(lap_time_s) FILTER (
            WHERE is_valid_lap = TRUE AND lap_time_s IS NOT NULL
        ) AS segment_best_s
    FROM assigned
    GROUP BY race_year, race_id, quali_segment
),

driver_segment_best AS (
    SELECT
        race_year,
        race_id,
        quali_segment,
        driver_id,
        MIN(lap_time_s) FILTER (
            WHERE is_valid_lap = TRUE AND lap_time_s IS NOT NULL
        ) AS driver_segment_best_s
    FROM assigned
    GROUP BY race_year, race_id, quali_segment, driver_id
)

SELECT
    a.lap_id,
    a.race_year,
    a.race_id,
    a.driver_id,
    a.constructor_id,
    a.lap_number,
    a.lap_start_time_s,
    a.lap_time_s,
    a.tyre_life,
    a.compound,
    a.is_personal_best,
    a.is_valid_lap,
    a.quali_segment,
    a.segment_index,
    sb.segment_best_s,
    db.driver_segment_best_s,
    a.lap_time_s / NULLIF(sb.segment_best_s, 0) AS ratio_to_segment_best,
    -- The gate. Within 107% of the segment's best lap, or the driver's own best
    -- effort in that segment (which keeps every driver represented even in a
    -- wet Q1 where the field spread exceeds the cut).
    COALESCE(
        a.is_valid_lap
        AND a.lap_time_s IS NOT NULL
        AND (
            a.lap_time_s
            <= {{ var('quali_push_lap_ratio') }} * sb.segment_best_s
            OR a.lap_time_s = db.driver_segment_best_s
        ),
        FALSE
    ) AS is_push_lap
FROM assigned AS a
LEFT JOIN segment_best AS sb
    ON
        a.race_year = sb.race_year
        AND a.race_id = sb.race_id
        AND a.quali_segment = sb.quali_segment
LEFT JOIN driver_segment_best AS db
    ON
        a.race_year = db.race_year
        AND a.race_id = db.race_id
        AND a.quali_segment = db.quali_segment
        AND a.driver_id = db.driver_id
ORDER BY a.race_year, a.race_id, a.driver_id, a.lap_number
