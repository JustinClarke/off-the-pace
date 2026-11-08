-- Driver x race summary ("why was he slow at Monza"). Grain: (driver_id,
-- race_id). rating_s = driver_skill_loro_s (median lap-by-lap gap to teammate,
-- negative = faster). rating_s IS the teammate gap, so teammate_gap_s =
-- rating_s (CO-01/T3: it used to be rating_s minus the teammate's rating_s,
-- i.e. twice the gap). No within-race rank or percentile (CO-01/T4): ordering
-- every driver's gap to his own teammate across the field read as a speed
-- ranking ("22nd of 22") and is not one, so the owner dropped it (2026-10-15).
-- The season mart keeps its teammate_gap_rank. positions_gained is NULL for a
-- pit-lane start (grid_position = 0), which is not a grid slot (CO-01/T5).
-- ci_low/high (TX-01): a distribution-free 95% CI for the median that
-- rating_s is, built from the same paired lap gaps
-- (int_driver_race_paired_laps): the order statistics [x_j, x_{n-j+1}] of the
-- n = paired_lap_count sorted gaps, j from macro median_ci_order_rank
-- (coverage >= 95%). NULL when n < 6 (no such interval exists). Not centred
-- on rating_s; for a two-driver car the teammate's CI is the exact mirror.
-- It used to be rating_s +/- 1.96 x the SE of the mean of
-- driver_skill_residual_s over ml_eligible laps, which bracketed a number it
-- was not computed from. rating_trust_label: suppressed (n < 6, no CI),
-- thin (6 <= n < 12), ok (n >= 12).
-- n_races is 1 by construction and omitted; n_clean_laps (ml_eligible laps
-- behind the component means) is given instead.
-- TX-02 reason columns (NULL when the value is present):
--   ci_unavailable_reason  PAIRED_N_BELOW_MIN when ci_low/ci_high are NULL.
--   residual_unavailable_reason when n_clean_laps (and so every component
--     mean) is NULL: NO_TELEMETRY / TYRE_QA_QUARANTINED from
--     mart_race_coverage for the race, else NO_ML_ELIGIBLE_LAPS.
-- Components are means over ml_eligible laps. mean_dirty_air_tax_s (TX-03)
-- is over ml_eligible laps with a MEASURED dirty-air tax only (a row in
-- int_dirty_air_tax_component with a non-NULL tax; n_dirty_air_measured_laps
-- counts them). fct_lap_residuals writes 0.0 on laps with no such row, and a
-- 0.0 there is not clean air, so those laps are left out; the mean is NULL
-- with dirty_air_unavailable_reason = NO_MEASURED_LAPS when none is measured.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT * FROM {{ ref('fct_lap_residuals') }}
),

clean AS (
    SELECT
        race_id, driver_id,
        COUNT(*) AS n_clean_laps,
        AVG(lap_time_s) AS avg_lap_time_s,
        AVG(fuel_component_s) AS mean_fuel_component_s,
        AVG(compound_component_s) AS mean_compound_component_s,
        AVG(constructor_component_s) AS mean_constructor_component_s,
        AVG(dirty_air_tax_s) AS mean_dirty_air_tax_s
    FROM laps
    WHERE ml_eligible = TRUE
    GROUP BY race_id, driver_id
),

-- TX-03: dirty-air mean over measured laps only (see header).
dirty_air AS (
    SELECT
        l.race_id,
        l.driver_id,
        COUNT(da.dirty_air_tax_s) AS n_dirty_air_measured_laps,
        AVG(CASE WHEN da.dirty_air_tax_s IS NOT NULL THEN l.dirty_air_tax_s END)
            AS mean_dirty_air_tax_s
    FROM laps AS l
    LEFT JOIN {{ ref('int_dirty_air_tax_component') }} AS da
        ON l.lap_id = da.lap_id
    WHERE l.ml_eligible = TRUE
    GROUP BY l.race_id, l.driver_id
),

completed AS (
    SELECT race_id, driver_id, COUNT(*) AS laps_completed
    FROM laps
    GROUP BY race_id, driver_id
),

results AS (
    SELECT
        race_id, driver_id,
        CASE
            WHEN grid_position >= 1 THEN grid_position - finish_position
        END AS positions_gained,
        is_dnf AS has_dnf
    FROM {{ ref('stg_results') }}
),

-- TX-01: the paired gaps behind rating_s, ranked, and the CI order
-- statistics.
paired AS (
    SELECT
        race_id,
        driver_id,
        paired_delta_s,
        COUNT(*) OVER (PARTITION BY race_id, driver_id) AS n,
        ROW_NUMBER() OVER (
            PARTITION BY race_id, driver_id ORDER BY paired_delta_s
        ) AS delta_rank
    FROM {{ ref('int_driver_race_paired_laps') }}
),

paired_n AS (
    SELECT DISTINCT n FROM paired
),

ci_rank AS (
    {{ median_ci_order_rank('paired_n', 'n') }}
),

