-- int_physical_ahead_pairs: summed over leaders, a follower-lap's pair seconds should equal
-- int_lap_physical_ahead.time_within_1s_phys_s, because both sum the same dt_s over the same samples
-- (same_lap, gap_s < 1 s). WARN, not error: this cross-checks two recomputations of the same per-sample build,
-- and a mismatch means the two models disagree on the definition, which is worth seeing, not hiding.
-- Valid_same_lap laps only (the lap model NULLs the column elsewhere). Flagged when the pair total is ABOVE the
-- lap total (it can never legitimately exceed it) or more than 1e-3 s BELOW it (a close sample with no leader,
-- which build_race_samples rules out). Tolerance 1e-3 s: the lap column and each pair row are rounded to 4 dp, so
-- a lap with k leaders differs by at most (k + 1) * 5e-5 s, well under 1e-3.
{{ config(severity='warn') }}
WITH pair_lap AS (
    SELECT race_id, follower_driver_id AS driver_id, lap_number, SUM(seconds_within_1s) AS pair_s
    FROM {{ ref('int_physical_ahead_pairs') }}
    GROUP BY race_id, follower_driver_id, lap_number
)
SELECT l.race_id, l.driver_id, l.lap_number, l.time_within_1s_phys_s, p.pair_s
FROM {{ ref('int_lap_physical_ahead') }} AS l
LEFT JOIN pair_lap AS p
    ON l.race_id = p.race_id AND l.driver_id = p.driver_id AND l.lap_number = p.lap_number
WHERE l.validity_class = 'valid_same_lap'
    AND ABS(COALESCE(p.pair_s, 0) - l.time_within_1s_phys_s) > 1e-3
