-- Safety-car hazard history: Madring is a 2026 debut and Barcelona keeps its history.
--
-- Checks, each with its own reason string:
--   madring_wrong_seasons   madring_grand_prix has any season other than 2026
--   madring_not_debut       its 2026 row has prior exposure, or any raw hazard
--                           (sc/vsc/any_hazard_per_lap) that is not NULL
--   spanish_2026_history    spanish_grand_prix 2026 (= Barcelona 2026) does not
--                           carry the Barcelona-Catalunya 2018-2025 history:
--                           8 prior races and 528 prior racing laps
--   barcelona_key_present   barcelona_grand_prix still exists as a key (it is
--                           re-keyed to spanish_grand_prix, so it must not)
-- The 8 / 528 figures are the measured Catalunya 2018-2025 totals (8 races) in
-- the warehouse at 2026-11; they are a regression pin, not a derived invariant.
-- If a Catalunya race is ever added or re-ingested, update them deliberately.
-- Gate: YES bug if any rows returned.

SELECT
    'madring_wrong_seasons' AS failure_reason,
    CAST(season AS VARCHAR) AS detail
FROM {{ ref('int_sc_hazard_history') }}
WHERE circuit_slug = 'madring_grand_prix' AND season != 2026

UNION ALL

SELECT
    'madring_not_debut' AS failure_reason,
    CAST(season AS VARCHAR) AS detail
FROM {{ ref('int_sc_hazard_history') }}
WHERE
    circuit_slug = 'madring_grand_prix'
    AND season = 2026
    AND (
        prior_races_n != 0
        OR prior_racing_laps != 0
        OR sc_hazard_per_lap IS NOT NULL
        OR vsc_hazard_per_lap IS NOT NULL
        OR any_hazard_per_lap IS NOT NULL
    )

UNION ALL

SELECT
    'madring_missing' AS failure_reason,
    '2026' AS detail
WHERE NOT EXISTS (
    SELECT 1 FROM {{ ref('int_sc_hazard_history') }}
    WHERE circuit_slug = 'madring_grand_prix' AND season = 2026
)

UNION ALL

SELECT
    'spanish_2026_history' AS failure_reason,
    prior_races_n || ' races / ' || prior_racing_laps || ' laps' AS detail
FROM {{ ref('int_sc_hazard_history') }}
WHERE
    circuit_slug = 'spanish_grand_prix'
    AND season = 2026
    AND (prior_races_n != 8 OR prior_racing_laps != 528)

UNION ALL

SELECT
    'barcelona_key_present' AS failure_reason,
    CAST(season AS VARCHAR) AS detail
FROM {{ ref('int_sc_hazard_history') }}
WHERE circuit_slug = 'barcelona_grand_prix'
