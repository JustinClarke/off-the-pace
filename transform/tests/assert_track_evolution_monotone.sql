-- Track evolution monotone test: rubber_component_s must be monotone non-increasing
-- across lap_number within a race (i.e. lap times improve or stay same as rubber builds).
WITH lagged AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        rubber_component_s,
        LAG(rubber_component_s) OVER (PARTITION BY race_year, race_id ORDER BY lap_number) AS prev_rubber_component_s
    FROM {{ ref('int_track_evolution') }}
)

SELECT *
FROM lagged
WHERE prev_rubber_component_s IS NOT NULL
  -- rubber_component_s should be less than or equal to prev_rubber_component_s
  -- (i.e. more negative or equal, representing speedup/lower lap time)
  AND rubber_component_s > prev_rubber_component_s + 0.0001
