-- T40 (WI-16a): the isolation panel is field-centred per (race, lap), on a real field.
--
-- y_s = x_s - (the lap's Ω field median of x_s), so on every (race, lap) the median of
-- y_s is 0 up to float rounding, and every cell holds at least
-- var('isolation_min_field_n') Ω laps. field_n is counted before the floor is applied and
-- the floor keeps or drops whole cells, so it must also equal the number of panel rows on
-- the cell. A failure of the first check means the centring is not over Ω (a different
-- row set, or a mean where a median was meant); of the second or third, that the floor
-- is not doing what the var says.
--
-- This is what lets every per-(race, lap) term -- field base, fuel, rubber, ambient --
-- cancel out of the ratings (T41 checks that directly).

WITH cells AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        MEDIAN(y_s) AS median_y_s,
        COUNT(*) AS n_rows,
        MIN(field_n) AS min_field_n,
        MAX(field_n) AS max_field_n
    FROM {{ ref('int_driver_isolation_lap_panel') }}
    GROUP BY race_year, race_id, lap_number
)

SELECT
    race_year,
    race_id,
    lap_number,
    median_y_s,
    n_rows,
    min_field_n,
    max_field_n
FROM cells
WHERE
    ABS(median_y_s) >= 1e-9
    OR min_field_n < {{ var('isolation_min_field_n') }}
    OR min_field_n != max_field_n
    OR min_field_n != n_rows
