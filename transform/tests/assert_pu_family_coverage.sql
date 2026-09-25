{{ config(severity='warn') }}

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
-- Warn, not error: an unmapped name is a to-do (add the row) and must not stop a
-- season's ingestion. Nothing computes on pu_family today, so a miss costs a wrong
-- label rather than a wrong number. The baseline is zero, so this asserts "no
-- unknown_pu" rather than "no more than last build".

SELECT
    constructor_id,
    pu_family
FROM {{ ref('dim_constructors') }}
WHERE pu_family = 'unknown_pu'
