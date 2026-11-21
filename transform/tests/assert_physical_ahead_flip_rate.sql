-- int_lap_physical_ahead: car-ahead identity flips between consecutive samples <= 1 s apart, per race,
-- above 0.5% of pairs (experiment 26 P4). WARN, not error: this is a KNOWN LIMIT, not a bug to hide.
-- Expected to warn on most 2018 and 2019 races (2018-2019 pos samples are 0.30 s apart, against 0.22-0.24 s
-- from 2020; the flips sit mostly in side_by_side / overlapping / lap1 / lapped samples whose laps are already
-- excluded, and valid_same_lap laps flip 0.04-0.06%) and on a few 2023-2025 races such as Canada 2025
-- (0.64%, exp 27; mostly lapped and overlapping pairs, exp 28). The rate is also carried as
-- int_traffic_exposure_race.identity_flip_rate.
{{ config(severity='warn') }}
SELECT
    race_id,
    SUM(n_ahead_pairs) AS pairs,
    SUM(n_ahead_flips)::DOUBLE / NULLIF(SUM(n_ahead_pairs), 0) AS flip_rate
FROM {{ ref('int_lap_physical_ahead') }}
GROUP BY race_id
HAVING SUM(n_ahead_flips)::DOUBLE / NULLIF(SUM(n_ahead_pairs), 0) >= 0.005
