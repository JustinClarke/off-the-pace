-- Layer 03: Air state classification and dirty-air thermal load.
-- Gap-to-car-ahead is taken directly from telemetry DistanceToDriverAhead
-- (meters),
-- converted to seconds using point speed: gap_s = distance_m / (speed_kph /
-- 3.6).
-- Sectors are approximated by relative distance thirds (S1: 0–33%, S2: 33–67%,
-- S3: 67–100%)
-- since precise sector boundary distances are not available in telemetry.
-- EW thermal loads use finite weighted sums partitioned on stint_id so load
-- resets at each stop.
-- time_in_dirty_air_s sums real per-sample elapsed time (from the merged
-- ~10Hz car/pos telemetry stream) where gap < 1.5s, replacing the coarse
-- "was the S2 sector median gap < 1.5s" binary with an actual duration.
--
-- F48 (WI-15a, 2026-09-25): dirty-air exposure is a function of the gap
-- alone. S2 (the only third that prices dirty air) used to test DRS before
-- the gap, so a car sitting <1.0 s behind through S2 with DRS open anywhere in
-- the third was coded 'drs_train' (dirty_air_share_lap = 0) while a car
-- 1.0-1.5 s behind was coded 'dirty_air' (share 1): the share was not monotone
-- in the gap, and 11,540 of the 25,624 training-eligible laps with an S2
-- median gap under 1 s (45%, 2026-09-25 build) were billed as clean air. Now
-- any S2 median gap
-- < 1.5 s is 'dirty_air' whatever DRS did. DRS is carried beside it as its own
-- column (s2_drs_active) instead of inside the classification, together with
-- the S2 median gap itself (s2_gap_median_s) so the monotonicity can be
-- asserted against the measured gap (assert_dirty_air_share_monotone, T38).
-- Whether DRS-open S2 laps really carry less aero load is a physics question
-- nothing in this tree settles; keeping DRS in a column leaves it answerable.
-- The straights (S1/S3) keep their tow/DRS split unchanged: 'drs_train' now
-- means "within 1 s with DRS open on a straight third" and never touches the
-- dirty-air share. Downstream, the share is the treatment in
-- int_dirty_air_tax_component's theta_air, so this change moves theta_air
-- and every dirty-air lap's label on the next build: that re-estimate belongs
-- to WI-01's label version bump, not to this model.
--
-- FD6 (CO-04, 2026-10-15; ruled B: a missing measurement is NULL, not a
-- guess). A lap with no measured gap anywhere on it used to be written as
-- 'free_air' with every dirty-air term 0.0. That is true for the race leader,
-- who has no car ahead: outside 2018, 98-100% of no-gap laps are the leader.
-- It is a guess for anyone else. 2018 has 1,824 such non-leader laps (8.2% of
-- its laps), all but two in 2018_1 Australia and 2018_2 Bahrain, which have no
-- telemetry at all in bronze. FastF1 has no position channel for either race
-- (FD6). Every other season has 2-32. So a non-leader lap with no
-- measured gap now gets NULL air_state_dominant, dirty_air_share_lap,
-- tow_benefit_lap_s, time_in_dirty_air_s and thermal loads. Leader laps keep
-- 'free_air' / 0.0 exactly as before. "Leader" is the lap's end-of-lap race
-- position (stg_laps.position = 1); a NULL position is not known to be the
-- leader, so it is treated as unmeasured (21 laps, 2026-10-15 build). Gaps
-- are all-or-nothing per lap on the 2026-10-15 build (no lap has a gap in
-- some sectors and not others), so the lap-level rule is exact.
-- The NULL takes precedence over the SC/VSC/red zeroing below: an unmeasured
-- lap is unknown whatever the track status.
-- Downstream, int_dirty_air_tax_component, fct_cliff_prediction_features,
-- int_sector_residual_decomposed and int_driver_isolation_lap_panel still
-- COALESCE these columns back to 0.0 / 'free_air'. That is outside this
-- model; see the CO-04 report.
--
-- T7 (CO-04): air_state_dominant used to be MODE() over the three sector
-- states, which is arbitrary when all three differ: 12,782 of 124,264
-- training-eligible laps (10.3%) on the 2026-10-15 build. The tie now goes to
-- the more traffic-affected state (dirty_air > drs_train > tow_zone >
-- free_air). On that build this reproduces every tied value DuckDB's MODE()
-- happened to return. The point is that it is now declared, not left to an
-- implementation detail.
{{ config(materialized='table') }}

