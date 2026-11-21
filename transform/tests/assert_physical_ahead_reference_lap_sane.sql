-- int_lap_physical_ahead: reference-lap sanity, per race. WARN only. Every projection in a race is onto the
-- polyline of ONE lap (fastest clean lap of one driver, see the .py header), so a bad reference degrades the
-- whole race silently. Flags a race when any of these look degenerate (provisional thresholds, not tuned):
--   * no polyline at all (track_length_m NULL, listed deliberately): 2018 Australia and Bahrain have no race
--     telemetry in bronze (source gap), so every lap is 'unknown' (no_position_samples);
--   * track_length_m outside 2,000-8,000 m (a clipped or doubled reference trace, not a circuit);
--   * more than 10% of laps unknown because the follower was > 15 m off the polyline
--     (unknown_reason_mode = 'follower_offline'): the polyline does not describe where cars drive;
--   * more than 50% of laps unknown for any reason (2021 Belgium: three laps behind the safety car, so real).
-- Races in seed_physical_ahead_known_reference_gaps (2018_1, 2018_2: no race telemetry; 2021_12: safety-car race)
-- are acknowledged and excluded. Nothing else is.
-- A reference trace that does not close (first and last sample far apart, typical 20 m) makes the closing chord cut
-- the corner at the line, so cars read 'offline' there (2020 Austria, 125 m, was 88% of laps). The reference lap
-- is therefore the fastest clean lap with a start-to-end gap under REFERENCE_MAX_CLOSURE_GAP_M (physical_ahead_core.py).
{{ config(severity='warn') }}
SELECT
    race_id,
    MAX(track_length_m) AS track_length_m,
    AVG(CASE WHEN unknown_reason_mode = 'follower_offline' THEN 1.0 ELSE 0.0 END) AS share_laps_offline,
    AVG(CASE WHEN validity_class = 'unknown' THEN 1.0 ELSE 0.0 END) AS share_laps_unknown
FROM {{ ref('int_lap_physical_ahead') }}
WHERE race_id NOT IN (SELECT race_id FROM {{ ref('seed_physical_ahead_known_reference_gaps') }})
GROUP BY race_id
HAVING
    MAX(track_length_m) IS NULL
    OR MAX(track_length_m) < 2000 OR MAX(track_length_m) > 8000
    OR AVG(CASE WHEN unknown_reason_mode = 'follower_offline' THEN 1.0 ELSE 0.0 END) > 0.10
    OR AVG(CASE WHEN validity_class = 'unknown' THEN 1.0 ELSE 0.0 END) > 0.50
