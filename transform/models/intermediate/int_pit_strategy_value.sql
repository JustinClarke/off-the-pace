-- Pit window opportunity cost.
-- For each driver stint, computes the optimal pit lap and the seconds-cost of
-- the actual pit decision relative to the modelled optimum.
--
-- Output grain: stint_id one row per stint.
-- PK: stint_id (FK to int_stint_geometry).
--
-- Identification: counterfactual cost calculation not causal inference.
-- The model answers "what would the total time loss have been if pitted at
-- lap L?" and takes the argmin over every lap in the horizon.
--
-- THE ARGMIN IS REAL NOW. Until 2026-08-23 this model wrote down a
-- Total_Cost(L) minimisation in its header and implemented "the first lap in
-- the cliff window where expected wear exceeds 0.5 s" -- a threshold with no
-- pit-loss term in it, so a longer pit lane could not move the answer. It
-- returned 'optimal' on 8 stints of 7,129 and 'unknown' on 2,231, which is
-- more than half of every stint that actually ended in a stop. The cost
-- surface now lives in int_pit_strategy_cost_curve, one row per candidate
-- lap, and this model is the argmin over it. See that model's header for the
-- cost function and for why the pit term has to depend on L at all.
--
-- optimal_pit_lap: argmin_L Total_Cost(L) over the horizon.
-- opportunity_cost_s: Total_Cost(actual) - Total_Cost(optimal). Non-negative
--   by construction, and now counts pitting EARLY as a cost too, which the
--   overrun-only definition it replaces could not.
-- undercut_threat_lap: first lap where gap-to-ahead < pit_loss + 1s.
-- strategy_verdict: optimal / overran / undercut_forced / early / unknown.
--
-- TWO HORIZONS, both reported. The verdict follows the two-stint window --
-- this stint's first lap through the next stint's last lap -- because that is
-- the only framing that is well posed for the 61% of stints belonging to a
-- 2-stop or longer race. The race-remainder optimum is carried alongside as a
-- diagnostic: it asks the bigger and harsher question, "if they had stopped
-- only once more, when?", and is unconditional on the rest of the strategy.
-- horizon_source records which one the verdict used.
--
-- Assumptions:
--   1. Cliff model (int_compound_cliff_predicted, via dim_compounds_season)
--      is the correct counterfactual, extrapolated past the observed stint.
--   2. Pit-lane loss is constant per circuit, taken from
--      int_pit_loss_circuit's empirical, EB-shrunk estimate (median in-lap +
--      out-lap loss over that venue's green-flag stops). The
--      circuit_reference.pit_lane_loss_s seed is the fallback for a circuit
--      that resolves no stops; pit_loss_source records which was used.
--   3. Undercut threat captured by gap_to_ahead (ignores overcut threat).
--   4. Last stint of race has no pit actual_pit_lap NULL.
--   5. Laps are counted in VALID laps, so optimal_pit_lap_in_stint means
--      "after this many racing laps on the set", not a chronological index.

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
        sg.lap_id,
        sg.stint_length_valid
    FROM {{ ref('int_stint_geometry') }} AS sg
    -- int_stint_geometry now carries SC/pit/invalid laps too; this model's
    -- degradation-cost simulation is pace-fitting, not a physics window, so
    -- it stays valid-lap-only (restores pre-A1 behaviour: SC laps must not
    -- inflate counted stint duration or leak into the undercut-threat gap
    -- scan below).
    WHERE sg.is_valid_lap = TRUE
),

cliff_per_lap AS (
    SELECT
        cp.lap_id,
        cp.cliff_onset_passed
    FROM {{ ref('int_compound_cliff_predicted') }} AS cp
),

