-- int_pit_strategy_cost_curve.sql · intermediate · grain: one row per
-- (stint_id, horizon_scope, candidate_pit_lap_offset)
--
-- The Total_Cost(L) surface int_pit_strategy_value's header has always
-- described and never computed. One row per candidate pit lap, so the
-- consumer's job is a plain argmin and the cost model is inspectable rather
-- than buried in a MIN(CASE ...).
--
-- For a candidate that pits after L laps of this stint, over a horizon of H
-- laps:
--
--   Total_Cost(L) = Σ_{a=a0+1}^{a0+L} wear_old(a)      -- old tyre, aged a0
--                 + Σ_{u=1}^{H-L}    wear_new(u)       -- the tyre actually
--                                                      -- fitted next
--                 + baseline_delta_s_per_lap × (H-L)   -- compound pace offset
--                 + pit_lane_loss_s × pit_discount(L)  -- the stop itself
--
-- L = H is the no-stop candidate: the whole horizon on the starting set, no
-- pit term. It is what makes a pit stop have to justify itself.
--
-- WHY THE PIT TERM DEPENDS ON L. Under a fixed one-stop it does not: the pit
-- loss is the same whenever you take it, so it adds a constant to every
-- candidate and drops straight out of the argmin. A longer pit lane would
-- move nothing, which is why the threshold this model replaces could ignore
-- pit loss and still look plausible. What breaks the tie is the safety car:
-- a stop under caution costs a fraction of a green-flag stop, and the longer
-- you run, the better the odds one has appeared. So
--
--   pit_discount(L) = 1 - (1 - m) × (1 - (1 - h)^L)
--
-- with h the circuit's per-racing-lap SC/VSC hazard from int_sc_hazard_history
-- and m = var('pit_sc_loss_multiplier'). It is non-increasing in L, so waiting
-- earns a discount proportional to the pit-lane loss, and a longer pit lane
-- pushes the optimum later -- which is asserted, not assumed, by
-- assert_pit_loss_pushes_optimum_later.
--
-- Horizon scopes, both emitted:
--   'window' -- this stint's first lap through the NEXT stint's last lap. One
--              stop inside a window whose ends are the driver's own strategy:
--              "was this stop on the right lap?" Well posed for a 2- or
--              3-stopper, where 61% of stints live.
--   'race'   -- this stint's first lap through the driver's last lap of the
--              race. "If they had stopped only once more, when?" Unconditional
--              on the rest of the strategy, and correspondingly harsher on
--              anyone who was never running a one-stop.
--
-- Laps are counted in VALID laps throughout, matching the age basis of the
-- cliff curve: SC and pit laps do not age a tyre the way a racing lap does.
--
-- Assumptions:
--   1. The wear curve of int_compound_cliff_predicted is the correct
--      counterfactual, extrapolated past the observed stint by evaluating the
--      same fitted polynomial at higher ages.
--   2. The next tyre is fitted new (age 1). Used sets exist; the stint table
--      cannot see them.
--   3. Track temperature is held at the stint's mean for both arms.
--   4. Exactly one stop inside the horizon.

{{ config(materialized='table', tags=['simulation', 'strategy']) }}

WITH ages AS (
    SELECT UNNEST(
        GENERATE_SERIES(1, {{ var('pit_strategy_max_age_laps', 160) }})
    ) AS age_laps
),

-- Every valid lap a driver ran in a race, indexed in race order. The index is
-- what lets a candidate reach past the end of the stint it belongs to: laps
-- L > this stint's length are real laps the driver ran on the next set.
driver_laps AS (
    SELECT
        sg.stint_id,
        sg.lap_id,
        sg.race_year,
        sg.race_id,
        sg.driver_id,
        sg.stint_number,
        sg.lap_number,
        sg.age_in_stint,
        sg.compound_in_stint AS compound,
        ROW_NUMBER() OVER (
            PARTITION BY sg.race_year, sg.race_id, sg.driver_id
            ORDER BY sg.lap_number
        ) AS driver_lap_idx
    FROM {{ ref('int_stint_geometry') }} AS sg
    WHERE sg.is_valid_lap = TRUE
),

stint_span AS (
    SELECT
        stint_id,
        race_year,
        race_id,
        driver_id,
        stint_number,
        MIN(driver_lap_idx) AS first_driver_lap_idx,
        MAX(driver_lap_idx) AS last_driver_lap_idx,
        -- Age of the set at the START of the stint. A stint opened on a used
        -- set begins part-way up its own wear curve.
        MIN(age_in_stint) - 1 AS start_age_laps,
        COUNT(*) AS valid_laps,
        MAX(compound) AS compound
    FROM driver_laps
    GROUP BY stint_id, race_year, race_id, driver_id, stint_number
),

