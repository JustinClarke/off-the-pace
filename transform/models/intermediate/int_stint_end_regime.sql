-- int_stint_end_regime.sql · intermediate · grain: one row per stint (stint_id)
-- Why did this stint end?
--
-- The stint-life survival target treats every stint as a single-event,
-- right-censored observation: either the tyre was changed (uncensored) or the
-- stint ran out of race (censored). "Uncensored" is not one event. 1,543 of
-- the 5,360 uncensored stints -- 28.8% -- end under a safety car, VSC or red
-- flag, which is not a statement about the tyre: it is the moment the pit wall
-- was handed a free stop. Green-ended stints run 19.44 laps, SC-ended ones
-- 11.14, red-flag-ended ones 5.34. This model names the cause so a consumer
-- can separate the tyre-limit process from the interruption process instead
-- of fitting their mixture.
--
-- Two facets are emitted, and they are NOT redundant:
--   end_regime       the track regime in force on the stint's final lap, for
--                    every stint including censored ones. Crossed with
--                    is_censored_stint this reproduces the measured
--                    decomposition exactly.
--   stint_end_cause  the six-class answer to "why did it end", which folds the
--                    regime into the censoring split. NULL where the stint is
--                    a FastF1 artefact rather than a stint (see below).
--
-- PRECEDENCE, declared rather than inherited from CASE order:
--
--   1. Censoring outranks regime. A censored stint is the driver's last of the
--      race, so it did not end in a tyre change whatever was flying at the
--      time; its causes are race_end and retirement. The regime that was in
--      force is still recorded in end_regime, so nothing is lost -- the
--      2021 Belgian GP, stopped and abandoned under red flag with 20 drivers
--      classified, comes out as race_end with end_regime = 'red_flag', which
--      is the true pair of facts.
--   2. Within an uncensored stint, regime severity decides:
--      red_flag > safety_car > vsc > green. TrackStatus is a concatenated
--      digit string, so one lap can carry several codes at once -- 276 final
--      laps carry red AND SC, 53 carry SC AND VSC, 17 carry red AND VSC. The
--      more severe neutralisation is the one that ended the stint; those 346
--      stints are marked is_multi_regime_end so the choice is auditable.
--   3. Within a censored stint, the classified result decides: a driver
--      running at the chequered flag ends on race_end, anyone else on
--      retirement.
--
-- CONFIDENCE. end_cause_confidence is 'observed' only where every input was
-- read rather than inferred. It steps down to 'inferred' where precedence had
-- to choose, where the pit marker is missing, or where disqualification hides
-- whether the driver was running; and to 'unassigned_stint' for the 325 2018
-- stints FastF1 never assigned a stint number to, whose cause is left NULL
-- because the row is an artefact of unassigned laps, not a stint that ended.
--
-- Owns is_censored_stint, which fct_stint_features reads from here. One
-- definition of "the driver's last stint of the race", used by the mart and by
-- the cause label that is built on top of it.
{{ config(materialized='table') }}

WITH stint_grain AS (
    SELECT
        stint_id,
        race_year,
        race_id,
        driver_id,
        -- Functionally determined by stint_id (which encodes it); MAX is just
        -- the aggregate that carries it past the GROUP BY. NULL survives as
        -- NULL, which is the unassigned-stint marker.
        MAX(stint_number) AS stint_number
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY stint_id, race_year, race_id, driver_id
),

-- Right-censoring for stint-life modelling. A driver's last stint of a race
-- ends at the chequered flag or at retirement, not at a tyre change: the tyre
-- still had life we never observed, so remaining_stint_life_laps on those laps
-- is a LOWER BOUND, not the truth. 46.2% of training rows sit on such a stint,
-- which is why the stint-life model is fitted with survival:aft over an
-- interval rather than squared error against a point. Anything that fits or
-- scores stint life must read this flag -- see ml/src/features.py.
censoring AS (
    SELECT
        stint_id,
        -- COALESCE, not a bare comparison: 325 stints in 2018 carry a NULL
        -- stint_number (343 laps FastF1 never assigned to a stint, 338 of them
        -- already invalid). CONCAT folds the NULL to '' when stint_id is built,
        -- so a driver-race has at most one such stint, and sorting it below
        -- every real stint says the true thing -- an unassigned lap is not the
        -- stint the driver finished on. Two drivers (2018_2 RIC, 2018_10 HAR)
        -- have no other stint, so theirs is both first and last and is marked
        -- censored, which keeps the flag a total partition. Left NULL instead,
        -- the flag would be neither TRUE nor FALSE and every join downstream
        -- would quietly drop those rows.
        COALESCE(stint_number, -1)
        = MAX(COALESCE(stint_number, -1)) OVER (PARTITION BY race_id, driver_id)
            AS is_censored_stint
    FROM stint_grain
),

