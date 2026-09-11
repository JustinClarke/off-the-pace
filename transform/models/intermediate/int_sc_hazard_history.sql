-- int_sc_hazard_history.sql · intermediate · grain: one row per circuit (venue
-- slug) × SEASON
-- Safety-Car / Virtual-Safety-Car base rate per circuit, expressed as a hazard
-- PER RACING LAP (not per race) so a Monte Carlo race simulator could draw an
-- interruption on each simulated lap. Estimated from the SC/VSC deployment
-- events in stg_track_status, with racing-lap exposure from stg_laps.
--
-- POINT-IN-TIME (02d, 2026-09-11). This model used to pool every season into a
-- single per-circuit rate, so a 2018 row read a hazard estimated partly from
-- 2024 races -- a textbook temporal leak the moment any of it reached the ML
-- contract. It is now an EXPANDING, SEASON-LAGGED rate: the row for
-- (circuit, season S) uses races at that circuit in seasons < S and nothing
-- else. Consumers MUST join on (circuit_slug, season), not circuit_slug alone.
--
-- Why season-lagged rather than race-lagged. The hazard is a standing property
-- of a venue (run-off, barrier proximity, pit-lane geometry, recovery access),
-- estimated from a handful of races; a within-season update would buy at most
-- one extra race of exposure while making the feature vary inside a weekend it
-- is meant to be constant across. "As of the start of the season" is also the
-- state of knowledge a strategist actually has when planning a race weekend.
--
-- The first season a circuit appears has NO prior exposure, so its raw hazard
-- is NULL rather than 0 -- "unknowable" and "measured, no events" are different
-- statements and the companion prior_races_n / prior_racing_laps columns are
-- what let a consumer tell them apart. Season 2018 is the earliest season in
-- the warehouse, so EVERY 2018 row is NULL on every rate, raw and shrunk: there
-- is no prior season for the circuit and none for the global prior either. See
-- schema.yml for the coverage table.
--
-- Scope: races with an ingested track_status timeline. Measured 2026-09-11 on
-- data/dev.duckdb, that is 148 of 148 races, 100% of every season 2018-2024 --
-- the "incomplete for some seasons" caveat the old header carried was stale.
-- Onset and exposure are taken over the SAME race set so the rate is well
-- defined. The venue key is the race name slug (e.g. monaco_grand_prix), which
-- recurs across seasons; stg_laps.race_id is the numeric per-season id, so we
-- map it to the slug via the track_status scope.
{{ config(materialized='table') }}

WITH races_in_scope AS (
    -- Every race with a track_status timeline, with its venue slug.
    SELECT DISTINCT
        race_year,
        race_id,
        race_slug AS circuit_slug
    FROM {{ ref('stg_track_status') }}
),

-- SC/VSC deployment ONSETS per race. status_code 4 = SCDeployed, 6 =
-- VSCDeployed
-- (7 = VSCEnding and 5 = Red are not counted as new-interruption onsets here).
onsets AS (
    SELECT
        ts.race_year,
        ts.race_id,
        COUNT(*) FILTER (WHERE ts.status_code = '4') AS n_sc_onsets,
        COUNT(*) FILTER (WHERE ts.status_code = '6') AS n_vsc_onsets
    FROM {{ ref('stg_track_status') }} AS ts
    GROUP BY ts.race_year, ts.race_id
),

-- Racing-lap exposure per race: the leader's lap count ≈ race distance, i.e.
-- the
-- number of per-lap hazard opportunities. Use the max lap_number observed.
exposure AS (
    SELECT
        race_year,
        race_id,
        MAX(lap_number) AS racing_laps
    FROM {{ ref('stg_laps') }}
    GROUP BY race_year, race_id
),

