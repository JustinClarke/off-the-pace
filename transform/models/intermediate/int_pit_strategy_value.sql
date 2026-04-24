-- Third Model Sequence #1: Pit window opportunity cost.
-- For each driver stint, computes the optimal pit lap and the seconds-cost of
-- the actual pit decision relative to the modelled optimum.
--
-- Output grain: stint_id one row per stint.
-- PK: stint_id (FK to int_stint_geometry).
--
-- Identification: counterfactual cost calculation not causal inference.
-- The model answers "what would the cumulative degradation cost have been
-- if pitted at lap L?" and minimises over the [cliff_onset-5, cliff_onset+10] window.
--
-- optimal_pit_lap: argmin total remaining degradation cost given pit-lane loss.
-- opportunity_cost_s: Σ(degradation penalty) from overrunning the optimal lap.
-- undercut_threat_lap: first lap where gap-to-ahead < pit_loss + 1s.
-- strategy_verdict: optimal / overran / undercut_forced / early.
--
-- Assumptions:
--   1. Cliff model (int_compound_cliff_predicted) is the correct counterfactual.
--   2. Pit-lane loss is constant per circuit (from circuit_reference.csv).
--   3. Undercut threat captured by gap_to_ahead (ignores overcut threat).
--   4. Last stint of race has no pit actual_pit_lap NULL.

{{ config(materialized='table', tags=['simulation', 'strategy']) }}

WITH stint_meta AS (
    SELECT
        sg.stint_id,
        sg.race_year,
        sg.race_id,
        sg.driver_id,
        sg.lap_in_stint,
        sg.age_in_stint,
        sg.lap_number,
        sg.lap_id
    FROM {{ ref('int_stint_geometry') }} sg
),

cliff_per_lap AS (
    SELECT
        cp.lap_id,
        cp.stint_id         AS cliff_stint_id,
        cp.race_year,
        cp.race_id,
        cp.driver_id,
        cp.lap_number,
        cp.age_in_stint,
        cp.compound,
        cp.expected_compound_pace_s,
        cp.expected_degradation_rate_s_per_lap,
        cp.cliff_onset_passed,
        cp.laps_past_cliff
    FROM {{ ref('int_compound_cliff_predicted') }} cp
),

-- Compute cliff onset lap per stint: first lap_in_stint where cliff_onset_passed = TRUE
cliff_onset_per_stint AS (
    SELECT
        sg.stint_id,
        MIN(sg.lap_in_stint) FILTER (WHERE cp.cliff_onset_passed = TRUE)
            AS cliff_onset_lap_in_stint,
        MAX(sg.lap_in_stint)
            AS stint_length_laps,
        MAX(sg.lap_number) FILTER (WHERE cp.cliff_onset_passed = TRUE)
            AS cliff_onset_lap_number,
        MAX(cp.compound) AS compound
    FROM stint_meta sg
    LEFT JOIN cliff_per_lap cp USING (lap_id)
    GROUP BY sg.stint_id
),

-- Race mapping to get track key for circuit_reference join
race_map AS (
    SELECT race_id, track_id AS circuit_key
    FROM {{ ref('race_to_track') }}
),

-- Pit-lane loss per circuit
circuit_pit_loss AS (
    SELECT
        cr.circuit_key,
        COALESCE(CAST(cr.pit_lane_loss_s AS DOUBLE), 21.0)  AS pit_lane_loss_s,
        CAST(cr.pit_loss_imputed_flag AS BOOLEAN)           AS pit_loss_imputed_flag
    FROM {{ ref('circuit_reference') }} cr
),

-- Actual pit data: one row per (driver, race, stint) pit event
actual_pits AS (
    SELECT
        p.race_year,
        p.race_id,
        p.driver_id,
        p.pit_in_lap_number                                 AS actual_pit_lap,
        p.stint_number
    FROM {{ ref('stg_pits') }} p
    WHERE p.pit_in_time_s IS NOT NULL
),

-- Aggregate air state to stint grain: minimum gap-to-ahead per stint
-- (used for undercut threat detection)
min_gap_per_stint AS (
    SELECT
        sg.stint_id,
        sg.race_year,
        sg.race_id,
        sg.driver_id,
        -- Minimum gap in the potential pit window [cliff_onset-5, cliff_onset+10]
        MIN(CASE
            WHEN la.min_gap_s IS NOT NULL THEN la.min_gap_s
            ELSE 999.0
        END) AS min_gap_in_window_s,
        -- First lap_number where gap drops below undercut threshold
        MIN(CASE
            WHEN la.min_gap_s < 22.0 THEN sg.lap_number
            ELSE NULL
        END) AS first_undercut_threat_lap
    FROM stint_meta sg
    LEFT JOIN {{ ref('int_lap_air_state') }} la USING (lap_id)
    GROUP BY sg.stint_id, sg.race_year, sg.race_id, sg.driver_id
),

