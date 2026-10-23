-- OUT: 02b_samples_before_first_track_status
-- Races where position samples precede the first track-status event (these
-- samples are excluded from "green" because their flag state is unknown).
SELECT race_id, COUNT(*) AS samples_without_status,
       (SELECT MIN(session_time_s) FROM ts WHERE ts.race_id = p.race_id) AS first_status_s,
       MIN(session_time_s) AS first_sample_s, MAX(lap_number) AS max_lap_affected
FROM pos_flags AS p WHERE status_code IS NULL GROUP BY 1 ORDER BY 2 DESC
