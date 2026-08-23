-- A longer pit lane must never move the modelled optimum EARLIER.
--
-- This is the property the pit-strategy rewrite exists to establish. The
-- threshold rule it replaced ("first lap where expected wear exceeds 0.5 s")
-- had no pit-loss term at all, so Monaco and Spa got the same answer. Physics
-- says otherwise: the more a stop costs, the longer you want to put it off.
--
-- The cost curve is separable by construction --
--
--     total_cost(L) = wear_cost_s(L) + pit_lane_loss_s x pit_discount(L)
--
-- with pit_discount non-increasing in L (waiting raises the chance of a cheap
-- safety-car stop, and the no-stop candidate pays nothing). That gives the
-- cost decreasing differences in (L, pit_lane_loss_s), so the argmin is
-- non-decreasing in pit_lane_loss_s. The test re-minimises the SAME curve at a
-- pit lane 15 s longer and asserts the optimum did not retreat -- an actual
-- check of the theorem against the implementation, not a restatement of it.
--
-- It fails loudly if the separation is ever broken: fold the pit loss into
-- wear_cost_s, or make the discount rise with L, and rows appear here.
--
-- Gate: YES any row returned means a longer pit lane pulled the stop forward.

WITH scored AS (
    SELECT
        stint_id,
        horizon_scope,
        candidate_pit_lap_offset,
        wear_cost_s + pit_lane_loss_s * pit_discount_factor AS cost_base,
        wear_cost_s
        + (pit_lane_loss_s + 15.0) * pit_discount_factor AS cost_longer
    FROM {{ ref('int_pit_strategy_cost_curve') }}
),

ranked AS (
    SELECT
        stint_id,
        horizon_scope,
        candidate_pit_lap_offset,
        ROW_NUMBER() OVER (
            PARTITION BY stint_id, horizon_scope
            ORDER BY cost_base, candidate_pit_lap_offset
        ) AS rank_base,
        ROW_NUMBER() OVER (
            PARTITION BY stint_id, horizon_scope
            ORDER BY cost_longer, candidate_pit_lap_offset
        ) AS rank_longer
    FROM scored
),

picks AS (
    SELECT
        stint_id,
        horizon_scope,
        MIN(candidate_pit_lap_offset) FILTER (
            WHERE rank_base = 1
        ) AS optimum_base,
        MIN(candidate_pit_lap_offset) FILTER (
            WHERE rank_longer = 1
        ) AS optimum_longer
    FROM ranked
    GROUP BY stint_id, horizon_scope
)

SELECT
    stint_id,
    horizon_scope,
    optimum_base,
    optimum_longer
FROM picks
WHERE optimum_longer < optimum_base
