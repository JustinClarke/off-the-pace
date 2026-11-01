-- WC-11 / WC-12 / WC-13 (BUILD-ORDER rule 7): in int_lap_wake_placeholder_cost a lap is either
-- modelled (a value, no reason) or unavailable (NULL value, a reason), never a
-- 0 standing in for "unknown"; a modelled value never exceeds the race's
-- assumed full-exposure loss for the lap (race x tyre x car); every row carries the DD-WC2 line (owner
-- rewording 2026-10-31) and the placeholder line (owner ruling 2026-10-30) word for word; and a race on the circuit-class fallback says
-- so in its basis (never silently). Returns the offending rows.
SELECT lap_id, value_label, wake_cost_placeholder_s, unavailable_reason, loss_source, loss_basis
FROM {{ ref('int_lap_wake_placeholder_cost') }}
WHERE
    (value_label = 'modelled'
        AND (wake_cost_placeholder_s IS NULL OR unavailable_reason IS NOT NULL))
    OR (value_label = 'unavailable'
        AND (wake_cost_placeholder_s IS NOT NULL OR unavailable_reason IS NULL))
    OR wake_cost_placeholder_s < 0
    OR wake_cost_placeholder_s > loss_s_per_lap_within_1s + 1e-9
    OR disclaimer IS DISTINCT FROM
        'Modelled: an assumed typical loss for this circuit, season, tyre and car, applied to the measured time spent close behind another car. Not calibrated on this driver''s own stints.'
    OR disclaimer_placeholder IS DISTINCT FROM
        'Placeholder = an interim value set by a fixed rule, not a measurement of this lap.'
    OR (loss_source = 'class_fallback' AND loss_basis NOT LIKE 'Fallback:%')
    OR (loss_source = 'race_structure' AND loss_basis NOT LIKE 'Assumed rule:%')
