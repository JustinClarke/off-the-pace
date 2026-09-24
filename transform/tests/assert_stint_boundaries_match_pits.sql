-- T19 (WI-05, F24). Stint boundaries agree with the pit record, or are quarantined.
-- Replaces assert_stint_boundaries_correct, which only checked that tyre age rises
-- within a stint and passed on all three races whose bronze stint numbering
-- ignores the pit stops (2018_3 China, 2022_11 Austria, 2025_6 Miami). Its one
-- real invariant is kept as check 5.
--
-- Re-derived here from int_stint_geometry (what is served) and stg_pits (the
-- oracle, matched 100% to Jolpica for 2019 and 2021-2025), independently of
-- stg_lap_tyre_qa's internals:
--
-- 1. every race was cross-checked (no lap without a tyre_qa_status);
-- 2. a SERVED ('ok') stint change has an in-lap in the window before it, or a
--    red flag on it or the lap before -- tyres cannot change without a pit visit
--    -- and (2b) no two served changes lean on the same stop;
-- 3. a QUARANTINED unit's stint changes sit exactly on the pit record (the lap
--    after an in-lap the car exited from) or on a red flag, and it serves no
--    compound and no tyre age;
-- 4. no race still served from bronze has the broken-feed signature: at least 3
--    racing stops (car rejoined and ran 3+ more laps, no red flag on the in-lap
--    or out-lap), and at least the quarantine share of them with no stint change
--    in the window after;
-- 5. tyre age never falls or stalls between consecutive valid laps of a stint.

WITH geom AS (
    SELECT
        g.*,
        LAG(g.stint_number) OVER w AS prev_stint_number,
        COALESCE(LAG(g.is_red_flag_lap) OVER w, FALSE) AS prev_is_red_flag_lap
    FROM {{ ref('int_stint_geometry') }} AS g
    WINDOW w AS (
        PARTITION BY g.race_year, g.race_id, g.driver_id ORDER BY g.lap_number
    )
),

pits AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        pit_in_lap_number,
        pit_out_lap_number
    FROM {{ ref('stg_pits') }}
),

changes AS (
    SELECT *
    FROM geom
    WHERE
        prev_stint_number IS NOT NULL
        AND stint_number IS NOT NULL
        AND stint_number <> prev_stint_number
),

driver_last_lap AS (
    SELECT race_year, race_id, driver_id, MAX(lap_number) AS last_lap
    FROM geom
    GROUP BY race_year, race_id, driver_id
),

racing_stops AS (
    SELECT
        p.race_year,
        p.race_id,
        p.driver_id,
        p.pit_in_lap_number,
        EXISTS (
            SELECT 1 FROM changes AS c
            WHERE
                c.race_year = p.race_year
                AND c.race_id = p.race_id
                AND c.driver_id = p.driver_id
                AND c.lap_number BETWEEN p.pit_in_lap_number + 1
                AND p.pit_in_lap_number + {{ var('tyre_qa_boundary_window_laps') }}
        ) AS has_change_after
    FROM pits AS p
    INNER JOIN driver_last_lap AS d
        ON
            p.race_year = d.race_year
            AND p.race_id = d.race_id
            AND p.driver_id = d.driver_id
    INNER JOIN geom AS in_lap
        ON
            p.race_year = in_lap.race_year
            AND p.race_id = in_lap.race_id
            AND p.driver_id = in_lap.driver_id
            AND p.pit_in_lap_number = in_lap.lap_number
    INNER JOIN geom AS out_lap
        ON
            p.race_year = out_lap.race_year
            AND p.race_id = out_lap.race_id
            AND p.driver_id = out_lap.driver_id
            AND p.pit_in_lap_number + 1 = out_lap.lap_number
    WHERE
        p.pit_out_lap_number IS NOT NULL
        AND d.last_lap >= p.pit_in_lap_number + 3
        AND NOT in_lap.is_red_flag_lap
        AND NOT out_lap.is_red_flag_lap
),

served_races AS (
    SELECT race_year, race_id
    FROM geom
    GROUP BY race_year, race_id
    HAVING BOOL_AND(tyre_qa_status <> 'quarantined_race')
)

-- 1.
SELECT
    'race_not_cross_checked' AS check_name,
    race_id AS detail
FROM geom
WHERE tyre_qa_status IS NULL
GROUP BY race_id

