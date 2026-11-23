-- Safety-car hazard history: in 2026 the Spanish GP is two different physical
-- circuits and must be two different keys.
--
-- 2026 spanish_grand_prix (race_id 2026_14) is Madrid (Madring); 2026
-- barcelona_grand_prix (2026_7) is Barcelona-Catalunya, whose 2018-2025 history
-- lives under the legacy key spanish_grand_prix. hazard_circuit_key therefore
-- gives Barcelona 2026 -> spanish_grand_prix and Madrid 2026 -> madring_grand_prix.
-- This returns a row if, for season 2026, either key is absent from
-- int_sc_hazard_history, or the two keys are the same value.
-- Gate: YES bug if any rows returned.

WITH keys_2026 AS (
    SELECT
        COALESCE(MAX(CASE WHEN circuit_slug = 'spanish_grand_prix' THEN 1 END), 0)
            AS has_spanish,
        COALESCE(MAX(CASE WHEN circuit_slug = 'madring_grand_prix' THEN 1 END), 0)
            AS has_madring
    FROM {{ ref('int_sc_hazard_history') }}
    WHERE season = 2026
),

mapped AS (
    -- The two source races as the macro keys them: must differ.
    SELECT
        {{ hazard_circuit_key('2026', "'barcelona_grand_prix'") }} AS barcelona_key,
        {{ hazard_circuit_key('2026', "'spanish_grand_prix'") }} AS madrid_key
)

SELECT
    k.has_spanish,
    k.has_madring,
    m.barcelona_key,
    m.madrid_key
FROM keys_2026 AS k
CROSS JOIN mapped AS m
WHERE k.has_spanish = 0
    OR k.has_madring = 0
    OR m.barcelona_key = m.madrid_key
