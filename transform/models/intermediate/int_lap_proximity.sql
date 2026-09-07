-- int_lap_proximity.sql · intermediate · grain: one row per race lap (lap_id)
-- Phase 10a: the true pairwise gap, from the position channel.
--
-- WHAT IS NEW HERE, AND WHY IT IS NOT ANOTHER RE-PROJECTION
-- --------------------------------------------------------
-- Every existing traffic feature in this warehouse descends from ONE number:
-- FastF1's `DistanceToDriverAhead`, which int_lap_air_state divides by point
-- speed to get a gap in seconds. That conversion assumes the car ahead is
-- travelling at the same speed as the car behind, which is exactly false in
-- the situation the feature exists to describe (a slower car being caught).
--
-- This model does not convert a distance into a time. It measures a time:
--   * cut each lap into 100 equal fractions of RelativeDistance (~50 m);
--   * for each (driver, lap, bin) take the session clock at which that driver
--     first entered that bin -- a CROSSING TIME of a fixed point on track;
--   * inside one (race, bin), order every crossing by that clock. The car
--     ahead on track is the previous crossing, and the gap is the difference
--     of two readings of the same clock at the same point in space.
-- That is the definition F1's own timing screens use. It needs no speed
-- assumption, it is correct for a car being lapped (a lapped car IS the car
-- ahead on track of whoever is about to pass it, whatever the lap counters
-- say), and it is available at the position channel's native ~369
-- samples/lap/driver rather than at lap grain.
--
-- The scalars below are per lap. A pairwise matrix is a warehouse
-- intermediate and never a browser payload; the join to the mart carries
-- eleven doubles per lap, not a 20x20 matrix per sample.
--
-- COST (measured 2026-09-05, 7 seasons / 118.7M telemetry rows):
-- the crossing table is 16,045,328 rows and the whole model builds in ~3 s.
-- The Phase 10 risk note predicted this would be the phase that made dev
-- builds painful; it is cheaper than either existing telemetry model
-- (int_lap_air_state 57.8 s, int_lap_telemetry_aggregates 19.3 s).
{{ config(materialized='table') }}

WITH pos AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        session_time_s,
        speed_kph,
        driver_ahead_number,
        distance_to_ahead_m,
        CAST(FLOOR(relative_distance * 100) AS INTEGER) AS track_bin
    FROM {{ ref('stg_telemetry_position') }}
),

-- Car number -> three-letter code, so FastF1's own driver_ahead can be
-- compared like-for-like with the identity this model derives. stg_results is
-- one row per driver per race, so this is a 20-row-per-race lookup.
driver_numbers AS (
    SELECT DISTINCT
        race_id,
        driver_number,
        driver_id
    FROM {{ ref('stg_results') }}
    WHERE driver_number IS NOT NULL
),

