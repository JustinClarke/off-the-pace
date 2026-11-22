-- int_lap_rain_state has exactly one row for every (race_year, race_id, lap_number)
-- of stg_laps: no lap is lost (a lap with no weather is NO_WEATHER, not absent) and
-- the weather join does not multiply laps. Also checks that the consumers that read
-- the state through int_lap_residual_decomposed see the same value as the model and
-- keep one row per lap_id (the join on a unique race-lap key cannot duplicate laps).
-- Returns offending rows; passes when empty.
WITH spine AS (
    SELECT DISTINCT race_year, race_id, lap_number
    FROM {{ ref('stg_laps') }}
),

state AS (
    SELECT race_year, race_id, lap_number, COUNT(*) AS n_rows
    FROM {{ ref('int_lap_rain_state') }}
    GROUP BY race_year, race_id, lap_number
),

residual_dupes AS (
    SELECT lap_id, COUNT(*) AS n_rows
    FROM {{ ref('int_lap_residual_decomposed') }}
    GROUP BY lap_id
    HAVING COUNT(*) > 1
)

SELECT
    CAST(sp.race_year AS VARCHAR) || '|' || sp.race_id || '|' || CAST(sp.lap_number AS VARCHAR) AS lap_key,
    COALESCE(st.n_rows, 0) AS n_rows,
    'spine lap missing or duplicated in int_lap_rain_state' AS reason
FROM spine AS sp
LEFT JOIN state AS st
    ON
        sp.race_year = st.race_year
        AND sp.race_id = st.race_id
        AND sp.lap_number = st.lap_number
WHERE COALESCE(st.n_rows, 0) <> 1

UNION ALL

SELECT
    CAST(st.race_year AS VARCHAR) || '|' || st.race_id || '|' || CAST(st.lap_number AS VARCHAR),
    st.n_rows,
    'int_lap_rain_state lap not in stg_laps'
FROM state AS st
LEFT JOIN spine AS sp
    ON
        st.race_year = sp.race_year
        AND st.race_id = sp.race_id
        AND st.lap_number = sp.lap_number
WHERE sp.lap_number IS NULL

UNION ALL

SELECT lap_id, n_rows, 'int_lap_residual_decomposed duplicated lap_id after rain join'
FROM residual_dupes

UNION ALL

SELECT
    r.lap_id,
    1,
    'int_lap_residual_decomposed rain_state differs from int_lap_rain_state'
FROM {{ ref('int_lap_residual_decomposed') }} AS r
LEFT JOIN {{ ref('int_lap_rain_state') }} AS s
    ON
        r.race_year = s.race_year
        AND r.race_id = s.race_id
        AND r.lap_number = s.lap_number
WHERE r.rain_state IS DISTINCT FROM COALESCE(s.rain_state, 'NO_WEATHER')
