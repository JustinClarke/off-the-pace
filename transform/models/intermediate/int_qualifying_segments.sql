-- Q1 / Q2 / Q3 windows, recovered by anchoring the session-status timeline to
-- the official per-driver segment times.
--
-- The qualifying lap table has no segment column   FastF1 reports one flat lap
-- set per Q session   so every baseline downstream of it was, until this model,
-- computed per race rather than per segment. That pools a Q1 first effort with
-- a Q3 final lap across ~1s of track evolution and a self-selected top-10
-- field, which is what made the session median an unusable field-pace baseline.
--
-- Two sources, because neither is sufficient alone:
--
--  * stg_session_status_qualifying gives the green lights, but not which of
--    them opens a segment. A red flag inside Q1/Q2/Q3 is written 'Aborted' …
--    'Started', so greens outnumber segments; and counting the 'Finished'
--    events instead fails on the sessions whose final segment was red-flagged
--    at its end, where the chequered flag never falls.
--  * stg_results_qualifying gives each driver's official best lap in each
--    segment. Matched back to the lap that set it, those are anchor laps with
--    known session times   they cannot say where a segment *starts*, but they
--    bracket it exactly.
--
-- So: the anchors bracket where segment k can open   after segment k−1's last
-- anchor lap, at or before segment k's first. Inside that bracket the chequered
-- flag decides when there is one (segment k opens at the first green after it),
-- and the last green in the bracket decides when there is not, which is the
-- case for a segment that was red-flagged to a close.
--
-- Lap assignment uses window_start_s / window_end_s rather than the green
-- window: a lap that starts after the chequered flag of its segment (the in-lap
-- every driver runs) still belongs to that segment, so each window runs from
-- its own green light up to the *next* segment's green light. Q1's window is
-- open at the bottom so pre-session installation laps land in Q1.
--
-- A session with no qualifying results in bronze produces no rows here at all,
-- and int_qualifying_push_laps then falls back to treating it as one
-- unsegmented session   the pre-segment behaviour, not a dropped row set.
--
-- Output grain: one row per (race_year, race_id, quali_segment).
-- PK: quali_segment_id.

{{ config(materialized='table', tags=['simulation', 'qualifying']) }}

WITH status_events AS (
    SELECT
        race_year,
        race_id,
        session_time_s,
        LOWER(status) AS status,
        is_red_flag_stop,
        is_green_light
    FROM {{ ref('stg_session_status_qualifying') }}
),

greens AS (
    SELECT
        race_year,
        race_id,
        session_time_s AS green_s
    FROM status_events
    WHERE is_green_light
),

-- Official segment bests, one row per driver × segment they set a time in.
official_bests AS (
    SELECT
        race_year, race_id, driver_id, 1 AS segment_index,
        q1_time_s AS official_best_s
    FROM {{ ref('stg_results_qualifying') }}
    WHERE q1_time_s IS NOT NULL
    UNION ALL
    SELECT
        race_year, race_id, driver_id, 2 AS segment_index,
        q2_time_s AS official_best_s
    FROM {{ ref('stg_results_qualifying') }}
    WHERE q2_time_s IS NOT NULL
    UNION ALL
    SELECT
        race_year, race_id, driver_id, 3 AS segment_index,
        q3_time_s AS official_best_s
    FROM {{ ref('stg_results_qualifying') }}
    WHERE q3_time_s IS NOT NULL
),

-- Laps that could have set an official time. Deleted laps are excluded: a
-- deleted lap can be faster than the driver's official best and would then
-- match the wrong segment.
candidate_laps AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_start_time_s,
        lap_time_s
    FROM {{ ref('stg_laps_qualifying') }}
    WHERE
        lap_start_time_s IS NOT NULL
        AND lap_time_s IS NOT NULL
        AND NOT is_deleted
        AND NOT is_pit_lap
),

-- Match each official time back to the lap that set it, one segment at a time
-- and in order. Both sides come from the same millisecond-precision source, so
-- the tolerance only absorbs the nanosecond→second float cast.
--
-- The chain matters: a driver can set the identical time in two segments (HAM's
-- Q2 and Q3 bests in 2018 Rd1 are both 82.051s), and matching each segment
-- independently then anchors Q2 to a Q3 lap and drags the whole boundary with
-- it. Requiring each anchor to fall after the previous segment's resolves it,
-- because a lap inside segment k-1 that beats its own official best would
-- contradict the official result.
q1_anchor AS (
    SELECT
        o.race_year,
        o.race_id,
        o.driver_id,
        MIN(l.lap_start_time_s) AS anchor_s
    FROM official_bests AS o
    INNER JOIN candidate_laps AS l
        ON
            o.race_year = l.race_year
            AND o.race_id = l.race_id
            AND o.driver_id = l.driver_id
            AND ABS(l.lap_time_s - o.official_best_s) < 0.0005
    WHERE o.segment_index = 1
    GROUP BY o.race_year, o.race_id, o.driver_id
),