driver_span AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        MAX(driver_lap_idx) AS driver_last_lap_idx
    FROM driver_laps
    GROUP BY race_year, race_id, driver_id
),

-- The chronologically next stint, by lap order rather than stint_number + 1:
-- a red-flag race can leave gaps in the numbering.
stint_seq AS (
    SELECT
        s.stint_id,
        s.race_year,
        s.race_id,
        s.driver_id,
        s.first_driver_lap_idx,
        s.last_driver_lap_idx,
        s.start_age_laps,
        s.valid_laps,
        s.compound,
        LEAD(s.compound) OVER (
            PARTITION BY s.race_year, s.race_id, s.driver_id
            ORDER BY s.first_driver_lap_idx
        ) AS next_compound,
        LEAD(s.last_driver_lap_idx) OVER (
            PARTITION BY s.race_year, s.race_id, s.driver_id
            ORDER BY s.first_driver_lap_idx
        ) AS next_last_driver_lap_idx
    FROM stint_span AS s
),

-- Stint-mean track temperature. The per-lap value drives the cliff model; a
-- counterfactual that reprices every candidate lap needs one number per stint,
-- and the term it feeds is a constant per lap either way.
stint_temp AS (
    SELECT
        dl.stint_id,
        AVG(w.track_temp_c) AS track_temp_c
    FROM driver_laps AS dl
    INNER JOIN {{ ref('stg_weather') }} AS w ON dl.lap_id = w.lap_id
    GROUP BY dl.stint_id
),

race_map AS (
    SELECT
        race_id,
        track_id AS circuit_key
    FROM {{ ref('race_to_track') }}
),

-- Cumulative wear by tyre age, per fitted compound curve. Age-dependent terms
-- only: grip_peak and the temperature offset are per-lap constants and are
-- carried separately, because whether they belong in the argmin at all is a
-- judgement call the pit_strategy_baseline_delta var exposes.
compound_wear_per_age AS (
    SELECT
        p.circuit_key,
        p.compound_code,
        p.season,
        a.age_laps,
        p.compound_grip_peak,
        p.compound_optimal_temp_low,
        -- Capped. The hockey-stick is a polynomial with nothing holding its
        -- tail down: extrapolated to age 80 it reaches 136 s/lap, and it is
        -- not only an extrapolation artefact -- the fitted curve already
        -- emits up to 93 s/lap on laps that were actually run (p99 30.8).
        -- A car losing more than pit_strategy_max_wear_s_per_lap against its
        -- own compound baseline is not making a strategy decision any more,
        -- and letting the tail run turns opportunity_cost_s into a number
        -- with no physical reading. Real cliff falloff is 1-3 s/lap, so the
        -- default sits well clear of the region the decision lives in.
        LEAST(
            p.compound_wear_gradient * a.age_laps
            + 0.002 * POWER(a.age_laps, 2)
            + p.compound_cliff_severity
            * GREATEST(a.age_laps - p.compound_cliff_onset_laps, 0.0),
            {{ var('pit_strategy_max_wear_s_per_lap', 10.0) }}
        ) AS wear_s
    FROM {{ ref('dim_compounds_season') }} AS p
    CROSS JOIN ages AS a
),

