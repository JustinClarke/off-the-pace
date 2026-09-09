-- Circuit × constructor interaction model: Circuit × constructor interaction
-- term.
-- Some constructors are systematically faster at specific circuits beyond their
-- season-average coefficient (e.g., Ferrari at Monza due to low-drag trim).
-- This model estimates that circuit-specific bonus/penalty using EW-smoothed
-- within-season race deviations from the circuit baseline.
--
-- Method: per (constructor, circuit), take the deviation of the per-race
-- constructor_structural_pace_s from the constructor's season-to-date average,
-- then smooth with a weak prior toward zero over that pairing's PRIOR visits.
--
-- Both windows are point-in-time (08f-2). They used to be GROUP BYs and both
-- reached forward. The season average was over the WHOLE season, so a lap in
-- round 3 was measured against round 22; the circuit pool was over EVERY ingested
-- season at once -- 522 cells, mean 2.79 seasons, and 57.4% of pre-2024 panel rows
-- sat in a cell that also held a 2024 observation, each season carrying mean weight
-- 0.35. That one reaches a live feature: circuit_constructor_interaction_s ->
-- constructor_component_s -> driver_skill_residual_s -> int_lap_anomaly_flags ->
-- cliff_candidate_flag, so the evaluation season sat inside a feature training rows
-- could see.
--
-- A constructor's first race of a season has no season-to-date average, so its
-- deviation is NULL and contributes no observation to any circuit pool. A pairing's
-- first visit to a circuit has no prior visits, so n_obs = 0 and the interaction
-- falls back to 0.0 -- the same fallback the model already used for an unobserved
-- cell, and every downstream consumer already COALESCEs to it.
--
-- Output grain: one row per (race_year, race_id, constructor_id).
-- PK: surrogate hash of (race_year, race_id, constructor_id).

{{ config(materialized='table', tags=['simulation', 'ghost_car']) }}

WITH constructor_pace AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        constructor_structural_pace_s,
        panel_observations_n,
        -- Chronological position within the season. race_id is 'YYYY_R' as a
        -- string, so it sorts 2023_10 before 2023_2 -- ordering a point-in-time
        -- window on it directly would silently scramble the time axis. Verified
        -- over the warehouse: every race_id matches '^[0-9]{4}_[0-9]+$', and
        -- (race_year, round_n) identifies all 147 races.
        CAST(SPLIT_PART(race_id, '_', 2) AS INTEGER) AS round_n
    FROM {{ ref('int_constructor_structural_pace') }}
),

race_map AS (
    SELECT race_id, track_id AS circuit_key
    FROM {{ ref('race_to_track') }}
),

-- Map event slug (circuit_key) -> physical circuit_id, so the shrinkage pool
-- below is per physical venue (e.g. mexican_grand_prix + mexico_city_grand_prix
-- share one pool) rather than per renamed-event/double-header key.
circuit_map AS (
    SELECT
        circuit_key,
        {{ circuit_id_from_name('circuit_name') }} AS circuit_id
    FROM {{ ref('circuit_reference') }}
),

with_circuit AS (
    SELECT
        cp.race_year,
        cp.race_id,
        cp.constructor_id,
        cp.constructor_structural_pace_s,
        cp.panel_observations_n,
        cp.round_n,
        rm.circuit_key,
        COALESCE(cm.circuit_id, rm.circuit_key) AS circuit_id
    FROM constructor_pace AS cp
    LEFT JOIN race_map AS rm ON cp.race_id = rm.race_id
    LEFT JOIN circuit_map AS cm ON rm.circuit_key = cm.circuit_key
),

-- Season-TO-DATE constructor coefficient (to compute deviation): the mean over
-- this constructor's races strictly before this one, within the same season.
-- NULL at the season's first race, which is the honest answer -- there is no
-- season level to deviate from yet.
constructor_season_avg AS (
    SELECT
        *,
        AVG(constructor_structural_pace_s) OVER (
            PARTITION BY race_year, constructor_id
            ORDER BY round_n
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS season_avg_pace_s
    FROM with_circuit
),

-- Circuit-level constructor baseline (pooled across seasons with shrinkage).
-- Pools on circuit_id (physical venue), not circuit_key (event slug): a
-- renamed-event or double-header key would otherwise split a constructor's
-- circuit-specific bonus/penalty across two thinner, independent cells.
circuit_constructor_obs AS (
    SELECT
        *,
        -- Deviation of this race from the constructor's season to date. NULL, not
        -- COALESCE(...,0.0), where there is no season-to-date average: coalescing
        -- would make the deviation the constructor's raw pace and feed that whole
        -- level into the circuit pool as if it were a circuit effect.
        constructor_structural_pace_s - season_avg_pace_s
            AS pace_circuit_deviation_s
    FROM constructor_season_avg
),

-- Shrinkage: Bayesian posterior of circuit-constructor deviation toward 0,
-- estimated over this pairing's visits STRICTLY BEFORE this race. Expanding, not
-- trailing-N: a constructor visits a circuit about once a season, so a capped
-- window would usually hold one observation or none.
circuit_constructor_agg AS (
    SELECT
        *,
        COUNT(pace_circuit_deviation_s) OVER w AS n_obs,
        AVG(pace_circuit_deviation_s) OVER w AS observed_mean_s,
        STDDEV_POP(pace_circuit_deviation_s) OVER w AS observed_std_s
    FROM circuit_constructor_obs
    WINDOW w AS (
        PARTITION BY constructor_id, circuit_id
        ORDER BY race_year, round_n
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    )
),

with_shrinkage AS (
    SELECT
        *,
        -- Bayesian shrinkage toward 0: prior_weight = 3 (weak prior).
        -- n_obs = 0 gives NULL here (0 * NULL), which the final SELECT
        -- COALESCEs to 0.0 -- no prior visit, no known circuit effect.
        (n_obs * observed_mean_s)
        / NULLIF(n_obs + 3.0, 0) AS shrunk_interaction_s
    FROM circuit_constructor_agg
)

-- Output grain and columns are unchanged. No join back to the race grain is
-- needed any more: the pool is a window over the race-grain panel, so it already
-- carries one row per (race_year, race_id, constructor_id).
-- interaction_obs_n now means PRIOR visits, not total visits, and is 0 on a
-- pairing's first visit.
SELECT
    CONCAT(
        CAST(race_year AS VARCHAR), '_',
        race_id, '_',
        constructor_id
    ) AS constructor_race_id,
    race_year,
    race_id,
    constructor_id,
    circuit_key,
    COALESCE(shrunk_interaction_s, 0.0) AS circuit_constructor_interaction_s,
    COALESCE(n_obs, 0) AS interaction_obs_n,
    COALESCE(observed_std_s, 0.0) AS interaction_se_s
FROM with_shrinkage
ORDER BY race_year, race_id, constructor_id