UNION ALL

-- 2.
SELECT
    'served_stint_change_without_pit_stop' AS check_name,
    c.race_id || ' ' || c.driver_id || ' lap ' || c.lap_number AS detail
FROM changes AS c
WHERE
    c.tyre_qa_status = 'ok'
    AND NOT c.is_red_flag_lap
    AND NOT c.prev_is_red_flag_lap
    AND NOT EXISTS (
        SELECT 1 FROM pits AS p
        WHERE
            p.race_year = c.race_year
            AND p.race_id = c.race_id
            AND p.driver_id = c.driver_id
            AND p.pit_in_lap_number BETWEEN c.lap_number
            - {{ var('tyre_qa_boundary_window_laps') }}
            AND c.lap_number - 1
    )

UNION ALL

-- 2b. One stop explains one change: two served (non-red-flag) stint changes may
--     not share the same nearest preceding in-lap.
SELECT
    'served_stint_changes_sharing_one_pit_stop' AS check_name,
    s.race_id || ' ' || s.driver_id || ' in-lap ' || s.in_lap AS detail
FROM (
    SELECT
        c.race_id,
        c.driver_id,
        (
            SELECT MAX(p.pit_in_lap_number) FROM pits AS p
            WHERE
                p.race_year = c.race_year
                AND p.race_id = c.race_id
                AND p.driver_id = c.driver_id
                AND p.pit_in_lap_number BETWEEN c.lap_number
                - {{ var('tyre_qa_boundary_window_laps') }}
                AND c.lap_number - 1
        ) AS in_lap
    FROM changes AS c
    WHERE
        c.tyre_qa_status = 'ok'
        AND NOT c.is_red_flag_lap
        AND NOT c.prev_is_red_flag_lap
) AS s
WHERE s.in_lap IS NOT NULL
GROUP BY s.race_id, s.driver_id, s.in_lap
HAVING COUNT(*) > 1

UNION ALL

-- 3a.
SELECT
    'quarantined_stint_change_off_pit_record' AS check_name,
    c.race_id || ' ' || c.driver_id || ' lap ' || c.lap_number AS detail
FROM changes AS c
WHERE
    c.tyre_qa_status <> 'ok'
    AND NOT c.is_red_flag_lap
    AND NOT c.prev_is_red_flag_lap
    AND NOT EXISTS (
        SELECT 1 FROM pits AS p
        WHERE
            p.race_year = c.race_year
            AND p.race_id = c.race_id
            AND p.driver_id = c.driver_id
            AND p.pit_in_lap_number = c.lap_number - 1
            AND p.pit_out_lap_number IS NOT NULL
    )

UNION ALL

-- 3b.
SELECT
    'quarantined_lap_serves_tyre_data' AS check_name,
    race_id || ' ' || driver_id || ' lap ' || lap_number AS detail
FROM geom
WHERE
    tyre_qa_status <> 'ok'
    AND (compound_in_stint IS NOT NULL OR age_in_stint IS NOT NULL)

UNION ALL

-- 4.
SELECT
    'broken_tyre_feed_still_served' AS check_name,
    rs.race_id || ': ' || COUNT(*) FILTER (WHERE NOT rs.has_change_after)
    || ' of ' || COUNT(*) || ' racing stops unmatched' AS detail
FROM racing_stops AS rs
INNER JOIN served_races AS sr
    ON rs.race_year = sr.race_year AND rs.race_id = sr.race_id
GROUP BY rs.race_id
HAVING
    COUNT(*) FILTER (WHERE NOT rs.has_change_after) >= 3
    AND COUNT(*) FILTER (WHERE NOT rs.has_change_after)
    >= {{ var('tyre_qa_race_unmatched_pit_share_min') }} * COUNT(*)

UNION ALL

-- 5.
SELECT
    'tyre_age_not_rising_within_stint' AS check_name,
    stint_id || ' lap ' || lap_number AS detail
FROM (
    SELECT
        stint_id,
        lap_number,
        age_in_stint,
        LAG(age_in_stint) OVER (
            PARTITION BY stint_id ORDER BY lap_number
        ) AS prev_age
    FROM {{ ref('int_lap_residual_decomposed') }}
    WHERE stint_id IS NOT NULL
) AS a
WHERE a.age_in_stint <= a.prev_age