-- Compute cliff onset lap per stint: first lap_in_stint where
-- cliff_onset_passed = TRUE. Reported for context; it no longer bounds the
-- search, because a minimisation that is only allowed to look near the cliff
-- cannot discover that the cliff is not where the money is.
cliff_onset_per_stint AS (
    SELECT
        sg.stint_id,
        MIN(sg.lap_in_stint) FILTER (WHERE cp.cliff_onset_passed = TRUE)
            AS cliff_onset_lap_in_stint,
        MAX(sg.stint_length_valid) AS stint_length_laps
    FROM stint_meta AS sg
    LEFT JOIN cliff_per_lap AS cp ON sg.lap_id = cp.lap_id
    GROUP BY sg.stint_id
),

-- Race mapping to get track key for circuit_reference join
race_map AS (
    SELECT
        race_id,
        track_id AS circuit_key
    FROM {{ ref('race_to_track') }}
),

-- Pit-lane loss per circuit. The empirical estimate wins wherever it exists:
-- it is measured off that venue's own green-flag stops and spans ~16-31 s,
-- where the seed constant is 21.0 s flat for the 8 circuits nobody measured
-- and 19-24 s for the rest. The seed only fills in for a circuit that
-- resolved no clean stops at all.
circuit_pit_loss AS (
    SELECT
        cr.circuit_key,
        COALESCE(
            pl.pit_loss_s_shrunk,
            CAST(cr.pit_lane_loss_s AS DOUBLE),
            21.0
        ) AS pit_lane_loss_s,
        CASE
            WHEN pl.pit_loss_s_shrunk IS NOT NULL THEN 'empirical'
            WHEN cr.pit_lane_loss_s IS NOT NULL THEN 'seed'
            ELSE 'default'
        END AS pit_loss_source,
        -- Imputed now means "nothing was measured for this circuit on either
        -- side", not "the seed row was a guess".
        (
            pl.pit_loss_s_shrunk IS NULL
            AND COALESCE(CAST(cr.pit_loss_imputed_flag AS BOOLEAN), TRUE)
        ) AS pit_loss_imputed_flag
    FROM {{ ref('circuit_reference') }} AS cr
    LEFT JOIN {{ ref('int_pit_loss_circuit') }} AS pl
        ON cr.circuit_key = pl.circuit_slug
),

-- Actual pit data: one row per (driver, race, stint) pit event
actual_pits AS (
    SELECT
        p.race_year,
        p.race_id,
        p.driver_id,
        p.pit_in_lap_number AS actual_pit_lap,
        p.stint_number
    FROM {{ ref('stg_pits') }} AS p
    WHERE p.pit_in_time_s IS NOT NULL
),

-- Aggregate air state to stint grain: minimum gap-to-ahead per stint
-- (used for undercut threat detection)
min_gap_per_stint AS (
    SELECT
        sg.stint_id,
        -- Minimum gap over the stint.
        MIN(COALESCE(la.min_gap_s, 999.0)) AS min_gap_in_window_s,
        -- First lap_number where the gap ahead drops under one pit stop plus
        -- a second of margin. The threshold is the circuit's own pit-lane
        -- loss, so a long pit lane opens the undercut window earlier than a
        -- short one instead of every venue sharing a flat 22 s.
        MIN(CASE
            WHEN la.min_gap_s < COALESCE(cpl.pit_lane_loss_s, 21.0) + 1.0
                THEN sg.lap_number
        END) AS first_undercut_threat_lap
    FROM stint_meta AS sg
    LEFT JOIN {{ ref('int_lap_air_state') }} AS la ON sg.lap_id = la.lap_id
    LEFT JOIN race_map AS rm ON sg.race_id = rm.race_id
    LEFT JOIN circuit_pit_loss AS cpl ON rm.circuit_key = cpl.circuit_key
    GROUP BY sg.stint_id
),

-- ─── The argmin ────────────────────────────────────────────────────────────
curve AS (
    SELECT
        stint_id,
        horizon_scope,
        horizon_laps,
        stint_valid_laps,
        candidate_pit_lap_offset,
        candidate_lap_number,
        total_cost_s
    FROM {{ ref('int_pit_strategy_cost_curve') }}
),

