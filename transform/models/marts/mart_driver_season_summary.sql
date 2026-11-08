-- Driver x season summary for LLM explanations ("22nd of 22").
-- Grain: (driver_id, race_year). Sorted by year, rank.
-- rating_s = era_adjusted_rating (shrunk teammate-relative gap, seconds;
-- negative = faster). rating_s IS already the gap to his teammate(s) (season
-- average over every teammate he raced, pooled), so teammate_gap_s = rating_s;
-- it used to be rating_s minus the teammate's rating_s, about twice the gap
-- (CO-01/T3). teammate_id is the single teammate with the most clean laps; a
-- driver who changed teammates mid-season is still rated against all of them.
-- teammate_gap_rank 1 = most negative gap, i.e. furthest ahead of his own
-- teammate; it is NOT a speed ranking against the field (CO-01/T4). It and
-- teammate_gap_percentile are a point ordering of rating_s with no
-- uncertainty: adjacent ranks are almost never separated by the CI (171 of
-- 173 drivers' CIs overlap the next-ranked driver's on the v16 build), so
-- quote a rank only with the CI. rank_separated_from_next (TX-06) is TRUE
-- when this driver's ci_high < the next-ranked driver's ci_low that season.
-- rating_se_s, rating_confidence, total_clean_laps_n and the two anchor flags
-- are carried unchanged from int_era_normalized_driver_rating. Component
-- means are over ml_eligible laps only (seconds, positive = slower);
-- mean_dirty_air_tax_s (TX-03) only over those with a measured dirty-air tax
-- (a row in int_dirty_air_tax_component with a non-NULL tax), since
-- fct_lap_residuals writes 0.0 where there is none. NULL with
-- dirty_air_unavailable_reason = NO_MEASURED_LAPS when none is measured.
-- Primary constructor = the one the driver ran the most clean laps for;
-- teammate = the other driver with the most clean laps for that constructor.
-- n_races_unrated (TX-02): races the driver has laps for in fct_lap_residuals
-- that season with no mart_race_driver_summary row (e.g. 2021_16, all wet);
-- mart_race_coverage says why per race.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT
        race_year, driver_id, constructor_id, fuel_component_s,
        compound_component_s, constructor_component_s, dirty_air_tax_s
    FROM {{ ref('fct_lap_residuals') }}
    WHERE ml_eligible = TRUE
),

-- TX-03: dirty-air mean over measured laps only (see header).
dirty_air AS (
    SELECT
        f.race_year,
        f.driver_id,
        COUNT(da.dirty_air_tax_s) AS n_dirty_air_measured_laps,
        AVG(CASE WHEN da.dirty_air_tax_s IS NOT NULL THEN f.dirty_air_tax_s END)
            AS mean_dirty_air_tax_s
    FROM {{ ref('fct_lap_residuals') }} AS f
    LEFT JOIN {{ ref('int_dirty_air_tax_component') }} AS da
        ON f.lap_id = da.lap_id
    WHERE f.ml_eligible = TRUE
    GROUP BY f.race_year, f.driver_id
),

driver_constructor AS (
    SELECT race_year, driver_id, constructor_id, COUNT(*) AS n_laps
    FROM laps
    GROUP BY race_year, driver_id, constructor_id
),

primary_team AS (
    SELECT race_year, driver_id, constructor_id, n_laps
    FROM driver_constructor
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY race_year, driver_id
        ORDER BY n_laps DESC, constructor_id ASC
    ) = 1
),

components AS (
    SELECT
        race_year,
        driver_id,
        AVG(fuel_component_s) AS mean_fuel_component_s,
        AVG(compound_component_s) AS mean_compound_component_s,
        AVG(constructor_component_s) AS mean_constructor_component_s,
        AVG(dirty_air_tax_s) AS mean_dirty_air_tax_s
    FROM laps
    GROUP BY race_year, driver_id
),

