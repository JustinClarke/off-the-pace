-- stg_lap_tyre_qa.sql · staging · grain: one row per race lap (lap_id)
--
-- Bronze tyre QA (WI-05: F24, F25). Bronze Stint / TyreLife / Compound come
-- from FastF1's TimingAppData and are wrong in two known ways; this model
-- repairs one and quarantines the other, and int_stint_geometry reads the
-- result instead of stg_laps' raw columns. The raw values are kept alongside
-- (bronze_*) so every repair is inspectable.
--
-- 1. F25 -- REPAIR. In 17 of 21 2018 races lap 1 carries no Stint (one car a
--    race misses lap 2 as well), and TyreLife starts counting at the first
--    assigned lap, so lap_in_stint and age_in_stint read one lap low for the
--    whole first stint (independent check: the Q2-tyre starters' age at lap 2
--    is exactly one lower than in 2018 R18-21 and 2019, in both grid groups).
--    When a driver's first var('tyre_qa_max_unassigned_leading_laps') laps or
--    fewer are unassigned and no stop falls inside them, they join the first
--    stint and take its compound, and the stint's TyreLife is offset by the
--    number of laps filled (lap i of the gap gets the first assigned lap's
--    TyreLife + i - 1). If the car pitted inside the gap (2018 lap-1 stops),
--    the laps up to that in-lap are the stint before bronze's first one, with
--    unknown tyres (NULL), and no offset is applied: bronze's count started on
--    the new set.
--
-- 2. F24 -- CROSS-CHECK AND QUARANTINE. Every race's (repaired) bronze stint
--    numbering is cross-checked against the pit record (stg_pits, matched
--    100% to Jolpica for 2019 and 2021-2025):
--      * unexplained stint change: bronze starts a new stint with no in-lap in
--        the var('tyre_qa_boundary_window_laps') laps before it and no red
--        flag on it or the lap before -- or whose in-lap an earlier change
--        already claimed (one stop, one change). A tyre change needs a pit
--        visit (or a red flag), so this is bronze contradicting the pit record.
--      * unmatched racing stop: an in-lap after which the car rejoined and ran
--        3+ more laps, with no red flag on it or its out-lap, and no bronze
--        stint change within the window after it. Drive-through penalties land
--        here legitimately -- one or two a race -- so this is only read as a
--        race share.
--    A race is QUARANTINED when it has at least
--    var('tyre_qa_race_unexplained_boundaries_min') unexplained stint changes,
--    or at least var('tyre_qa_race_unmatched_pit_share_min') of its racing
--    stops unmatched (and at least 3 of them). Outside quarantined races, one
--    DRIVER-RACE is quarantined when it has any unexplained stint change, or
--    laps bronze never assigned beyond the repairable lap-1 gap. Quarantine
--    serves the pit record, not bronze: the stint ordinal is rebuilt as 1 +
--    the stops (in-laps the car exited from) before the lap, plus bronze's own
--    stint changes on red-flag laps (tyres change in the pit lane under the
--    flag, with no in-lap), and compound / tyre_life are NULL -- a tyre age
--    that contradicts the pit record is not served, and a NULL age leaves the
--    row out of training (is_training_eligible needs age_in_stint > 3). Known
--    limit: in a quarantined unit a drive-through also opens a stint.
--
-- tyre_qa_status is the quarantine list: 'ok', 'quarantined_race',
-- 'quarantined_driver'; the race-level counts behind the verdict are carried
-- on every row. assert_stint_boundaries_match_pits (T19) and
-- assert_stint1_includes_lap1 (T20) re-derive both rules independently from
-- int_stint_geometry and stg_pits.
{{ config(materialized='view') }}

WITH laps AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        stint_number AS bronze_stint_number,
        tyre_life AS bronze_tyre_life,
        compound AS bronze_compound,
        COALESCE(is_red_flag_lap, FALSE) AS is_red_flag_lap
    FROM {{ ref('stg_laps') }}
),

pits AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        pit_in_lap_number,
        pit_out_lap_number IS NOT NULL AS car_exited
    FROM {{ ref('stg_pits') }}
),