-- One crossing per (driver, lap, bin): the session clock at which the driver
-- first entered the bin. MIN() rather than an ordered first-value because the
-- samples inside a bin are already the same crossing -- ~3.7 of them.
crossings AS (
    SELECT
        p.race_year,
        p.race_id,
        p.driver_id,
        p.lap_number,
        p.track_bin,
        MIN(p.session_time_s) AS crossing_time_s,
        AVG(p.speed_kph) AS bin_speed_kph,
        -- AVG/MIN and not MEDIAN/MODE, for two reasons measured on
        -- 2026-09-05. Cost: MODE() over a VARCHAR across the 16,045,328
        -- crossing groups took 129 s of a 136 s model; MIN() takes ~1 s, and
        -- both aggregates here run over the ~3.7 samples inside one ~50 m bin
        -- where FastF1's answer is effectively constant. Determinism: MIN is
        -- order-independent, ANY_VALUE is not, and this repo already has a
        -- build-to-build reproducibility incident from exactly that shape (see
        -- stg_telemetry's note on 982,303 tied samples) plus an oracle
        -- byte-stability gate that would catch it as drift rather than as a
        -- bug. Both columns are diagnostics for the head-to-head below, never
        -- features, so the tie-break rule does not have to be the exact one.
        -- ROUNDed because a parallel float AVG is not associative: summation
        -- order moves with thread scheduling, which left this column differing
        -- on 17 of 162,729 laps between two builds at max |diff| 1.14e-13
        -- (3.1e-16 relative). Last-bit noise, invisible to every consumer, but
        -- it breaks the byte-stability oracle. int_lap_air_state ROUNDs its
        -- thermal loads for the same reason.
        ROUND(AVG(p.distance_to_ahead_m), 6) AS ff_distance_to_ahead_m,
        MIN(dn.driver_id) AS ff_driver_ahead
    FROM pos AS p
    LEFT JOIN driver_numbers AS dn
        ON
            p.race_id = dn.race_id
            AND p.driver_ahead_number = dn.driver_number
    GROUP BY 1, 2, 3, 4, 5
),

-- The pairwise step. Ordering every crossing of one bin by its clock makes
-- the immediately-preceding row the car ahead on track and the row before
-- that the car ahead of IT -- which is what separates a train from a single
-- tow without ever materialising a pairwise matrix.
--
-- Self-match guard: when a driver is genuinely alone at a point on track, the
-- previous crossing of that bin is the same driver one lap earlier. That is
-- not a car ahead, it is a full lap of clear air, so the gap is nulled and
-- read downstream as free air (matching int_lap_air_state's existing
-- treatment of an unavailable gap).
--
-- Stoppage guard (proximity_max_gap_s, 300 s): the self-match guard catches
-- the common case but not a RED FLAG, where the session clock keeps running
-- through a stoppage of tens of minutes while the field sits in the pit lane.
-- The previous crossing of a bin is then a different driver, from before the
-- stoppage, and the arithmetic is correct but the answer is meaningless as a
-- proximity measure. Measured 2026-09-05: exactly one lap in 162,729 exceeds
-- 300 s (2023 São Paulo, VER lap 3, 1484.5 s -- that race's red flag), 23
-- exceed 120 s, and the 99.99th percentile is 125.4 s. Anything past the
-- bound is clear air, so it is nulled on the same rule as a self-match rather
-- than clamped to a number that would read as a real car.
neighbours AS (
    SELECT
        *,
        LAG(driver_id) OVER w AS ahead_driver_id,
        LAG(crossing_time_s) OVER w AS ahead_crossing_s,
        LAG(driver_id, 2) OVER w AS ahead2_driver_id,
        LAG(crossing_time_s, 2) OVER w AS ahead2_crossing_s,
        LEAD(driver_id) OVER w AS behind_driver_id,
        LEAD(crossing_time_s) OVER w AS behind_crossing_s
    FROM crossings
    -- driver_id is a TIE-BREAK, not decoration, and leaving it out was a live
    -- defect in this model's first build. crossing_time_s alone is not a total
    -- order inside a (race_id, track_bin): the position channel samples on a
    -- fixed cadence, so two cars running close together enter the same ~50 m
    -- bin at the same recorded instant. 223,602 of 15,821,726 crossings
    -- (1.39%) share a (race, bin, crossing_time) key -- e.g. 2024_4, bin 5,
    -- lap 44: NOR and SAI both at 9700.823. Inside a tied block LAG/LEAD pick
    -- an arbitrary neighbour and the choice moves with DuckDB's scan
    -- parallelism, so two builds of identical SQL disagreed: the p50 arm of
    -- this phase's own ablation scored 1.017496 against one build of the mart
    -- and 1.021648 against the next, a 0.28x-of-floor swing from nothing but a
    -- rebuild. This is the SAME defect stg_telemetry documents one layer down
    -- (982,303 car-channel samples tied on distance_m), found the same way --
    -- by a number moving when nothing had changed.
    --
    -- (crossing_time_s, driver_id) IS a total order here: a driver crosses a
    -- given bin at most once per lap, so two rows can only tie on both if one
    -- driver were on two laps at the same instant. Asserted by
    -- assert_proximity_crossing_total_order. Which of two side-by-side cars is
    -- called "ahead" is then arbitrary but STABLE, which is the property that
    -- matters -- physically they are alongside and either answer is defensible.
    WINDOW w AS (
        PARTITION BY race_id, track_bin ORDER BY crossing_time_s, driver_id
    )
),

gaps AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        track_bin,
        crossing_time_s,
        bin_speed_kph,
        ff_driver_ahead,
        ff_distance_to_ahead_m,
        CASE
            WHEN
                ahead_driver_id <> driver_id
                AND crossing_time_s - ahead_crossing_s
                <= {{ var('proximity_max_gap_s', 300.0) }}
                THEN crossing_time_s - ahead_crossing_s
        END AS gap_ahead_s,
        CASE
            WHEN
                ahead_driver_id <> driver_id
                AND crossing_time_s - ahead_crossing_s
                <= {{ var('proximity_max_gap_s', 300.0) }}
                THEN ahead_driver_id
        END AS gap_ahead_driver_id,
        -- The car ahead's own gap to the car ahead of it. Both under 1 s is a
        -- train (this car is in a chain of dirty air); only this car's gap
        -- under 1 s is a single tow.
        CASE
            WHEN
                ahead_driver_id <> driver_id
                AND ahead2_driver_id <> ahead_driver_id
                THEN ahead_crossing_s - ahead2_crossing_s
        END AS ahead_own_gap_s,
        CASE
            WHEN
                behind_driver_id <> driver_id
                AND behind_crossing_s - crossing_time_s
                <= {{ var('proximity_max_gap_s', 300.0) }}
                THEN behind_crossing_s - crossing_time_s
        END AS gap_behind_s,
        -- How long this driver spent in this bin. Used to turn a per-bin
        -- share into real seconds. Clamped at 5 s: a bin is ~1% of a lap
        -- (~0.9-1.2 s) in green-flag running, and an unclamped value would
        -- let one pit stop dominate a lap's exposure total.
        LEAST(
            COALESCE(
                LEAD(crossing_time_s) OVER wd - crossing_time_s, 1.0
            ), 5.0
        ) AS bin_duration_s
    FROM neighbours
    -- Second tie-break, and it was a second live defect. crossing_time_s looks
    -- like a total order per driver per race -- one telemetry sample cannot sit
    -- in two bins -- but it is not, AT THE LAP ROLLOVER: FastF1 hands the
    -- transition sample to both laps, so bin 99 of lap N and bin 0 of lap N+1
    -- carry the SAME crossing time. 76 such pairs across the 149 races (e.g.
    -- 2018_6 BOT, lap 25 bin 99 and lap 26 bin 0, both at 2384.384).
    -- Unordered, LEAD could return the far side of the pair and hand a bin a
    -- whole lap of duration instead of ~1 s -- which is why time_within_1s
    -- moved by up to 2.841 s (5.06% relative) between two builds while
    -- share_lap_within_1s, computed over the same bin SET, did not move at
    -- all. The set was stable; only the weights were not.
    -- (crossing_time_s, lap_number, track_bin) is total by construction: it
    -- contains the full crossings grain. Asserted by
    -- assert_proximity_crossing_total_order.
    WINDOW wd AS (
        PARTITION BY race_id, driver_id
        ORDER BY crossing_time_s, lap_number, track_bin
    )
),

-- Per-lap scalars. Every aggregate here is over the ~100 bins of one lap.
lap_scalars AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        COUNT(*) AS proximity_bin_count,

        -- (1) how close, at the closest and typically
        MIN(gap_ahead_s) AS gap_ahead_min_s,
        MEDIAN(gap_ahead_s) AS gap_ahead_median_s,

        -- (2) cars within 1 s / 2 s / 3 s, as a share of the lap's bins
        AVG(CASE WHEN gap_ahead_s < 1.0 THEN 1.0 ELSE 0.0 END)
            AS share_lap_within_1s,
        AVG(CASE WHEN gap_ahead_s < 2.0 THEN 1.0 ELSE 0.0 END)
            AS share_lap_within_2s,
        AVG(CASE WHEN gap_ahead_s < 3.0 THEN 1.0 ELSE 0.0 END)
            AS share_lap_within_3s,

        -- (3) the same exposure in real seconds, time-weighted by how long
        -- the driver actually spent in each bin
        -- ROUNDed for the same reason ff_distance_to_ahead_m is: a parallel
        -- float SUM is not associative, so summation order moves with thread
        -- scheduling. After both window tie-breaks were fixed this was the last
        -- unstable column, at 1 row of 162,729 and max |diff| 1.42e-14 -- pure
        -- last-bit noise, three orders of magnitude finer than the 1e-4 s kept
        -- here and eleven finer than anything the feature means. Rounded rather
        -- than tolerated because this repo gates on byte-stability, and a model
        -- that is *nearly* reproducible makes that gate flake instead of work.
        ROUND(SUM(bin_duration_s) FILTER (WHERE gap_ahead_s < 1.0), 4)
            AS time_within_1s,

        -- (4) train vs single tow: this car within 1 s of the car ahead AND
        -- that car within 1 s of the car ahead of it
        AVG(
            CASE
                WHEN gap_ahead_s < 1.0 AND ahead_own_gap_s < 1.0 THEN 1.0
                ELSE 0.0
            END
        ) AS share_lap_in_train,

        -- (5) does the car ahead hold a fixed identity or rotate
        COUNT(DISTINCT gap_ahead_driver_id) FILTER (WHERE gap_ahead_s < 3.0)
            AS n_distinct_cars_ahead_3s,

        -- (6) pressure from behind. Not a dirty-air term -- it is the arm the
        -- BLUE-flag check scores against (a car being lapped has the lapping
        -- car behind it, not ahead), and it is the half of traffic that
        -- DistanceToDriverAhead structurally cannot see.
        MIN(gap_behind_s) AS gap_behind_min_s,
        AVG(CASE WHEN gap_behind_s < 1.0 THEN 1.0 ELSE 0.0 END)
            AS share_lap_behind_within_1s,

        -- (7) the incumbent measure, carried at the same grain so the two can
        -- be compared rather than one asserted better. Phase 10a's checklist:
        -- keep the old columns for one version.
        MEDIAN(ff_distance_to_ahead_m) AS ff_distance_to_ahead_m,
        AVG(
            CASE
                WHEN ff_driver_ahead IS NULL THEN NULL
                WHEN ff_driver_ahead = gap_ahead_driver_id THEN 1.0
                ELSE 0.0
            END
        ) AS ff_ahead_identity_agreement
    FROM gaps
    GROUP BY 1, 2, 3, 4
),

