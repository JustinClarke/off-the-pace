-- 2025 Miami allocation metadata is present and labelled as a carry-forward from 2024:
-- C2/C3/C4, source_url 'carried_from_2024'. This is circuit allocation metadata only. It is
-- NOT lap-level compound evidence: stg_lap_tyre_qa keeps 2025_6 compounds NULL
-- (see assert_miami_2025_stays_quarantined). Returns a row if the seed row is missing or
-- differs from that label.

WITH miami AS (
    SELECT hard_code, medium_code, soft_code, source_url
    FROM {{ ref('tyre_allocations') }}
    WHERE race_year = 2025 AND circuit_key = 'miami_grand_prix'
)

SELECT
    '2025/miami_grand_prix' AS key,
    'miami 2025 allocation missing or not C2/C3/C4 carried_from_2024' AS reason
FROM (SELECT 1) AS one
WHERE NOT EXISTS (
    SELECT 1 FROM miami
    WHERE hard_code = 'C2' AND medium_code = 'C3' AND soft_code = 'C4'
      AND source_url = 'carried_from_2024'
)
