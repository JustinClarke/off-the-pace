-- CO-09 (D4, CD14). stint_id keys a TYRE RUN; the join rule holds both ways.
--
-- int_stint_geometry folds consecutive FastF1 stints into one run when the
-- compound is the same, the tyre age continues at last age + 1, and the earlier
-- stint did not end on a green-flag lap (a safety-car drive-through or a
-- red-flag pause on the same tyres) OR race control recorded a drive-through,
-- stop-go or time penalty for that car within one lap of the earlier stint's
-- last lap (owner, 2026-10-24, on CD14: a penalty served in the pit lane on the
-- same tyres). Re-derived here from the served laps and the message feed:
--
-- 1. 'unjoined_same_tyre_split': two consecutive served runs of a driver-race
--    that meet the rule -- the join was missed and a fake stint survived (the
--    Canada 2025 defect: real final stints labelled sc_pit);
-- 2. 'run_crosses_tyre_change': inside one run, consecutive laps whose tyre
--    age does not continue (+0 or +1 between adjacent laps) or whose compound
--    changes -- two different sets were folded into one run;
-- 3. 'green_join_without_penalty': inside one run, a FastF1 stint boundary
--    (stg_lap_tyre_qa numbering) whose earlier lap was green and has no
--    penalty message for the car within one lap -- a green same-tyre stop was
--    joined although the owner ruled those stay split (CD14 (2)).
WITH pit_penalties AS (
    SELECT DISTINCT
        rc.race_id,
        res.driver_id,
        rc.lap_number
    FROM {{ ref('stg_race_control') }} AS rc
    INNER JOIN {{ ref('stg_results') }} AS res
        ON
            rc.race_id = res.race_id
            AND REGEXP_EXTRACT(
                UPPER(rc.message_text),
                '(DRIVE[ -]?THROUGH|STOP ?/ ?GO|STOP-GO|TIME)'
                || ' PENALTY FOR CAR ([0-9]+)',
                2
            ) = res.driver_number
    WHERE rc.lap_number IS NOT NULL
),

laps AS (
    SELECT
        stint_id,
        race_year,
        race_id,
        driver_id,
        stint_number,
        lap_number,
        compound_in_stint,
        age_in_stint,
        (
            NOT is_red_flag_lap
            AND NOT is_safety_car_lap
            AND NOT is_vsc_lap
        ) AS is_green
    FROM {{ ref('int_stint_geometry') }}
    WHERE stint_number IS NOT NULL
),

runs AS (
    SELECT
        stint_id,
        race_year,
        race_id,
        driver_id,
        stint_number,
        ARG_MIN(compound_in_stint, lap_number) AS first_compound,
        ARG_MIN(age_in_stint, lap_number) AS first_age,
        ARG_MAX(compound_in_stint, lap_number) AS last_compound,
        ARG_MAX(age_in_stint, lap_number) AS last_age,
        ARG_MAX(is_green, lap_number) AS ended_green,
        MAX(lap_number) AS last_lap_number
    FROM laps
    GROUP BY stint_id, race_year, race_id, driver_id, stint_number
),

paired AS (
    SELECT
        *,
        LAG(last_compound) OVER w AS prev_compound,
        LAG(last_age) OVER w AS prev_last_age,
        LAG(ended_green) OVER w AS prev_ended_green,
        LAG(last_lap_number) OVER w AS prev_last_lap_number
    FROM runs
    WINDOW w AS (
        PARTITION BY race_year, race_id, driver_id ORDER BY stint_number
    )
),

within AS (
    SELECT
        stint_id,
        lap_number,
        compound_in_stint,
        age_in_stint,
        LAG(compound_in_stint) OVER w AS prev_compound,
        LAG(age_in_stint) OVER w AS prev_age
    FROM laps
    WINDOW w AS (PARTITION BY stint_id ORDER BY lap_number)
),

feed_boundaries AS (
    SELECT
        g.stint_id,
        g.race_id,
        g.driver_id,
        g.lap_number,
        q.stint_number AS feed_stint_number,
        LAG(q.stint_number) OVER w AS prev_feed_stint_number,
        LAG(
            NOT g.is_red_flag_lap
            AND NOT g.is_safety_car_lap
            AND NOT g.is_vsc_lap
        ) OVER w AS prev_lap_green,
        LAG(g.lap_number) OVER w AS prev_lap_number
    FROM {{ ref('int_stint_geometry') }} AS g
    INNER JOIN {{ ref('stg_lap_tyre_qa') }} AS q ON g.lap_id = q.lap_id
    WHERE g.stint_number IS NOT NULL
    WINDOW w AS (PARTITION BY g.stint_id ORDER BY g.lap_number)
)

SELECT
    'unjoined_same_tyre_split' AS check_name,
    stint_id AS detail
FROM paired
WHERE
    prev_compound = first_compound
    AND first_age = prev_last_age + 1
    AND (
        NOT prev_ended_green
        OR EXISTS (
            SELECT 1
            FROM pit_penalties AS pp
            WHERE
                pp.race_id = paired.race_id
                AND pp.driver_id = paired.driver_id
                AND pp.lap_number
                BETWEEN paired.prev_last_lap_number - 1
                AND paired.prev_last_lap_number + 1
        )
    )

UNION ALL

SELECT
    'run_crosses_tyre_change' AS check_name,
    stint_id || ' lap ' || lap_number AS detail
FROM within
WHERE
    prev_compound IS DISTINCT FROM compound_in_stint
    AND prev_compound IS NOT NULL
    OR age_in_stint - prev_age NOT IN (0, 1)

UNION ALL

SELECT
    'green_join_without_penalty' AS check_name,
    fb.stint_id || ' lap ' || fb.lap_number AS detail
FROM feed_boundaries AS fb
WHERE
    fb.feed_stint_number IS DISTINCT FROM fb.prev_feed_stint_number
    AND fb.prev_feed_stint_number IS NOT NULL
    AND fb.prev_lap_green
    AND NOT EXISTS (
        SELECT 1
        FROM pit_penalties AS pp
        WHERE
            pp.race_id = fb.race_id
            AND pp.driver_id = fb.driver_id
            AND pp.lap_number
            BETWEEN fb.prev_lap_number - 1
            AND fb.prev_lap_number + 1
    )
