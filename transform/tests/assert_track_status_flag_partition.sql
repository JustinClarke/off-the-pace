-- Track-status flag decode test.
-- FastF1 TrackStatus digits, ground-truthed against the bronze Message column
-- (see stg_track_status): 1=AllClear, 2=Yellow, 4=SCDeployed, 5=Red,
-- 6=VSCDeployed, 7=VSCEnding. TrackStatus is a concatenated string, so a lap
-- spanning a status change carries every code in effect during it.
--
-- The three lap flags must decode those digits exactly, and their union must be
-- the neutralised set the layer excludes. Prior to 2026-08, is_safety_car_lap
-- was '[467]' (SC ∪ VSC) and is_vsc_lap was '5' (red flag) — the union was
-- right by accident while both flags were individually wrong.

-- 1. is_safety_car_lap fires iff a 4 is present.
SELECT
    'sc_decode' AS check_name,
    lap_id,
    track_status,
    is_safety_car_lap AS actual,
    REGEXP_MATCHES(track_status, '.*4.*') AS expected
FROM {{ ref('stg_laps') }}
WHERE is_safety_car_lap != REGEXP_MATCHES(track_status, '.*4.*')

UNION ALL

-- 2. is_vsc_lap fires iff a 6 or 7 is present (never on 5).
SELECT
    'vsc_decode' AS check_name,
    lap_id,
    track_status,
    is_vsc_lap AS actual,
    REGEXP_MATCHES(track_status, '.*[67].*') AS expected
FROM {{ ref('stg_laps') }}
WHERE is_vsc_lap != REGEXP_MATCHES(track_status, '.*[67].*')

UNION ALL

-- 3. is_red_flag_lap fires iff a 5 is present.
SELECT
    'red_decode' AS check_name,
    lap_id,
    track_status,
    is_red_flag_lap AS actual,
    REGEXP_MATCHES(track_status, '.*5.*') AS expected
FROM {{ ref('stg_laps') }}
WHERE is_red_flag_lap != REGEXP_MATCHES(track_status, '.*5.*')

UNION ALL

-- 4. The three flags partition the neutralised set: their union is exactly
--    "TrackStatus contains a 4, 5, 6 or 7", which is the complement of
--    is_valid_lap's track-status condition. This is the invariant every
--    consumer's `NOT sc AND NOT vsc AND NOT red` filter depends on.
SELECT
    'neutralised_union' AS check_name,
    lap_id,
    track_status,
    (is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap) AS actual,
    REGEXP_MATCHES(track_status, '.*[4567].*') AS expected
FROM {{ ref('stg_laps') }}
WHERE
    (is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap)
    != REGEXP_MATCHES(track_status, '.*[4567].*')

UNION ALL

-- 5. A neutralised lap is never valid (is_valid_lap already excludes 4-7;
--    this pins the two definitions together so they cannot drift apart).
SELECT
    'valid_excludes_neutralised' AS check_name,
    lap_id,
    track_status,
    is_valid_lap AS actual,
    FALSE AS expected
FROM {{ ref('stg_laps') }}
WHERE
    (is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap)
    AND is_valid_lap