ranked AS (
    SELECT
        c.stint_id,
        c.horizon_scope,
        c.horizon_laps,
        c.candidate_pit_lap_offset,
        c.candidate_lap_number,
        c.total_cost_s,
        ROW_NUMBER() OVER (
            PARTITION BY c.stint_id, c.horizon_scope
            ORDER BY c.total_cost_s, c.candidate_pit_lap_offset
        ) AS cost_rank,
        MIN(c.total_cost_s) OVER (
            PARTITION BY c.stint_id, c.horizon_scope
        ) AS min_total_cost_s
    FROM curve AS c
),

optimum AS (
    SELECT
        stint_id,
        horizon_scope,
        horizon_laps,
        candidate_pit_lap_offset AS optimal_offset,
        -- The candidate lap is the last lap RUN on the set, so the stop
        -- itself is the lap after it -- which is the basis stg_pits records
        -- pit_in_lap_number on.
        candidate_lap_number + 1 AS optimal_pit_lap,
        total_cost_s AS optimal_total_cost_s
    FROM ranked
    WHERE cost_rank = 1
),

-- How sharply identified the optimum is: the share of candidate laps that are
-- more than a second worse than it. 1.0 = one lap stands out; near 0 = the
-- cost curve is flat and the exact lap barely matters.
sharpness AS (
    SELECT
        stint_id,
        horizon_scope,
        SUM(CASE WHEN total_cost_s > min_total_cost_s + 1.0 THEN 1 ELSE 0 END)
        / CAST(COUNT(*) AS DOUBLE) AS optimal_pit_lap_confidence
    FROM ranked
    GROUP BY stint_id, horizon_scope
),

-- The cost of the decision actually taken: run the set for exactly as many
-- valid laps as the stint lasted. Comparing offsets rather than lap numbers
-- keeps this exact -- an invalid lap before the stop would break a
-- lap-number match.
actual_cost AS (
    SELECT
        stint_id,
        horizon_scope,
        stint_valid_laps AS actual_offset,
        total_cost_s AS actual_total_cost_s
    FROM curve
    WHERE candidate_pit_lap_offset = stint_valid_laps
),

-- Verdict horizon: the two-stint window, falling back to the race remainder
-- for a stint with no successor (a driver who retired in the pit lane).
window_pick AS (
    SELECT
        o.stint_id,
        o.horizon_laps,
        o.optimal_offset,
        o.optimal_pit_lap,
        o.optimal_total_cost_s,
        s.optimal_pit_lap_confidence,
        a.actual_offset,
        a.actual_total_cost_s
    FROM optimum AS o
    LEFT JOIN sharpness AS s
        ON o.stint_id = s.stint_id AND o.horizon_scope = s.horizon_scope
    LEFT JOIN actual_cost AS a
        ON o.stint_id = a.stint_id AND o.horizon_scope = a.horizon_scope
    WHERE o.horizon_scope = 'window'
),

race_pick AS (
    SELECT
        o.stint_id,
        o.horizon_laps AS race_horizon_laps,
        o.optimal_offset AS optimal_offset_race,
        o.optimal_pit_lap AS optimal_pit_lap_race,
        o.optimal_total_cost_s AS optimal_total_cost_race_s,
        a.actual_total_cost_s AS actual_total_cost_race_s
    FROM optimum AS o
    LEFT JOIN actual_cost AS a
        ON o.stint_id = a.stint_id AND o.horizon_scope = a.horizon_scope
    WHERE o.horizon_scope = 'race'
),

-- Join actual pit laps, compute overrun and verdict
stint_base AS (
    SELECT
        stint_id,
        race_year,
        race_id,
        driver_id,
        MAX(stint_length_valid) AS stint_length_laps
    FROM stint_meta
    GROUP BY stint_id, race_year, race_id, driver_id
),

-- Get stint_number for joining to actual_pits
stint_numbers AS (
    -- GROUP BY already yields one row per stint_id; no DISTINCT needed.
    SELECT
        sg.stint_id,
        sg.race_year,
        sg.race_id,
        sg.driver_id,
        MIN(sg.lap_number) AS stint_start_lap,
        MAX(sg.lap_number) AS stint_end_lap
    FROM stint_meta AS sg
    GROUP BY sg.stint_id, sg.race_year, sg.race_id, sg.driver_id
),

