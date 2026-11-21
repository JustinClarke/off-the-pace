-- stg_results.sql · staging · grain: one row per driver × race (classified
-- result)
-- Renames FastF1 session.results to snake_case, casts nanoseconds → seconds,
-- and
-- derives an explicit DNF / classification split. No joins, no
-- aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_results') }}
),

-- F14: a disqualification is ruled after the flag, and bronze leaves a numeric
-- ClassifiedPosition on some of those rows (HAM and LEC at 2023_18, RUS at
-- 2024_14) where the other thirteen carry 'D'. Parsing ClassifiedPosition
-- alone therefore read those three as classified finishers. status says it
-- directly, so it is decided first: one parsed rank, NULL for a disqualified
-- driver, is what is_classified, is_dnf and dnf_cause below all read.
ranked AS (
    SELECT
        *,
        CASE
            WHEN status = 'Disqualified' THEN NULL
            ELSE TRY_CAST(classifiedposition AS INTEGER)
        END AS classified_rank,
        -- TODO(check back): classification 'R' is a retirement, but two 2026 rows
        -- (STR at 2026_1, ALB at 2026_7) carry status 'Lapped' with 'R'. Treated as
        -- DNF for now; confirm against the official result for both races.
        (CAST(classifiedposition AS VARCHAR) = 'R') AS retired_code
    FROM source
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
    -- a finisher for ranking) when ClassifiedPosition parses to an integer and
    -- the driver was not disqualified (see classified_rank above).
    classified_rank IS NOT NULL AS is_classified,

    -- DNF: not classified AND status is not a lapped-finish ('+N Lap(s)').
    -- 'Finished' and '+N Lap(s)' are completions; anything else that fails to
    -- classify is a retirement.
    (
        (
            classified_rank IS NULL
            AND status NOT LIKE '%Lap%'
            AND status <> 'Finished'
        )
        OR (retired_code AND status <> 'Disqualified')
    ) AS is_dnf,

    -- is_retired: the car stopped on track, whatever the classification. A
    -- driver who retires after covering about 90% of the race keeps an integer
    -- ClassifiedPosition (so is_classified is TRUE and is_dnf is FALSE) while
    -- status still says Retired / Engine / Collision. is_retired reads status
    -- alone: not 'Finished', not a lapped finish, and not 'Disqualified'
    -- (a disqualification is a ruling, not a retirement). is_classified,
    -- classified_rank and is_dnf are unchanged.
    (
        (
            status <> 'Finished'
            AND status NOT LIKE '%Lap%'
            AND status <> 'Disqualified'
        )
        OR (retired_code AND status <> 'Disqualified')
    ) AS is_retired,

    -- is_disqualified: a ruling after the race, not a retirement. Read from
    -- status, the same source as is_retired. is_dnf is unchanged and still
    -- counts disqualified drivers, so a consumer that wants them out must
    -- filter on NOT is_disqualified.
    (status = 'Disqualified') AS is_disqualified,

    -- Coarse DNF cause split for the DNF hazard model: mechanical vs
    -- racing-incident. Crash/collision/accident/spun → racing; the rest of the
    -- non-finishes are treated as mechanical/other. Read from status
    -- regardless of classification, so a classified retirement has a cause.
    CASE
        -- TODO(check back): 2026 STR and ALB carry status 'Lapped' with 'R'; cause is
        -- unknown, so they are non_classified until the official result is checked.
        WHEN retired_code AND status LIKE '%Lap%' THEN 'non_classified'
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

FROM ranked