q2_anchor AS (
    SELECT
        o.race_year,
        o.race_id,
        o.driver_id,
        MIN(l.lap_start_time_s) AS anchor_s
    FROM official_bests AS o
    INNER JOIN candidate_laps AS l
        ON
            o.race_year = l.race_year
            AND o.race_id = l.race_id
            AND o.driver_id = l.driver_id
            AND ABS(l.lap_time_s - o.official_best_s) < 0.0005
    LEFT JOIN q1_anchor AS a1
        ON
            o.race_year = a1.race_year
            AND o.race_id = a1.race_id
            AND o.driver_id = a1.driver_id
    WHERE
        o.segment_index = 2
        AND l.lap_start_time_s > COALESCE(a1.anchor_s, -1.0)
    GROUP BY o.race_year, o.race_id, o.driver_id
),

q3_anchor AS (
    SELECT
        o.race_year,
        o.race_id,
        o.driver_id,
        MIN(l.lap_start_time_s) AS anchor_s
    FROM official_bests AS o
    INNER JOIN candidate_laps AS l
        ON
            o.race_year = l.race_year
            AND o.race_id = l.race_id
            AND o.driver_id = l.driver_id
            AND ABS(l.lap_time_s - o.official_best_s) < 0.0005
    LEFT JOIN q2_anchor AS a2
        ON
            o.race_year = a2.race_year
            AND o.race_id = a2.race_id
            AND o.driver_id = a2.driver_id
    WHERE
        o.segment_index = 3
        AND l.lap_start_time_s > COALESCE(a2.anchor_s, -1.0)
    GROUP BY o.race_year, o.race_id, o.driver_id
),

anchor_laps AS (
    SELECT race_year, race_id, 1 AS segment_index, anchor_s AS lap_start_time_s
    FROM q1_anchor
    UNION ALL
    SELECT race_year, race_id, 2 AS segment_index, anchor_s AS lap_start_time_s
    FROM q2_anchor
    UNION ALL
    SELECT race_year, race_id, 3 AS segment_index, anchor_s AS lap_start_time_s
    FROM q3_anchor
),

anchors AS (
    SELECT
        race_year,
        race_id,
        segment_index,
        MIN(lap_start_time_s) AS first_anchor_s,
        MAX(lap_start_time_s) AS last_anchor_s,
        COUNT(*) AS anchor_lap_n
    FROM anchor_laps
    GROUP BY race_year, race_id, segment_index
),

-- Each segment carries the previous segment's last anchor as its lower bound.
bracketed AS (
    SELECT
        a.race_year,
        a.race_id,
        a.segment_index,
        a.first_anchor_s,
        a.last_anchor_s,
        a.anchor_lap_n,
        prev.first_anchor_s AS prev_first_anchor_s,
        prev.last_anchor_s AS prev_last_anchor_s
    FROM anchors AS a
    LEFT JOIN anchors AS prev
        ON
            a.race_year = prev.race_year
            AND a.race_id = prev.race_id
            AND prev.segment_index = a.segment_index - 1
),

-- Resolve each segment's green light inside the bracket its anchors define.
--
-- Inside that bracket a chequered flag, if there is one, is decisive: the last
-- chequered flag falling between the previous segment's first anchor lap and
-- this one's closed the previous segment, so this segment opens at the first
-- green after it. Both ends of that search earn their place. Taking the *last*
-- such flag matters where a segment carries more than one   2022 Montreal
-- writes Q2's interruption as a second Started/Finished pair rather than an
-- Aborted, so its Q2 spans two chequered flags. Bounding the search below at
-- the previous segment's first anchor matters where the previous segment never
-- got a chequered flag at all   2021 Spa, whose Q2 was red-flagged to a close;
-- without that bound the search reaches back to Q1's flag and opens Q3 at Q2's
-- green.
-- With no chequered flag in the bracket, the last green inside it is the
-- opening.
bracket_chequered AS (
    SELECT
        b.race_year,
        b.race_id,
        b.segment_index,
        MAX(f.session_time_s) AS chequered_s
    FROM bracketed AS b
    LEFT JOIN status_events AS f
        ON
            b.race_year = f.race_year
            AND b.race_id = f.race_id
            AND f.status = 'finished'
            AND f.session_time_s > COALESCE(b.prev_first_anchor_s, -1.0)
            AND b.first_anchor_s >= f.session_time_s
    GROUP BY b.race_year, b.race_id, b.segment_index
),

