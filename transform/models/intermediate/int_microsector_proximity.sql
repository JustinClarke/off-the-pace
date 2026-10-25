-- int_microsector_proximity.sql · intermediate · grain: one row per
-- (race, driver, lap, micro-sector), PK microsector_id.
-- DA-02 (_roadmap/_dirty-air/wi/DA-02-tables.md, design note sections 1 and 3):
-- the micro-sector panel the dirty-air identification (DA-03, W11 option C) is
-- fitted on. NO LABEL READS THIS MODEL; nothing in the label spine, the ML
-- contract marts or the isolation panel references it.
--
-- WHAT A ROW IS
--   time_s   how long the driver took to drive micro-sector m of the lap: the
--            interpolated crossing time of boundary m + 1 minus that of m
--            (int_microsector_crossings). The 20 micro-sectors of a lap sum
--            exactly to the difference of its two lap-line crossings.
--   y_s      time_s minus the MEDIAN time_s of the timing-valid cars on the
--            same (race, lap, micro-sector), positive = slower than the field.
--            Whatever hits the whole field on that stretch at that moment
--            (track evolution, wind, a lap-1 queue) cancels. NULL below
--            var('microsector_min_field_n') cars.
--   gap_behind_s / behind_lap_number  the same for the car behind (the P1
--            placebo)
--   entry gap  gap_ahead_s: the seconds between the car ahead reaching boundary
--            m and this car reaching it. ONLY the entry gap prices the
--            micro-sector; the exit gap (exit_gap_ahead_s) is an outcome (a car
--            that loses time opens the gap itself) and is carried for the lead
--            window check only.
--
-- THE CAR AHEAD is the previous on-track crossing of the same boundary in the
-- same race, over all laps and drivers, ordered by (crossing_time_s,
-- driver_id), which is a total order (a driver crosses a boundary once per
-- lap). This is int_lap_proximity's definition at 20 interpolated points
-- instead of 100 first-sample bins, so it is correct for lapped cars. A
-- crossing inside the driver's own pit window is not on track and is dropped
-- before the ordering (F43). When the previous crossing is the driver's own
-- (alone for a lap) or is more than var('proximity_max_gap_s') earlier (a red
-- flag), there is no car ahead: ahead_driver_id and gap_ahead_s are NULL, and
-- the row is invalid, NOT zero (the CO-04 rule: unknown is not clean air).
--
-- LAPPED CARS (DD5, owner 2026-10-23). The car ahead is lapped when its lap
-- number is lower than the driver's at the same point. A lapped car within
-- var('microsector_lapped_ahead_window_s') makes the row invalid
-- (lapped_ahead_within_window); beyond it the row sits in the reference band
-- whoever the car is. A car ahead on a HIGHER lap is lapping the driver and is
-- an ordinary car ahead. is_lapped_ahead records which.
--
-- invalid_reason (one code, first match wins; NULL = valid)
--   lap1                      lap_number < 2 (standing start, no clean order)
--   pit_lane                  either boundary inside the driver's own pit
--                             window
--   no_next_crossing          the next boundary was not reached or not recorded
--   off_track                 a straddling sample pair was not OnTrack
--   wide_bracket              a boundary interpolated across > max_bracket_s
--   non_green_flag            the track status was not '1' (all clear) at
--                             either boundary, or changed in between, or is
--                             unknown. The status is
--                             circuit-wide: a local yellow in any marshal
--                             sector drops every driver's micro-sector until
--                             it clears (the marshal-sector map is not in
--                             bronze, DD6, so a local yellow cannot be placed)
--   post_restart              within 2 laps after an SC, VSC or red-flag lap
--   car_ahead_unknown         see above
--   lapped_ahead_within_window  see above
-- Rows with a timing problem (the first five codes) have no usable time_s;
-- the rows from car_ahead_unknown on have a good time and an unusable
-- exposure. y_s is defined on both kinds of the second group (and on valid
-- rows), because the field median should not lose the cars that happen to be
-- alone.
--
-- gap_band is the design note's step function: <0.5, 0.5-1, 1-1.5, 1.5-2, 2-3,
-- and >3 s as the reference band. It is NULL on an invalid row.
--
-- Times are ROUNDed at source; every window has a total ORDER BY; see
-- assert_microsector_total_order.
{{ config(materialized='table', tags=['dirty_air_dynamic']) }}

