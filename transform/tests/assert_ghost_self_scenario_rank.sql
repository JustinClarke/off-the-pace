-- Results-anchored gate for the ghost chain: no structural test elsewhere in
-- this suite anchors a ghost output to official results, so a mart that
-- predicts Sargeant beats Verstappen could otherwise ship green. This test
-- anchors the self-scenario (every driver in their OWN car, where all
-- host-vs-ego swaps are 0 so predicted pace == actual pace): the
-- fuel-adjusted mean pace must recover official finishing order.
--
-- Per race, over classified finishers: rank drivers by predicted_mean_residual_pace_s
-- (fuel-adjusted, the ranked quantity) and correlate that rank with the official
-- finish position. Spearman = Pearson of ranks (DuckDB has no native spearman), so
-- CORR over the two rank vectors is the per-race Spearman rho.
--
-- Gate: mean per-race rho >= 0.5 AND no race with rho < 0. Ranking drivers by
-- raw clean-lap pace (no model at all) reproduces official order at rho ~0.87,
-- so that is the practical ceiling this gate can approach.
--
-- SCOPE (honest): because self-scenario swaps are 0, this validates the recombination
-- PACE / decomposition, not the counterfactual car swap itself. Car-swap
-- regressions live in CROSS scenarios and cannot be caught by any self-scenario test;
-- assert_cliff_seed_severity_bounded.sql is a deterministic tripwire on the cliff-seed
-- path, and a cross-scenario championship-plausibility gate would need to live at the
-- app layer.

WITH self_scenario AS (
    SELECT
        race_year,
        race_id,
        ego_driver_id,
        predicted_mean_residual_pace_s
    FROM {{ ref('fct_ghost_race_finish') }}
    WHERE is_self_scenario
),

official AS (
    SELECT
        race_year,
        race_id,
        driver_id AS ego_driver_id,
        finish_position
    FROM {{ ref('stg_results') }}
    WHERE is_classified
      AND finish_position IS NOT NULL
),

joined AS (
    SELECT
        s.race_year,
        s.race_id,
        s.ego_driver_id,
        s.predicted_mean_residual_pace_s,
        o.finish_position
    FROM self_scenario s
    JOIN official o USING (race_year, race_id, ego_driver_id)
),

-- Rank predicted pace WITHIN the classified field per race (faster = better).
ranked AS (
    SELECT
        race_year,
        race_id,
        finish_position,
        RANK() OVER (
            PARTITION BY race_year, race_id
            ORDER BY predicted_mean_residual_pace_s ASC
        ) AS predicted_rank
    FROM joined
),

per_race AS (
    SELECT
        race_year,
        race_id,
        CORR(CAST(predicted_rank AS DOUBLE), CAST(finish_position AS DOUBLE)) AS rho,
        COUNT(*) AS n_drivers
    FROM ranked
    GROUP BY race_year, race_id
    -- Need enough classified drivers for a stable rank correlation.
    HAVING COUNT(*) >= 5
),

summary AS (
    SELECT
        AVG(rho)  AS mean_rho,
        MIN(rho)  AS min_rho,
        COUNT(*)  AS n_races
    FROM per_race
    WHERE rho IS NOT NULL
)

-- Test fails (returns rows) if the mean falls below 0.5 or any single race is
-- negatively correlated with official order.
SELECT
    mean_rho,
    min_rho,
    n_races
FROM summary
WHERE mean_rho < 0.5
   OR min_rho < 0.0
