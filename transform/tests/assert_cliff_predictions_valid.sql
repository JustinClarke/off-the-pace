-- Check that expected_compound_pace_s is not defaulting to 0 or 0.5.
-- If they are 0 or 0.5, it means the seed parameters failed to join properly.
SELECT compound, race_id
FROM {{ ref('int_compound_cliff_predicted') }}
WHERE expected_compound_pace_s = 0.0 OR expected_compound_pace_s = 0.5