-- The lap the stint ended on, chronologically. For an uncensored stint that is
-- the in-lap (5,032 of 5,360 carry the pit marker), so the regime read here is
-- the regime the stop was taken under, not the one the out-lap ran in.
final_lap AS (
    SELECT
        stint_id,
        lap_id,
        lap_number,
        lap_in_stint,
        is_pit_lap,
        is_red_flag_lap,
        is_safety_car_lap,
        is_vsc_lap
    FROM {{ ref('int_stint_geometry') }}
    QUALIFY
        ROW_NUMBER() OVER (PARTITION BY stint_id ORDER BY lap_in_stint DESC)
        = 1
),

-- Last lap anyone completed in the race, used only to resolve the
-- disqualification case below.
race_distance AS (
    SELECT
        race_year,
        race_id,
        MAX(lap_number) AS race_final_lap
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY race_year, race_id
),

classified AS (
    SELECT
        sg.stint_id,
        sg.race_year,
        sg.race_id,
        sg.driver_id,
        sg.stint_number,
        cen.is_censored_stint,
        fl.lap_id AS end_lap_id,
        fl.lap_number AS end_lap_number,
        fl.lap_in_stint AS end_lap_in_stint,
        fl.is_pit_lap AS ended_on_pit_lap,

        CASE
            WHEN fl.is_red_flag_lap THEN 'red_flag'
            WHEN fl.is_safety_car_lap THEN 'safety_car'
            WHEN fl.is_vsc_lap THEN 'vsc'
            ELSE 'green'
        END AS end_regime,

        (
            CAST(fl.is_red_flag_lap AS INTEGER)
            + CAST(fl.is_safety_car_lap AS INTEGER)
            + CAST(fl.is_vsc_lap AS INTEGER)
        ) > 1 AS is_multi_regime_end,

        -- Was the driver still circulating when the flag fell? 'Finished',
        -- '+N Lap(s)' and 'Lapped' are the completion statuses; every other
        -- status means the car stopped, including the ones FastF1 still
        -- classifies (87 'Retired' rows are unclassified, 23 are classified
        -- because the driver had covered 90% of the distance -- both stopped,
        -- so is_classified is the wrong test here and status is the right one).
        --
        -- Disqualification is the one status that hides the answer: it is a
        -- post-race ruling, not a reason a stint ended, and it lands on
        -- drivers who ran to the flag and on drivers who did not. Resolve it
        -- on distance instead. The 1-lap tolerance covers a driver one lap
        -- down; nobody in the disqualified set sits between, the 10 rows split
        -- 9 at the race's final lap or one short (2019_17 RIC and HUL, 52 of
        -- 53) and one stopped at 30 of 69 (2024_21 HUL).
        (
            COALESCE(res.status, '') = 'Finished'
            OR COALESCE(res.status, '') LIKE '%Lap%'
            OR (
                COALESCE(res.status, '') = 'Disqualified'
                AND fl.lap_number >= rd.race_final_lap - 1
            )
        ) AS was_running_at_flag,

        COALESCE(res.status, '') = 'Disqualified'
            AS end_cause_from_disqualification
    FROM stint_grain AS sg
    INNER JOIN censoring AS cen ON sg.stint_id = cen.stint_id
    INNER JOIN final_lap AS fl ON sg.stint_id = fl.stint_id
    INNER JOIN race_distance AS rd
        ON sg.race_year = rd.race_year AND sg.race_id = rd.race_id
    LEFT JOIN {{ ref('stg_results') }} AS res
        ON
            sg.race_year = res.race_year
            AND sg.race_id = res.race_id
            AND sg.driver_id = res.driver_id
)

SELECT
    stint_id,
    race_year,
    race_id,
    driver_id,
    stint_number,
    end_lap_id,
    end_lap_number,
    end_lap_in_stint,
    is_censored_stint,
    end_regime,
    is_multi_regime_end,
    ended_on_pit_lap,
    was_running_at_flag,

    CASE
        WHEN stint_number IS NULL THEN NULL
        WHEN is_censored_stint AND was_running_at_flag THEN 'race_end'
        WHEN is_censored_stint THEN 'retirement'
        WHEN end_regime = 'red_flag' THEN 'red'
        WHEN end_regime = 'safety_car' THEN 'sc_pit'
        WHEN end_regime = 'vsc' THEN 'vsc_pit'
        ELSE 'green_pit'
    END AS stint_end_cause,

    CASE
        WHEN stint_number IS NULL THEN 'unassigned_stint'
        WHEN is_multi_regime_end THEN 'inferred'
        WHEN end_cause_from_disqualification THEN 'inferred'
        WHEN NOT is_censored_stint AND NOT ended_on_pit_lap THEN 'inferred'
        ELSE 'observed'
    END AS end_cause_confidence
FROM classified
