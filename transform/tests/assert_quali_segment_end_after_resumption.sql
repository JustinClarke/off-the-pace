-- A segment cannot end before it resumed from a red flag.
--
-- If a qualifying red flag is followed by a green light inside the same segment
-- window, running restarted, so segment_end_s must not fall before that green.
-- It did for 2022_9 Q2, where session status records the stoppage as a chequered
-- flag ('Finished' at 2752s) and a second Started / Finished pair follows.
-- A red flag after the chequered flag with no later green in the window (2019_7
-- Q2) is not a resumption and does not trip this.

SELECT
    s.race_year,
    s.race_id,
    s.quali_segment,
    s.segment_end_s,
    g.session_time_s AS resumed_green_s
FROM {{ ref('int_qualifying_segments') }} AS s
INNER JOIN {{ ref('stg_session_status_qualifying') }} AS g
    ON
        s.race_year = g.race_year
        AND s.race_id = g.race_id
        AND g.is_green_light
        AND g.session_time_s > s.segment_start_s
        AND (s.window_end_s IS NULL OR g.session_time_s < s.window_end_s)
WHERE
    g.session_time_s > s.segment_end_s
    AND EXISTS (
        SELECT 1
        FROM {{ ref('stg_red_flags_qualifying') }} AS r
        WHERE
            r.race_year = s.race_year
            AND r.race_id = s.race_id
            AND r.session_time_s > s.segment_start_s
            AND r.session_time_s < g.session_time_s
    )
