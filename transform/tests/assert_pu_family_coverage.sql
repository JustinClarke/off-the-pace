{{ config(severity='error') }}

-- F54 (WI-09), the guard F17's slow-rot flag needs. Every constructor in
-- dim_constructors has a power-unit family: none falls through to 'unknown_pu'.
--
-- dim_constructors.pu_mapping is a hand-kept list keyed on the team name, and F1
-- renames its teams every year or two; a new name lands in the warehouse the day
-- its first race does, with no mapping row behind it. Before this test, three of
-- 19 constructors (Alfa Romeo Racing, Kick Sauber, Racing Bulls, all renames) sat
-- at 'unknown_pu' and nothing flagged it: pu_family reaches fct_lap_residuals and
-- fct_driver_skill_features unchecked.
--
-- Error: the baseline is zero and this asserts "no unknown_pu" rather than "no more than
-- last build". A new team name failing here is the intended prompt to add its row to
-- dim_constructors.pu_mapping before the season reaches the marts; a warn would let
-- the gap pass silently, which is how three constructors sat unmapped before.

SELECT
    constructor_id,
    pu_family
FROM {{ ref('dim_constructors') }}
WHERE pu_family = 'unknown_pu'
