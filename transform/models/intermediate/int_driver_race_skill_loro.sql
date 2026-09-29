-- Equal-car driver skill at race grain: the driver against the other
-- driver(s) of the same car in the same race (LORO = leave-one-driver-out:
-- a driver is never part of his own baseline).
--
-- driver_skill_loro_s -- the RATING chain's input (int_driver_season_ratings
-- -> int_era_normalized_driver_rating, and int_driver_circuit_affinity).
--   WI-14b (F40, FD5 ruled option C, 2026-09-28): the median of the
--   LAP-BY-LAP gap to the teammate. Own and teammate clean laps are paired on
--   (race, car, lap_number) and the rating is
--       MEDIAN(own lap_time_s - teammate lap_time_s)  over laps both ran clean.
--   Both drivers on one lap number carry the same modelled fuel load and see
--   the same field pace, so the fuel and field terms cancel inside each pair
--   without being subtracted, and the statistic never reads
--   int_field_pace_curve (a lap with no field pace is still a real lap here,
--   not a zero -- see the note on clean_panel below).
--   What it replaced, and why. It was P20(own pace delta) minus the teammate's
--   MEDIAN pace delta: a ceiling compared with a typical lap. That splits
--   exactly into a spread term, P20(own) - median(own) (mean -0.92 s, the
--   driver's own lap-time scatter), plus the real teammate gap (mean 0.000).
--   A driver whose laps scattered more was rated faster, both teammates in
--   79% of two-driver cars were rated faster than each other, and the mean
--   pair sum was -1.83 s instead of 0. P20-vs-P20 (FD5 option A) squares the
--   level but still correlates -0.25 with spread; the paired median is
--   spread-independent (0.03) and beat median-vs-median (option B) on
--   split-half reliability (0.75 vs 0.65) and qualifying agreement (0.74 vs
--   0.66) in the FD5 design round (WI-14 doc). The "ceiling kills cruise
--   drag" intent is given up: a lap-matched comparison already compares the
--   two drivers under the same race situation lap by lap.
--   Antisymmetric by construction for a two-driver car: the teammate's
--   paired deltas are the exact negatives of the driver's, so the two
--   ratings sum to 0 (T30, assert_teammate_rating_antisymmetric). NULL when
--   no teammate has a clean lap on any lap number the driver ran clean (no
--   equal-car reference; 2 of 1,571 car-races on the 2026-09-28 build).
--
-- driver_skill_loro_mean_s -- median(own pace delta) minus the mean of the
--   teammates' median pace deltas (FD5 option B). Kept as a comparison
--   column; no dbt model reads it.
--
-- driver_skill_field_s -- field-anchored: median(own pace delta) minus the
--   de-biased constructor x race FE (int_constructor_car_fe.car_fe_s, car pace
--   net of driver skill). Used only by int_driver_circuit_era_affinity (Ghost
--   Standings leaderboard). Fixes the weak-teammate inflation bug (e.g.
--   Albon/Sargeant): the old constructor median absorbed the team's driver
--   skill, so subtracting it handed a weak driver's slowness back as "skill".
--   The car FE has a global driver anchor, so it removes the car only.
--
-- Output grain: (race_year, race_id, driver_id). One row per driver per race.
-- PK: driver_race_skill_id (surrogate hash).
--
-- Sign conventions, seconds, negative = faster:
--   driver_skill_loro_s       negative = faster than his teammate on the
--                             same laps (a teammate-relative gap, NOT a gap to
--                             the field)
--   driver_skill_loro_mean_s  negative = faster than his teammate(s)
--   driver_skill_field_s      negative = faster than the de-biased car term

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

field_pace AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        field_pace_smoothed_s
    FROM {{ ref('int_field_pace_curve') }}
),

laps_meta AS (
    SELECT
        lap_id,
        constructor_id
    FROM {{ ref('stg_laps') }}
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

-- Resolve race_id → circuit_key via race_to_track seed (same source as
-- fct_driver_skill_features, so the affinity consumers get identical
-- circuit_key values).
race_to_track AS (
    SELECT
        race_id,
        track_id AS circuit_key
    FROM {{ ref('race_to_track') }}
),

-- De-biased modelled car pace (constructor×race FE, net of driver skill);
-- used to compute driver_skill_field_s. See int_constructor_car_fe.
car_fe AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        car_fe_s
    FROM {{ ref('int_constructor_car_fe') }}
),

-- Per clean lap: the raw lap time (feeds the paired, lap-by-lap teammate
-- rating) and the pace delta vs the smoothed field median (feeds the median
-- and field-anchored signals).
-- W56: where the field curve has no row for a lap, pace_delta_s is NULL
-- (medians skip it). ~3.3% of laps. driver_skill_loro_s does not read this
-- field curve; it is built from lap_time_s differences only.
clean_panel AS (
    SELECT
        f.race_year,
        f.race_id,
        f.driver_id,
        lm.constructor_id,
        f.lap_number,
        f.lap_time_s,
        f.lap_time_s - fp.field_pace_smoothed_s AS pace_delta_s
    FROM fuel AS f
    INNER JOIN laps_meta AS lm ON f.lap_id = lm.lap_id
    LEFT JOIN field_pace AS fp
        ON
            f.race_year = fp.race_year
            AND f.race_id = fp.race_id
            AND f.lap_number = fp.lap_number
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
),