WITH geom AS (
    SELECT
        stint_id,
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        is_safety_car_lap,
        is_vsc_lap,
        is_red_flag_lap
    FROM {{ ref('int_stint_geometry') }}
    -- Deliberately no is_valid_lap filter: this model consumes the full
    -- chronological sequence (SC/VSC/pit laps included) so the EWMA thermal
    -- load decays through those laps instead of treating the lap before/
    -- after a gap as adjacent.
),

telemetry AS (
    SELECT
        race_id,
        CAST(season AS INTEGER) AS race_year,
        driver_id,
        CAST(lap_number AS INTEGER) AS lap_number,
        speed_kph,
        distance_m,
        relativedistance AS relative_distance,
        distancetodriverahead AS distance_to_ahead_m,
        date AS sample_ts,
        -- Convert to time gap (s); null when car is stationary or gap
        -- unavailable
        CASE
            WHEN distancetodriverahead IS NOT NULL AND speed_kph > 1.0
                THEN distancetodriverahead / (speed_kph / 3.6)
        END AS gap_to_ahead_s,
        -- Sector proxy by relative distance thirds
        CASE
            WHEN relativedistance < 0.33 THEN 1
            WHEN relativedistance < 0.67 THEN 2
            ELSE 3
        END AS sector_proxy,
        drs
    FROM {{ source('bronze_f1', 'raw_telemetry') }}
    WHERE speed_kph > 0
),

-- Real elapsed time since the previous sample in the merged ~10Hz car/pos
-- stream (per driver-lap). Used to sum actual dirty-air exposure time rather
-- than approximate it from a single per-sector median gap. The first sample
-- of each lap has no predecessor (NULL dt, contributes 0) -- a fixed,
-- negligible (~one sample period) undercount common to every lap.
telemetry_dt AS (
    SELECT
        *,
        EPOCH(sample_ts - LAG(sample_ts) OVER w) AS dt_s
    FROM telemetry
    WINDOW w AS (
        PARTITION BY race_year, race_id, driver_id, lap_number
        ORDER BY sample_ts
    )
),

-- Real per-lap dirty-air exposure time: sum of sample dt where gap < 1.5s,
-- replacing the coarse "was the S2 median gap < 1.5s" binary with an actual
-- duration. Null gap samples are not counted as dirty-air time; a lap with
-- no gap sample at all is the leader (0.0) or unmeasured (NULL), decided in
-- with_stint (FD6, CO-04).
lap_dirty_air_time AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        SUM(dt_s) FILTER (
            WHERE gap_to_ahead_s IS NOT NULL AND gap_to_ahead_s < 1.5
        ) AS time_in_dirty_air_s
    FROM telemetry_dt
    GROUP BY race_year, race_id, driver_id, lap_number
),

-- Aggregate per lap × sector_proxy: median gap and DRS state
sector_agg AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        sector_proxy AS sector,
        -- Median gap per sector (robust to outliers from backmarker passes)
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gap_to_ahead_s)
        FILTER (WHERE gap_to_ahead_s IS NOT NULL)
            AS gap_median_s,
        COUNT(*) FILTER (WHERE gap_to_ahead_s IS NOT NULL) AS gap_sample_count,
        -- DRS active: FastF1 encodes active DRS as values 10, 12, 14
        MAX(CASE WHEN drs IN (10, 12, 14) THEN 1 ELSE 0 END) AS drs_active
    FROM telemetry
    GROUP BY race_year, race_id, driver_id, lap_number, sector_proxy
),

-- Classify each sector by air state.
-- S2 is classified on the gap alone (F48): DRS is not consulted there. The
-- S1/S3 branches are the pre-F48 logic unchanged -- DRS still splits a sub-1 s
-- follow on a straight into 'drs_train' vs 'tow_zone'.
-- FD6 (CO-04): a sector with no gap sample is unmeasured (NULL), not
-- 'free_air'. Whether a lap with no gap is free air (the leader) or unknown
-- (anyone else) is decided at lap level in with_stint, which has the position.
sector_classified AS (
    SELECT
        *,
        CASE
            WHEN gap_median_s IS NULL THEN NULL
            WHEN gap_median_s > 2.0 THEN 'free_air'
            WHEN sector = 2 AND gap_median_s < 1.5 THEN 'dirty_air'
            WHEN
                sector != 2 AND gap_median_s < 1.0 AND drs_active = 1
                THEN 'drs_train'
            WHEN sector != 2 AND gap_median_s < 1.0 THEN 'tow_zone'
            ELSE 'free_air'
        END AS sector_air_state,
        -- Dirty air intensity (S2 only): inverse distance, floored at 0.3s gap
        CASE
            WHEN sector = 2 AND gap_median_s IS NOT NULL AND gap_median_s < 1.5
                THEN 1.0 / GREATEST(gap_median_s, 0.3)
            ELSE 0.0
        END AS dirty_air_intensity_sector
    FROM sector_agg
),

