-- T29, data half (WI-02, F39). An unknown tyre age must never produce a
-- valid-looking wear value.
--
-- DuckDB's LEAST and GREATEST skip NULL arguments. With age_in_stint NULL the
-- wear curve's LEAST(NULL, cap) returned the cap itself, so every lap whose age
-- was unknown carried exactly 10 s of wear -- 4,107 laps once stg_lap_tyre_qa's
-- quarantine NULLed the age on whole stints -- and GREATEST(NULL - onset, 0)
-- read "no cliff yet" rather than "unknown". A range test cannot see either:
-- 10.0 and 0.0 are in range. So this asserts the NULL itself: on a lap with no
-- known age, every age-dependent column of the curve is NULL.
--
-- The other direction (known age, NULL wear) is the conditional not_null on
-- compound_wear_s and expected_compound_pace_s in intermediate/schema.yml.

SELECT
    lap_id,
    race_id,
    compound,
    compound_wear_s,
    expected_compound_pace_s,
    laps_past_cliff,
    expected_degradation_rate_s_per_lap
FROM {{ ref('int_compound_cliff_predicted') }}
WHERE
    age_in_stint IS NULL
    AND (
        compound_wear_s IS NOT NULL
        OR expected_compound_pace_s IS NOT NULL
        OR laps_past_cliff IS NOT NULL
        OR expected_degradation_rate_s_per_lap IS NOT NULL
    )
