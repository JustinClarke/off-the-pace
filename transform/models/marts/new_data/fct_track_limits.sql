-- TX-24. Deleted laps (FastF1 Deleted / DeletedReason), one row per deleted
-- lap, race and qualifying. NOT exported (scratch-only until AP-09 / AX-28).
-- turn_number is parsed when the reason names a turn ('TRACK LIMITS AT TURN
-- 4'); otherwise NULL with the raw text kept. Reconciles with the Bronze
-- Deleted totals per session (assert_track_limits_reconcile).
{{ config(materialized='table', tags=['marts', 'new_data']) }}

WITH laps AS (
    SELECT
        race_year, race_id, 'R' AS session_type, driver_id, constructor_id,
        lap_number, deleted_reason
    FROM {{ ref('stg_laps') }}
    WHERE is_deleted
    UNION ALL
    SELECT
        race_year, race_id, 'Q' AS session_type, driver_id, constructor_id,
        lap_number, deleted_reason
    FROM {{ ref('stg_laps_qualifying') }}
    WHERE is_deleted
)

SELECT
    CONCAT(race_id, '_', session_type, '_', driver_id, '_', CAST(lap_number AS VARCHAR))
        AS deleted_lap_id,
    race_year,
    race_id,
    session_type,
    driver_id,
    constructor_id,
    lap_number,
    deleted_reason,
    UPPER(deleted_reason) LIKE 'TRACK LIMITS%' AS is_track_limits,
    TRY_CAST(REGEXP_EXTRACT(UPPER(deleted_reason), 'TURN (\d+)', 1) AS INTEGER)
        AS turn_number,
    UPPER(deleted_reason) LIKE '%(NEXT LAP)%' AS is_next_lap_deletion
FROM laps
ORDER BY race_year, race_id, session_type, driver_id, lap_number
