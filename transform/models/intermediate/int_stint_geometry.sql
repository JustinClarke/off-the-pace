-- Layer 03: Foundation for all downstream window functions.
-- Partition key for all physics-layer windows is `stint_id`, not lap_number.
-- age_in_stint uses tyre_life (may exceed lap_in_stint if set used in
-- qualifying).
-- Carries the FULL chronological lap sequence (SC/VSC/pit/invalid laps
-- included) so downstream LAG/EWMA windows decay correctly across those
-- gaps instead of treating the lap before/after a gap as adjacent.
-- `lap_in_stint` is the chronological ordinal (total laps);
-- `valid_lap_in_stint` is the ordinal among valid laps only (NULL on invalid
-- laps) for consumers that fit pace/regression models and need SC/pit laps
-- excluded.
--
-- WI-05 (F24, F25): stint_number, tyre_life (-> age_in_stint) and compound
-- come from stg_lap_tyre_qa, not raw bronze. That model fills the 2018 lap-1
-- stint gap (and the one-lap TyreLife shortfall it causes), cross-checks every
-- race's stint numbering against the pit record, and for a quarantined race or
-- driver-race serves the pit record's stint ordinal with NULL compound and age
-- instead of a boundary that contradicts it. tyre_qa_status and stint_source
-- say which applied to each lap.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT
        l.lap_id,
        l.race_year,
        l.race_id,
        l.driver_id,
        l.lap_number,
        l.is_valid_lap,
        l.is_pit_lap,
        l.is_safety_car_lap,
        l.is_vsc_lap,
        l.is_red_flag_lap,
        q.stint_number,
        q.tyre_life,
        q.compound,
        q.stint_source,
        q.tyre_qa_status
    FROM {{ ref('stg_laps') }} AS l
    INNER JOIN {{ ref('stg_lap_tyre_qa') }} AS q
        ON l.lap_id = q.lap_id
),

tyre_allocations AS (
    SELECT * FROM {{ ref('stg_tyre_allocations') }}
),

-- stg_laps.circuit_key is `CAST(race_id AS VARCHAR)` (stg_laps.sql:22) - a
-- RACE key like '2024_24', NOT a circuit slug. By contrast
-- stg_tyre_allocations.circuit_key is a circuit slug like
-- 'abu_dhabi_grand_prix'. The two domains are disjoint, so joining them
-- directly matches zero rows and fails silently (see 08p). The mart resolves
-- the slug through this seed and so does this model.
race_to_track AS (
    SELECT race_id, track_id AS circuit_slug
    FROM {{ ref('race_to_track') }}
),

-- CO-09 (D4, CD14): a stint is a TYRE RUN, not a FastF1 stint number.
--
-- FastF1 opens a new stint whenever the car passes through the pit lane or the
-- race is suspended, even when the same tyres stay on and their age keeps
-- counting. A safety-car drive-through or a red-flag pause therefore split one
-- set's life into several "stints", and the first fragment was labelled as
-- ending in a tyre change it never had. Canada 2025 (2025_10) is the clearest
-- case: every car got three fake one-lap stints at the end, so its real final
-- stint was labelled sc_pit. On the 2026-10-22 dev build there were 442
-- back-to-back same-compound pairs with age + 1, 406 of them at a neutralised
-- boundary (299 safety car, 107 red flag).
--
-- The rule (owner rulings CD14 2026-10-23, D4 2026-10-24):
--   consecutive FastF1 stints of one driver-race form one run when
--     (1a) the compound is the same (and known) and the next stint's first
--          tyre age is the previous stint's last age + 1 -- no reset, no stall;
--     (2)  the previous stint did NOT end on a green-flag lap -- green-flag
--          same-tyre stops are left split (CD14 (2) = no) -- UNLESS
--     (2b) race control recorded a drive-through, stop-go or time penalty for
--          that same car within one lap of the previous stint's last lap
--          (owner, 2026-10-24, recorded on CD14): the car served a penalty in
--          the pit lane and kept its tyres, so it is the same tyre run. On the
--          2026-10-22 dev build 23 of the 36 green age + 1 pairs carry such a
--          message and join; the other 13 stay split (no penalty recorded),
--          including 2023_20 PIA/RIC lap 2 and 2020_14 OCO lap 1, which look
--          like neutralised stops the track-status flags missed -- flagged in
--          the CO-09 evidence, deliberately NOT special-cased here;
--   the run ends where its last fragment ends.
-- stint_id is RE-KEYED to the run (D4: re-key everywhere, no separate run id).
-- stint_number becomes the run's ordinal as FastF1 numbered its FIRST stint,
-- so every run that was never joined keeps its stint_id byte for byte, and a
-- joined run takes the id of its first fragment. Numbers can therefore skip
-- (1, 2, 4) after a join; the order is preserved. Quarantined units (NULL
-- compound and age) never join. Laps FastF1 never assigned stay NULL, as
-- before.
--
-- Penalty messages (rule 2b). stg_race_control's driver_id is resolved from the
-- message's own car-number field, which the FIA leaves empty on steward
-- decisions (0 of 349 penalty messages resolve), so the car number is read
-- from the text ("... PENALTY FOR CAR 44 (HAM) ...") and resolved to a driver
-- through stg_results on the same race, as stg_race_control does. Only an
-- imposed or served penalty counts: "UNDER INVESTIGATION" / "NOTED" messages
-- that merely mention a penalty do not have "PENALTY FOR CAR".
pit_penalties AS (
    SELECT DISTINCT
        rc.race_id,
        res.driver_id,
        rc.lap_number
    FROM {{ ref('stg_race_control') }} AS rc
    INNER JOIN {{ ref('stg_results') }} AS res
        ON
            rc.race_id = res.race_id
            AND REGEXP_EXTRACT(
                UPPER(rc.message_text),
                '(DRIVE[ -]?THROUGH|STOP ?/ ?GO|STOP-GO|TIME)'
                || ' PENALTY FOR CAR ([0-9]+)',
                2
            ) = res.driver_number
    WHERE rc.lap_number IS NOT NULL
),