{%- set n = var('microsector_n') %}
{%- set bracket = var('microsector_max_bracket_s') %}
{%- set lapped_win = var('microsector_lapped_ahead_window_s') %}

WITH crossings AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        microsector,
        boundary_k,
        crossing_time_s,
        bracket_s,
        on_track
    FROM {{ ref('int_microsector_crossings') }}
),

-- Session flag state: the code in force at an instant (the worst code if two
-- are logged at the same instant, as DA-01), and the instants it is not '1'.
status_at AS (
    SELECT
        race_id,
        session_time_s,
        MAX(status_code) AS status_code
    FROM {{ ref('stg_track_status') }}
    GROUP BY race_id, session_time_s
),

non_green_events AS (
    SELECT DISTINCT
        race_id,
        session_time_s
    FROM {{ ref('stg_track_status') }}
    WHERE status_code != '1'
),

pit_windows AS (
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

with_flags AS (
    SELECT
        c.*,
        s.status_code AS status_code_at,
        EXISTS(
            SELECT 1
            FROM pit_windows AS w
            WHERE
                w.race_id = c.race_id
                AND w.driver_id = c.driver_id
                AND c.crossing_time_s BETWEEN w.pit_in_time_s
                AND w.pit_out_time_s
        ) AS in_pit
    FROM crossings AS c
    ASOF LEFT JOIN status_at AS s
        ON
            c.race_id = s.race_id
            AND c.crossing_time_s >= s.session_time_s
),

-- Order every on-track crossing of one boundary by its clock. Self-match and
-- stoppage guards as int_lap_proximity.
neighbours AS (
    SELECT
        *,
        LAG(driver_id) OVER w AS prev_driver_id,
        LAG(lap_number) OVER w AS prev_lap_number,
        LAG(crossing_time_s) OVER w AS prev_crossing_s,
        LEAD(driver_id) OVER w AS next_driver_id,
        LEAD(lap_number) OVER w AS next_lap_number,
        LEAD(crossing_time_s) OVER w AS next_crossing_s
    FROM with_flags
    WHERE NOT in_pit
    WINDOW w AS (
        PARTITION BY race_year, race_id, microsector
        ORDER BY crossing_time_s, driver_id
    )
),

gapped AS (
    SELECT
        f.race_year,
        f.race_id,
        f.driver_id,
        f.lap_number,
        f.microsector,
        f.boundary_k,
        f.crossing_time_s,
        f.bracket_s,
        f.on_track,
        f.status_code_at,
        f.in_pit,
        CASE
            WHEN
                nb.prev_driver_id IS NOT NULL
                AND nb.prev_driver_id != f.driver_id
                AND f.crossing_time_s - nb.prev_crossing_s
                <= {{ var('proximity_max_gap_s') }}
                THEN nb.prev_driver_id
        END AS ahead_driver_id,
        CASE
            WHEN
                nb.prev_driver_id IS NOT NULL
                AND nb.prev_driver_id != f.driver_id
                AND f.crossing_time_s - nb.prev_crossing_s
                <= {{ var('proximity_max_gap_s') }}
                THEN nb.prev_lap_number
        END AS ahead_lap_number,
        CASE
            WHEN
                nb.prev_driver_id IS NOT NULL
                AND nb.prev_driver_id != f.driver_id
                AND f.crossing_time_s - nb.prev_crossing_s
                <= {{ var('proximity_max_gap_s') }}
                THEN ROUND(f.crossing_time_s - nb.prev_crossing_s, 6)
        END AS gap_ahead_s,
        CASE
            WHEN
                nb.next_driver_id IS NOT NULL
                AND nb.next_driver_id != f.driver_id
                AND nb.next_crossing_s - f.crossing_time_s
                <= {{ var('proximity_max_gap_s') }}
                THEN ROUND(nb.next_crossing_s - f.crossing_time_s, 6)
        END AS gap_behind_s,
        CASE
            WHEN
                nb.next_driver_id IS NOT NULL
                AND nb.next_driver_id != f.driver_id
                AND nb.next_crossing_s - f.crossing_time_s
                <= {{ var('proximity_max_gap_s') }}
                THEN nb.next_lap_number
        END AS behind_lap_number
    FROM with_flags AS f
    LEFT JOIN neighbours AS nb
        ON
            f.race_year = nb.race_year
            AND f.race_id = nb.race_id
            AND f.driver_id = nb.driver_id
            AND f.boundary_k = nb.boundary_k
),

-- Pair each boundary with the driver's next one: the micro-sector.
sectors AS (
    SELECT
        *,
        LEAD(boundary_k) OVER wd AS next_boundary_k,
        LEAD(crossing_time_s) OVER wd AS end_time_s,
        LEAD(bracket_s) OVER wd AS end_bracket_s,
        LEAD(on_track) OVER wd AS end_on_track,
        LEAD(status_code_at) OVER wd AS end_status_code,
        LEAD(in_pit) OVER wd AS end_in_pit,
        LEAD(gap_ahead_s) OVER wd AS exit_gap_ahead_s
    FROM gapped
    WINDOW wd AS (
        PARTITION BY race_year, race_id, driver_id
        ORDER BY boundary_k
    )
),

-- Laps since the last neutralised lap, race-wide (any driver's lap flagged
-- SC, VSC or red), for the restart exclusion.
lap_neutralised AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        BOOL_OR(
            COALESCE(is_safety_car_lap, FALSE)
            OR COALESCE(is_vsc_lap, FALSE)
            OR COALESCE(is_red_flag_lap, FALSE)
        ) AS is_neutralised_lap
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY race_year, race_id, lap_number
),

