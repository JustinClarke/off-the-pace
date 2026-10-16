-- Layer 04: Field pace reference curve per race.
-- Trimmed mean (10%) of fuel- and compound-corrected lap times over eligible
-- laps at each lap number, then smoothed with a 5-lap centred rolling average.
-- Eligible laps: not out-laps; not the last two valid laps of a non-final
-- stint (the in-lap rule: the pit in-lap itself is already not a valid lap, and
-- the lap before it is dropped as well; the final stint keeps every lap);
-- within per-lap 107% of fastest lap; free or tow air; known tyre cost.
-- Used downstream as the base against which driver skill residuals are
-- measured. The base is neutral to both fuel and compound (subtracted once
-- here, not again downstream).
--
-- CO-04 (2026-10-15), four changes:
--   FD6: a lap whose air state is unmeasured (int_lap_air_state NULL: no gap
--     and not the leader) is not known to be in clean air, so it does not
--     enter the base. The `IN ('free_air', 'tow_zone')` filter already drops
--     a NULL; this is noted so nobody "fixes" it with a COALESCE. 2018_1
--     Australia and 2018_2 Bahrain have no telemetry at all in bronze, so
--     only the leader is known to be in clean air there. Every cell is thin,
--     so BOTH RACES ARE EXCLUDED FROM THE FIELD BASE: no base, and so no
--     residual and no training label for any of their laps. Owner decision
--     (2026-10-15): keep them dropped rather than guess their air state.
--   W43: the smoother no longer reaches across a neutralisation. A lap number
--     is neutralised when any driver's lap at that number carries an SC, VSC
--     or red flag (int_stint_geometry). Neutralised lap numbers split the race
--     into green segments, and the 5-row window runs inside one segment only.
--     A neutralised cell smooths with nothing but itself. Before this the
--     window spanned the gap: smoothed minus own trimmed mean was -0.57 s on
--     restart cells and -0.45 s on the cell after an SC/red restart, against
--     +0.01 s on other green cells (2026-10-15 build; W43 measured -0.70 /
--     -0.46 on 2026-09-27).
--   Restart laps (W43's alternative, owner decision 2026-10-15): the boundary
--     alone left the bias, because the restart lap is slower than the green
--     laps after it, so a window that starts there still leans fast: -1.04 s
--     on the first green lap after an SC/red flag and -0.49 s on the second,
--     and +0.18 / +0.14 s on the third and fourth, whose windows took in the
--     two slow laps. So the first two green lap numbers after an SC or red
--     flag are restart-adjacent (is_restart_adjacent_lap): each takes its own
--     trimmed mean as its base and feeds no other cell's window. A VSC ends
--     without the queue and the cold-tyre restart; its first two green laps
--     measured -0.06 / 0.00 s and smooth as ordinary green cells.
--   W44: a cell with fewer than 5 eligible laps (low_sample_flag) has no base
--     (field_pace_smoothed_s NULL, the same "NULL, not a guess" rule as F1 and
--     FD6), and its trimmed mean does not feed its neighbours' window either.
--     Before this, 374 of 377 thin cells carried a base, 157 of them borrowed
--     entirely from neighbours because their own trimmed mean was NULL.
--   smoothing_window_first_lap / _last_lap record which cells a base was
--   averaged over, so the two rules above are checkable from the output
--   (assert_field_pace_smoothing_respects_boundaries).
{{ config(materialized='table') }}

WITH fuel_state AS (
    SELECT
        stint_id,
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        weight_corrected_lap_time
    FROM {{ ref('int_lap_fuel_state') }}
),

geom AS (
    SELECT
        stint_id,
        lap_id,
        valid_lap_in_stint,
        stint_length_valid
    FROM {{ ref('int_stint_geometry') }}
),

air AS (
    SELECT lap_id, air_state_dominant
    FROM {{ ref('int_lap_air_state') }}
),

-- W43 (CO-04): race-level neutralisation per lap number. A driver's lap is
-- flagged when its own track status saw SC/VSC/red, so a deployment flags
-- lap N for cars that had crossed the line and N-1 for those that had not.
-- "Any driver" keeps both: a lap number that was partly neutralised for part
-- of the field is a boundary, not a green cell.
neutralised_lap AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        BOOL_OR(
            COALESCE(is_safety_car_lap, FALSE)
            OR COALESCE(is_vsc_lap, FALSE)
            OR COALESCE(is_red_flag_lap, FALSE)
        ) AS is_neutralised_lap,
        -- Restart rule (header): an SC or red flag, not a VSC
        BOOL_OR(
            COALESCE(is_safety_car_lap, FALSE)
            OR COALESCE(is_red_flag_lap, FALSE)
        ) AS is_sc_or_red_lap
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY race_year, race_id, lap_number
),