fragment_bounds AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        stint_number,
        MAX(lap_number) AS last_lap_number,
        ARG_MIN(compound, lap_number) AS first_compound,
        ARG_MIN(tyre_life, lap_number) AS first_tyre_life,
        ARG_MAX(compound, lap_number) AS last_compound,
        ARG_MAX(tyre_life, lap_number) AS last_tyre_life,
        ARG_MAX(
            NOT (is_red_flag_lap OR is_safety_car_lap OR is_vsc_lap),
            lap_number
        ) AS ended_green
    FROM laps
    WHERE stint_number IS NOT NULL
    GROUP BY race_year, race_id, driver_id, stint_number
),

fragment_pairs AS (
    SELECT
        *,
        LAG(last_compound) OVER w AS prev_last_compound,
        LAG(last_tyre_life) OVER w AS prev_last_tyre_life,
        LAG(ended_green) OVER w AS prev_ended_green,
        LAG(last_lap_number) OVER w AS prev_last_lap_number
    FROM fragment_bounds
    WINDOW w AS (
        PARTITION BY race_year, race_id, driver_id ORDER BY stint_number
    )
),

fragment_joins AS (
    SELECT
        fp.*,
        COALESCE(
            fp.prev_last_compound = fp.first_compound
            AND fp.first_tyre_life = fp.prev_last_tyre_life + 1
            AND (
                NOT fp.prev_ended_green
                OR EXISTS (
                    SELECT 1
                    FROM pit_penalties AS pp
                    WHERE
                        pp.race_id = fp.race_id
                        AND pp.driver_id = fp.driver_id
                        AND pp.lap_number
                        BETWEEN fp.prev_last_lap_number - 1
                        AND fp.prev_last_lap_number + 1
                )
            ),
            FALSE
        ) AS joins_previous
    FROM fragment_pairs AS fp
),

fragment_runs AS (
    SELECT
        *,
        SUM(CASE WHEN joins_previous THEN 0 ELSE 1 END) OVER (
            PARTITION BY race_year, race_id, driver_id
            ORDER BY stint_number
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS run_ordinal
    FROM fragment_joins
),

fragment_to_run AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        stint_number AS fragment_stint_number,
        MIN(stint_number) OVER (
            PARTITION BY race_year, race_id, driver_id, run_ordinal
        ) AS run_stint_number
    FROM fragment_runs
),

run_laps AS (
    SELECT
        l.* REPLACE (fr.run_stint_number AS stint_number)
    FROM laps AS l
    LEFT JOIN fragment_to_run AS fr
        ON
            l.race_year = fr.race_year
            AND l.race_id = fr.race_id
            AND l.driver_id = fr.driver_id
            AND l.stint_number = fr.fragment_stint_number
),

with_stint_id AS (
    SELECT
        *,
        CONCAT(
            CAST(race_year AS VARCHAR), '_',
            CAST(race_id AS VARCHAR), '_',
            CAST(driver_id AS VARCHAR), '_',
            CAST(stint_number AS VARCHAR)
        ) AS stint_id,

        ROW_NUMBER() OVER (
            PARTITION BY race_year, race_id, driver_id, stint_number
            ORDER BY lap_number
        ) AS lap_in_stint
    FROM run_laps
),

with_stint_length AS (
    SELECT
        *,
        COUNT(*) OVER (
            PARTITION BY stint_id
        ) AS stint_length_actual,
        COUNT(*) FILTER (WHERE is_valid_lap) OVER (
            PARTITION BY stint_id
        ) AS stint_length_valid,
        CASE
            WHEN is_valid_lap THEN
                COUNT(*) FILTER (WHERE is_valid_lap) OVER (
                    PARTITION BY stint_id
                    ORDER BY lap_number
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                )
        END AS valid_lap_in_stint
    FROM with_stint_id
),

-- 08p: absolute Pirelli C1-C5 identity for the relative hard/medium/soft
-- label. NULL for all of 2018 by construction (the seed starts at 2019) and
-- for INTERMEDIATE/WET laps in every season (wets are not on the C-scale).
-- Every slick lap 2019-2024 resolves. Provenance is flagged in schema.yml:
-- the seed is user-attested, not archivally sourced, and is NON-QUOTABLE
-- per 08d/08p.
with_compound_code AS (
    SELECT
        wsl.*,
        ta.compound_code
    FROM with_stint_length AS wsl
    LEFT JOIN race_to_track AS rtt
        ON wsl.race_id = rtt.race_id
    LEFT JOIN tyre_allocations AS ta
        ON
            wsl.race_year = ta.race_year
            AND rtt.circuit_slug = ta.circuit_key
            AND LOWER(wsl.compound) = ta.compound_label
)

SELECT
    stint_id,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    stint_number,
    lap_in_stint,
    valid_lap_in_stint,
    tyre_life AS age_in_stint,
    compound AS compound_in_stint,
    compound_code,
    stint_length_actual,
    stint_length_valid,
    is_valid_lap,
    is_pit_lap,
    is_safety_car_lap,
    is_vsc_lap,
    is_red_flag_lap,
    CAST(NULL AS BOOLEAN) AS planned_vs_actual_flag,
    stint_source,
    tyre_qa_status
FROM with_compound_code