ratings AS (
    SELECT
        r.driver_id,
        r.season AS race_year,
        r.era_adjusted_rating AS rating_s,
        r.era_adjusted_rating_ci_low_s AS ci_low,
        r.era_adjusted_rating_ci_high_s AS ci_high,
        r.n_races,
        r.era_adjusted_rating_se_s AS rating_se_s,
        r.rating_confidence,
        r.total_clean_laps_n,
        r.bridge_driver_anchor_flag,
        r.low_anchor_sample_flag
    FROM {{ ref('int_era_normalized_driver_rating') }} AS r
    INNER JOIN primary_team AS p
        ON r.driver_id = p.driver_id AND r.season = p.race_year
),

ranked AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY race_year ORDER BY rating_s
        ) AS teammate_gap_rank,
        COUNT(*) OVER (PARTITION BY race_year) AS n_drivers,
        -- Next-ranked driver's ci_low (ties broken by driver_id); NULL for
        -- the last-ranked driver of the season.
        LEAD(ci_low) OVER (
            PARTITION BY race_year ORDER BY rating_s, driver_id
        ) AS next_ranked_ci_low
    FROM ratings
),

teammates AS (
    SELECT
        a.race_year,
        a.driver_id,
        b.driver_id AS teammate_id
    FROM primary_team AS a
    INNER JOIN driver_constructor AS b
        ON
            a.race_year = b.race_year
            AND a.constructor_id = b.constructor_id
            AND a.driver_id <> b.driver_id
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY a.race_year, a.driver_id
        ORDER BY b.n_laps DESC, b.driver_id ASC
    ) = 1
),

unrated AS (
    SELECT
        f.race_year,
        f.driver_id,
        COUNT(DISTINCT f.race_id) FILTER (
            WHERE m.race_id IS NULL
        ) AS n_races_unrated
    FROM {{ ref('fct_lap_residuals') }} AS f
    LEFT JOIN {{ ref('mart_race_driver_summary') }} AS m
        ON f.race_id = m.race_id AND f.driver_id = m.driver_id
    GROUP BY f.race_year, f.driver_id
),

constructor_rank AS (
    SELECT
        race_year,
        constructor_id,
        RANK() OVER (
            PARTITION BY race_year ORDER BY AVG(constructor_component_s)
        ) AS constructor_rank
    FROM laps
    GROUP BY race_year, constructor_id
)

SELECT
    k.driver_id,
    k.race_year,
    k.rating_s,
    k.teammate_gap_rank,
    k.n_drivers,
    1.0 - (k.teammate_gap_rank - 1.0) / NULLIF(k.n_drivers - 1, 0)
        AS teammate_gap_percentile,
    k.ci_low,
    k.ci_high,
    k.n_races,
    t.teammate_id,
    CASE WHEN t.teammate_id IS NOT NULL THEN k.rating_s END AS teammate_gap_s,
    p.constructor_id,
    cr.constructor_rank,
    c.mean_fuel_component_s,
    c.mean_compound_component_s,
    c.mean_constructor_component_s,
    dair.mean_dirty_air_tax_s,
    COALESCE(u.n_races_unrated, 0) AS n_races_unrated,
    COALESCE(dair.n_dirty_air_measured_laps, 0) AS n_dirty_air_measured_laps,
    CASE
        WHEN dair.mean_dirty_air_tax_s IS NULL THEN 'NO_MEASURED_LAPS'
    END AS dirty_air_unavailable_reason,
    k.rating_se_s,
    k.rating_confidence,
    k.total_clean_laps_n,
    k.bridge_driver_anchor_flag,
    k.low_anchor_sample_flag,
    k.ci_high < k.next_ranked_ci_low AS rank_separated_from_next
FROM ranked AS k
INNER JOIN primary_team AS p
    ON k.driver_id = p.driver_id AND k.race_year = p.race_year
LEFT JOIN components AS c
    ON k.driver_id = c.driver_id AND k.race_year = c.race_year
LEFT JOIN teammates AS t
    ON k.driver_id = t.driver_id AND k.race_year = t.race_year
LEFT JOIN constructor_rank AS cr
    ON p.constructor_id = cr.constructor_id AND p.race_year = cr.race_year
LEFT JOIN dirty_air AS dair
    ON k.driver_id = dair.driver_id AND k.race_year = dair.race_year
LEFT JOIN unrated AS u
    ON k.driver_id = u.driver_id AND k.race_year = u.race_year
ORDER BY k.race_year, k.teammate_gap_rank
