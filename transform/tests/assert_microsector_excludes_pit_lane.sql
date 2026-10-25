-- DA-02 (F43 / T33 at micro-sector grain): a pit-lane crossing is nobody's car
-- ahead and not a traffic micro-sector. A valid row (invalid_reason IS NULL)
-- has neither of its own two boundaries inside its driver's pit window, and the
-- crossing of the car ahead it is priced against is not inside THAT driver's
-- pit window either. Same window rule as int_lap_proximity (stg_pits; an open
-- stop closes var('proximity_pit_window_open_s') after entry).
--
-- Vacuity guard: the panel must hold at least one pit_lane row per 1,000 rows
-- (dev 2026-10-24: 4.3 per 1,000), so a pit filter that matched nothing cannot
-- make this pass by checking an empty set.
WITH pit_windows AS (
    SELECT
        race_id,
        driver_id,
        pit_in_time_s,
        COALESCE(
            pit_out_time_s,
            pit_in_time_s + {{ var('proximity_pit_window_open_s', 120.0) }}
        ) AS pit_out_time_s
    FROM {{ ref('stg_pits') }}
    WHERE pit_in_time_s IS NOT NULL
),

valid AS (
    SELECT
        microsector_id,
        race_id,
        driver_id,
        entry_time_s,
        entry_time_s + time_s AS exit_time_s,
        ahead_driver_id,
        ahead_lap_number,
        microsector,
        entry_time_s - gap_ahead_s AS ahead_time_s
    FROM {{ ref('int_microsector_proximity') }}
    WHERE invalid_reason IS NULL
)

SELECT
    'valid row has a boundary inside its own pit window' AS issue,
    v.microsector_id AS detail
FROM valid AS v
INNER JOIN pit_windows AS w
    ON
        v.race_id = w.race_id
        AND v.driver_id = w.driver_id
        AND (
            v.entry_time_s BETWEEN w.pit_in_time_s AND w.pit_out_time_s
            OR v.exit_time_s BETWEEN w.pit_in_time_s AND w.pit_out_time_s
        )

UNION ALL

SELECT
    'car ahead was inside its own pit window' AS issue,
    v.microsector_id AS detail
FROM valid AS v
INNER JOIN pit_windows AS w
    ON
        v.race_id = w.race_id
        AND v.ahead_driver_id = w.driver_id
        AND v.ahead_time_s BETWEEN w.pit_in_time_s AND w.pit_out_time_s

UNION ALL

SELECT
    'fewer than 1 pit_lane row per 1,000 rows' AS issue,
    CAST(COUNT(*) FILTER (WHERE invalid_reason = 'pit_lane') AS VARCHAR) AS detail
FROM {{ ref('int_microsector_proximity') }}
HAVING
    COUNT(*) FILTER (WHERE invalid_reason = 'pit_lane') * 1000.0 < COUNT(*)
