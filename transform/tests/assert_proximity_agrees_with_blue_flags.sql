-- int_lap_proximity must agree with the FIA's own traffic label.
--
-- WHY THIS TEST EXISTS AND WHAT MAKES IT DIFFERENT
-- ------------------------------------------------
-- Every other traffic signal in this warehouse is a transform of FastF1
-- telemetry, so none of them can check another: agreeing with dirty_air_share
-- would only prove that two functions of the same bytes agree. A waved blue
-- flag is race control saying "car N is being lapped on lap L". It is
-- independent of the position channel, and it is the only supervised traffic
-- label this project has (4,909 of them, plan §17 / open item 13).
--
-- THE ASSERTION, and why it is per-season rather than pooled.
-- On a lap where a driver is being lapped there is, by definition, a car
-- close by. So the median closest car -- ahead or behind, whichever is nearer
-- -- must be smaller on blue-flagged laps than on the rest. Measured
-- 2026-09-05 over 149 races: **0.30 s vs 0.60 s** pooled, and the sign holds
-- in all 7 seasons independently (blue/other: 0.300/0.801, 0.300/0.600,
-- 0.440/0.659, 0.220/0.860, 0.200/0.460, 0.201/0.441, 0.200/0.520), which is
-- why the test asserts per season and not on the pooled figure. A pooled
-- assertion would survive one season inverting; this one would not.
--
-- The incumbent measure fails this same check: `dirty_air_share_lap` moves the
-- WRONG WAY on the identical split (0.2402 non-blue -> 0.1327 blue), because a
-- car being lapped has the fast car BEHIND it and DistanceToDriverAhead only
-- looks forward. That is the gap this feature family exists to close.
--
-- The 0.85 factor is slack, not a target: the worst per-season ratio is 2020's
-- 0.440/0.659 = 0.67, and the best is 2021's 0.26. The failure being guarded
-- against is the measure decoupling from physical reality altogether (a
-- binning bug, a self-match leaking in, the crossing clock losing its common
-- origin), which sends the ratio to ~1.0, not a seasonal wobble around 0.67.
--
-- Neutralised laps are excluded on the same reasoning int_lap_proximity zeroes
-- them: under a safety car the whole field is within a second of itself and
-- both arms of the comparison collapse.
--
-- THIS TEST IS VACUOUS ON THE CI FIXTURE, DELIBERATELY, AND THAT IS RECORDED
-- HERE SO A GREEN CI RUN IS NOT MISREAD AS EVIDENCE. The `n_blue >= 100` guard
-- is what makes the median a median rather than a coin flip, and the three-race
-- fixture carries 12 / 1 / 0 blue flags per season (verified 2026-09-05 against
-- data/ci.duckdb: 3,116 proximity laps, 10 of them blue-flagged). No season
-- clears the guard, so on `--target ci` this test asserts over an empty set --
-- the "gate asserting over nothing" shape Corrections §6 catalogues. It is a
-- dev/prod gate: on data/dev.duckdb it exercises 7 seasons carrying 257-1,079
-- blue flags each. Enlarging the fixture until a season clears 100 would mean
-- carrying several more races of telemetry in git; lowering the guard would
-- make the test flaky rather than make it work.
WITH blue AS (
    SELECT DISTINCT
        race_id,
        driver_id,
        lap_number
    FROM {{ ref('stg_race_control') }}
    WHERE is_blue_flag_event
),

labelled AS (
    SELECT
        p.race_year,
        LEAST(
            COALESCE(p.gap_ahead_min_s, 99.0),
            COALESCE(p.gap_behind_min_s, 99.0)
        ) AS closest_car_s,
        b.race_id IS NOT NULL AS is_blue_lap
    FROM {{ ref('int_lap_proximity') }} AS p
    LEFT JOIN blue AS b
        ON
            p.race_id = b.race_id
            AND p.driver_id = b.driver_id
            AND p.lap_number = b.lap_number
    WHERE
        NOT p.is_neutralised_lap
        AND p.proximity_bin_count IS NOT NULL
),

per_season AS (
    SELECT
        race_year,
        COUNT(*) FILTER (WHERE is_blue_lap) AS n_blue,
        MEDIAN(closest_car_s) FILTER (WHERE is_blue_lap) AS blue_closest_s,
        MEDIAN(closest_car_s) FILTER (WHERE NOT is_blue_lap) AS other_closest_s
    FROM labelled
    GROUP BY 1
)

SELECT
    race_year,
    n_blue,
    blue_closest_s,
    other_closest_s
FROM per_season
WHERE
    n_blue >= 100
    AND blue_closest_s > 0.85 * other_closest_s
