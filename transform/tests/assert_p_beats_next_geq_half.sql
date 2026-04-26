-- Fix 3 pairwise-consistency invariant: p_beats_next is the probability a driver
-- finishes ahead of the one ranked immediately below it. Since drivers are ranked
-- by ascending predicted mean pace, the higher-ranked driver always has the lower
-- (or equal) predicted pace, so under the symmetric normal approximation its
-- probability of beating the next driver must be >= 0.5. A tiny epsilon absorbs
-- floating-point noise in the CDF approximation. Any row below 0.5 means the rank
-- order and the probability model disagree a recombination bug.

SELECT
    ghost_race_id,
    predicted_finish_position,
    p_beats_next
FROM {{ ref('fct_ghost_race_finish') }}
WHERE p_beats_next IS NOT NULL
  AND p_beats_next < 0.5 - 1e-6