lap_pit AS (
    SELECT
        l.*,
        p.pit_in_lap_number IS NOT NULL AS is_in_lap,
        COALESCE(p.car_exited, FALSE) AS is_exited_in_lap
    FROM laps AS l
    LEFT JOIN pits AS p
        ON
            l.race_year = p.race_year
            AND l.race_id = p.race_id
            AND l.driver_id = p.driver_id
            AND l.lap_number = p.pit_in_lap_number
),

-- Per driver-race: where bronze's stint numbering starts, the tyre it starts
-- on, and the first stop.
driver_race AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        MIN(lap_number) FILTER (
            WHERE bronze_stint_number IS NOT NULL
        ) AS first_assigned_lap,
        ARG_MIN(bronze_stint_number, lap_number) FILTER (
            WHERE bronze_stint_number IS NOT NULL
        ) AS first_stint_number,
        ARG_MIN(bronze_tyre_life, lap_number) FILTER (
            WHERE bronze_stint_number IS NOT NULL
        ) AS first_tyre_life,
        ARG_MIN(bronze_compound, lap_number) FILTER (
            WHERE bronze_stint_number IS NOT NULL
        ) AS first_compound,
        MIN(lap_number) FILTER (WHERE is_in_lap) AS first_in_lap,
        MAX(lap_number) AS last_lap
    FROM lap_pit
    GROUP BY race_year, race_id, driver_id
),

-- F25 repair.
repaired AS (
    SELECT
        lp.*,
        dr.last_lap,
        dr.first_assigned_lap - 1 AS unassigned_leading_laps,
        (
            dr.first_assigned_lap - 1
            BETWEEN 1 AND {{ var('tyre_qa_max_unassigned_leading_laps') }}
        ) AS is_repairable_gap,
        COALESCE(dr.first_in_lap < dr.first_assigned_lap, FALSE)
            AS stopped_in_gap,
        dr.first_in_lap,
        dr.first_assigned_lap,
        dr.first_stint_number,
        dr.first_tyre_life,
        dr.first_compound
    FROM lap_pit AS lp
    LEFT JOIN driver_race AS dr
        ON
            lp.race_year = dr.race_year
            AND lp.race_id = dr.race_id
            AND lp.driver_id = dr.driver_id
),

filled AS (
    SELECT
        *,
        CASE
            -- a leading gap lap, no stop inside the gap: first stint
            WHEN
                is_repairable_gap AND lap_number < first_assigned_lap
                AND NOT stopped_in_gap
                THEN first_stint_number
            -- a leading gap lap up to the in-lap of a stop inside the gap:
            -- the stint before bronze's first one
            WHEN
                is_repairable_gap AND lap_number < first_assigned_lap
                AND lap_number <= first_in_lap
                THEN first_stint_number - 1
            -- a gap lap after that stop: already on bronze's first set
            WHEN is_repairable_gap AND lap_number < first_assigned_lap
                THEN first_stint_number
            ELSE bronze_stint_number
        END AS qa_stint_number,
        CASE
            WHEN
                is_repairable_gap AND lap_number < first_assigned_lap
                AND NOT stopped_in_gap
                THEN first_tyre_life + lap_number - 1
            WHEN is_repairable_gap AND lap_number < first_assigned_lap
                THEN NULL
            -- the first stint of a filled gap: TyreLife counted from the first
            -- assigned lap, so it is short by the laps filled
            WHEN
                is_repairable_gap AND NOT stopped_in_gap
                AND bronze_stint_number = first_stint_number
                THEN bronze_tyre_life + unassigned_leading_laps
            ELSE bronze_tyre_life
        END AS qa_tyre_life,
        CASE
            WHEN
                is_repairable_gap AND lap_number < first_assigned_lap
                AND lap_number <= first_in_lap
                AND stopped_in_gap
                THEN NULL
            WHEN is_repairable_gap AND lap_number < first_assigned_lap
                THEN first_compound
            ELSE bronze_compound
        END AS qa_compound,
        CASE
            WHEN is_repairable_gap AND NOT stopped_in_gap
                THEN unassigned_leading_laps
            ELSE 0
        END AS tyre_life_offset_laps
    FROM repaired
),