-- Per (race, constructor, driver): median pace delta (feeds the option-B
-- teammate baseline and the field-anchored signal) and the clean-lap count.
driver_race_agg AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        driver_id,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pace_delta_s)
            AS driver_median_pace_delta_s,
        COUNT(*) AS clean_lap_count
    FROM clean_panel
    GROUP BY race_year, race_id, constructor_id, driver_id
),

-- F40 / FD5 option C. Pair every clean lap with each same-car teammate's
-- clean lap on the SAME lap number. (race_year, race_id, driver_id,
-- lap_number) is unique in int_lap_fuel_state, so a two-driver car yields at
-- most one pair per lap per direction, and the teammate's row for a lap is
-- this row with the sign flipped.
paired_laps AS (
    SELECT
        own.race_year,
        own.race_id,
        own.constructor_id,
        own.driver_id,
        own.lap_time_s - mate.lap_time_s AS paired_delta_s
    FROM clean_panel AS own
    INNER JOIN clean_panel AS mate
        ON
            own.race_year = mate.race_year
            AND own.race_id = mate.race_id
            AND own.constructor_id = mate.constructor_id
            AND own.lap_number = mate.lap_number
            AND own.driver_id <> mate.driver_id
),

paired_agg AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        driver_id,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY paired_delta_s)
            AS paired_median_delta_s,
        COUNT(*) AS paired_lap_count
    FROM paired_laps
    GROUP BY race_year, race_id, constructor_id, driver_id
),

-- Per (race, constructor): sum/count of driver medians, to build the LORO
-- baseline.
car_agg AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        SUM(driver_median_pace_delta_s) AS sum_driver_median_s,
        COUNT(*) AS n_car_drivers
    FROM driver_race_agg
    GROUP BY race_year, race_id, constructor_id
),

deconf AS (
    SELECT
        dra.race_year,
        dra.race_id,
        dra.driver_id,
        dra.constructor_id,
        dra.clean_lap_count,
        ca.n_car_drivers,
        -- LORO car baseline = mean of the OTHER same-car drivers' medians
        -- (excludes the
        -- focal driver). NULL when the driver is the only one with clean laps
        -- in his car
        -- that race (no equal-car reference → race drops out, same as a NULL
        -- residual).
        CASE
            WHEN ca.n_car_drivers > 1
                THEN
                    (ca.sum_driver_median_s - dra.driver_median_pace_delta_s)
                    / (ca.n_car_drivers - 1)
        END AS loro_car_baseline_s,
        dra.driver_median_pace_delta_s,
        pa.paired_median_delta_s,
        COALESCE(pa.paired_lap_count, 0) AS paired_lap_count
    FROM driver_race_agg AS dra
    INNER JOIN
        car_agg AS ca
        ON
            dra.race_year = ca.race_year
            AND dra.race_id = ca.race_id
            AND dra.constructor_id = ca.constructor_id
    LEFT JOIN paired_agg AS pa
        ON
            dra.race_year = pa.race_year
            AND dra.race_id = pa.race_id
            AND dra.constructor_id = pa.constructor_id
            AND dra.driver_id = pa.driver_id
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'd.race_year', 'd.race_id', 'd.driver_id'
    ]) }}
        AS driver_race_skill_id,
    d.driver_id,
    d.race_year,
    d.race_id,
    d.constructor_id,
    rtt.circuit_key,
    -- Equal-car rating (F40, FD5 option C): median lap-by-lap gap to the
    -- teammate. Negative = faster than the teammate. Used by the RATING
    -- chain. See the header.
    d.paired_median_delta_s AS driver_skill_loro_s,
    -- Field-anchored equal-car skill: median pace minus the de-biased modelled
    -- car
    -- term (int_constructor_car_fe.car_fe_s, the constructor×race FE net of
    -- driver
    -- skill). Uses the MEDIAN on the same pace_delta panel the FE is fit
    -- from,
    -- so the level is consistent. Subtracting the de-biased car term removes
    -- the car
    -- WITHOUT crediting a weak driver's slowness as skill (the bug when the old
    -- constructor median which absorbs the team's driver skill was subtracted).
    -- NULL when the constructor×race FE is unidentified for this race.
    -- Used ONLY by int_driver_circuit_era_affinity (Ghost Car Standings
    -- leaderboard).
    d.driver_median_pace_delta_s - cfe.car_fe_s AS driver_skill_field_s,
    -- Median vs the teammates' median (FD5 option B). Comparison column only;
    -- no dbt model reads it.
    d.driver_median_pace_delta_s
    - d.loro_car_baseline_s AS driver_skill_loro_mean_s,
    d.loro_car_baseline_s,
    d.n_car_drivers,
    d.clean_lap_count,
    -- Laps paired with a teammate's clean lap on the same lap number (the
    -- sample behind driver_skill_loro_s). 0 when driver_skill_loro_s is NULL.
    d.paired_lap_count
FROM deconf AS d
LEFT JOIN race_to_track AS rtt ON d.race_id = rtt.race_id
LEFT JOIN car_fe AS cfe
    ON
        d.race_year = cfe.race_year
        AND d.race_id = cfe.race_id
        AND d.constructor_id = cfe.constructor_id
ORDER BY d.race_year DESC, d.race_id ASC, d.driver_id ASC