-- The modal car ahead and how much of the lap it held, computed separately
-- because it needs a per-(lap, ahead-driver) count before it can be reduced.
ahead_identity AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        MAX(bins_with_this_car) AS max_bins_one_car_ahead,
        SUM(bins_with_this_car) AS bins_with_any_car_ahead
    FROM (
        SELECT
            race_year,
            race_id,
            driver_id,
            lap_number,
            gap_ahead_driver_id,
            COUNT(*) AS bins_with_this_car
        FROM gaps
        WHERE gap_ahead_s < 3.0 AND gap_ahead_driver_id IS NOT NULL
        GROUP BY 1, 2, 3, 4, 5
    ) AS per_car
    GROUP BY 1, 2, 3, 4
),

-- Lap identity + the masking flags. Same spine as int_lap_air_state so the
-- two traffic families are joinable lap-for-lap.
ident AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        is_safety_car_lap,
        is_vsc_lap,
        is_red_flag_lap
    FROM {{ ref('int_stint_geometry') }}
),

joined AS (
    SELECT
        i.lap_id,
        i.stint_id,
        i.race_year,
        i.race_id,
        i.driver_id,
        i.lap_number,
        i.lap_in_stint,
        -- SC/VSC bunching trap, same as int_lap_air_state: under a safety car
        -- the field closes to sub-second gaps at a pace that generates no aero
        -- load at all. Zeroing rather than nulling keeps the column's meaning
        -- ("aerodynamic traffic exposure") true on those laps instead of
        -- recording the bunching as traffic.
        (i.is_safety_car_lap OR i.is_vsc_lap OR i.is_red_flag_lap)
            AS is_neutralised_lap,
        s.proximity_bin_count,
        s.gap_ahead_min_s,
        s.gap_ahead_median_s,
        s.share_lap_within_1s,
        s.share_lap_within_2s,
        s.share_lap_within_3s,
        s.time_within_1s,
        s.share_lap_in_train,
        s.n_distinct_cars_ahead_3s,
        s.gap_behind_min_s,
        s.share_lap_behind_within_1s,
        s.ff_distance_to_ahead_m,
        s.ff_ahead_identity_agreement,
        a.max_bins_one_car_ahead,
        a.bins_with_any_car_ahead
    FROM ident AS i
    LEFT JOIN lap_scalars AS s
        ON
            i.race_year = s.race_year
            AND i.race_id = s.race_id
            AND i.driver_id = s.driver_id
            AND i.lap_number = s.lap_number
    LEFT JOIN ahead_identity AS a
        ON
            i.race_year = a.race_year
            AND i.race_id = a.race_id
            AND i.driver_id = a.driver_id
            AND i.lap_number = a.lap_number
)