-- One actual pit per stint: the pit that TERMINATES the stint (the latest
-- pit-in
-- within the stint's lap window). Red-flag races (e.g. 2022 Monaco) can record
-- two
-- pit events inside a single FastF1 stint number without this dedupe the same
-- stint_id matches multiple actual_pits rows and the stint_id grain breaks.
stint_actual_pit AS (
    SELECT
        sn.stint_id,
        MAX(ap.actual_pit_lap) AS actual_pit_lap
    FROM stint_numbers AS sn
    INNER JOIN actual_pits AS ap
        ON
            sn.race_year = ap.race_year
            AND sn.race_id = ap.race_id
            AND sn.driver_id = ap.driver_id
            AND ap.actual_pit_lap
            BETWEEN sn.stint_start_lap AND sn.stint_end_lap
            + 1
    GROUP BY sn.stint_id
),

-- Compound and cliff context, plus the pieces the verdict reads.
assembled AS (
    SELECT
        sb.stint_id,
        sb.race_year,
        sb.race_id,
        sb.driver_id,
        sb.stint_length_laps,
        cos.cliff_onset_lap_in_stint,
        ap.actual_pit_lap,
        mgps.first_undercut_threat_lap,
        cpl.pit_lane_loss_s,
        cpl.pit_loss_source,
        cpl.pit_loss_imputed_flag,
        wp.optimal_offset,
        wp.optimal_pit_lap,
        wp.optimal_pit_lap_confidence,
        wp.actual_offset,
        wp.horizon_laps,
        wp.optimal_total_cost_s,
        wp.actual_total_cost_s,
        rp.race_horizon_laps,
        rp.optimal_offset_race,
        rp.optimal_pit_lap_race,
        rp.optimal_total_cost_race_s,
        rp.actual_total_cost_race_s,
        CASE
            WHEN wp.optimal_offset IS NOT NULL THEN 'two_stint'
            WHEN rp.optimal_offset_race IS NOT NULL THEN 'race_remainder'
        END AS horizon_source
    FROM stint_base AS sb
    LEFT JOIN cliff_onset_per_stint AS cos ON sb.stint_id = cos.stint_id
    LEFT JOIN min_gap_per_stint AS mgps ON sb.stint_id = mgps.stint_id
    LEFT JOIN race_map AS rm ON sb.race_id = rm.race_id
    LEFT JOIN circuit_pit_loss AS cpl ON rm.circuit_key = cpl.circuit_key
    LEFT JOIN stint_actual_pit AS ap ON sb.stint_id = ap.stint_id
    LEFT JOIN window_pick AS wp ON sb.stint_id = wp.stint_id
    LEFT JOIN race_pick AS rp ON sb.stint_id = rp.stint_id
),

-- Fall back to the race-remainder horizon where no next stint exists.
resolved AS (
    SELECT
        a.*,
        COALESCE(a.optimal_offset, a.optimal_offset_race) AS pick_offset,
        COALESCE(a.optimal_pit_lap, a.optimal_pit_lap_race) AS pick_pit_lap,
        COALESCE(a.horizon_laps, a.race_horizon_laps) AS pick_horizon_laps,
        COALESCE(
            a.actual_total_cost_s, a.actual_total_cost_race_s
        ) AS pick_actual_cost_s,
        COALESCE(
            a.optimal_total_cost_s, a.optimal_total_cost_race_s
        ) AS pick_optimal_cost_s
    FROM assembled AS a
),

geom AS (
    SELECT
        stint_id,
        MAX(compound_in_stint) AS compound
    FROM {{ ref('int_stint_geometry') }}
    WHERE is_valid_lap = TRUE
    GROUP BY stint_id
)

SELECT
    r.stint_id,
    r.race_year,
    r.race_id,
    r.driver_id,
    g.compound,
    r.cliff_onset_lap_in_stint,
    r.stint_length_laps,
    -- Laps to run on the set before boxing, in valid laps.
    r.pick_offset AS optimal_pit_lap_in_stint,
    r.pick_pit_lap AS optimal_pit_lap,
    -- Actual pit lap: pit_in_lap_number for the pit stop at the END of this
    -- stint
    r.actual_pit_lap,
    -- Overrun: actual minus optimal (negative = pitted early). Compared in
    -- offsets, so an invalid lap before the stop cannot skew it.
    CASE
        WHEN r.actual_pit_lap IS NULL OR r.pick_offset IS NULL THEN NULL
        ELSE r.actual_offset - r.pick_offset
    END AS overrun_laps,
    -- Opportunity cost: Total_Cost(actual) - Total_Cost(optimal). Zero for a
    -- stint that never stopped, which had no pit decision to grade.
    CASE
        WHEN r.actual_pit_lap IS NULL THEN 0.0
        WHEN r.pick_optimal_cost_s IS NULL THEN 0.0
        ELSE GREATEST(r.pick_actual_cost_s - r.pick_optimal_cost_s, 0.0)
    END AS opportunity_cost_s,
    -- Confidence: share of candidate laps more than 1 s worse than the
    -- optimum. Flat curve -> low, sharp minimum -> high.
    COALESCE(r.optimal_pit_lap_confidence, 0.0) AS optimal_pit_lap_confidence,
    -- Undercut threat: first lap where gap < pit_loss + 1.0 s
    r.first_undercut_threat_lap AS undercut_threat_lap,
    -- Pit-lane loss
    COALESCE(r.pit_lane_loss_s, 21.0) AS pit_lane_loss_s,
    COALESCE(r.pit_loss_source, 'default') AS pit_loss_source,
    COALESCE(r.pit_loss_imputed_flag, TRUE) AS pit_loss_imputed_flag,
    -- Which horizon the verdict used, and how long it was.
    r.horizon_source,
    r.pick_horizon_laps AS horizon_laps,
    -- The race-remainder optimum, carried as a diagnostic alongside the
    -- verdict's two-stint one.
    r.optimal_offset_race AS optimal_pit_lap_race_in_stint,
    r.optimal_pit_lap_race,
    CASE
        WHEN r.actual_pit_lap IS NULL THEN 0.0
        WHEN r.optimal_total_cost_race_s IS NULL THEN 0.0
        ELSE GREATEST(
            r.actual_total_cost_race_s - r.optimal_total_cost_race_s, 0.0
        )
    END AS opportunity_cost_race_s,
    -- Strategy verdict
    CASE
        WHEN r.actual_pit_lap IS NULL
            THEN NULL
        WHEN r.pick_offset IS NULL
            THEN 'unknown'
        WHEN
            ABS(r.actual_offset - r.pick_offset)
            <= {{ var('pit_strategy_optimal_band_laps', 1) }}
            THEN 'optimal'
        WHEN
            r.actual_offset
            > r.pick_offset + {{ var('pit_strategy_optimal_band_laps', 1) }}
            THEN 'overran'
        -- The stop came early AND it came as the undercut window opened.
        -- The window has to be a window: undercut_threat_lap is the FIRST lap
        -- of the stint where the gap ahead drops under a pit stop, which
        -- 95.5% of stints have somewhere, so "the threat existed at some
        -- point" classifies nothing. Requiring the stop to land inside a few
        -- laps of it is what the verdict's name actually claims.
        WHEN
            r.first_undercut_threat_lap IS NOT NULL
            AND r.actual_pit_lap
            BETWEEN r.first_undercut_threat_lap - 2
            AND r.first_undercut_threat_lap
            + {{ var('pit_strategy_undercut_window_laps', 3) }}
            THEN 'undercut_forced'
        ELSE 'early'
    END AS strategy_verdict
FROM resolved AS r
LEFT JOIN geom AS g ON r.stint_id = g.stint_id
ORDER BY r.race_year, r.race_id, r.driver_id
