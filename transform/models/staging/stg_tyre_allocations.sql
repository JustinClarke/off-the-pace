-- Pirelli weekend compound nominations: which C-code each of hard/medium/soft
-- actually was for a given race. `compound_label` has been relative since 2019
-- (Pirelli picks 3 of 5 physical compounds per weekend), so "SOFT" at one
-- circuit is not the same rubber as "SOFT" at another. This model supplies the
-- absolute scale that makes them comparable.
--
-- PROVENANCE  the seed is USER-SUPPLIED AND SELF-VERIFIED, not machine-sourced.
-- `source_url` names the Pirelli per-race preview each row is attributed to, but
-- only 47 of the 128 URLs resolve; the rest 404 against the live press site,
-- which no longer serves its pre-2025 archive. The values were accepted on the
-- user's authority to unblock downstream work and are expected to be replaced
-- once an archival source is available. Do NOT quote a claim that rests on this
-- table without re-sourcing it first. See _improvements/work/08-foundations-repair.md (08d).
--
-- Seed is wide (one row per race); this model unpivots to one row per
-- (race, label) so the grain matches how consumers join it.
-- allocated_sets_per_driver is FIA technical allocation data, not carried by
-- Pirelli's compound announcements, so it is NULL by construction.
{{ config(materialized='view') }}

WITH allocations AS (
    SELECT * FROM {{ ref('tyre_allocations') }}
),

unpivoted AS (
    SELECT race_year, circuit_key, hard_code   AS compound_code, 'hard'   AS compound_label, source_url FROM allocations
    UNION ALL
    SELECT race_year, circuit_key, medium_code AS compound_code, 'medium' AS compound_label, source_url FROM allocations
    UNION ALL
    SELECT race_year, circuit_key, soft_code   AS compound_code, 'soft'   AS compound_label, source_url FROM allocations
)

SELECT
    CAST(race_year AS INTEGER)         AS race_year,
    CAST(circuit_key AS VARCHAR)       AS circuit_key,
    CAST(compound_code AS VARCHAR)     AS compound_code,
    CAST(compound_label AS VARCHAR)    AS compound_label,
    CAST(NULL AS INTEGER)              AS allocated_sets_per_driver,
    CAST(source_url AS VARCHAR)        AS source_url
FROM unpivoted
