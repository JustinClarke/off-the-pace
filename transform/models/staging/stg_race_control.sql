-- stg_race_control.sql · staging · grain: one row per race-control message
-- The FIA message feed. Ingested for 149 races since the beginning of this
-- project and, until Phase 10a, consumed by nothing (plan open item 13).
--
-- It is staged now for one specific reason: the 4,909 waved blue flags are a
-- traffic label produced by race control, not by the position channel. Every
-- other traffic signal in this warehouse -- dirty_air_share_lap, the air-state
-- classes, and now int_lap_proximity -- descends from FastF1 telemetry, so
-- none of them can validate another without circularity. A blue flag says
-- "car N was being lapped on lap L" on the FIA's authority, which makes it the
-- only supervised check available for the proximity features that is not
-- derived from the same sensor.
--
-- The car number is resolved to the three-letter driver_id here rather than
-- downstream, so every consumer joins on the same key the rest of the
-- warehouse uses.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_race_control') }}
),

driver_numbers AS (
    SELECT DISTINCT
        race_id,
        driver_number,
        driver_id
    FROM {{ ref('stg_results') }}
    WHERE driver_number IS NOT NULL
),

renamed AS (
    SELECT
        CAST(s.season AS INTEGER) AS race_year,
        CAST(s.race_id AS VARCHAR) AS race_id,
        CAST(s.race AS VARCHAR) AS race_slug,
        CAST(s.index AS INTEGER) AS message_index,

        -- Session clock of the message. Deliberately NOT reconciled with the
        -- telemetry SessionTime: the two have different origins (this column
        -- runs to ~55,000 s on a two-hour race, i.e. it is a wall-clock
        -- derivative, not session-elapsed). Lap is the join key that works.
        --
        -- TRY_CAST and not CAST, because the CI fixture and production bronze
        -- disagree on this column's TYPE: all 149 production race_control
        -- parquets carry it as `double`, and all three fixture files carry it
        -- as `timestamp[ns]`. A plain CAST raises "Unimplemented type for cast
        -- (TIMESTAMP_NS -> DOUBLE)" on the fixture. That divergence went
        -- unnoticed through a full green `dbt build --target ci` because this
        -- model is a VIEW and nothing in the CI suite selected the column --
        -- it was the oracle hash gate, which reads every model, that found it.
        -- TRY_CAST yields the real number on production bronze and NULL on the
        -- fixture, which is the honest answer for a value that type cannot
        -- express, and it cannot raise. Nothing joins on this column.
        TRY_CAST(s.session_time_s AS DOUBLE) AS message_time_s,
        CAST(s.category AS VARCHAR) AS message_category,
        CAST(s.message AS VARCHAR) AS message_text,
        UPPER(NULLIF(TRIM(CAST(s.flag AS VARCHAR)), '')) AS flag,
        CAST(s.scope AS VARCHAR) AS scope,
        CAST(s.sector AS INTEGER) AS marshal_sector,
        CAST(s.lap AS INTEGER) AS lap_number,
        NULLIF(TRIM(CAST(s.racingnumber AS VARCHAR)), '') AS driver_number,
        dn.driver_id
    FROM source AS s
    LEFT JOIN driver_numbers AS dn
        ON
            CAST(s.race_id AS VARCHAR) = dn.race_id
            AND NULLIF(TRIM(CAST(s.racingnumber AS VARCHAR)), '')
            = dn.driver_number
)

SELECT
    race_year,
    race_id,
    race_slug,
    message_index,
    message_time_s,
    message_category,
    message_text,
    flag,
    scope,
    marshal_sector,
    lap_number,
    driver_number,
    driver_id,
    -- The label Phase 10a validates against: this driver was being lapped on
    -- this lap. Requires the identity and the lap to both resolve, which is
    -- why it is a flag rather than a filter -- a blue flag whose car number
    -- did not resolve is a data gap, not a negative.
    -- COALESCE and not a bare `flag = 'BLUE'`: `flag` is NULL on the 246
    -- non-flag messages that nevertheless carry a resolvable driver and lap
    -- (DRS and CarEvent messages), and SQL's three-valued logic makes
    -- `NULL = 'BLUE' AND TRUE` evaluate to NULL rather than FALSE. That left a
    -- boolean column with 246 NULLs, which the not_null test caught. A
    -- non-flag message is a definite FALSE here, not an unknown.
    (
        COALESCE(flag, '') = 'BLUE'
        AND driver_id IS NOT NULL
        AND lap_number IS NOT NULL
    ) AS is_blue_flag_event
FROM renamed