since_neutralised AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        lap_number - MAX(CASE WHEN is_neutralised_lap THEN lap_number END)
            OVER (
                PARTITION BY race_year, race_id
                ORDER BY lap_number
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS laps_since_neutralised
    FROM lap_neutralised
),

classified AS (
    SELECT
        s.*,
        sn.laps_since_neutralised,
        -- The status changed between the two boundaries
        EXISTS(
            SELECT 1
            FROM non_green_events AS e
            WHERE
                e.race_id = s.race_id
                AND e.session_time_s > s.crossing_time_s
                AND e.session_time_s <= s.end_time_s
        ) AS status_event_inside,
        s.next_boundary_k = s.boundary_k + 1 AS has_next
    FROM sectors AS s
    LEFT JOIN since_neutralised AS sn
        ON
            s.race_year = sn.race_year
            AND s.race_id = sn.race_id
            AND s.lap_number = sn.lap_number
),

timed AS (
    SELECT
        *,
        CASE
            WHEN lap_number < 2 THEN 'lap1'
            WHEN in_pit OR COALESCE(end_in_pit, FALSE) THEN 'pit_lane'
            WHEN NOT COALESCE(has_next, FALSE) THEN 'no_next_crossing'
            WHEN NOT (on_track AND end_on_track) THEN 'off_track'
            WHEN
                bracket_s > {{ bracket }} OR end_bracket_s > {{ bracket }}
                THEN 'wide_bracket'
            WHEN
                COALESCE(status_code_at, '?') != '1'
                OR COALESCE(end_status_code, '?') != '1'
                OR status_event_inside
                THEN 'non_green_flag'
            WHEN
                laps_since_neutralised BETWEEN 1 AND 2
                OR laps_since_neutralised = 0
                THEN 'post_restart'
        END AS timing_invalid_reason
    FROM classified
),

