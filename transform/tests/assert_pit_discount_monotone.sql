-- The safety-car pit discount must be non-increasing in the candidate lap.
--
-- The mechanism underneath assert_pit_loss_pushes_optimum_later. Running one
-- lap longer can only raise the cumulative chance that a caution has already
-- appeared, so the expected cost of the stop can only fall:
--
--     pit_discount(L) = 1 - (1 - m) x (1 - (1 - h)^L)
--
-- monotone as long as h >= 0 and the SC loss multiplier m <= 1. Both are vars,
-- and a var set outside those bounds would quietly invert the incentive --
-- making the model recommend stopping EARLIER at circuits with more safety
-- cars, which is backwards. This catches that at build time rather than
-- letting it surface as a strange-looking optimum.
--
-- The no-stop candidate (laps_on_new_set = 0) is excluded: it pays no pit
-- cost at all, so its discount is a hard 0 and is not part of the sequence.
--
-- Gate: YES any row returned means waiting got MORE expensive, not less.

WITH stepped AS (
    SELECT
        stint_id,
        horizon_scope,
        candidate_pit_lap_offset,
        pit_discount_factor,
        LAG(pit_discount_factor) OVER (
            PARTITION BY stint_id, horizon_scope
            ORDER BY candidate_pit_lap_offset
        ) AS prev_discount
    FROM {{ ref('int_pit_strategy_cost_curve') }}
    WHERE laps_on_new_set > 0
)

SELECT
    stint_id,
    horizon_scope,
    candidate_pit_lap_offset,
    prev_discount,
    pit_discount_factor
FROM stepped
WHERE
    prev_discount IS NOT NULL
    AND pit_discount_factor > prev_discount + 1e-12
