-- DA-02: int_microsector_proximity must agree with the FIA's own traffic label,
-- the micro-sector twin of assert_proximity_agrees_with_blue_flags (read that
-- header for why a blue flag is the one independent traffic label, how race
-- control's clock is matched to FastF1's, and why the match is on the driver's
-- OWN lap). The matching CTEs below are that test's, unchanged.
--
-- THE STATISTIC. A car being lapped has the lapping car behind it, so on its
-- blue-flagged lap some micro-sector entry should have a car within 1 s
-- behind. Per timing-valid lap (at least 15 of the 20 micro-sectors have a
-- usable time, which leaves out neutralised laps by construction), the lap is
-- 'clear behind' when NO micro-sector entry has gap_behind_s < 1.0 s (a NULL
-- gap_behind_s is no car). The share of clear-behind laps must be smaller on
-- blue laps than on the rest: blue <= 0.85 x other, per season, as in the lap
-- test. The factor is slack, not a target; the failure guarded against is the
-- boundary crossing clock losing its common origin, which sends the ratio to
-- about 1.0. Blue laps that are neutralised in int_lap_proximity are left out
-- (both arms collapse under a safety car); blue laps that are not neutralised
-- but have no usable micro-sector data (a yellow, a lap-1 or post-restart lap,
-- a pit lap, or 2018's two races with no telemetry) count as lost, and a season
-- fails if more than 15% of its blue-flag messages are lost. The lap test's 5%
-- does not carry over: the micro-sector panel drops every non-green interval,
-- so it legitimately loses more (measured on dev 2026-10-24: 2.5-11.0%, worst
-- 2018, which also holds the 28 telemetry-less blue laps). n_raw >= 100, so the
-- test is vacuous on the three-race CI fixture exactly as the lap test is.
-- Measured blue/other clear-behind ratio, 2018-2025: 0.19-0.28 against the 0.85
-- bar.
WITH blue_msgs AS (
    SELECT
        race_year,
        race_id,
        message_index,
        driver_id,
        message_time_s
    FROM {{ ref('stg_race_control') }}
    WHERE is_blue_flag_event
),

driver_laps AS (
    SELECT
        race_id,
        driver_id,
        lap_number,
        lap_start_time_s AS lap_start_s,
        COALESCE(
            LEAD(lap_start_time_s) OVER (
                PARTITION BY race_id, driver_id ORDER BY lap_number
            ),
            lap_start_time_s + lap_time_s
        ) AS lap_end_s
    FROM {{ ref('stg_laps') }}
    WHERE lap_start_time_s IS NOT NULL
),

-- The leader's lap L window: race control's lap counter.
leader_laps AS (
    SELECT
        race_id,
        lap_number,
        MIN(lap_start_time_s) AS leader_start_s
    FROM {{ ref('stg_laps') }}
    GROUP BY 1, 2
),

-- Each message admits a band of clock offsets: those that put it inside the
-- leader's window for its lap.
offset_bands AS (
    SELECT
        rc.race_id,
        rc.message_time_s - nxt.leader_start_s - 1.0 AS offset_lo,
        rc.message_time_s - cur.leader_start_s + 1.0 AS offset_hi
    FROM {{ ref('stg_race_control') }} AS rc
    INNER JOIN leader_laps AS cur
        ON rc.race_id = cur.race_id AND rc.lap_number = cur.lap_number
    INNER JOIN leader_laps AS nxt
        ON rc.race_id = nxt.race_id AND rc.lap_number + 1 = nxt.lap_number
    WHERE rc.message_time_s IS NOT NULL
),

offset_candidates AS (
    SELECT
        c.race_id,
        c.candidate_s,
        COUNT(*) FILTER (
            WHERE c.candidate_s BETWEEN b.offset_lo AND b.offset_hi
        ) AS n_consistent
    FROM (
        SELECT race_id, offset_lo AS candidate_s FROM offset_bands
        UNION
        SELECT race_id, offset_hi AS candidate_s FROM offset_bands
    ) AS c
    INNER JOIN offset_bands AS b ON c.race_id = b.race_id
    GROUP BY 1, 2
),

-- Midpoint of the best-supported offsets: deterministic, no tie-break needed.
best_support AS (
    SELECT
        race_id,
        MAX(n_consistent) AS max_consistent
    FROM offset_candidates
    GROUP BY 1
),

race_offset AS (
    SELECT
        c.race_id,
        (MIN(c.candidate_s) + MAX(c.candidate_s)) / 2.0 AS offset_s
    FROM offset_candidates AS c
    INNER JOIN best_support AS b
        ON
            c.race_id = b.race_id
            AND c.n_consistent = b.max_consistent
    GROUP BY 1
),

-- One row per message, with the driver's own lap (NULL = unmatched).
msg_matched AS (
    SELECT
        m.race_year,
        m.race_id,
        m.message_index,
        m.driver_id,
        MAX(dl.lap_number) AS own_lap
    FROM blue_msgs AS m
    LEFT JOIN race_offset AS o ON m.race_id = o.race_id
    LEFT JOIN driver_laps AS dl
        ON
            m.race_id = dl.race_id
            AND m.driver_id = dl.driver_id
            AND m.message_time_s - o.offset_s >= dl.lap_start_s
            AND m.message_time_s - o.offset_s < dl.lap_end_s
    GROUP BY 1, 2, 3, 4
),

blue_laps AS (
    SELECT DISTINCT
        race_year,
        race_id,
        driver_id,
        own_lap AS lap_number
    FROM msg_matched
    WHERE own_lap IS NOT NULL
),

usable_laps AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        COALESCE(MIN(gap_behind_s) >= 1.0, TRUE) AS no_car_within_1s_behind
    FROM {{ ref('int_microsector_proximity') }}
    WHERE timing_invalid_reason IS NULL
    GROUP BY race_year, race_id, driver_id, lap_number
    HAVING COUNT(*) >= 15
),

