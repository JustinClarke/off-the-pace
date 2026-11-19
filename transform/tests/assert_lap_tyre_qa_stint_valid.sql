-- Every race lap served by stg_lap_tyre_qa has a non-NULL stint ordinal >= 1
-- (a lap with no resolvable stint is quarantined onto the pit-record ordinal,
-- never served 'ok' with a NULL).
--
-- Caught (2018, before the fix): lap-1 pit with bronze's first stint = 1 gave
-- stint 0 on 2018_5 HAR, 2018_5 SIR, 2018_13 VER (`first_stint_number - 1`),
-- and three laps of driver-races bronze never assigned (2018_10 HAR, 2018_2 RIC)
-- were 'ok' with a NULL stint. Both now fail this test if they return.

SELECT
    lap_id,
    'stint_below_1_or_null' AS check_name,
    CAST(stint_number AS VARCHAR) || ' ' || tyre_qa_status AS detail
FROM {{ ref('stg_lap_tyre_qa') }}
WHERE stint_number IS NULL OR stint_number < 1