SELECT
    lap_id,
    stint_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    lap_in_stint,
    is_neutralised_lap,
    proximity_bin_count,

    -- Raw gaps (NULL = no car ahead within a full lap; free air)
    gap_ahead_min_s,
    gap_ahead_median_s,
    gap_behind_min_s,

    -- Exposure shares, zeroed on neutralised laps
    CASE
        WHEN is_neutralised_lap THEN 0.0
        ELSE COALESCE(share_lap_within_1s, 0.0)
    END AS share_lap_within_1s,
    CASE
        WHEN is_neutralised_lap THEN 0.0
        ELSE COALESCE(share_lap_within_2s, 0.0)
    END AS share_lap_within_2s,
    CASE
        WHEN is_neutralised_lap THEN 0.0
        ELSE COALESCE(share_lap_within_3s, 0.0)
    END AS share_lap_within_3s,
    CASE
        WHEN is_neutralised_lap THEN 0.0
        ELSE COALESCE(time_within_1s, 0.0)
    END AS time_within_1s,
    CASE
        WHEN is_neutralised_lap THEN 0.0
        ELSE COALESCE(share_lap_in_train, 0.0)
    END AS share_lap_in_train,
    CASE
        WHEN is_neutralised_lap THEN 0.0
        ELSE COALESCE(share_lap_behind_within_1s, 0.0)
    END AS share_lap_behind_within_1s,

    -- Identity stability of the car ahead: 1.0 = one car held the whole lap
    -- (a settled follow), low = the car ahead rotated (traffic being passed,
    -- or a lapping sequence). NULL when no car was within 3 s all lap, which
    -- is a different statement from "the identity was unstable" and is left
    -- as NULL rather than defaulted for exactly that reason.
    CAST(n_distinct_cars_ahead_3s AS INTEGER) AS n_distinct_cars_ahead_3s,
    CASE
        WHEN COALESCE(bins_with_any_car_ahead, 0) > 0
            THEN
                CAST(max_bins_one_car_ahead AS DOUBLE)
                / bins_with_any_car_ahead
    END AS ahead_identity_stability,

    -- The incumbent measure at the same grain, for the head-to-head
    ff_distance_to_ahead_m,
    ff_ahead_identity_agreement
FROM joined
