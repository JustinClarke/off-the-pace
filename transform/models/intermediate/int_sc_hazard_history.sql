-- int_sc_hazard_history.sql · intermediate · grain: one row per circuit (venue
-- slug)
-- Safety-Car / Virtual-Safety-Car base rate per circuit, expressed as a hazard
-- PER RACING LAP (not per race) so the MC finish-order core (§4.5) can draw an
-- interruption on each simulated lap. Estimated from the SC/VSC deployment
-- events
-- in stg_track_status, with racing-lap exposure from stg_laps.
--
-- Scope: only races that have an ingested track_status timeline (partial during
-- the
-- v0.2 backfill). Onset and exposure are taken over the SAME race set so the
-- rate is
-- well defined. The venue key is the race name slug (e.g. monaco_grand_prix),
-- which
-- recurs across seasons; stg_laps.race_id is the numeric per-season id, so we
-- map it
-- to the slug via the track_status scope.
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

per_circuit AS (
    SELECT
        circuit_slug,
        COUNT(*) AS n_races,
        SUM(n_sc_onsets) AS n_sc_onsets,
        SUM(n_vsc_onsets) AS n_vsc_onsets,
        SUM(n_sc_onsets + n_vsc_onsets) AS n_any_onsets,
        SUM(racing_laps) AS racing_laps
    FROM per_race
    GROUP BY circuit_slug
),

-- Global pooled rates, used as the shrinkage prior for thin circuits.
global_rate AS (
    SELECT
        CAST(SUM(n_sc_onsets) AS DOUBLE)
        / NULLIF(SUM(racing_laps), 0) AS sc_rate,
        CAST(SUM(n_vsc_onsets) AS DOUBLE)
        / NULLIF(SUM(racing_laps), 0) AS vsc_rate,
        CAST(SUM(n_any_onsets) AS DOUBLE)
        / NULLIF(SUM(racing_laps), 0) AS any_rate
    FROM per_circuit
)

SELECT
    c.circuit_slug,
    c.n_races,
    c.n_sc_onsets,
    c.n_vsc_onsets,
    c.n_any_onsets,
    c.racing_laps,

    -- Raw empirical hazard per racing lap.
    CAST(c.n_sc_onsets AS DOUBLE) / c.racing_laps AS sc_hazard_per_lap,
    CAST(c.n_vsc_onsets AS DOUBLE) / c.racing_laps AS vsc_hazard_per_lap,
    CAST(c.n_any_onsets AS DOUBLE) / c.racing_laps AS any_hazard_per_lap,

    -- Empirical-Bayes shrunk hazard toward the global pooled rate. Pseudo-count
    -- {{ var('sc_hazard_prior_laps', 600) }} laps of prior weight (≈ a few
    -- races'
    -- worth of exposure) keeps single-race circuits from reading 0 or extreme.
    (c.n_sc_onsets + g.sc_rate * {{ var('sc_hazard_prior_laps', 600) }})
    / (c.racing_laps + {{ var('sc_hazard_prior_laps', 600) }})
        AS sc_hazard_per_lap_shrunk,
    (c.n_vsc_onsets + g.vsc_rate * {{ var('sc_hazard_prior_laps', 600) }})
    / (c.racing_laps + {{ var('sc_hazard_prior_laps', 600) }})
        AS vsc_hazard_per_lap_shrunk,
    (c.n_any_onsets + g.any_rate * {{ var('sc_hazard_prior_laps', 600) }})
    / (c.racing_laps + {{ var('sc_hazard_prior_laps', 600) }})
        AS any_hazard_per_lap_shrunk
FROM per_circuit AS c
CROSS JOIN global_rate AS g
ORDER BY c.circuit_slug