per_race AS (
    SELECT
        s.circuit_slug,
        s.race_year,
        s.race_id,
        COALESCE(o.n_sc_onsets, 0) AS n_sc_onsets,
        COALESCE(o.n_vsc_onsets, 0) AS n_vsc_onsets,
        e.racing_laps
    FROM races_in_scope AS s
    LEFT JOIN onsets AS o ON s.race_year = o.race_year AND s.race_id = o.race_id
    INNER JOIN exposure AS e
        ON s.race_year = e.race_year AND s.race_id = e.race_id
    WHERE e.racing_laps > 0
),

-- One row per circuit × season: that season's OWN totals at that venue. This is
-- the grain the trailing window runs over, and it is deliberately one row per
-- (circuit_slug, season) -- 02g's fan-out defect was a window frame evaluated
-- at
-- a finer grain than the key it was later joined on.
per_circuit_season AS (
    SELECT
        circuit_slug,
        race_year AS season,
        COUNT(*) AS season_races_n,
        SUM(n_sc_onsets) AS season_sc_onsets,
        SUM(n_vsc_onsets) AS season_vsc_onsets,
        SUM(n_sc_onsets + n_vsc_onsets) AS season_any_onsets,
        SUM(racing_laps) AS season_racing_laps
    FROM per_race
    GROUP BY circuit_slug, race_year
),

-- Global per-season totals, the input to the season-lagged pooled prior. The
-- prior has to be lagged too: shrinking a 2019 circuit toward a rate that
-- pooled 2024 leaks through the back door, which is exactly the defect this
-- rebuild exists to remove.
per_season_global AS (
    SELECT
        season,
        SUM(season_sc_onsets) AS season_sc_onsets,
        SUM(season_vsc_onsets) AS season_vsc_onsets,
        SUM(season_any_onsets) AS season_any_onsets,
        SUM(season_racing_laps) AS season_racing_laps
    FROM per_circuit_season
    GROUP BY season
),

-- Pooled rate as of the START of each season: all circuits, seasons < S.
-- Unpartitioned window (partition_by=none) because a pooled rate has no entity
-- axis -- the whole table is one series.
global_prior AS (
    SELECT
        season,
        {{ trailing_sum(
            'season_sc_onsets', none, ['season'], frame='range'
        ) }}
        / NULLIF({{ trailing_sum(
            'season_racing_laps', none, ['season'], frame='range'
        ) }}, 0) AS prior_global_sc_rate,
        {{ trailing_sum(
            'season_vsc_onsets', none, ['season'], frame='range'
        ) }}
        / NULLIF({{ trailing_sum(
            'season_racing_laps', none, ['season'], frame='range'
        ) }}, 0) AS prior_global_vsc_rate,
        {{ trailing_sum(
            'season_any_onsets', none, ['season'], frame='range'
        ) }}
        / NULLIF({{ trailing_sum(
            'season_racing_laps', none, ['season'], frame='range'
        ) }}, 0) AS prior_global_any_rate
    FROM per_season_global
),

-- The expanding, season-lagged window. Every aggregate below ends at
-- `1 PRECEDING` on the season axis via trailing_sum, so no row can see its own
-- season or any later one. frame='range' orders by season VALUE, so the frame
-- is "seasons strictly earlier than S" rather than "the N rows above me" -- the
-- two coincide at this grain and RANGE keeps that true if the grain ever moves.
lagged AS (
    SELECT
        circuit_slug,
        season,
        season_races_n,
        {{ trailing_sum(
            'season_races_n', ['circuit_slug'], ['season'], frame='range'
        ) }} AS prior_races_n,
        {{ trailing_observation_count(
            'season_races_n', ['circuit_slug'], ['season'], frame='range'
        ) }} AS prior_seasons_n,
        {{ trailing_sum(
            'season_sc_onsets', ['circuit_slug'], ['season'], frame='range'
        ) }} AS prior_sc_onsets,
        {{ trailing_sum(
            'season_vsc_onsets', ['circuit_slug'], ['season'], frame='range'
        ) }} AS prior_vsc_onsets,
        {{ trailing_sum(
            'season_any_onsets', ['circuit_slug'], ['season'], frame='range'
        ) }} AS prior_any_onsets,
        {{ trailing_sum(
            'season_racing_laps', ['circuit_slug'], ['season'], frame='range'
        ) }} AS prior_racing_laps
    FROM per_circuit_season
)

