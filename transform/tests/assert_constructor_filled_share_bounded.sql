-- constructor_filled_share is in [0, 1] and equals 1.0 exactly when
-- constructor_measured_laps_n is 0 (and the constructor has ml_eligible
-- laps, so the share exists). Both marts. Returns violating rows.
WITH mart_rows AS (
    SELECT
        'race' AS grain,
        race_id AS unit_id,
        driver_id,
        constructor_filled_share,
        constructor_measured_laps_n
    FROM {{ ref('mart_race_driver_summary') }}
    UNION ALL
    SELECT
        'season' AS grain,
        CAST(race_year AS VARCHAR) AS unit_id,
        driver_id,
        constructor_filled_share,
        constructor_measured_laps_n
    FROM {{ ref('mart_driver_season_summary') }}
)

SELECT *
FROM mart_rows
WHERE
    constructor_filled_share < 0
    OR constructor_filled_share > 1
    OR (
        constructor_measured_laps_n = 0
        AND constructor_filled_share IS DISTINCT FROM 1.0
        AND constructor_filled_share IS NOT NULL
    )
    OR (
        constructor_measured_laps_n > 0
        AND (
            constructor_filled_share IS NULL
            OR constructor_filled_share = 1.0
        )
    )
