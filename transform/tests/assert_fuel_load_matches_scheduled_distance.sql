-- T6 + T24, folded into one test per F52 (WI-05: F6, F32, F52).
--
-- F6 (race_lap_count read off the race's own last VALID lap, so fuel encoded how
-- the race ended) and F32 (starting fuel = laps x a hand-set rate with no cap:
-- 134 of 171 races over the FIA limit) hit the same neutralised races, and fixing
-- either alone can hide the other's symptom. So this checks the COMBINATION: the
-- fuel plan must be the scheduled distance burned at a legal load, and that
-- scheduled distance must itself be a plausible race distance.
--
-- 1. every race has a scheduled distance (race_scheduled_laps), and every race
--    with a valid lap has fuel rows;
-- 2. race_lap_count IS the scheduled distance -- not MAX(lap_number) over any
--    lap subset -- and covers every lap actually run (all laps, valid or not);
-- 3. the load a lap's fuel implies at the start (fuel_mass_kg + burn x laps
--    already run) is one number per race, is within the season's FIA limit, and
--    burns to exactly zero over the scheduled laps -- no fuel left in the tank at
--    the scheduled flag and none missing before it;
-- 4. no lap that was run finds the tank empty;
-- 5. scheduled_laps x the venue's lap length is a real race distance (FIA: the
--    fewest laps over 305 km; 260 km at Monaco). Band 250-320 km, wide enough for
--    dim_circuits' one-length-per-slug approximation across layout changes.
--    This is the independent check on the scheduled distance itself.

WITH seed AS (
    SELECT race_id, race_year, scheduled_laps
    FROM {{ ref('race_scheduled_laps') }}
),

races AS (
    SELECT
        race_id,
        MAX(lap_number) AS max_lap_run,
        BOOL_OR(is_valid_lap) AS has_valid_lap
    FROM {{ ref('stg_laps') }}
    GROUP BY race_id
),

fuel_by_race AS (
    SELECT
        race_id,
        ANY_VALUE(race_year) AS race_year,
        MIN(race_lap_count) AS min_race_lap_count,
        MAX(race_lap_count) AS max_race_lap_count,
        MIN(
            fuel_mass_kg + fuel_consumption_rate_kg_per_lap * (lap_number - 1)
        ) AS min_implied_start_kg,
        MAX(
            fuel_mass_kg + fuel_consumption_rate_kg_per_lap * (lap_number - 1)
        ) AS max_implied_start_kg,
        MAX(fuel_consumption_rate_kg_per_lap) AS rate_kg_per_lap,
        MIN(fuel_mass_kg) AS min_fuel_mass_kg
    FROM {{ ref('int_lap_fuel_state') }}
    GROUP BY race_id
)

SELECT
    'race_without_scheduled_distance' AS check_name,
    r.race_id AS detail
FROM races AS r
LEFT JOIN seed AS s ON r.race_id = s.race_id
WHERE s.scheduled_laps IS NULL OR s.scheduled_laps <= 0

UNION ALL

SELECT
    'race_without_fuel_rows' AS check_name,
    r.race_id AS detail
FROM races AS r
LEFT JOIN fuel_by_race AS f ON r.race_id = f.race_id
WHERE r.has_valid_lap AND f.race_id IS NULL

UNION ALL

SELECT
    'race_lap_count_is_not_the_scheduled_distance' AS check_name,
    f.race_id || ': ' || f.min_race_lap_count || '-' || f.max_race_lap_count
    || ' vs scheduled ' || s.scheduled_laps AS detail
FROM fuel_by_race AS f
INNER JOIN seed AS s ON f.race_id = s.race_id
WHERE
    f.min_race_lap_count IS DISTINCT FROM s.scheduled_laps
    OR f.max_race_lap_count IS DISTINCT FROM s.scheduled_laps

UNION ALL

SELECT
    'scheduled_distance_shorter_than_laps_run' AS check_name,
    r.race_id || ': scheduled ' || s.scheduled_laps || ', ran ' || r.max_lap_run
        AS detail
FROM races AS r
INNER JOIN seed AS s ON r.race_id = s.race_id
WHERE s.scheduled_laps < r.max_lap_run

UNION ALL

SELECT
    'implied_start_fuel_not_one_legal_load' AS check_name,
    f.race_id || ': ' || ROUND(f.min_implied_start_kg, 3) || '-'
    || ROUND(f.max_implied_start_kg, 3) || ' kg, limit '
    || {{ fuel_regulatory_max_kg('f.race_year') }} AS detail
FROM fuel_by_race AS f
WHERE
    f.max_implied_start_kg IS NULL
    OR f.max_implied_start_kg - f.min_implied_start_kg > 1e-6
    OR {{ fuel_regulatory_max_kg('f.race_year') }} IS NULL
    OR f.max_implied_start_kg > {{ fuel_regulatory_max_kg('f.race_year') }} + 1e-6

UNION ALL

SELECT
    'start_fuel_does_not_burn_to_zero_over_scheduled_laps' AS check_name,
    f.race_id || ': ' || ROUND(f.max_implied_start_kg, 3) || ' kg vs '
    || ROUND(f.rate_kg_per_lap * s.scheduled_laps, 3) || ' kg burned' AS detail
FROM fuel_by_race AS f
INNER JOIN seed AS s ON f.race_id = s.race_id
WHERE ABS(f.max_implied_start_kg - f.rate_kg_per_lap * s.scheduled_laps) > 1e-6

UNION ALL

SELECT
    'tank_empty_on_a_lap_that_was_run' AS check_name,
    f.race_id AS detail
FROM fuel_by_race AS f
WHERE f.min_fuel_mass_kg <= 0

UNION ALL

SELECT
    'scheduled_distance_not_a_race_distance' AS check_name,
    s.race_id || ': ' || s.scheduled_laps || ' laps x ' || d.lap_length_km
    || ' km' AS detail
FROM seed AS s
INNER JOIN {{ ref('race_to_track') }} AS rt ON s.race_id = rt.race_id
INNER JOIN {{ ref('dim_circuits') }} AS d ON rt.track_id = d.circuit_key
WHERE s.scheduled_laps * d.lap_length_km NOT BETWEEN 250 AND 320
