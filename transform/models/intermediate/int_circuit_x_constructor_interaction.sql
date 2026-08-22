-- Circuit × constructor interaction model: Circuit × constructor interaction
-- term.
-- Some constructors are systematically faster at specific circuits beyond their
-- season-average coefficient (e.g., Ferrari at Monza due to low-drag trim).
-- This model estimates that circuit-specific bonus/penalty using EW-smoothed
-- within-season race deviations from the circuit baseline.
--
-- Method: per (constructor, circuit), take the deviation of the per-race
-- constructor_structural_pace_s from the constructor's season average, then
-- smooth with a weak prior toward zero.
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
        panel_observations_n
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
        rm.circuit_key,
        COALESCE(cm.circuit_id, rm.circuit_key) AS circuit_id
    FROM constructor_pace AS cp
    LEFT JOIN race_map AS rm ON cp.race_id = rm.race_id
    LEFT JOIN circuit_map AS cm ON rm.circuit_key = cm.circuit_key
),

-- Season-average constructor coefficient (to compute deviation)
constructor_season_avg AS (
    SELECT
        race_year,
        constructor_id,
        AVG(constructor_structural_pace_s) AS season_avg_pace_s
    FROM with_circuit
    GROUP BY race_year, constructor_id
),

-- Circuit-level constructor baseline (pooled across seasons with shrinkage).
-- Pools on circuit_id (physical venue), not circuit_key (event slug): a
-- renamed-event or double-header key would otherwise split a constructor's
-- circuit-specific bonus/penalty across two thinner, independent cells.
circuit_constructor_obs AS (
    SELECT
        wc.constructor_id,
        wc.circuit_id,
        wc.race_year,
        wc.race_id,
        -- Deviation of this race from the season average for this constructor
        wc.constructor_structural_pace_s - COALESCE(csa.season_avg_pace_s, 0.0)
            AS pace_circuit_deviation_s,
        wc.panel_observations_n
    FROM with_circuit AS wc
    LEFT JOIN constructor_season_avg AS csa
        ON
            wc.race_year = csa.race_year
            AND wc.constructor_id = csa.constructor_id
),

-- Shrinkage: Bayesian posterior of circuit-constructor deviation toward 0
circuit_constructor_agg AS (
    SELECT
        constructor_id,
        circuit_id,
        COUNT(*) AS n_obs,
        AVG(pace_circuit_deviation_s) AS observed_mean_s,
        STDDEV_POP(pace_circuit_deviation_s) AS observed_std_s
    FROM circuit_constructor_obs
    GROUP BY constructor_id, circuit_id
),

with_shrinkage AS (
    SELECT
        *,
        -- Bayesian shrinkage toward 0: prior_weight = 3 (weak prior)
        (n_obs * observed_mean_s)
        / NULLIF(n_obs + 3.0, 0) AS shrunk_interaction_s
    FROM circuit_constructor_agg
)

-- Join back to the race grain for downstream model consumption. Output grain
-- and circuit_key column are unchanged -- only the shrinkage pool moved to
-- circuit_id.
SELECT
    CONCAT(
        CAST(wc.race_year AS VARCHAR), '_',
        wc.race_id, '_',
        wc.constructor_id
    ) AS constructor_race_id,
    wc.race_year,
    wc.race_id,
    wc.constructor_id,
    wc.circuit_key,
    COALESCE(ws.shrunk_interaction_s, 0.0) AS circuit_constructor_interaction_s,
    COALESCE(ws.n_obs, 0) AS interaction_obs_n,
    COALESCE(ws.observed_std_s, 0.0) AS interaction_se_s
FROM with_circuit AS wc
LEFT JOIN with_shrinkage AS ws
    ON
        wc.constructor_id = ws.constructor_id
        AND wc.circuit_id = ws.circuit_id
ORDER BY wc.race_year, wc.race_id, wc.constructor_id
