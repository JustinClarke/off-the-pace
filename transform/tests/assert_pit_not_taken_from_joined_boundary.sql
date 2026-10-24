{{ config(severity='error', tags=['simulation', 'strategy']) }}
-- CO-09 knock-on, found by the CO-17 audit. Since the tyre-run key a stint can
-- span several FastF1 fragments joined across a same-tyre pit-in (safety-car
-- drive-through, red-flag pit, penalty). Those stops did not change the tyres,
-- so int_pit_strategy_value must never take one as the stint's stop. Fails on
-- any stint whose actual_pit_lap lies before its last fragment starts. Before
-- the fix: 119 rows (111 race_end, 8 retirement runs graded against a
-- drive-through).
WITH fragment_laps AS (
    SELECT
        sg.stint_id,
        sg.lap_number,
        qa.stint_number AS fragment_stint_number,
        MAX(qa.stint_number) OVER (PARTITION BY sg.stint_id)
            AS last_fragment_stint_number
    FROM {{ ref('int_stint_geometry') }} AS sg
    INNER JOIN {{ ref('stg_lap_tyre_qa') }} AS qa ON sg.lap_id = qa.lap_id
),

last_fragment AS (
    SELECT
        stint_id,
        MIN(lap_number) AS last_fragment_first_lap
    FROM fragment_laps
    WHERE fragment_stint_number = last_fragment_stint_number
    GROUP BY stint_id
)

SELECT
    v.stint_id,
    v.actual_pit_lap,
    lf.last_fragment_first_lap,
    er.stint_end_cause
FROM {{ ref('int_pit_strategy_value') }} AS v
INNER JOIN last_fragment AS lf ON v.stint_id = lf.stint_id
INNER JOIN {{ ref('int_stint_end_regime') }} AS er ON v.stint_id = er.stint_id
WHERE v.actual_pit_lap < lf.last_fragment_first_lap