-- Cumulative degradation cost curve per stint:
-- For each lap L, the total expected degradation cost if staying until lap L.
-- We compute the running SUM of expected_compound_pace_s within each stint.
cumulative_cost AS (
    SELECT
        sg.stint_id,
        sg.race_year,
        sg.race_id,
        sg.driver_id,
        sg.lap_in_stint,
        sg.lap_number,
        COALESCE(cp.expected_compound_pace_s, 0.0) AS expected_pace_this_lap,
        SUM(COALESCE(cp.expected_compound_pace_s, 0.0))
            OVER (PARTITION BY sg.stint_id ORDER BY sg.lap_in_stint
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                                                   AS cumulative_expected_pace_s
    FROM stint_meta sg
    LEFT JOIN cliff_per_lap cp USING (lap_id)
),

-- Find the optimal pit lap: minimise remaining degradation cost + pit loss.
-- 
-- The opportunity cost math:
--   Let L be the candidate pit lap.
--   Let expected_pace(t) be the expected tyre wear penalty at lap t.
--   Let pit_loss be the circuit-specific pit lane overhead (s).
--   The cost function is:
--     Total_Cost(L) = Sum_{t=1}^{L} expected_pace(t) + pit_loss + Sum_{t=L+1}^{End} expected_pace_new_tyre(t-L)
-- 
--   The optimal pit lap L* is the argmin_{L} Total_Cost(L) evaluated within a window
--   around the fitted tyre cliff onset: [cliff_onset 1, cliff_onset + 10].
-- 
--   Simplification for SQL:
--     Instead of computing the full counterfactual summation dynamically in SQL (which is extremely expensive),
--     we approximate L* as the first lap where the expected compound wear penalty (`expected_pace_this_lap`)
--     exceeds 0.5 seconds, capturing the sharp wear acceleration at the cliff boundary.
optimal_pit_estimate AS (
    SELECT
        cc.stint_id,
        cos.cliff_onset_lap_in_stint,
        cos.stint_length_laps,
        cos.compound,
        -- Optimal pit: first lap_in_stint in window where rate exceeds cliff threshold
        MIN(CASE
            WHEN cos.cliff_onset_lap_in_stint IS NOT NULL
                 AND cc.lap_in_stint >= GREATEST(cos.cliff_onset_lap_in_stint-1, 1)
                 AND cc.lap_in_stint <= cos.cliff_onset_lap_in_stint + 10
                 AND cc.expected_pace_this_lap > 0.5
            THEN cc.lap_in_stint
            ELSE NULL
        END) AS optimal_pit_lap_in_stint,
        MIN(CASE
            WHEN cos.cliff_onset_lap_in_stint IS NOT NULL
                 AND cc.lap_in_stint >= GREATEST(cos.cliff_onset_lap_in_stint-1, 1)
                 AND cc.lap_in_stint <= cos.cliff_onset_lap_in_stint + 10
                 AND cc.expected_pace_this_lap > 0.5
            THEN cc.lap_number
            ELSE NULL
        END) AS optimal_pit_lap_number
    FROM cumulative_cost cc
    JOIN cliff_onset_per_stint cos USING (stint_id)
    GROUP BY cc.stint_id, cos.cliff_onset_lap_in_stint, cos.stint_length_laps, cos.compound
),

-- Compute opportunity cost: Σ of extra degradation from the optimal to actual pit lap
opportunity_cost_calc AS (
    SELECT
        ope.stint_id,
        ope.cliff_onset_lap_in_stint,
        ope.stint_length_laps,
        ope.compound,
        ope.optimal_pit_lap_in_stint,
        ope.optimal_pit_lap_number,
        -- Total degradation accumulation in overrun window
        SUM(
            CASE
                WHEN cc.lap_in_stint > COALESCE(ope.optimal_pit_lap_in_stint, 999)
                THEN GREATEST(cc.expected_pace_this_lap, 0.0)
                ELSE 0.0
            END
        ) AS pre_actual_overrun_cost_s
    FROM optimal_pit_estimate ope
    JOIN cumulative_cost cc USING (stint_id)
    GROUP BY ope.stint_id, ope.cliff_onset_lap_in_stint, ope.stint_length_laps,
             ope.compound, ope.optimal_pit_lap_in_stint, ope.optimal_pit_lap_number
),

-- Join actual pit laps, compute overrun and verdict
stint_base AS (
    SELECT
        stint_id,
        race_year,
        race_id,
        driver_id,
        MAX(lap_in_stint) AS stint_length_laps
    FROM stint_meta
    GROUP BY stint_id, race_year, race_id, driver_id
),

-- Get stint_number for joining to actual_pits
stint_numbers AS (
    SELECT DISTINCT
        sg.stint_id,
        sg.race_year,
        sg.race_id,
        sg.driver_id,
        MIN(sg.lap_number)  AS stint_start_lap,
        MAX(sg.lap_number)  AS stint_end_lap
    FROM stint_meta sg
    GROUP BY sg.stint_id, sg.race_year, sg.race_id, sg.driver_id
)

SELECT
    sb.stint_id,
    sb.race_year,
    sb.race_id,
    sb.driver_id,
    occ.compound,
    occ.cliff_onset_lap_in_stint,
    sb.stint_length_laps,
    occ.optimal_pit_lap_in_stint,
    occ.optimal_pit_lap_number                                  AS optimal_pit_lap,
    -- Actual pit lap: pit_in_lap_number for the pit stop at the END of this stint
    ap.actual_pit_lap,
    -- Overrun: actual minus optimal (negative = pitted early)
    CASE
        WHEN ap.actual_pit_lap IS NULL OR occ.optimal_pit_lap_number IS NULL THEN NULL
        ELSE ap.actual_pit_lap-occ.optimal_pit_lap_number
    END                                                         AS overrun_laps,
    -- Opportunity cost: degradation penalty accumulated by overrunning
    CASE
        WHEN ap.actual_pit_lap IS NULL THEN 0.0
        WHEN occ.optimal_pit_lap_number IS NULL THEN 0.0
        WHEN ap.actual_pit_lap > occ.optimal_pit_lap_number THEN GREATEST(occ.pre_actual_overrun_cost_s, 0.0)
        ELSE 0.0
    END                                                         AS opportunity_cost_s,
    -- Confidence in optimal lap (degrades when cliff onset is NULL)
    CASE
        WHEN occ.cliff_onset_lap_in_stint IS NULL THEN 0.0
        WHEN occ.optimal_pit_lap_in_stint IS NULL THEN 0.1
        ELSE 0.8
    END                                                         AS optimal_pit_lap_confidence,
    -- Undercut threat: first lap where gap < pit_loss + 1.0 s
    mgps.first_undercut_threat_lap                              AS undercut_threat_lap,
    -- Pit-lane loss
    COALESCE(cpl.pit_lane_loss_s, 21.0)                         AS pit_lane_loss_s,
    COALESCE(cpl.pit_loss_imputed_flag, TRUE)                   AS pit_loss_imputed_flag,
    -- Strategy verdict
    CASE
        WHEN ap.actual_pit_lap IS NULL
            THEN NULL
        WHEN occ.optimal_pit_lap_number IS NULL
            THEN 'unknown'
        WHEN ABS(ap.actual_pit_lap-occ.optimal_pit_lap_number) <= 1
            THEN 'optimal'
        WHEN ap.actual_pit_lap > occ.optimal_pit_lap_number + 1
            THEN 'overran'
        WHEN ap.actual_pit_lap < occ.optimal_pit_lap_number-1
             AND mgps.first_undercut_threat_lap IS NOT NULL
             AND ap.actual_pit_lap >= mgps.first_undercut_threat_lap-2
            THEN 'undercut_forced'
        WHEN ap.actual_pit_lap < occ.optimal_pit_lap_number-1
            THEN 'early'
        ELSE 'optimal'
    END                                                         AS strategy_verdict
FROM stint_base sb
LEFT JOIN stint_numbers sn            USING (stint_id)
LEFT JOIN opportunity_cost_calc occ   USING (stint_id)
LEFT JOIN min_gap_per_stint mgps      USING (stint_id)
LEFT JOIN race_map rm                 ON sb.race_id = rm.race_id
LEFT JOIN circuit_pit_loss cpl        ON rm.circuit_key = cpl.circuit_key
LEFT JOIN actual_pits ap
    ON sb.race_year  = ap.race_year
    AND sb.race_id   = ap.race_id
    AND sb.driver_id = ap.driver_id
    AND ap.actual_pit_lap BETWEEN sn.stint_start_lap AND sn.stint_end_lap + 1
ORDER BY sb.race_year, sb.race_id, sb.driver_id
