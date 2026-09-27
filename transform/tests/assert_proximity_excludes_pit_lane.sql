-- T33 (F43, WI-15a). A car in the pit lane is never "the car ahead".
--
-- int_lap_proximity orders every crossing of a track bin by the session clock
-- and reads the previous crossing as the car ahead. Before F43 nothing removed
-- crossings made in the pit lane, so a car driving down the pit lane alongside
-- the main straight became the car ahead of whoever passed it on track: 6,355
-- training-eligible laps (4.5%) had gap_ahead_min_s set by a pit-lane car,
-- median 0.88 s against 3.32 s to the real car ahead, 2,932 of them crossing
-- the 1 s threshold (round3/r3_proximity_pitlane_car_ahead.py).
--
-- This checks the OUTPUT against the oracle, rather than trusting the model's
-- filter: for every lap with a gap_ahead_min_s, the car that set it
-- (gap_ahead_min_driver_id) must not have been inside its own stg_pits window
-- when it crossed that bin (at gap_ahead_min_crossing_s - gap_ahead_min_s),
-- and this driver must not have been inside its own window either (a pit-lane
-- bin is not a traffic bin of the pit lap). The window is the same one the
-- model uses, open-ended stops closed by the same var. A third arm makes the
-- diagnostic columns themselves non-optional: a lap with a gap must name the
-- car and the time, or the first two arms would pass on NULLs.
--
-- Scope, stated so nobody reads more into a pass than it proves: this sees the
-- bin that set each lap's MINIMUM gap only. The shares and time_within_1s are
-- computed over the same filtered crossing set, so a regression that let
-- pit-lane crossings back in would show here first (it is the minimum those
-- crossings pull down), but a pass is not a bin-by-bin proof for the shares.
-- Pit-lane race starts are outside the window set by construction: stg_pits
-- keeps stops only, and a car starting from the pit lane has no pit_in_time_s.
-- On the 2026-09-25 build that leaves 139 lap-1 laps whose closest car ahead
-- was a pit-lane starter still in the pit lane, none of them training-eligible
-- (lap 1 is never a valid lap). Known and not covered here.
{{ config(severity='error') }}

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

closest AS (
    SELECT
        lap_id,
        race_id,
        driver_id,
        lap_number,
        gap_ahead_min_s,
        gap_ahead_min_driver_id,
        gap_ahead_min_crossing_s,
        gap_ahead_min_crossing_s - gap_ahead_min_s AS ahead_crossing_s
    FROM {{ ref('int_lap_proximity') }}
    WHERE gap_ahead_min_s IS NOT NULL
)

SELECT
    'car_ahead_in_pit_lane' AS violation,
    c.lap_id,
    c.gap_ahead_min_s,
    c.gap_ahead_min_driver_id,
    c.ahead_crossing_s AS crossing_s,
    w.pit_in_time_s,
    w.pit_out_time_s
FROM closest AS c
INNER JOIN pit_windows AS w
    ON
        c.race_id = w.race_id
        AND c.gap_ahead_min_driver_id = w.driver_id
        AND c.ahead_crossing_s BETWEEN w.pit_in_time_s AND w.pit_out_time_s

UNION ALL

SELECT
    'own_crossing_in_pit_lane' AS violation,
    c.lap_id,
    c.gap_ahead_min_s,
    c.gap_ahead_min_driver_id,
    c.gap_ahead_min_crossing_s AS crossing_s,
    w.pit_in_time_s,
    w.pit_out_time_s
FROM closest AS c
INNER JOIN pit_windows AS w
    ON
        c.race_id = w.race_id
        AND c.driver_id = w.driver_id
        AND c.gap_ahead_min_crossing_s
        BETWEEN w.pit_in_time_s AND w.pit_out_time_s

UNION ALL

SELECT
    'closest_car_not_named' AS violation,
    c.lap_id,
    c.gap_ahead_min_s,
    c.gap_ahead_min_driver_id,
    c.gap_ahead_min_crossing_s AS crossing_s,
    NULL AS pit_in_time_s,
    NULL AS pit_out_time_s
FROM closest AS c
WHERE
    c.gap_ahead_min_driver_id IS NULL
    OR c.gap_ahead_min_crossing_s IS NULL