-- Restart-adjacent lap numbers: the first green lap after an SC/red-flag lap,
-- and the green lap after that (header). Over every lap number in the race,
-- like pace_segment below, so a restart lap with no cell is still placed.
restart_lap AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        NOT is_neutralised_lap
        AND (
            COALESCE(LAG(is_sc_or_red_lap, 1) OVER w, FALSE)
            OR (
                NOT COALESCE(LAG(is_neutralised_lap, 1) OVER w, TRUE)
                AND COALESCE(LAG(is_sc_or_red_lap, 2) OVER w, FALSE)
            )
        ) AS is_restart_adjacent_lap
    FROM neutralised_lap
    WINDOW w AS (PARTITION BY race_year, race_id ORDER BY lap_number)
),

-- Green segments: the running count of neutralised lap numbers is constant
-- across a run of green laps and steps at each neutralised lap. Computed over
-- every lap number in the race (not only the cells that have eligible laps),
-- so a neutralised lap with no cell of its own still splits the window.
pace_segment AS (
    SELECT
        n.race_year,
        n.race_id,
        n.lap_number,
        n.is_neutralised_lap,
        r.is_restart_adjacent_lap,
        SUM(CASE WHEN n.is_neutralised_lap THEN 1 ELSE 0 END) OVER (
            PARTITION BY n.race_year, n.race_id
            ORDER BY n.lap_number
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS pace_segment_id
    FROM neutralised_lap AS n
    INNER JOIN restart_lap AS r
        ON
            n.race_year = r.race_year
            AND n.race_id = r.race_id
            AND n.lap_number = r.lap_number
),

-- Compound correction from the cliff model
compound AS (
    SELECT
        lap_id,
        expected_compound_pace_s
    FROM {{ ref('int_compound_cliff_predicted') }}
),

-- Fastest lap per race per lap_number (for per-lap 107% filter)
per_lap_fastest AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        MIN(lap_time_s) AS per_lap_fastest_lap_s
    FROM fuel_state
    GROUP BY race_year, race_id, lap_number
),

-- Identify final stint per driver per race (to preserve final-stint laps).
-- Picked by the stint_id that holds the driver's highest lap_number, not
-- MAX(stint_id): stint_id is 'YYYY_race_driver_N' (int_stint_geometry), a
-- string, so MAX() would pick stint_number 9 over 10 for any driver with
-- double-digit stops (rare, but a multi-stop chaos race is exactly where the
-- final-stint carve-out matters most).
final_stint_per_driver AS (
    SELECT race_year, race_id, driver_id, stint_id AS final_stint_id
    FROM fuel_state
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY race_year, race_id, driver_id
        ORDER BY lap_number DESC
    ) = 1
),

eligible AS (
    SELECT
        f.race_year,
        f.race_id,
        f.lap_number,
        -- Compound-corrected lap time: weight-corrected minus compound cost.
        -- No COALESCE: a lap with an unknown tyre cost (F39, unknown tyre
        -- age) is dropped from the baseline below rather than entering it as
        -- a free 0 s tyre (2,756 laps on the 2026-09-27 build).
        f.weight_corrected_lap_time - c.expected_compound_pace_s
            AS compound_corrected_lap_time
    FROM fuel_state AS f
    INNER JOIN geom AS g ON f.lap_id = g.lap_id
    INNER JOIN air AS a ON f.lap_id = a.lap_id
    INNER JOIN per_lap_fastest AS plf
        ON
            f.race_year = plf.race_year
            AND f.race_id = plf.race_id
            AND f.lap_number = plf.lap_number
    LEFT JOIN final_stint_per_driver AS fsd
        ON
            f.race_year = fsd.race_year
            AND f.race_id = fsd.race_id
            AND f.driver_id = fsd.driver_id
    LEFT JOIN compound AS c ON f.lap_id = c.lap_id
    WHERE
        -- no out-laps
        g.valid_lap_in_stint > 1
        -- no in-laps, except for final stint which keeps all laps
        AND (
            f.stint_id = fsd.final_stint_id
            OR g.valid_lap_in_stint < g.stint_length_valid - 1
        )
        -- per-lap 107% of fastest lap for that lap_number (handles
        -- mixed-condition races)
        AND f.lap_time_s < 1.07 * plf.per_lap_fastest_lap_s
        -- clean air. A NULL (unmeasured, FD6) is not clean air and is
        -- dropped here on purpose: do not COALESCE it (header, CO-04).
        AND a.air_state_dominant IN ('free_air', 'tow_zone')
        AND f.weight_corrected_lap_time IS NOT NULL
        -- WI-01: unknown tyre cost stays out of the baseline (see above)
        AND c.expected_compound_pace_s IS NOT NULL
),

