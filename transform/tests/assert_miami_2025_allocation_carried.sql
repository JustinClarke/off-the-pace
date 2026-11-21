-- 2025 Miami allocation metadata is present and is the official 2025 nomination (C3/C4/C5),
-- sourced from formula1.com. This is circuit allocation metadata only. It is NOT lap-level
-- compound evidence: stg_lap_tyre_qa keeps 2025_6 compounds NULL
-- (see assert_miami_2025_stays_quarantined). Returns a row if the seed row is missing or
-- differs from that nomination. Updated 2026-11-19: this test expected the old carried-forward
-- C2/C3/C4 from 2024, which the seed no longer holds.

WITH miami AS (
    SELECT hard_code, medium_code, soft_code, source_url
    FROM {{ ref('tyre_allocations') }}
    WHERE race_year = 2025 AND circuit_key = 'miami_grand_prix'
)

SELECT
    '2025/miami_grand_prix' AS key,
    'miami 2025 allocation missing or not official C3/C4/C5 nomination' AS reason
FROM (SELECT 1) AS one
WHERE NOT EXISTS (
    SELECT 1 FROM miami
    WHERE hard_code = 'C3' AND medium_code = 'C4' AND soft_code = 'C5'
      AND source_url LIKE 'https://www.formula1.com/%'
)