SELECT
    c.circuit_slug,
    c.season,
    c.season_races_n,
    c.prior_seasons_n,

    -- The companion counts are reported UNFLOORED and never NULL -- 0 means
    -- "no prior exposure", which is a fact, not a missing value. 02g shipped
    -- these NULL below its gate and made the estimate's own NULLs
    -- unexplainable from the data; that is the defect being avoided here.
    -- trailing_sum returns NULL on an empty window (its contract: no
    -- observations, nothing summed), so the zero is applied at this boundary
    -- and the NULL is carried by the RATES instead, where it belongs.
    COALESCE(c.prior_races_n, 0) AS prior_races_n,
    COALESCE(c.prior_sc_onsets, 0) AS prior_sc_onsets,
    COALESCE(c.prior_vsc_onsets, 0) AS prior_vsc_onsets,
    COALESCE(c.prior_any_onsets, 0) AS prior_any_onsets,
    COALESCE(c.prior_racing_laps, 0) AS prior_racing_laps,

    -- Raw empirical hazard per racing lap, over prior seasons only. NULL where
    -- the circuit has no prior exposure (its debut season), which is a
    -- different statement from a measured zero.
    CAST(COALESCE(c.prior_sc_onsets, 0) AS DOUBLE)
    / NULLIF(c.prior_racing_laps, 0) AS sc_hazard_per_lap,
    CAST(COALESCE(c.prior_vsc_onsets, 0) AS DOUBLE)
    / NULLIF(c.prior_racing_laps, 0) AS vsc_hazard_per_lap,
    CAST(COALESCE(c.prior_any_onsets, 0) AS DOUBLE)
    / NULLIF(c.prior_racing_laps, 0) AS any_hazard_per_lap,

    -- Empirical-Bayes shrunk hazard toward the SEASON-LAGGED global pooled
    -- rate. Pseudo-count {{ var('sc_hazard_prior_laps', 600) }} laps of prior
    -- weight (≈ a few races' worth of exposure) keeps thin circuits from
    -- reading 0 or extreme. A circuit in its debut season has zero prior
    -- exposure and so shrinks all the way to the pooled prior, which is the
    -- correct EB answer and is why these stay non-NULL where the raw rate is
    -- NULL. They go NULL only when the pooled prior itself is unknowable --
    -- season 2018, the first season in the warehouse.
    (
        COALESCE(c.prior_sc_onsets, 0)
        + g.prior_global_sc_rate * {{ var('sc_hazard_prior_laps', 600) }}
    )
    / (
        COALESCE(c.prior_racing_laps, 0)
        + {{ var('sc_hazard_prior_laps', 600) }}
    ) AS sc_hazard_per_lap_shrunk,
    (
        COALESCE(c.prior_vsc_onsets, 0)
        + g.prior_global_vsc_rate * {{ var('sc_hazard_prior_laps', 600) }}
    )
    / (
        COALESCE(c.prior_racing_laps, 0)
        + {{ var('sc_hazard_prior_laps', 600) }}
    ) AS vsc_hazard_per_lap_shrunk,
    (
        COALESCE(c.prior_any_onsets, 0)
        + g.prior_global_any_rate * {{ var('sc_hazard_prior_laps', 600) }}
    )
    / (
        COALESCE(c.prior_racing_laps, 0)
        + {{ var('sc_hazard_prior_laps', 600) }}
    ) AS any_hazard_per_lap_shrunk
FROM lagged AS c
INNER JOIN global_prior AS g ON c.season = g.season
ORDER BY c.circuit_slug, c.season
