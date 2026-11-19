-- TX-01. The paired lap-time gaps behind the race rating, one row per
-- (race, driver, lap_number, teammate). paired_delta_s = own lap_time_s minus
-- the same-car teammate's lap_time_s on the same lap number, over laps both
-- drivers ran clean. int_driver_race_skill_loro.driver_skill_loro_s is the
-- MEDIAN of adjusted_paired_delta_s (paired_delta_s net of the tyre
-- difference, see below) over rows where it is not NULL, and its
-- paired_lap_count is their COUNT, per (race, driver); mart_race_driver_summary builds its order-statistic CI for
-- that median from the same rows.
--
-- The clean filter below (lap time present, correction_weight = 1, no
-- rainfall on the lap) is the rating's clean panel and must stay identical to
-- clean_panel in int_driver_race_skill_loro, which still needs the unpaired
-- laps (and their pace delta) for its median and field-anchored signals.
-- assert_mart_race_ci_brackets_rating checks that the two agree on n and on
-- the median for every rated driver-race.
--
-- Tyre-state adjustment (owner option 2). Every pair with both laps clean is
-- kept and rated; none is filtered on tyre state. Each paired delta is
-- adjusted for the tyre difference between the two laps:
--   tyre_component_diff_s    = own tyre component - teammate tyre component
--   adjusted_paired_delta_s  = paired_delta_s - tyre_component_diff_s
-- The tyre component is int_lap_residual_decomposed.compound_component_s, the
-- ONE column the decomposition prices tyre state with (expected_compound_pace_s
-- from int_compound_cliff_predicted: fitted compound grip_peak + linear wear by
-- tyre age + the saturating post-cliff ramp + the 0.005 s/deg ambient offset).
-- It is the only tyre-state term, so it is the only one summed. The other
-- components cancel or are not tyre: fuel_component_s is a function of lap
-- number (same for both cars on a lap); rubber and ambient track evolution sit
-- inside the field base, equal for both on a lap number; constructor_component_s
-- is the same car; dirty_air_tax_s is traffic, not tyre, and is left in the
-- delta. No new tyre curve is estimated.
-- ASSUMPTION: the fitted curve (per circuit x compound x season cell) prices
-- tyre state correctly for both drivers, so the residual gap is driver pace.
-- A misfit curve (e.g. the cliff onset) moves the adjustment, not the data.
-- NULL is never read as 0: if either lap has no compound_component_s (unknown
-- tyre age, F39, or no decomposition row) adjusted_paired_delta_s is NULL and
-- tyre_adjustment_missing = TRUE; such pairs are not rated.
-- paired_delta_s is unchanged (raw gap).
--
-- pair_is_comparable / pair_exclusion_reason (same compound, tyre ages within
-- var('paired_lap_max_tyre_age_gap') = 2 laps; reasons different_compound,
-- tyre_age_gap_gt_2, tyre_data_missing) are INFORMATIVE flags only. No
-- consumer filters on them. Used by the tyre-removal proof (same-compound vs
-- different-compound pairs).
--
-- For a two-driver car the teammate's rows are this driver's rows with the
-- sign flipped. (race_year, race_id, driver_id, lap_number) is unique in
-- int_lap_fuel_state, so a two-driver car gives at most one row per lap per
-- direction.
{{ config(
    materialized='table', tags=['driver_rating', 'causal_decomposition']
) }}

WITH fuel AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s
    FROM {{ ref('int_lap_fuel_state') }}
),

laps_meta AS (
    SELECT
        lap_id,
        constructor_id,
        compound,
        tyre_life
    FROM {{ ref('stg_laps') }}
),

tyre_component AS (
    SELECT
        lap_id,
        compound_component_s
    FROM {{ ref('int_lap_residual_decomposed') }}
),

corrections AS (
    SELECT
        lap_id,
        correction_weight
    FROM {{ ref('int_event_corrections') }}
),

evolution AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        rainfall_flag
    FROM {{ ref('int_track_evolution') }}
),

clean_panel AS (
    SELECT
        f.race_year,
        f.race_id,
        f.driver_id,
        tc.compound_component_s,
        lm.constructor_id,
        lm.compound,
        lm.tyre_life,
        f.lap_number,
        f.lap_time_s
    FROM fuel AS f
    INNER JOIN laps_meta AS lm ON f.lap_id = lm.lap_id
    LEFT JOIN tyre_component AS tc ON f.lap_id = tc.lap_id
    LEFT JOIN corrections AS cor ON f.lap_id = cor.lap_id
    LEFT JOIN evolution AS e
        ON
            f.race_year = e.race_year
            AND f.race_id = e.race_id
            AND f.lap_number = e.lap_number
    WHERE
        f.lap_time_s IS NOT NULL
        AND COALESCE(cor.correction_weight, 1.0) = 1.0
        AND COALESCE(e.rainfall_flag, FALSE) = FALSE
)

SELECT
    own.race_year,
    own.race_id,
    own.constructor_id,
    own.driver_id,
    mate.driver_id AS teammate_id,
    own.lap_number,
    own.lap_time_s - mate.lap_time_s AS paired_delta_s,
    own.compound_component_s AS own_tyre_component_s,
    mate.compound_component_s AS teammate_tyre_component_s,
    own.compound_component_s - mate.compound_component_s
        AS tyre_component_diff_s,
    own.lap_time_s - mate.lap_time_s
    - (own.compound_component_s - mate.compound_component_s)
        AS adjusted_paired_delta_s,
    (
        own.compound_component_s IS NULL
        OR mate.compound_component_s IS NULL
    ) AS tyre_adjustment_missing,
    own.compound AS own_compound,
    mate.compound AS teammate_compound,
    own.tyre_life AS own_tyre_life,
    mate.tyre_life AS teammate_tyre_life,
    (
        own.compound IS NOT NULL
        AND mate.compound IS NOT NULL
        AND own.tyre_life IS NOT NULL
        AND mate.tyre_life IS NOT NULL
        AND own.compound = mate.compound
        AND ABS(own.tyre_life - mate.tyre_life)
        <= {{ var('paired_lap_max_tyre_age_gap') }}
    ) AS pair_is_comparable,
    CASE
        WHEN
            own.compound IS NULL OR mate.compound IS NULL
            OR own.tyre_life IS NULL OR mate.tyre_life IS NULL
            THEN 'tyre_data_missing'
        WHEN own.compound <> mate.compound THEN 'different_compound'
        WHEN
            ABS(own.tyre_life - mate.tyre_life)
            > {{ var('paired_lap_max_tyre_age_gap') }}
            THEN 'tyre_age_gap_gt_2'
    END AS pair_exclusion_reason
FROM clean_panel AS own
INNER JOIN clean_panel AS mate
    ON
        own.race_year = mate.race_year
        AND own.race_id = mate.race_id
        AND own.constructor_id = mate.constructor_id
        AND own.lap_number = mate.lap_number
        AND own.driver_id <> mate.driver_id
ORDER BY
    own.race_year, own.race_id, own.driver_id, own.lap_number, mate.driver_id