with_time AS (
    SELECT
        *,
        CASE
            WHEN timing_invalid_reason IS NULL
                THEN ROUND(end_time_s - crossing_time_s, 6)
        END AS time_s
    FROM timed
),

field AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        microsector,
        COUNT(time_s) AS field_n,
        MEDIAN(time_s) AS field_median_time_s
    FROM with_time
    GROUP BY race_year, race_id, lap_number, microsector
),

final AS (
    SELECT
        t.*,
        f.field_n,
        CASE
            WHEN
                t.time_s IS NOT NULL
                AND f.field_n >= {{ var('microsector_min_field_n') }}
                THEN ROUND(t.time_s - f.field_median_time_s, 6)
        END AS y_s,
        t.ahead_lap_number < t.lap_number AS is_lapped_ahead
    FROM with_time AS t
    LEFT JOIN field AS f
        ON
            t.race_year = f.race_year
            AND t.race_id = f.race_id
            AND t.lap_number = f.lap_number
            AND t.microsector = f.microsector
)

SELECT
    CONCAT(
        fi.race_year, '_', fi.race_id, '_', fi.driver_id, '_', fi.lap_number,
        '_', LPAD(CAST(fi.microsector AS VARCHAR), 2, '0')
    ) AS microsector_id,
    CONCAT(
        fi.race_year, '_', fi.race_id, '_', fi.driver_id, '_', fi.lap_number
    ) AS lap_id,
    fi.race_year,
    fi.race_id,
    fi.driver_id,
    fi.lap_number,
    fi.microsector,
    fi.crossing_time_s AS entry_time_s,
    fi.time_s,
    fi.field_n,
    fi.y_s,
    fi.ahead_driver_id,
    fi.ahead_lap_number,
    fi.is_lapped_ahead,
    fi.gap_ahead_s,
    fi.gap_behind_s,
    -- The car behind on a HIGHER lap is lapping this driver (a blue-flag
    -- case, not a following car): the P1 placebo uses the same-lap cars only.
    fi.behind_lap_number,
    fi.exit_gap_ahead_s,
    -- The car ahead's own field-relative time in the same micro-sector (design
    -- note s3, aheadResid): it controls for a slow car ahead. NULL when the car
    -- ahead has no usable y_s there.
    ah.y_s AS ahead_y_s,
    fi.timing_invalid_reason,
    CASE
        WHEN fi.timing_invalid_reason IS NOT NULL THEN fi.timing_invalid_reason
        WHEN fi.ahead_driver_id IS NULL THEN 'car_ahead_unknown'
        WHEN
            fi.is_lapped_ahead
            AND fi.gap_ahead_s < {{ lapped_win }}
            THEN 'lapped_ahead_within_window'
    END AS invalid_reason,
    CASE
        WHEN
            fi.timing_invalid_reason IS NULL
            AND fi.ahead_driver_id IS NOT NULL
            AND NOT (fi.is_lapped_ahead AND fi.gap_ahead_s < {{ lapped_win }})
            THEN
                CASE
                    WHEN fi.gap_ahead_s < 0.5 THEN '0_lt0.5'
                    WHEN fi.gap_ahead_s < 1.0 THEN '1_0.5to1'
                    WHEN fi.gap_ahead_s < 1.5 THEN '2_1to1.5'
                    WHEN fi.gap_ahead_s < 2.0 THEN '3_1.5to2'
                    WHEN fi.gap_ahead_s < 3.0 THEN '4_2to3'
                    ELSE '5_gt3_reference'
                END
    END AS gap_band
FROM final AS fi
LEFT JOIN final AS ah
    ON
        fi.race_year = ah.race_year
        AND fi.race_id = ah.race_id
        AND fi.ahead_driver_id = ah.driver_id
        AND fi.ahead_lap_number = ah.lap_number
        AND fi.microsector = ah.microsector
ORDER BY fi.race_year, fi.race_id, fi.driver_id, fi.lap_number, fi.microsector
