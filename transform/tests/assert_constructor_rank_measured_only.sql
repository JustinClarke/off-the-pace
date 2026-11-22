-- constructor_rank is a RANK over constructors' measured-lap means only.
-- Recomputes it from fct_lap_residuals (ml_eligible AND NOT filled) per
-- race and per season and compares both marts: NULL rank with status
-- NO_MEASURED_LAPS where no measured lap exists, a non-NULL rank with status
-- OK otherwise, and the recomputed rank equal to the stored one. Returns
-- violating rows. No race id is required (CI fixture safe).
WITH race_ref AS (
    SELECT
        race_id AS unit_id,
        constructor_id,
        RANK() OVER (PARTITION BY race_id ORDER BY AVG(constructor_component_s))
            AS ref_rank
    FROM {{ ref('fct_lap_residuals') }}
    WHERE ml_eligible = TRUE AND NOT constructor_pace_is_filled
    GROUP BY race_id, constructor_id
),

season_ref AS (
    SELECT
        CAST(race_year AS VARCHAR) AS unit_id,
        constructor_id,
        RANK() OVER (PARTITION BY race_year ORDER BY AVG(constructor_component_s))
            AS ref_rank
    FROM {{ ref('fct_lap_residuals') }}
    WHERE ml_eligible = TRUE AND NOT constructor_pace_is_filled
    GROUP BY race_year, constructor_id
),

mart_rows AS (
    SELECT
        'race' AS grain,
        m.race_id AS unit_id,
        m.driver_id,
        m.constructor_id,
        m.constructor_rank,
        m.constructor_rank_status,
        m.constructor_measured_laps_n,
        r.ref_rank
    FROM {{ ref('mart_race_driver_summary') }} AS m
    LEFT JOIN race_ref AS r
        ON m.race_id = r.unit_id AND m.constructor_id = r.constructor_id
    UNION ALL
    SELECT
        'season' AS grain,
        CAST(m.race_year AS VARCHAR) AS unit_id,
        m.driver_id,
        m.constructor_id,
        m.constructor_rank,
        m.constructor_rank_status,
        m.constructor_measured_laps_n,
        r.ref_rank
    FROM {{ ref('mart_driver_season_summary') }} AS m
    LEFT JOIN season_ref AS r
        ON CAST(m.race_year AS VARCHAR) = r.unit_id
        AND m.constructor_id = r.constructor_id
)

SELECT *
FROM mart_rows
WHERE
    constructor_rank IS DISTINCT FROM ref_rank
    OR (
        constructor_measured_laps_n = 0
        AND (constructor_rank IS NOT NULL OR constructor_rank_status <> 'NO_MEASURED_LAPS')
    )
    OR (
        constructor_measured_laps_n > 0
        AND (constructor_rank IS NULL OR constructor_rank_status <> 'OK')
    )