blue_lap_status AS (
    SELECT
        b.race_year,
        COUNT(*) AS n_blue_laps,
        COUNT(*) FILTER (WHERE p.is_neutralised_lap) AS n_neutralised,
        COUNT(*) FILTER (
            WHERE NOT COALESCE(p.is_neutralised_lap, FALSE) AND l.lap_number IS NULL
        ) AS n_no_proximity
    FROM blue_laps AS b
    LEFT JOIN {{ ref('int_lap_proximity') }} AS p
        ON
            b.race_id = p.race_id
            AND b.driver_id = p.driver_id
            AND b.lap_number = p.lap_number
    LEFT JOIN usable_laps AS l
        ON
            b.race_id = l.race_id
            AND b.driver_id = l.driver_id
            AND b.lap_number = l.lap_number
    GROUP BY 1
),

msg_counts AS (
    SELECT
        m.race_year,
        COUNT(*) AS n_raw,
        COUNT(*) FILTER (WHERE m.own_lap IS NULL) AS n_unmatched,
        COUNT(m.own_lap) - ANY_VALUE(bl.n_blue_laps) AS n_duplicate
    FROM msg_matched AS m
    LEFT JOIN blue_lap_status AS bl ON m.race_year = bl.race_year
    GROUP BY 1
),

labelled AS (
    SELECT
        l.race_year,
        l.no_car_within_1s_behind,
        b.race_id IS NOT NULL AS is_blue_lap
    FROM usable_laps AS l
    LEFT JOIN blue_laps AS b
        ON
            l.race_id = b.race_id
            AND l.driver_id = b.driver_id
            AND l.lap_number = b.lap_number
),

per_season AS (
    SELECT
        race_year,
        COUNT(*) FILTER (WHERE is_blue_lap) AS n_scored,
        AVG(CAST(no_car_within_1s_behind AS DOUBLE)) FILTER (
            WHERE is_blue_lap
        ) AS blue_clear_behind_share,
        AVG(CAST(no_car_within_1s_behind AS DOUBLE)) FILTER (
            WHERE NOT is_blue_lap
        ) AS other_clear_behind_share
    FROM labelled
    GROUP BY 1
),

report AS (
    SELECT
        mc.race_year,
        mc.n_raw,
        mc.n_unmatched,
        mc.n_duplicate,
        bl.n_blue_laps,
        bl.n_neutralised,
        bl.n_no_proximity,
        ps.n_scored,
        ps.blue_clear_behind_share,
        ps.other_clear_behind_share,
        ps.blue_clear_behind_share
        / NULLIF(ps.other_clear_behind_share, 0) AS clear_behind_ratio,
        (mc.n_unmatched + COALESCE(bl.n_no_proximity, 0))
        / CAST(mc.n_raw AS DOUBLE) AS lost_share
    FROM msg_counts AS mc
    LEFT JOIN blue_lap_status AS bl ON mc.race_year = bl.race_year
    LEFT JOIN per_season AS ps ON mc.race_year = ps.race_year
)

SELECT *
FROM report
WHERE
    n_raw >= 100
    AND (
        lost_share > 0.15
        OR n_scored IS NULL
        OR blue_clear_behind_share > 0.85 * other_clear_behind_share
    )
