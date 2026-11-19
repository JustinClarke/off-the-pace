-- Tyres alone must not decide wet (roadmap WI-05 rule). Where the field tyre share exists and its
-- vote is 0 (share below var('wet_field_tyre_share_min')), the lap cannot be wet. Returns one row
-- per violating lap.

SELECT
    lap_id AS key,
    'wet with no tyre support: share ' || CAST(field_wet_tyre_share AS VARCHAR) AS reason
FROM {{ ref('stg_weather') }}
WHERE rainfall_flag
  AND field_wet_tyre_share IS NOT NULL
  AND field_wet_tyre_share < {{ var('wet_field_tyre_share_min') }}