-- Pre-compute percent rank so it can be used as a filter in the aggregation
-- operation
eligible_ranked AS (
    SELECT
        *,
        PERCENT_RANK() OVER (
            PARTITION BY race_year, race_id, lap_number
            ORDER BY compound_corrected_lap_time
        ) AS pct_rank
    FROM eligible
),

-- Trimmed mean per race × lap_number (10% trim = drop top and bottom 10%)
trimmed AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        COUNT(*) AS eligible_lap_count,
        AVG(compound_corrected_lap_time) FILTER (
            WHERE pct_rank BETWEEN 0.10 AND 0.90
        )
            AS field_pace_trimmed_mean_s
    FROM eligible_ranked
    GROUP BY race_year, race_id, lap_number
),

-- What each cell offers its window (W44): its trimmed mean only when at
-- least 5 cars measured it. A thin cell stays a row (it still has a position
-- in the window) but contributes nothing.
smoothing_input AS (
    SELECT
        t.race_year,
        t.race_id,
        t.lap_number,
        t.eligible_lap_count,
        t.field_pace_trimmed_mean_s,
        t.eligible_lap_count < 5 AS low_sample_flag,
        s.is_neutralised_lap,
        s.is_restart_adjacent_lap,
        s.pace_segment_id,
        -- A neutralised or restart-adjacent cell smooths with nothing but
        -- itself (header): its own lap number is its window partition.
        CASE
            WHEN s.is_neutralised_lap OR s.is_restart_adjacent_lap
                THEN t.lap_number
        END AS isolated_lap_number,
        CASE
            WHEN t.eligible_lap_count >= 5 THEN t.field_pace_trimmed_mean_s
        END AS window_value_s
    FROM trimmed AS t
    INNER JOIN pace_segment AS s
        ON
            t.race_year = s.race_year
            AND t.race_id = s.race_id
            AND t.lap_number = s.lap_number
),

-- 5-lap centred rolling average for rubber gradient extraction, inside one
-- green segment (W43). isolated_lap_number puts each neutralised and each
-- restart-adjacent cell in a partition of its own, so it averages only
-- itself and is absent from the green cells' windows; the remaining green
-- cells of the segment (NULL isolated_lap_number) smooth together.
smoothed AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        eligible_lap_count,
        field_pace_trimmed_mean_s,
        low_sample_flag,
        is_neutralised_lap,
        is_restart_adjacent_lap,
        AVG(window_value_s) OVER w AS window_mean_s,
        MIN(CASE WHEN window_value_s IS NOT NULL THEN lap_number END) OVER w
            AS window_first_lap,
        MAX(CASE WHEN window_value_s IS NOT NULL THEN lap_number END) OVER w
            AS window_last_lap
    FROM smoothing_input
    WINDOW w AS (
        PARTITION BY race_year, race_id, pace_segment_id, isolated_lap_number
        ORDER BY lap_number
        ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING
    )
)

SELECT
    race_year,
    race_id,
    lap_number,
    eligible_lap_count,
    field_pace_trimmed_mean_s,
    -- W44: no base below 5 cars (header)
    CASE WHEN NOT low_sample_flag THEN window_mean_s END
        AS field_pace_smoothed_s,
    low_sample_flag,
    is_neutralised_lap,
    is_restart_adjacent_lap,
    -- The lap numbers of the first and last cells averaged into
    -- field_pace_smoothed_s (NULL when it is NULL).
    CASE WHEN NOT low_sample_flag THEN window_first_lap END
        AS smoothing_window_first_lap,
    CASE WHEN NOT low_sample_flag THEN window_last_lap END
        AS smoothing_window_last_lap
FROM smoothed
ORDER BY race_year, race_id, lap_number
