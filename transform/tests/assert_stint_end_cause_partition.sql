-- stint_end_cause must partition the stint population exactly as its class
-- names read, and it must do so under the declared precedence: censoring
-- outranks regime, and within an uncensored stint red_flag > safety_car > vsc
-- > green. Both halves are easy to lose silently. Reorder the CASE in
-- int_stint_end_regime and 276 stints whose final lap carries red AND safety
-- car change class with nothing failing; let the censoring split fall below
-- the regime split and every stint that ended under a deployment stops being
-- a race_end or a retirement.
--
-- The derivation below is independent of the model's CTEs. It reaches the
-- stint's final lap through MAX(lap_number) rather than a row-number over
-- lap_in_stint, and rebuilds the censoring window and the running-at-the-flag
-- test from staging, so it fails if either definition drifts rather than
-- moving with it.
WITH final_lap_number AS (
    SELECT
        stint_id,
        MAX(lap_number) AS end_lap_number
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY stint_id
),

final_lap AS (
    SELECT
        g.stint_id,
        g.race_year,
        g.race_id,
        g.driver_id,
        g.stint_number,
        g.lap_number,
        g.is_red_flag_lap,
        g.is_safety_car_lap,
        g.is_vsc_lap
    FROM {{ ref('int_stint_geometry') }} AS g
    INNER JOIN final_lap_number AS f
        ON g.stint_id = f.stint_id AND g.lap_number = f.end_lap_number
),

race_distance AS (
    SELECT
        race_year,
        race_id,
        MAX(lap_number) AS race_final_lap
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY race_year, race_id
),

stint_ordinals AS (
    SELECT DISTINCT
        stint_id,
        race_id,
        driver_id,
        stint_number
    FROM {{ ref('int_stint_geometry') }}
),

expected AS (
    SELECT
        fl.stint_id,
        CASE
            WHEN fl.stint_number IS NULL THEN NULL
            WHEN
                COALESCE(so.stint_number, -1)
                = MAX(COALESCE(so.stint_number, -1))
                    OVER (PARTITION BY so.race_id, so.driver_id)
                THEN
                    CASE
                        WHEN
                            COALESCE(r.status, '') IN ('Finished', 'Lapped')
                            OR COALESCE(r.status, '') LIKE '+%Lap%'
                            OR (
                                COALESCE(r.status, '') = 'Disqualified'
                                AND fl.lap_number + 1 >= rd.race_final_lap
                            )
                            THEN 'race_end'
                        ELSE 'retirement'
                    END
            WHEN fl.is_red_flag_lap THEN 'red'
            WHEN fl.is_safety_car_lap THEN 'sc_pit'
            WHEN fl.is_vsc_lap THEN 'vsc_pit'
            ELSE 'green_pit'
        END AS expected_cause
    FROM final_lap AS fl
    INNER JOIN stint_ordinals AS so ON fl.stint_id = so.stint_id
    INNER JOIN race_distance AS rd
        ON fl.race_year = rd.race_year AND fl.race_id = rd.race_id
    LEFT JOIN {{ ref('stg_results') }} AS r
        ON
            fl.race_year = r.race_year
            AND fl.race_id = r.race_id
            AND fl.driver_id = r.driver_id
)

SELECT
    m.stint_id,
    m.is_censored_stint,
    m.end_regime,
    m.stint_end_cause AS actual_cause,
    e.expected_cause
FROM {{ ref('int_stint_end_regime') }} AS m
INNER JOIN expected AS e ON m.stint_id = e.stint_id
WHERE m.stint_end_cause IS DISTINCT FROM e.expected_cause
