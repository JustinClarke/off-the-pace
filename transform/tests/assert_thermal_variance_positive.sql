-- Check that track_temp_c varies within a race. If max - min < 0.1, the thermal logic is broken or missing.
WITH race_temp AS (
  SELECT race_id, MAX(track_temp_c) - MIN(track_temp_c) as temp_range
  FROM {{ ref('int_track_evolution') }}
  GROUP BY race_id
)
SELECT * FROM race_temp WHERE temp_range < 0.1