compound_curve AS (
    SELECT
        circuit_key,
        compound_code,
        season,
        age_laps,
        compound_grip_peak,
        compound_optimal_temp_low,
        SUM(wear_s) OVER (
            PARTITION BY circuit_key, compound_code, season
            ORDER BY age_laps
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cum_wear_s
    FROM compound_wear_per_age
),

-- Pit-lane loss per circuit, on the same precedence as int_pit_strategy_value:
-- empirical, then the seed, then a flat constant.
circuit_pit_loss AS (
    SELECT
        cr.circuit_key,
        COALESCE(
            pl.pit_loss_s_shrunk,
            CAST(cr.pit_lane_loss_s AS DOUBLE),
            21.0
        ) AS pit_lane_loss_s
    FROM {{ ref('circuit_reference') }} AS cr
    LEFT JOIN {{ ref('int_pit_loss_circuit') }} AS pl
        ON cr.circuit_key = pl.circuit_slug
),

-- One row per stint with everything the cost function needs. A stint whose
-- own compound has no fitted curve is dropped here: no curve, no argmin, and
-- the consumer reports 'unknown' rather than an argmin over a flat zero.
stint_base AS (
    SELECT
        s.stint_id,
        s.race_year,
        s.race_id,
        s.driver_id,
        s.first_driver_lap_idx,
        s.start_age_laps,
        s.valid_laps,
        s.compound,
        COALESCE(s.next_compound, s.compound) AS next_compound,
        rm.circuit_key,
        COALESCE(cpl.pit_lane_loss_s, 21.0) AS pit_lane_loss_s,
        COALESCE(sc.any_hazard_per_lap_shrunk, 0.0) AS sc_hazard_per_lap,
        st.track_temp_c,
        CASE
            WHEN s.next_last_driver_lap_idx IS NULL THEN NULL
            ELSE s.next_last_driver_lap_idx - s.first_driver_lap_idx + 1
        END AS window_horizon_laps,
        ds.driver_last_lap_idx - s.first_driver_lap_idx + 1 AS race_horizon_laps
    FROM stint_seq AS s
    INNER JOIN driver_span AS ds
        ON
            s.race_year = ds.race_year
            AND s.race_id = ds.race_id
            AND s.driver_id = ds.driver_id
    INNER JOIN race_map AS rm ON s.race_id = rm.race_id
    LEFT JOIN circuit_pit_loss AS cpl ON rm.circuit_key = cpl.circuit_key
    LEFT JOIN {{ ref('int_sc_hazard_history') }} AS sc
        ON rm.circuit_key = sc.circuit_slug
    LEFT JOIN stint_temp AS st ON s.stint_id = st.stint_id
),

-- Both horizons, stacked. 'window' is absent for a stint with no successor.
scoped AS (
    SELECT
        sb.*,
        'window' AS horizon_scope,
        sb.window_horizon_laps AS horizon_laps
    FROM stint_base AS sb
    WHERE
        sb.window_horizon_laps IS NOT NULL
        AND sb.window_horizon_laps
        <= {{ var('pit_strategy_max_age_laps', 160) }}

    UNION ALL

    SELECT
        sb.*,
        'race' AS horizon_scope,
        sb.race_horizon_laps AS horizon_laps
    FROM stint_base AS sb
    WHERE
        sb.race_horizon_laps > 0
        AND sb.race_horizon_laps
        <= {{ var('pit_strategy_max_age_laps', 160) }}
),

-- One row per candidate pit lap. L runs 1..H; L = H is the no-stop candidate.
candidates AS (
    SELECT
        sc.stint_id,
        sc.race_year,
        sc.race_id,
        sc.driver_id,
        sc.horizon_scope,
        sc.horizon_laps,
        sc.valid_laps,
        sc.start_age_laps,
        sc.compound,
        sc.next_compound,
        sc.circuit_key,
        sc.pit_lane_loss_s,
        sc.sc_hazard_per_lap,
        sc.track_temp_c,
        sc.first_driver_lap_idx,
        a.age_laps AS candidate_pit_lap_offset,
        sc.horizon_laps - a.age_laps AS laps_on_new_set
    FROM scoped AS sc
    INNER JOIN ages AS a ON sc.horizon_laps >= a.age_laps
),

priced AS (
    SELECT
        c.stint_id,
        c.race_year,
        c.race_id,
        c.driver_id,
        c.horizon_scope,
        c.horizon_laps,
        c.valid_laps,
        c.candidate_pit_lap_offset,
        c.laps_on_new_set,
        c.compound,
        c.next_compound,
        c.pit_lane_loss_s,
        c.sc_hazard_per_lap,
        c.first_driver_lap_idx,
        -- Old set, aged start_age_laps, run for candidate_pit_lap_offset more
        -- laps. cum_wear is indexed from age 1, so the already-served age is
        -- subtracted off rather than re-charged.
        old_c.cum_wear_s - COALESCE(old_0.cum_wear_s, 0.0) AS old_wear_cost_s,
        COALESCE(new_c.cum_wear_s, 0.0) AS new_wear_cost_s,
        -- Per-lap pace offset between the two compounds: grip_peak plus the
        -- temperature term, both of which are per-compound CONSTANTS in the
        -- seed rather than fitted quantities. The
        -- pit_strategy_baseline_delta var decides whether they are allowed to
        -- move the argmin; see the model's schema.yml note.
        {% if var('pit_strategy_baseline_delta', true) %}
            COALESCE(new_c0.compound_grip_peak, old_c0.compound_grip_peak, 0.0)
            - COALESCE(old_c0.compound_grip_peak, 0.0)
            + 0.005 * (
                LEAST(
                    GREATEST(
                        COALESCE(c.track_temp_c, 30.0)
                        - COALESCE(new_c0.compound_optimal_temp_low, 20.0),
                        0.0
                    ),
                    30.0
                )
                - LEAST(
                    GREATEST(
                        COALESCE(c.track_temp_c, 30.0)
                        - COALESCE(old_c0.compound_optimal_temp_low, 20.0),
                        0.0
                    ),
                    30.0
                )
            )
        {% else %}
        0.0
        {% endif %}
            AS baseline_delta_s_per_lap,
        -- P(a caution has appeared within L laps), and the discount it buys.
        1.0 - POWER(1.0 - c.sc_hazard_per_lap, c.candidate_pit_lap_offset)
            AS sc_probability,
        CASE
            WHEN c.laps_on_new_set = 0 THEN 0.0
            ELSE
                1.0 - (1.0 - {{ var('pit_sc_loss_multiplier', 0.5) }})
                * (
                    1.0
                    - POWER(
                        1.0 - c.sc_hazard_per_lap, c.candidate_pit_lap_offset
                    )
                )
        END AS pit_discount_factor
    FROM candidates AS c
    INNER JOIN compound_curve AS old_c
        ON
            c.circuit_key = old_c.circuit_key
            AND c.compound = old_c.compound_code
            AND c.race_year = old_c.season
            AND old_c.age_laps = c.start_age_laps + c.candidate_pit_lap_offset
    LEFT JOIN compound_curve AS old_0
        ON
            c.circuit_key = old_0.circuit_key
            AND c.compound = old_0.compound_code
            AND c.race_year = old_0.season
            AND c.start_age_laps = old_0.age_laps
    LEFT JOIN compound_curve AS new_c
        ON
            c.circuit_key = new_c.circuit_key
            AND c.next_compound = new_c.compound_code
            AND c.race_year = new_c.season
            AND c.laps_on_new_set = new_c.age_laps
    -- Age-1 rows carry the per-compound constants for the baseline term.
    LEFT JOIN compound_curve AS old_c0
        ON
            c.circuit_key = old_c0.circuit_key
            AND c.compound = old_c0.compound_code
            AND c.race_year = old_c0.season
            AND old_c0.age_laps = 1
    LEFT JOIN compound_curve AS new_c0
        ON
            c.circuit_key = new_c0.circuit_key
            AND c.next_compound = new_c0.compound_code
            AND c.race_year = new_c0.season
            AND new_c0.age_laps = 1
)

SELECT
    pr.stint_id,
    pr.race_year,
    pr.race_id,
    pr.driver_id,
    pr.horizon_scope,
    pr.horizon_laps,
    pr.valid_laps AS stint_valid_laps,
    pr.candidate_pit_lap_offset,
    pr.laps_on_new_set,
    pr.compound,
    pr.next_compound,
    dl.lap_number AS candidate_lap_number,
    pr.old_wear_cost_s,
    pr.new_wear_cost_s,
    pr.baseline_delta_s_per_lap * pr.laps_on_new_set AS baseline_cost_s,
    pr.pit_lane_loss_s,
    pr.sc_hazard_per_lap,
    pr.sc_probability,
    pr.pit_discount_factor,
    pr.pit_lane_loss_s * pr.pit_discount_factor AS pit_cost_s,
    -- Everything that does not scale with pit_lane_loss_s. Split out so a
    -- consumer -- or a test -- can re-minimise at a different pit loss without
    -- rebuilding the curve.
    pr.old_wear_cost_s
    + pr.new_wear_cost_s
    + pr.baseline_delta_s_per_lap * pr.laps_on_new_set AS wear_cost_s,
    pr.old_wear_cost_s
    + pr.new_wear_cost_s
    + pr.baseline_delta_s_per_lap * pr.laps_on_new_set
    + pr.pit_lane_loss_s * pr.pit_discount_factor AS total_cost_s
FROM priced AS pr
LEFT JOIN driver_laps AS dl
    ON
        pr.race_year = dl.race_year
        AND pr.race_id = dl.race_id
        AND pr.driver_id = dl.driver_id
        AND dl.driver_lap_idx
        = pr.first_driver_lap_idx + pr.candidate_pit_lap_offset - 1
