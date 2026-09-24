-- 06a — Pit-timing opportunity cost, remeasured 2026-09-20.
--
-- Run against data/dev.duckdb after `dbt build --select +int_pit_strategy_value`
-- from transform/ (profile dev). Reproduces every number in
-- 06a_pit_timing_tail.md and the "Verified 2026-09-20" block of
-- ../../work/06-publication.md.
--
-- cd transform && python3 -c "
--   import duckdb
--   con = duckdb.connect('../data/dev.duckdb', read_only=True)
--   ... run the blocks below ...
-- "
-- (must run with cwd = transform/, because stg_laps's underlying source glob
-- is a relative path)

-- ── Headline distribution, all 7,129 stints, both horizons ─────────────────
SELECT
    'opportunity_cost_s (window -- headline)' AS metric,
    count(*) AS n,
    median(opportunity_cost_s) AS median_s,
    avg(opportunity_cost_s) AS mean_s,
    100.0 * sum(CASE WHEN opportunity_cost_s = 0.0 THEN 1 ELSE 0 END)
        / count(*) AS pct_exactly_zero,
    quantile_cont(opportunity_cost_s, 0.90) AS p90_s,
    quantile_cont(opportunity_cost_s, 0.95) AS p95_s,
    quantile_cont(opportunity_cost_s, 0.99) AS p99_s,
    max(opportunity_cost_s) AS max_s
FROM int_pit_strategy_value
UNION ALL
SELECT
    'opportunity_cost_race_s (race-remainder -- diagnostic)',
    count(*),
    median(opportunity_cost_race_s),
    avg(opportunity_cost_race_s),
    100.0 * sum(CASE WHEN opportunity_cost_race_s = 0.0 THEN 1 ELSE 0 END)
        / count(*),
    quantile_cont(opportunity_cost_race_s, 0.90),
    quantile_cont(opportunity_cost_race_s, 0.95),
    quantile_cont(opportunity_cost_race_s, 0.99),
    max(opportunity_cost_race_s)
FROM int_pit_strategy_value;

-- ── Decompose the 47.3% "exactly zero" share ────────────────────────────────
-- 42.0% never pit again this race (no decision to grade, structural 0).
-- 5.4% pitted and landed on the modelled optimum exactly.
SELECT
    count(*) FILTER (WHERE actual_pit_lap IS NULL) AS no_stop_stints,
    count(*) FILTER (
        WHERE actual_pit_lap IS NOT NULL AND opportunity_cost_s = 0.0
    ) AS pitted_and_optimal,
    count(*) FILTER (WHERE opportunity_cost_s = 0.0) AS all_exact_zero,
    count(*) AS total
FROM int_pit_strategy_value;

-- ── Tail concentration: share of total seconds lost in the worst decile ────
WITH ranked AS (
    SELECT
        opportunity_cost_s,
        ntile(10) OVER (ORDER BY opportunity_cost_s) AS decile
    FROM int_pit_strategy_value
)
SELECT
    decile,
    count(*) AS n,
    sum(opportunity_cost_s) AS total_s_lost
FROM ranked
GROUP BY decile
ORDER BY decile;
-- share in decile 10 / sum(all deciles) = 0.611 (61.1%)

-- ── Per-constructor breakdown, n > 150 ──────────────────────────────────────
-- Driver -> constructor is a clean join: zero (race_id, driver_id) pairs map
-- to more than one constructor_id in stg_laps (checked directly, 2026-09-20).
WITH driver_constructor AS (
    SELECT DISTINCT race_id, driver_id, constructor_id
    FROM stg_laps
),
joined AS (
    SELECT v.*, dc.constructor_id
    FROM int_pit_strategy_value AS v
    LEFT JOIN driver_constructor AS dc
        ON v.race_id = dc.race_id AND v.driver_id = dc.driver_id
)
SELECT
    constructor_id,
    count(*) AS n,
    median(opportunity_cost_s) AS median_window_s,
    avg(opportunity_cost_s) AS mean_window_s,
    median(opportunity_cost_race_s) AS median_race_s,
    avg(opportunity_cost_race_s) AS mean_race_s,
    min(race_year) AS first_season,
    max(race_year) AS last_season
FROM joined
GROUP BY constructor_id
HAVING count(*) > 150
ORDER BY mean_window_s;
