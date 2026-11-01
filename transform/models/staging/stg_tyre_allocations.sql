-- Pirelli weekend compound nominations: which C-code each of hard/medium/soft
-- actually was for a given race. `compound_label` has been relative since 2019
-- (Pirelli picks 3 of 5 physical compounds per weekend), so "SOFT" at one
-- circuit is not the same rubber as "SOFT" at another. This model supplies the
-- absolute scale that makes them comparable.
--
-- PROVENANCE  the seed is USER-SUPPLIED AND SELF-VERIFIED, not machine-sourced.
-- `source_url` names the Pirelli per-race preview each row is attributed to,
-- but only 47 of the 128 2019-2024 URLs resolve; the rest 404 against the live
-- press site, which no longer serves its pre-2025 archive. The values were
-- accepted on the user's authority to unblock downstream work and are expected
-- to be replaced once an archival source is available. Do NOT quote a claim
-- that rests on this table without re-sourcing it first. See
-- _improvements/work/08-foundations-repair.md (08d).
--
-- KNOWN WRONG (WC-16, 2026-10-31)  a fetched source for every race
-- (_roadmap/_wake-calibration/_evidence/WC-16-2026-10-31/c_numbers.csv and
-- c_numbers_report.md) confirms all 2019-2023 rows and 23 of 24 for 2024, but
-- 12 seed rows are wrong (seed hard/medium/soft -> verified):
--   2024_16 Italy          C2/C3/C4 -> C3/C4/C5
--   2025_5  Saudi Arabia   C2/C3/C4 -> C3/C4/C5
--   2025_7  Emilia Romagna C3/C4/C5 -> C4/C5/C6
--   2025_8  Monaco         C3/C4/C5 -> C4/C5/C6
--   2025_10 Canada         C3/C4/C5 -> C4/C5/C6
--   2025_12 Britain        C1/C2/C3 -> C2/C3/C4
--   2025_13 Belgium        C2/C3/C4 -> C1/C3/C4
--   2025_15 Netherlands    C1/C2/C3 -> C2/C3/C4
--   2025_16 Italy          C2/C3/C4 -> C3/C4/C5
--   2025_17 Azerbaijan     C3/C4/C5 -> C4/C5/C6
--   2025_19 United States  C2/C3/C4 -> C1/C3/C4
--   2025_20 Mexico City    C3/C4/C5 -> C2/C4/C5
-- and the missing 2025_6 Miami row is C3/C4/C5. The correction is HELD: this
-- view feeds fct_power_law_training (int_stint_geometry -> int_power_law_lap),
-- an ML input, so the seed is corrected with the ML redo (PK1,
-- _roadmap/_ai-integration). The C6 rows also need the seed's C1-C5
-- accepted_values widened. Details in seeds/schema.yml (tyre_allocations).
--
-- COVERAGE  2019-2025: 151 seed rows, 453 rows here (151 races x 3 labels).
-- 2019-2024 is 128 races (every ingested race). 2025 is 23 of the 24 ingested
-- races (no Miami row), and every
-- 2025 row is CARRIED FORWARD from that circuit's 2023 or 2024 allocation
-- (`source_url` is
-- 'carried_from_20xx', not a URL), not read from a 2025 preview. Per-season
-- counts are pinned by tests/assert_tyre_allocations_rows_per_season.sql.
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
    SELECT
        race_year,
        circuit_key,
        hard_code AS compound_code,
        'hard' AS compound_label,
        source_url
    FROM allocations
    UNION ALL
    SELECT
        race_year,
        circuit_key,
        medium_code AS compound_code,
        'medium' AS compound_label,
        source_url
    FROM allocations
    UNION ALL
    SELECT
        race_year,
        circuit_key,
        soft_code AS compound_code,
        'soft' AS compound_label,
        source_url
    FROM allocations
)

SELECT
    CAST(race_year AS INTEGER) AS race_year,
    CAST(circuit_key AS VARCHAR) AS circuit_key,
    CAST(compound_code AS VARCHAR) AS compound_code,
    CAST(compound_label AS VARCHAR) AS compound_label,
    CAST(NULL AS INTEGER) AS allocated_sets_per_driver,
    CAST(source_url AS VARCHAR) AS source_url
FROM unpivoted
