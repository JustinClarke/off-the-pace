-- T38 (F48, WI-15a). dirty_air_share_lap is non-increasing in the measured S2
-- gap: following closer can never make a lap LESS dirty-air.
--
-- Before F48, int_lap_air_state tested DRS before the gap in S2, so an S2
-- median gap under 1.0 s with DRS open anywhere in the third was coded
-- 'drs_train' (share 0) while 1.0-1.5 s was coded 'dirty_air' (share 1).
-- Binned by S2 gap, the share ran ~0.51-0.70 below 1 s, then 1.000 at
-- 1.0-1.5 s: 11,657 of 25,927 training-eligible sub-1 s laps (45%) were billed
-- as clean air, and dirty_air_share_lap is both a contract feature and, lagged
-- one lap, the treatment in theta_air (round3/r3_dirty_air_drs_train.py).
--
-- The check is on the relation between the model's OUTPUT share and the gap
-- it measured (s2_gap_median_s), not on the CASE that produces it: 0.1 s bins
-- over 0-3 s, and every bin's share must be >= the share of every bin at a
-- larger gap. Global, not adjacent-pairs: a dip that recovers two bins later
-- is still a violation. Exact up to float noise -- on non-neutralised laps the
-- share is a deterministic function of the gap, so any violation is logic.
-- SC/VSC/red-flag laps are excluded because the model zeroes the share there
-- by design (no aero load at neutralised pace), whatever the gap.
{{ config(severity='error') }}

WITH laps AS (
    SELECT
        a.s2_gap_median_s,
        a.dirty_air_share_lap
    FROM {{ ref('int_lap_air_state') }} AS a
    INNER JOIN {{ ref('int_stint_geometry') }} AS g ON a.lap_id = g.lap_id
    WHERE
        a.s2_gap_median_s IS NOT NULL
        AND a.s2_gap_median_s < 3.0
        AND NOT COALESCE(g.is_safety_car_lap, FALSE)
        AND NOT COALESCE(g.is_vsc_lap, FALSE)
        AND NOT COALESCE(g.is_red_flag_lap, FALSE)
),

bins AS (
    SELECT
        FLOOR(s2_gap_median_s * 10) / 10.0 AS gap_bin_s,
        COUNT(*) AS n_laps,
        AVG(dirty_air_share_lap) AS share_dirty
    FROM laps
    GROUP BY 1
),

with_further AS (
    SELECT
        gap_bin_s,
        n_laps,
        share_dirty,
        MAX(share_dirty) OVER (
            ORDER BY gap_bin_s DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS max_share_at_larger_gap
    FROM bins
)

SELECT
    gap_bin_s,
    n_laps,
    share_dirty,
    max_share_at_larger_gap
FROM with_further
WHERE share_dirty < max_share_at_larger_gap - 1e-9
