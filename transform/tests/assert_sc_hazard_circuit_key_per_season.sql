-- Safety-car hazard history: within one season, one venue key must not span more
-- than one PHYSICAL circuit.
--
-- The venue key (hazard_circuit_key) pools races. If two different physical
-- circuits in the SAME season land on one key, that key's history is a blend of
-- two tracks, which is exactly the 2026 defect (Madrid filed under the
-- Barcelona-Catalunya history). This test joins every race feeding
-- int_sc_hazard_history to bronze session_info (race-depth files, session_type
-- 'R') and returns any (circuit_slug, season) that maps to more than one
-- Meeting_Circuit_Key.
--
-- WHAT THIS PROVES: no season has two distinct Meeting_Circuit_Key values under
-- one hazard key.
-- WHAT IT DOES NOT PROVE: Meeting_Circuit_Key is NOT a clean physical identifier.
-- Key 149 is shared by Jeddah (2021-25) and Mugello (2020), so equal keys do not
-- guarantee the same circuit. Two different circuits that happened to share a key
-- in the same season would pass; that is not known to occur. The check is
-- deliberately per-SEASON only: a slug legitimately spans different keys across
-- years (the circuit can be re-keyed upstream), so a cross-season
-- "one key per slug" assertion would be wrong and is not made here.
-- The Madrid/Barcelona split itself is asserted by
-- assert_sc_hazard_2026_spanish_madring_distinct.
-- Gate: YES bug if any rows returned.

WITH races_in_scope AS (
    SELECT DISTINCT
        race_year,
        race_id,
        {{ hazard_circuit_key('race_year', 'race_slug') }} AS circuit_slug
    FROM {{ ref('stg_track_status') }}
),

physical AS (
    SELECT DISTINCT
        race_id,
        Meeting_Circuit_Key AS meeting_circuit_key
    FROM read_parquet(
        '{{ var("bronze_base", "../data/bronze") }}/session_info/*/*/session_info.parquet'
    )
    WHERE session_type = 'R'
)

SELECT
    s.circuit_slug,
    s.race_year AS season,
    COUNT(DISTINCT p.meeting_circuit_key) AS n_physical_keys,
    STRING_AGG(DISTINCT CAST(p.meeting_circuit_key AS VARCHAR), ',') AS keys
FROM races_in_scope AS s
INNER JOIN physical AS p ON s.race_id = p.race_id
GROUP BY s.circuit_slug, s.race_year
HAVING COUNT(DISTINCT p.meeting_circuit_key) > 1
