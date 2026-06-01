-- stg_results.sql · staging · grain: one row per driver × race (classified
-- result)
-- Renames FastF1 session.results to snake_case, casts nanoseconds → seconds,
-- and
-- derives an explicit DNF / classification split (replacing the MAX(position)
-- finish derivation downstream see transform-v0.2 §5.4). No joins, no
-- aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_results') }}
)

SELECT
    -- Surrogate key
    CONCAT(
        CAST(race_id AS VARCHAR), '_',
        CAST(abbreviation AS VARCHAR)
    ) AS result_id,

    -- Session / circuit identifiers.
    -- race_id is the numeric FastF1 event id (e.g. 2018_4) matches
    -- stg_laps.race_id.
    -- race_slug is the human-readable name (e.g. azerbaijan_grand_prix).
    CAST(season AS INTEGER) AS race_year,
    CAST(race_id AS VARCHAR) AS race_id,
    CAST(race AS VARCHAR) AS race_slug,

    -- Driver / constructor
    CAST(abbreviation AS VARCHAR) AS driver_id,
    CAST(drivernumber AS VARCHAR) AS driver_number,
    CAST(teamname AS VARCHAR) AS constructor_id,

    -- Positions
    CAST(position AS INTEGER) AS finish_position,
    CAST(classifiedposition AS VARCHAR) AS classified_position,
    CAST(gridposition AS INTEGER) AS grid_position,
    CAST(points AS DOUBLE) AS points,

    -- Total race time (winner) / gap to winner (others), nanoseconds → seconds
    CASE WHEN time IS NOT NULL THEN CAST(time AS DOUBLE) / 1e9 END
        AS time_or_gap_s,

    -- Raw status string ('Finished', '+1 Lap', 'Engine', 'Collision', ...)
    CAST(status AS VARCHAR) AS status,

    -- Classification flags.
    -- ClassifiedPosition is numeric for ranked finishers;
    -- 'R'/'D'/'W'/'E'/'F'/'N'
    -- for retired/disqualified/withdrawn/etc. A driver is "classified" (counts
    -- as
    -- a finisher for ranking) when ClassifiedPosition parses to an integer.
    TRY_CAST(classifiedposition AS INTEGER) IS NOT NULL AS is_classified,

    -- DNF: not classified AND status is not a lapped-finish ('+N Lap(s)').
    -- 'Finished' and '+N Lap(s)' are completions; anything else that fails to
    -- classify is a retirement.
    (
        TRY_CAST(classifiedposition AS INTEGER) IS NULL
        AND status NOT LIKE '%Lap%'
        AND status <> 'Finished'
    ) AS is_dnf,

    -- Coarse DNF cause split for the DNF hazard model (§5.4): mechanical vs
    -- racing-incident. Crash/collision/accident/spun → racing; the rest of the
    -- non-finishes are treated as mechanical/other.
    CASE
        WHEN TRY_CAST(classifiedposition AS INTEGER) IS NOT NULL THEN NULL
        WHEN status LIKE '%Lap%' OR status = 'Finished' THEN NULL
        WHEN
            REGEXP_MATCHES(
                LOWER(status),
                'collision|accident|crash|spun|spin|contact|damage'
            )
            THEN 'racing'
        WHEN
            REGEXP_MATCHES(LOWER(status), 'disqualif|withdr|did not')
            THEN 'non_classified'
        ELSE 'mechanical'
    END AS dnf_cause

FROM source