-- T7 (CO-04): the lap's dominant air state is its most frequent measured
-- sector state; a tie (every measured sector different) goes to the more
-- traffic-affected state, dirty_air > drs_train > tow_zone > free_air.
-- Replaces MODE(), which picks arbitrarily on a tie (header). Unmeasured
-- sectors (NULL state) do not vote; a lap with none has no row here.
lap_dominant_state AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        sector_air_state AS air_state_dominant
    FROM (
        SELECT
            race_year,
            race_id,
            driver_id,
            lap_number,
            sector_air_state,
            COUNT(*) AS n_sectors_in_state
        FROM sector_classified
        WHERE sector_air_state IS NOT NULL
        GROUP BY race_year, race_id, driver_id, lap_number, sector_air_state
    )
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY race_year, race_id, driver_id, lap_number
        ORDER BY
            n_sectors_in_state DESC,
            CASE sector_air_state
                WHEN 'dirty_air' THEN 4
                WHEN 'drs_train' THEN 3
                WHEN 'tow_zone' THEN 2
                WHEN 'free_air' THEN 1
            END DESC
    ) = 1
),

-- Aggregate to lap level
lap_air AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        -- Share of S2 sectors classified as dirty air (0 or 1 since one S2 per
        -- lap)
        MAX(
            CASE
                WHEN
                    sector = 2 AND sector_air_state = 'dirty_air'
                    THEN 1.0
                ELSE 0.0
            END
        )
            AS dirty_air_share_lap,
        -- Tow benefit: negative (saves time) when in tow_zone on straight
        -- sectors
        SUM(CASE WHEN sector_air_state = 'tow_zone' THEN -0.15 ELSE 0.0 END)
            AS tow_benefit_lap_s,
        MAX(dirty_air_intensity_sector) AS dirty_air_intensity,
        -- NULL when no sector of the lap has a gap sample (FD6, with_stint)
        MIN(gap_median_s) AS min_gap_s,
        -- F48: the measured S2 gap the share is a function of, and the DRS
        -- state it no longer consults. One S2 row per lap, so MAX just picks
        -- it; NULL when the lap has no S2 telemetry (gap) or no S2 row (DRS).
        MAX(CASE WHEN sector = 2 THEN gap_median_s END) AS s2_gap_median_s,
        MAX(CASE WHEN sector = 2 THEN drs_active END) AS s2_drs_active
    FROM sector_classified
    GROUP BY race_year, race_id, driver_id, lap_number
),

-- FD6 (CO-04): end-of-lap race position, to tell the leader (no car ahead, so
-- no gap really is free air) from a car whose gap is unmeasured.
lap_position AS (
    SELECT
        lap_id,
        position
    FROM {{ ref('stg_laps') }}
),

-- Lap-level joins, plus the FD6 flag: no gap measured anywhere on the lap
-- (no telemetry row, or telemetry with no car-ahead distance) and not the
-- leader. A NULL position is not known to be the leader, so it counts.
lap_joined AS (
    SELECT
        g.stint_id,
        g.lap_id,
        g.race_year,
        g.race_id,
        g.driver_id,
        g.lap_number,
        g.lap_in_stint,
        g.is_safety_car_lap OR g.is_vsc_lap OR g.is_red_flag_lap
            AS is_neutralised_lap,
        a.min_gap_s IS NULL AND COALESCE(p.position, 0) != 1
            AS is_air_unmeasured,
        a.dirty_air_share_lap,
        a.tow_benefit_lap_s,
        a.dirty_air_intensity,
        d.air_state_dominant,
        a.min_gap_s,
        a.s2_gap_median_s,
        a.s2_drs_active,
        t.time_in_dirty_air_s
    FROM geom AS g
    LEFT JOIN lap_position AS p ON g.lap_id = p.lap_id
    LEFT JOIN lap_air AS a
        ON
            g.race_year = a.race_year
            AND g.race_id = a.race_id
            AND g.driver_id = a.driver_id
            AND g.lap_number = a.lap_number
    LEFT JOIN lap_dominant_state AS d
        ON
            g.race_year = d.race_year
            AND g.race_id = d.race_id
            AND g.driver_id = d.driver_id
            AND g.lap_number = d.lap_number
    LEFT JOIN lap_dirty_air_time AS t
        ON
            g.race_year = t.race_year
            AND g.race_id = t.race_id
            AND g.driver_id = t.driver_id
            AND g.lap_number = t.lap_number
),

