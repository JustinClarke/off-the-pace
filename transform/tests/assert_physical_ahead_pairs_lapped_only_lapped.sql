-- Every row of int_physical_ahead_pairs_lapped must sit on a lap that int_lap_physical_ahead classes as lapped.
-- Returns offending rows (including pairs with no lap row at all).
{{ config(severity='error') }}
SELECT p.race_id, p.follower_driver_id, p.leader_driver_id, p.lap_number, l.is_lapped_lap
FROM {{ ref('int_physical_ahead_pairs_lapped') }} AS p
LEFT JOIN {{ ref('int_lap_physical_ahead') }} AS l
    ON p.race_id = l.race_id AND p.follower_driver_id = l.driver_id AND p.lap_number = l.lap_number
WHERE l.is_lapped_lap IS NOT TRUE