paired_ci AS (
    SELECT
        p.race_id,
        p.driver_id,
        ANY_VALUE(p.n) AS paired_lap_count,
        MAX(p.paired_delta_s) FILTER (
            WHERE p.delta_rank = cr.ci_rank_j
        ) AS ci_low,
        MAX(p.paired_delta_s) FILTER (
            WHERE p.delta_rank = p.n - cr.ci_rank_j + 1
        ) AS ci_high
    FROM paired AS p
    INNER JOIN ci_rank AS cr ON p.n = cr.n
    GROUP BY p.race_id, p.driver_id
),

ratings AS (
    SELECT
        driver_id, race_id, race_year, constructor_id, circuit_key,
        driver_skill_loro_s AS rating_s
    FROM {{ ref('int_driver_race_skill_loro') }}
    WHERE driver_skill_loro_s IS NOT NULL
),

counted AS (
    SELECT
        *,
        COUNT(*) OVER (PARTITION BY race_id) AS n_drivers
    FROM ratings
),

teammates AS (
    SELECT
        a.race_id,
        a.driver_id,
        b.driver_id AS teammate_id
    FROM ratings AS a
    INNER JOIN ratings AS b
        ON
            a.race_id = b.race_id
            AND a.constructor_id = b.constructor_id
            AND a.driver_id <> b.driver_id
    LEFT JOIN clean AS bc
        ON b.race_id = bc.race_id AND b.driver_id = bc.driver_id
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY a.race_id, a.driver_id
        ORDER BY bc.n_clean_laps DESC NULLS LAST, b.driver_id ASC
    ) = 1
),

constructor_rank AS (
    SELECT
        l.race_id,
        l.constructor_id,
        RANK() OVER (
            PARTITION BY l.race_id ORDER BY AVG(l.constructor_component_s)
        ) AS constructor_rank
    FROM laps AS l
    WHERE l.ml_eligible = TRUE
    GROUP BY l.race_id, l.constructor_id
)

SELECT
    k.driver_id,
    k.race_id,
    k.race_year,
    dc.circuit_id,
    k.rating_s,
    k.n_drivers,
    pc.ci_low,
    pc.ci_high,
    c.n_clean_laps,
    t.teammate_id,
    CASE WHEN t.teammate_id IS NOT NULL THEN k.rating_s END AS teammate_gap_s,
    k.constructor_id,
    cr.constructor_rank,
    c.mean_fuel_component_s,
    c.mean_compound_component_s,
    c.mean_constructor_component_s,
    dair.mean_dirty_air_tax_s,
    c.avg_lap_time_s,
    cp.laps_completed,
    r.positions_gained,
    COALESCE(r.has_dnf, FALSE) AS has_dnf,
    pc.paired_lap_count,
    CASE
        WHEN pc.paired_lap_count >= 12 THEN 'ok'
        WHEN pc.paired_lap_count >= 6 THEN 'thin'
        ELSE 'suppressed'
    END AS rating_trust_label,
    CASE
        WHEN pc.ci_low IS NULL THEN 'PAIRED_N_BELOW_MIN'
    END AS ci_unavailable_reason,
    CASE
        WHEN c.n_clean_laps IS NOT NULL THEN NULL
        WHEN NOT rc.has_telemetry THEN 'NO_TELEMETRY'
        WHEN rc.tyre_qa_status = 'quarantined_race' THEN 'TYRE_QA_QUARANTINED'
        ELSE 'NO_ML_ELIGIBLE_LAPS'
    END AS residual_unavailable_reason,
    COALESCE(dair.n_dirty_air_measured_laps, 0) AS n_dirty_air_measured_laps,
    CASE
        WHEN dair.mean_dirty_air_tax_s IS NULL THEN 'NO_MEASURED_LAPS'
    END AS dirty_air_unavailable_reason
FROM counted AS k
LEFT JOIN clean AS c ON k.race_id = c.race_id AND k.driver_id = c.driver_id
LEFT JOIN dirty_air AS dair
    ON k.race_id = dair.race_id AND k.driver_id = dair.driver_id
LEFT JOIN paired_ci AS pc
    ON k.race_id = pc.race_id AND k.driver_id = pc.driver_id
LEFT JOIN completed AS cp
    ON k.race_id = cp.race_id AND k.driver_id = cp.driver_id
LEFT JOIN results AS r ON k.race_id = r.race_id AND k.driver_id = r.driver_id
LEFT JOIN teammates AS t ON k.race_id = t.race_id AND k.driver_id = t.driver_id
LEFT JOIN constructor_rank AS cr
    ON k.race_id = cr.race_id AND k.constructor_id = cr.constructor_id
LEFT JOIN {{ ref('dim_circuits') }} AS dc ON k.circuit_key = dc.circuit_key
LEFT JOIN {{ ref('mart_race_coverage') }} AS rc ON k.race_id = rc.race_id
ORDER BY k.race_year, k.race_id, k.rating_s, k.driver_id