green_choice AS (
    SELECT
        b.race_year,
        b.race_id,
        b.segment_index,
        -- Q1: the session's first green light.
        MIN(g.green_s) AS first_green_s,
        -- Q2/Q3, chequered branch: the first green after that flag.
        MIN(g.green_s) FILTER (
            WHERE
            g.green_s > c.chequered_s
            AND g.green_s <= b.first_anchor_s
        ) AS green_after_chequered_s,
        -- Q2/Q3, no-chequered branch: the last green inside the bracket.
        MAX(g.green_s) FILTER (
            WHERE
            g.green_s <= b.first_anchor_s
            AND g.green_s > COALESCE(b.prev_last_anchor_s, -1.0)
        ) AS last_green_in_bracket_s
    FROM bracketed AS b
    LEFT JOIN bracket_chequered AS c
        ON
            b.race_year = c.race_year
            AND b.race_id = c.race_id
            AND b.segment_index = c.segment_index
    LEFT JOIN greens AS g
        ON b.race_year = g.race_year AND b.race_id = g.race_id
    GROUP BY b.race_year, b.race_id, b.segment_index
),

resolved AS (
    SELECT
        b.*,
        -- The last fallback   no green light resolved at all, or no status
        -- timeline for the session   is the segment's own first anchor lap,
        -- which is the latest the segment can possibly have opened.
        CASE
            WHEN b.segment_index = 1
                THEN COALESCE(gc.first_green_s, b.first_anchor_s)
            ELSE COALESCE(
                gc.green_after_chequered_s,
                gc.last_green_in_bracket_s,
                b.first_anchor_s
            )
        END AS segment_start_s
    FROM bracketed AS b
    INNER JOIN green_choice AS gc
        ON
            b.race_year = gc.race_year
            AND b.race_id = gc.race_id
            AND b.segment_index = gc.segment_index
),

windowed AS (
    SELECT
        *,
        LEAD(segment_start_s) OVER (
            PARTITION BY race_year, race_id ORDER BY segment_index
        ) AS next_segment_start_s
    FROM resolved
),

-- Terminal event of each segment, looked up inside its own window: the
-- chequered flag when there is one, otherwise the unresumed red flag that ended
-- it, otherwise the session's 'Finalised'.
with_end AS (
    SELECT
        w.*,
        (
            SELECT
                COALESCE(
                    MIN(e.session_time_s) FILTER (WHERE e.status = 'finished'),
                    MAX(e.session_time_s) FILTER (WHERE e.status = 'aborted'),
                    MIN(e.session_time_s) FILTER (WHERE e.status = 'finalised')
                )
            FROM status_events AS e
            WHERE
                e.race_year = w.race_year
                AND e.race_id = w.race_id
                AND e.session_time_s > w.segment_start_s
                AND (
                    w.next_segment_start_s IS NULL
                    OR e.session_time_s < w.next_segment_start_s
                )
        ) AS segment_end_s,
        (
            SELECT COUNT(*)
            FROM status_events AS e
            WHERE
                e.race_year = w.race_year
                AND e.race_id = w.race_id
                AND e.is_red_flag_stop
                AND e.session_time_s > w.segment_start_s
                AND (
                    w.next_segment_start_s IS NULL
                    OR e.session_time_s < w.next_segment_start_s
                )
        ) AS stoppage_n
    FROM windowed AS w
)

SELECT
    CONCAT(
        CAST(race_id AS VARCHAR), '_Q', CAST(segment_index AS VARCHAR)
    ) AS quali_segment_id,
    race_year,
    race_id,
    CONCAT('Q', CAST(segment_index AS VARCHAR)) AS quali_segment,
    segment_index,
    segment_start_s,
    segment_end_s,
    -- Wall-clock span, stoppages included. Nominally 1080s (Q1), 900s (Q2),
    -- 720s (Q3); longer whenever a red flag suspended the clock, and longer
    -- again for a segment that ended under a red flag, whose terminal event is
    -- the session's 'Finalised' rather than a chequered flag.
    segment_end_s - segment_start_s AS segment_span_s,
    stoppage_n,
    anchor_lap_n,
    -- Lap-assignment window. Open at the bottom for Q1 (installation laps run
    -- before the green light) and at the top for Q3.
    CASE WHEN segment_index > 1 THEN segment_start_s END AS window_start_s,
    next_segment_start_s AS window_end_s
FROM with_end
ORDER BY race_year, race_id, segment_index
