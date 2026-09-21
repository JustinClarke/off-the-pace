-- 00d: the three corner phases must share ONE sign convention, and the index
-- must be their plain sum.
--
-- WHAT WENT WRONG. int_corner_skill_residuals built braking_loss_s as
-- (own braking_point_m - field median) * dt_per_dm. braking_point_m is the
-- distance along the lap of the first sample on the brakes, so a LARGER value
-- means braking LATER, which is faster -- the column named "loss" was measuring
-- a gain. The other two phases are built the other way round: positive
-- mid_corner_residual_s is apex speed BELOW the field median, positive
-- exit_residual_s is full throttle regained LATER, both losses.
-- mart_corner_skill_driver then summed all three z-scores into
-- corner_skill_index and ordered ASC, with no negation anywhere in between, and
-- app/src/features/corner-phase-skill ranked a public leaderboard on it. One of
-- three terms was inverted the whole time.
--
-- WHY THE EXISTING TESTS COULD NOT SEE IT. assert_corner_closure checks that
-- the three columns sum to corner_residual_total_s -- true under either sign.
-- assert_corner_inputs_lap_grain_closure checks COUNTs. The trailing-window
-- test checks the NULL pattern on lap 2. Every one of them is sign-agnostic,
-- which is how a sign defect survived two rebuilds (02g, 02c) of this model.
--
-- ASSERTION 1 -- braking_sign_convention (corner grain).
-- The direction is pinned against the RAW GEOMETRY in int_corner_metrics, not
-- against a recomputed median, so the test does not verify the construction
-- using the construction. Within one (race_year, race_id, corner_name,
-- lap_number) group every row is scored against the SAME trailing field median
-- M, and dt_per_dm = 1 / (s2 trap speed in m/s) is strictly positive. So under
-- the correct convention braking_loss_s > 0 implies braking_point_m < M and
-- braking_loss_s < 0 implies braking_point_m > M: the sign is a step function
-- of the braking point at M. Therefore, in any group containing both signs,
-- EVERY row claiming lost time must brake EARLIER than every row claiming
-- gained time.
-- A group where the latest-braking "loss" row sits beyond the earliest-braking
-- "gain" row is a sign inversion.
--
-- The test needs no knowledge of M or of dt_per_dm, only that dt_per_dm > 0.
--
-- NON-VACUOUS, measured on data/dev.duckdb: under the old (own - field)
-- definition this returned 98,769 violating groups out of the 98,769 groups
-- that contain both signs at all -- a 100% failure rate. Under (field-own): 0.
--
-- ASSERTION 2 -- index_is_the_plain_sum (mart grain).
-- The other place the defect could have been "fixed" was inside the mart, by
-- negating the braking z at the point of summation. 00d ruled against that: the
-- app prints all three z-scores next to the index under a legend that says the
-- index sums them, so a hidden negation makes a published table stop adding up.
-- This assertion pins that ruling -- corner_skill_index must equal the sum of
-- the three published z-scores to within their own rounding (each is ROUND(.,2)
-- and the index is ROUND(sum, 2), so 0.02 covers the worst case).

WITH braking_geometry AS (
    SELECT
        csr.race_year,
        csr.race_id,
        csr.corner_name,
        csr.lap_number,
        csr.braking_loss_s,
        cm.braking_point_m
    FROM {{ ref('int_corner_skill_residuals') }} AS csr
    INNER JOIN {{ ref('int_corner_metrics') }} AS cm
        ON
            csr.race_year = cm.race_year
            AND csr.race_id = cm.race_id
            AND csr.driver_id = cm.driver_id
            AND csr.lap_number = cm.lap_number
            AND csr.corner_name = cm.corner_name
    WHERE
        csr.braking_loss_s IS NOT NULL
        AND cm.braking_point_m IS NOT NULL
),

braking_extremes AS (
    SELECT
        race_year,
        race_id,
        corner_name,
        lap_number,
        -- The latest braking point among rows claiming to have LOST time.
        MAX(braking_point_m) FILTER (
            WHERE braking_loss_s > 0
        ) AS latest_brake_among_losses_m,
        -- The earliest braking point among rows claiming to have GAINED time.
        MIN(braking_point_m) FILTER (
            WHERE braking_loss_s < 0
        ) AS earliest_brake_among_gains_m
    FROM braking_geometry
    GROUP BY race_year, race_id, corner_name, lap_number
)

SELECT
    'braking_sign_convention' AS check_name,
    race_year,
    race_id,
    corner_name,
    CAST(lap_number AS VARCHAR) AS subject,
    latest_brake_among_losses_m AS value_a,
    earliest_brake_among_gains_m AS value_b,
    'a row credited with lost time braked LATER than a row credited with '
    || 'gained time: braking_loss_s has the inverted sign' AS issue
FROM braking_extremes
WHERE
    latest_brake_among_losses_m IS NOT NULL
    AND earliest_brake_among_gains_m IS NOT NULL
    AND latest_brake_among_losses_m > earliest_brake_among_gains_m

UNION ALL

SELECT
    'index_is_the_plain_sum' AS check_name,
    race_year,
    CAST(NULL AS VARCHAR) AS race_id,
    CAST(NULL AS VARCHAR) AS corner_name,
    driver_id AS subject,
    corner_skill_index AS value_a,
    braking_skill_z + mid_corner_skill_z + exit_skill_z AS value_b,
    'corner_skill_index is not the sum of the three published z-scores: a '
    || 'phase is being negated or reweighted at summation' AS issue
FROM {{ ref('mart_corner_skill_driver') }}
WHERE
    corner_skill_index IS NOT NULL
    AND ABS(
        corner_skill_index
        - (braking_skill_z + mid_corner_skill_z + exit_skill_z)
    ) > 0.02
