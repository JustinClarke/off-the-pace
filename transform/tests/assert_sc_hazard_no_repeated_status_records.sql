-- Repeated-record guard for int_sc_hazard_history.
--
-- The SC/VSC onset count is COUNT(*) of status '4' / '6' rows per race. That is
-- only a count of distinct deployments if no two adjacent status rows carry the
-- same code: two consecutive '4' rows with no status change between them are one
-- state reported twice. This test flags such adjacent repeats, in staging order
-- (session_time_s, then status_code), matching the model's LEAD ordering.
-- Gate: YES bug if any rows are returned.

WITH ordered AS (
    SELECT
        race_year,
        race_id,
        session_time_s,
        status_code,
        LEAD(status_code) OVER (
            PARTITION BY race_year, race_id
            ORDER BY session_time_s, status_code
        ) AS next_status_code,
        LEAD(session_time_s) OVER (
            PARTITION BY race_year, race_id
            ORDER BY session_time_s, status_code
        ) AS next_session_time_s
    FROM {{ ref('stg_track_status') }}
)

SELECT
    race_year,
    race_id,
    status_code,
    session_time_s,
    next_session_time_s
FROM ordered
WHERE status_code IN ('4', '6')
  AND next_status_code = status_code