-- Stint changes on the repaired numbering, and the in-lap each one follows.
seq AS (
    SELECT
        *,
        LAG(qa_stint_number) OVER w AS prev_qa_stint_number,
        COALESCE(LAG(is_red_flag_lap) OVER w, FALSE) AS prev_is_red_flag_lap,
        COALESCE(LAG(is_exited_in_lap) OVER w, FALSE)
            AS prev_is_exited_in_lap,
        MAX(CASE WHEN is_in_lap THEN lap_number END) OVER (
            w ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS last_in_lap_before
    FROM filled
    WINDOW w AS (
        PARTITION BY race_year, race_id, driver_id ORDER BY lap_number
    )
),

boundaries AS (
    SELECT
        *,
        COALESCE(
            prev_qa_stint_number IS NOT NULL
            AND qa_stint_number IS NOT NULL
            AND qa_stint_number <> prev_qa_stint_number,
            FALSE
        ) AS is_stint_change
    FROM seq
),

-- The in-lap a (non-red-flag) stint change would be explained by: the latest
-- in-lap within the window before it.
claimed AS (
    SELECT
        *,
        is_stint_change
        AND (is_red_flag_lap OR prev_is_red_flag_lap)
            AS is_red_flag_stint_change,
        CASE
            WHEN
                is_stint_change
                AND NOT (is_red_flag_lap OR prev_is_red_flag_lap)
                AND lap_number - last_in_lap_before
                <= {{ var('tyre_qa_boundary_window_laps') }}
                THEN last_in_lap_before
        END AS candidate_in_lap
    FROM boundaries
),

-- One stop explains one stint change. A second change claiming the same
-- in-lap (bronze opening two stints around a single stop, e.g. 2018_13 VER:
-- stint 1 on lap 2 only, stint 2 from lap 3, tyre age running on unbroken) is
-- unexplained.
classified AS (
    SELECT
        *,
        is_stint_change
        AND NOT is_red_flag_stint_change
        AND (
            candidate_in_lap IS NULL
            OR candidate_in_lap = COALESCE(prev_claimed_in_lap, -1)
        ) AS is_unexplained_stint_change,
        CASE
            WHEN candidate_in_lap <> COALESCE(prev_claimed_in_lap, -1)
                THEN candidate_in_lap
        END AS matched_in_lap
    FROM (
        SELECT
            *,
            MAX(candidate_in_lap) OVER (
                PARTITION BY race_year, race_id, driver_id
                ORDER BY lap_number
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS prev_claimed_in_lap
        FROM claimed
    ) AS c
),

-- In-laps a bronze stint change follows within the window.
matched_stops AS (
    SELECT DISTINCT
        race_year,
        race_id,
        driver_id,
        matched_in_lap AS lap_number
    FROM classified
    WHERE matched_in_lap IS NOT NULL
),

-- Racing stops: the car rejoined and ran 3+ more laps, no red flag on the
-- in-lap or the out-lap.
racing_stops AS (
    SELECT
        c.race_year,
        c.race_id,
        c.driver_id,
        c.lap_number,
        ms.lap_number IS NOT NULL AS is_matched
    FROM classified AS c
    INNER JOIN classified AS out_lap
        ON
            c.race_year = out_lap.race_year
            AND c.race_id = out_lap.race_id
            AND c.driver_id = out_lap.driver_id
            AND c.lap_number + 1 = out_lap.lap_number
    LEFT JOIN matched_stops AS ms
        ON
            c.race_year = ms.race_year
            AND c.race_id = ms.race_id
            AND c.driver_id = ms.driver_id
            AND c.lap_number = ms.lap_number
    WHERE
        c.is_exited_in_lap
        AND NOT c.is_red_flag_lap
        AND NOT out_lap.is_red_flag_lap
        AND c.last_lap >= c.lap_number + 3
),

race_stops AS (
    SELECT
        race_year,
        race_id,
        COUNT(*) AS n_racing_stops,
        COUNT(*) FILTER (WHERE NOT is_matched) AS n_unmatched_racing_stops
    FROM racing_stops
    GROUP BY race_year, race_id
),

race_changes AS (
    SELECT
        race_year,
        race_id,
        COUNT(*) FILTER (
            WHERE is_unexplained_stint_change
        ) AS n_unexplained_stint_changes
    FROM classified
    GROUP BY race_year, race_id
),

race_qa AS (
    SELECT
        rc.race_year,
        rc.race_id,
        rc.n_unexplained_stint_changes,
        COALESCE(rs.n_racing_stops, 0) AS n_racing_stops,
        COALESCE(rs.n_unmatched_racing_stops, 0) AS n_unmatched_racing_stops,
        COALESCE(
            rc.n_unexplained_stint_changes
            >= {{ var('tyre_qa_race_unexplained_boundaries_min') }}
            OR (
                rs.n_unmatched_racing_stops >= 3
                AND rs.n_unmatched_racing_stops
                >= {{ var('tyre_qa_race_unmatched_pit_share_min') }}
                * rs.n_racing_stops
            ),
            FALSE
        ) AS is_race_quarantined
    FROM race_changes AS rc
    LEFT JOIN race_stops AS rs
        ON rc.race_year = rs.race_year AND rc.race_id = rs.race_id
),

driver_qa AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        COUNT(*) FILTER (
            WHERE is_unexplained_stint_change
        ) AS n_unexplained_stint_changes_driver,
        COUNT(*) FILTER (WHERE qa_stint_number IS NULL) AS n_unassigned_laps,
        COUNT(*) FILTER (WHERE qa_stint_number IS NOT NULL) AS n_assigned_laps
    FROM classified
    GROUP BY race_year, race_id, driver_id
),

verdict AS (
    SELECT
        c.*,
        rq.n_unexplained_stint_changes,
        rq.n_racing_stops,
        rq.n_unmatched_racing_stops,
        CASE
            WHEN rq.is_race_quarantined THEN 'quarantined_race'
            WHEN
                dq.n_unexplained_stint_changes_driver > 0
                OR (dq.n_unassigned_laps > 0 AND dq.n_assigned_laps > 0)
                THEN 'quarantined_driver'
            ELSE 'ok'
        END AS tyre_qa_status,
        -- The pit record's stint ordinal: 1 + stops the car exited from before
        -- this lap + bronze's red-flag stint changes up to it.
        1 + SUM(
            CASE
                WHEN c.prev_is_exited_in_lap OR c.is_red_flag_stint_change
                    THEN 1
                ELSE 0
            END
        ) OVER (
            PARTITION BY c.race_year, c.race_id, c.driver_id
            ORDER BY c.lap_number
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS pit_stint_ordinal
    FROM classified AS c
    INNER JOIN race_qa AS rq
        ON c.race_year = rq.race_year AND c.race_id = rq.race_id
    INNER JOIN driver_qa AS dq
        ON
            c.race_year = dq.race_year
            AND c.race_id = dq.race_id
            AND c.driver_id = dq.driver_id
)

SELECT
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    -- Served tyre state (what int_stint_geometry reads).
    CASE
        WHEN tyre_qa_status = 'ok' THEN qa_stint_number
        ELSE pit_stint_ordinal
    END AS stint_number,
    CASE WHEN tyre_qa_status = 'ok' THEN qa_tyre_life END AS tyre_life,
    CASE WHEN tyre_qa_status = 'ok' THEN qa_compound END AS compound,
    CASE
        WHEN tyre_qa_status <> 'ok' THEN 'pit_record'
        WHEN qa_stint_number IS NULL THEN NULL
        WHEN
            tyre_life_offset_laps > 0
            OR (is_repairable_gap AND lap_number < first_assigned_lap)
            THEN 'bronze_lap1_repaired'
        ELSE 'bronze'
    END AS stint_source,
    tyre_life_offset_laps,
    tyre_qa_status,
    -- Race-level evidence behind the verdict (the quarantine list).
    n_unexplained_stint_changes,
    n_racing_stops,
    n_unmatched_racing_stops,
    is_unexplained_stint_change,
    -- Bronze as ingested.
    bronze_stint_number,
    bronze_tyre_life,
    bronze_compound
FROM verdict
