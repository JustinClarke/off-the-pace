-- Pins the same rule from the threshold side: when a field tyre share exists, rainfall_flag may
-- be TRUE only if the share reaches var('wet_field_tyre_share_min'). Rain or humidity alone never
-- make a lap wet while the field is on slicks. Returns one row per violating lap.

SELECT
    lap_id AS key,
    'share ' || CAST(field_wet_tyre_share AS VARCHAR) || ' below '
        || CAST({{ var('wet_field_tyre_share_min') }} AS VARCHAR) || ' but flagged wet' AS reason
FROM {{ ref('stg_weather') }}
WHERE field_wet_tyre_share IS NOT NULL
  AND rainfall_flag
  AND field_wet_tyre_share < {{ var('wet_field_tyre_share_min') }}
