-- T44 (WI-16a): the rolling ~5-lap window never reaches forward.
--
-- fct_driver_isolation_lap's windows are a RANGE frame on lap_number, partitioned by
-- stint. This test recomputes every window by a different mechanism -- an explicit
-- self-join on laps of the same stint with lap_number in
-- [l - (var('isolation_window_laps') - 1), l] -- and requires the stored values to match
-- (pattern: assert_corner_trailing_window_no_forward_reach). A frame that reached forward,
-- or that crossed a stint boundary, would see laps the recomputation cannot, and differ.
--
-- Checked, each to 1e-9: window_n_laps, the two window counts (pure and pair-laps), and
-- the two window values (pure over non-extrapolated laps and relative as
-- SUM(relative * n_peers) / SUM(n_peers)), including that each value is NULL exactly when
-- its count is below var('isolation_window_min_laps').

{%- set w = var('isolation_window_laps') - 1 %}
{%- set min_n = var('isolation_window_min_laps') %}

WITH laps AS (
    SELECT
        lap_id,
        stint_id,
        lap_number,
        pure_skill_gain_s,
        pure_is_extrapolated,
        relative_pace_gain_s,
        n_peers
    FROM {{ ref('fct_driver_isolation_lap') }}
),

recomputed AS (
    SELECT
        focal.lap_id,
        COUNT(*) AS n_laps,
        COUNT(CASE WHEN NOT prior.pure_is_extrapolated THEN prior.pure_skill_gain_s END) AS n_pure,
        AVG(CASE WHEN NOT prior.pure_is_extrapolated THEN prior.pure_skill_gain_s END) AS pure_mean,
        SUM(prior.n_peers) AS n_pair_laps,
        SUM(prior.relative_pace_gain_s * prior.n_peers) AS relative_weighted_sum
    FROM laps AS focal
    INNER JOIN laps AS prior
        ON
            focal.stint_id = prior.stint_id
            AND prior.lap_number <= focal.lap_number
            AND prior.lap_number >= focal.lap_number - {{ w }}
    GROUP BY focal.lap_id
),

expected AS (
    SELECT
        lap_id,
        n_laps,
        n_pure,
        n_pair_laps,
        CASE WHEN n_pure >= {{ min_n }} THEN pure_mean END AS pure_5lap,
        CASE WHEN n_pair_laps >= {{ min_n }} THEN relative_weighted_sum / n_pair_laps END
            AS relative_5lap
    FROM recomputed
)

SELECT
    m.lap_id,
    m.window_n_laps,
    e.n_laps,
    m.pure_skill_5lap_gain_s,
    e.pure_5lap,
    m.relative_pace_5lap_gain_s,
    e.relative_5lap
FROM {{ ref('fct_driver_isolation_lap') }} AS m
INNER JOIN expected AS e
    ON m.lap_id = e.lap_id
WHERE
    m.window_n_laps != e.n_laps
    OR m.window_n_pure_laps != e.n_pure
    OR m.window_n_pair_laps != e.n_pair_laps
    OR (m.pure_skill_5lap_gain_s IS NULL) != (e.pure_5lap IS NULL)
    OR (m.relative_pace_5lap_gain_s IS NULL) != (e.relative_5lap IS NULL)
    OR ABS(m.pure_skill_5lap_gain_s - e.pure_5lap) > 1e-9
    OR ABS(m.relative_pace_5lap_gain_s - e.relative_5lap) > 1e-9