-- Lap-level air state on the stint geometry spine, for ordered windows.
-- FD6 first: an unmeasured non-leader lap is NULL on every air-state term
-- (header). Otherwise a lap with no gap is the leader in free air, and the
-- COALESCEs below fill 'free_air' / 0.0 for exactly those laps; a lap with a
-- measured gap and no dirty-air sample likewise has a true 0.0 exposure time.
-- SC/VSC bunching trap: under SC the field closes to <1s gaps, which would
-- otherwise spike dirty-air share/intensity on exactly the laps where there
-- is no real aero load (SC pace). Zero both on SC/VSC laps so the EWMA
-- decays toward zero through the gap instead of teleporting across it.
with_stint AS (
    SELECT
        stint_id,
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        CASE
            WHEN is_air_unmeasured THEN NULL
            WHEN is_neutralised_lap THEN 0.0
            ELSE COALESCE(dirty_air_share_lap, 0.0)
        END AS dirty_air_share_lap,
        CASE
            WHEN is_air_unmeasured THEN NULL
            ELSE COALESCE(tow_benefit_lap_s, 0.0)
        END AS tow_benefit_lap_s,
        CASE
            WHEN is_air_unmeasured THEN NULL
            WHEN is_neutralised_lap THEN 0.0
            ELSE COALESCE(dirty_air_intensity, 0.0)
        END AS dirty_air_intensity,
        CASE
            WHEN is_air_unmeasured THEN NULL
            ELSE COALESCE(air_state_dominant, 'free_air')
        END AS air_state_dominant,
        min_gap_s,
        -- Raw measurements, not zeroed on SC/VSC laps (min_gap_s is not
        -- either): they describe what was measured, not what is priced.
        s2_gap_median_s,
        CAST(s2_drs_active AS BOOLEAN) AS s2_drs_active,
        CASE
            WHEN is_air_unmeasured THEN NULL
            WHEN is_neutralised_lap THEN 0.0
            ELSE COALESCE(time_in_dirty_air_s, 0.0)
        END AS time_in_dirty_air_s
    FROM lap_joined
),

-- EW thermal loads finite weighted sum approximation partitioned by stint.
-- Surface: α=0.6, 5-lap lookback. Bulk: α=0.25, 10-lap lookback.
-- LAG's third argument (0.0) fills only the laps before the stint started,
-- where the load really is 0 (it resets at each stop). An unmeasured lap
-- inside the lookback (FD6) stays NULL, so the load is NULL until it leaves
-- the window rather than pricing the unknown lap as clean air. Until CO-04
-- this was COALESCE(LAG(..), 0), which was the same thing only while
-- dirty_air_intensity could not be NULL.
thermal AS (
    SELECT
        *,
        -- Surface load (α=0.6): weights = 0.6, 0.24, 0.096, 0.038, 0.015
        ROUND(
            0.600 * dirty_air_intensity
            + 0.240 * LAG(dirty_air_intensity, 1, 0.0) OVER w
            + 0.096 * LAG(dirty_air_intensity, 2, 0.0) OVER w
            + 0.038 * LAG(dirty_air_intensity, 3, 0.0) OVER w
            + 0.015 * LAG(dirty_air_intensity, 4, 0.0) OVER w,
            4
        ) AS dirty_air_thermal_load_surface,

        -- Bulk load (α=0.25): weights decay slowly-0.25, 0.1875, 0.141, ...
        ROUND(
            0.2500 * dirty_air_intensity
            + 0.1875 * LAG(dirty_air_intensity, 1, 0.0) OVER w
            + 0.1406 * LAG(dirty_air_intensity, 2, 0.0) OVER w
            + 0.1055 * LAG(dirty_air_intensity, 3, 0.0) OVER w
            + 0.0791 * LAG(dirty_air_intensity, 4, 0.0) OVER w
            + 0.0593 * LAG(dirty_air_intensity, 5, 0.0) OVER w
            + 0.0445 * LAG(dirty_air_intensity, 6, 0.0) OVER w
            + 0.0334 * LAG(dirty_air_intensity, 7, 0.0) OVER w
            + 0.0250 * LAG(dirty_air_intensity, 8, 0.0) OVER w
            + 0.0188 * LAG(dirty_air_intensity, 9, 0.0) OVER w,
            4
        ) AS dirty_air_thermal_load_bulk

    FROM with_stint
    WINDOW w AS (
        PARTITION BY stint_id
        ORDER BY lap_in_stint
        ROWS BETWEEN 10 PRECEDING AND CURRENT ROW
    )
)

SELECT
    stint_id,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    lap_in_stint,
    dirty_air_share_lap,
    tow_benefit_lap_s,
    dirty_air_thermal_load_surface,
    dirty_air_thermal_load_bulk,
    air_state_dominant,
    min_gap_s,
    time_in_dirty_air_s,
    s2_gap_median_s,
    s2_drs_active
FROM thermal
