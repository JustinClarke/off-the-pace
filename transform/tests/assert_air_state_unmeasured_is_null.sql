-- CO-04 / FD6 (ruled B: a missing measurement is NULL, not a guess).
-- A lap with no measured gap to the car ahead is free air only if the car is
-- leading. For anyone else the air state is unknown, and int_lap_air_state
-- must say so with NULL rather than 'free_air' / 0.0.
--
-- One row per failure:
--   'non_leader_guessed' -- a non-leader (or unknown-position) lap with no
--     measured gap that still carries an air state, a dirty-air term, a tow
--     benefit, an exposure time or a thermal load.
--   'leader_changed' -- a leader lap with no measured gap that is no longer
--     'free_air' with 0.0 share / tow / exposure, which is what it always
--     was. Thermal loads are left out of this side on purpose: a leader lap
--     whose 5- or 10-lap lookback includes an unmeasured lap of the same
--     stint has an unknown load, and NULL is right there.
--
-- Leader = end-of-lap race position 1 (stg_laps.position), the same
-- definition the model uses.
{{ config(severity='error') }}

WITH laps AS (
    SELECT
        a.lap_id,
        a.race_year,
        a.race_id,
        a.driver_id,
        a.lap_number,
        a.air_state_dominant,
        a.dirty_air_share_lap,
        a.tow_benefit_lap_s,
        a.time_in_dirty_air_s,
        a.dirty_air_thermal_load_surface,
        a.dirty_air_thermal_load_bulk,
        COALESCE(l.position = 1, FALSE) AS is_race_leader
    FROM {{ ref('int_lap_air_state') }} AS a
    LEFT JOIN {{ ref('stg_laps') }} AS l ON a.lap_id = l.lap_id
    WHERE a.min_gap_s IS NULL
)

SELECT
    'non_leader_guessed' AS failure,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    air_state_dominant,
    dirty_air_share_lap
FROM laps
WHERE
    NOT is_race_leader
    AND (
        air_state_dominant IS NOT NULL
        OR dirty_air_share_lap IS NOT NULL
        OR tow_benefit_lap_s IS NOT NULL
        OR time_in_dirty_air_s IS NOT NULL
        OR dirty_air_thermal_load_surface IS NOT NULL
        OR dirty_air_thermal_load_bulk IS NOT NULL
    )

UNION ALL

SELECT
    'leader_changed' AS failure,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    air_state_dominant,
    dirty_air_share_lap
FROM laps
WHERE
    is_race_leader
    AND (
        air_state_dominant IS DISTINCT FROM 'free_air'
        OR dirty_air_share_lap IS DISTINCT FROM 0.0
        OR tow_benefit_lap_s IS DISTINCT FROM 0.0
        OR time_in_dirty_air_s IS DISTINCT FROM 0.0
    )
