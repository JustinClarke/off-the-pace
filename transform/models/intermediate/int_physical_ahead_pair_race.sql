-- int_physical_ahead_pair_race.sql · intermediate · grain: one row per (race_id, follower, leader)
--
-- MEASUREMENT ONLY. Total seconds one car spent within 1 s behind a named other car over a race, summed from
-- int_physical_ahead_pairs on VALID laps only (validity_class = 'valid_same_lap'). Non-valid laps are never
-- counted here, and are never read as clear air. Descriptive columns only: no time loss, no dirty-air seconds,
-- no column that says or implies that following made a lap slow. Not wired to any page.
--
--   seconds_within_1s          valid laps, including SC / VSC / red-flag laps (the field bunches there)
--   seconds_within_1s_green    valid laps known NOT to be neutralised (is_neutralised_lap IS FALSE, from
--                              int_lap_physical_ahead). A lap whose flag is NULL is unknown, so it is left out of
--                              the green sum on purpose (and stays in seconds_within_1s); it is never read as green.
--
-- A pair with no valid lap holding a sample under 1 s has no row. A row can still carry 0 seconds (a lone sample whose
-- dt_s is 0, e.g. the last sample of a lap), so a row means 'at least one close sample', not 'seconds > 0'. The pair-level car-ahead identity flips of
-- int_lap_physical_ahead apply (a flip splits one stretch of following across two pairs).
{{ config(materialized='table') }}

SELECT
    p.race_id,
    MIN(p.season) AS season,
    p.follower_driver_id,
    p.leader_driver_id,
    ROUND(SUM(p.seconds_within_1s), 4) AS seconds_within_1s,
    ROUND(SUM(p.seconds_within_1s) FILTER (WHERE l.is_neutralised_lap IS FALSE), 4) AS seconds_within_1s_green,
    COUNT(DISTINCT p.lap_number) AS n_laps_within_1s,
    SUM(p.n_samples_within_1s) AS n_samples_within_1s,
    MIN(p.min_gap_s) AS min_gap_s
FROM {{ ref('int_physical_ahead_pairs') }} AS p
LEFT JOIN {{ ref('int_lap_physical_ahead') }} AS l
    ON p.race_id = l.race_id AND p.follower_driver_id = l.driver_id AND p.lap_number = l.lap_number
WHERE p.validity_class = 'valid_same_lap'
GROUP BY p.race_id, p.follower_driver_id, p.leader_driver_id
