-- int_lap_proximity must agree with the FIA's own traffic label.
--
-- WHY THIS TEST EXISTS AND WHAT MAKES IT DIFFERENT
-- ------------------------------------------------
-- Every other traffic signal in this warehouse is a transform of FastF1
-- telemetry, so none of them can check another: agreeing with dirty_air_share
-- would only prove that two functions of the same bytes agree. A waved blue
-- flag is race control saying "car N is being lapped". It is independent of
-- the position channel, and it is the only supervised traffic label this
-- project has: 5,388 blue-flag messages over 8 seasons (2018-2025, 173 races).
--
-- THE STATISTIC: share of laps with NO car within 1 s behind.
-- A car being lapped has the lapping car BEHIND it, so the arm scored is
-- gap_behind_min_s, read as a rate: the share of laps on which it is NULL or
-- >= 1.0 s (no car within 1 s behind at any of the lap's ~100 bins). Smaller
-- is closer, and it must be smaller on blue-flagged laps than on the rest.
--
-- It replaces MEDIAN(LEAST(gap_ahead_min_s, gap_behind_min_s)), which
-- SATURATED: the position channel stamps cars running together with the same
-- clock reading (~0.24 s cadence), so a per-lap MIN gap is often exactly 0.0
-- and the blue-lap median sat on that floor (0.0 in 2025). A statistic sitting
-- on its floor cannot exceed 0.85 x anything, so the 2025 row passed by
-- construction rather than by evidence. A threshold rate is not pinned by the
-- quantisation: a tie at 0.0 is correctly "a car within 1 s", and the rate can
-- still move anywhere in [0, 1] if the measure decouples.
--
-- THE MATCHING: each flag is scored on the DRIVER'S OWN lap.
-- Race control numbers laps by the leader. A car being lapped is, by
-- definition, on an earlier lap of its own (of matched messages: 1 lap down
-- 65%, 2 down 30%, 3+ down 4%, 0 down 0.7%), so joining on (driver,
-- race-control lap) scored the wrong lap of nearly every flag. The
-- laps-down is not a constant: it grows during the race and differs per car,
-- so no fixed L-1 shift is used.
-- Instead each message is placed on the session clock:
--   * race control's message clock has a different origin from FastF1's
--     session clock (a wall-clock derivative, see stg_race_control), but the
--     offset is ONE constant per race. It is fitted per race as the offset
--     consistent with the most messages, where "consistent" means the message
--     falls inside the leader's lap L window from stg_laps (earliest
--     lap_start_time_s of lap L to that of lap L+1), +-1 s for the message
--     clock's whole-second resolution. Uses every race-control message, none
--     of them the position channel, so the matching is not circular.
--   * the flag's own lap is the lap of that driver whose
--     [lap_start_time_s, next lap's start) contains the corrected message
--     time.
-- Checked on dev 2026-10-22, P(car within 1 s behind) on the matched lap and
-- its neighbours, own lap +k: k=-1 0.500, k=0 0.957, k=+1 0.637. Against the
-- race-control lap the best any fixed shift reaches is 0.882 (L-1), and the
-- old L itself scores 0.552 -- barely above the 0.454 base rate.
--
-- THE ASSERTION, per season (a pooled one would survive a season inverting).
-- Measured 2026-10-22 on data/dev.duckdb (read-only copy), share of laps with
-- no car within 1 s behind, blue / other, and the ratio:
--   year  raw unm  dup  laps neu nop scored  blue/other   ratio
--   2018  862   7  132  723  19  28   676  0.052/0.595  0.087
--   2019 1079   1  179  899  21   0   878  0.035/0.581  0.061
--   2020  451   3   62  386   5   0   381  0.089/0.587  0.152
--   2021  969  11  170  788  12   0   776  0.048/0.613  0.078
--   2022  525  14   84  427  22   0   405  0.032/0.532  0.060
--   2023  342   5   63  274   3   0   271  0.033/0.528  0.063
--   2024  681   8  147  526   3   0   523  0.029/0.541  0.053
--   2025  479   5  130  344   4   0   340  0.026/0.513  0.052
-- raw = unm + dup + laps and laps = neu + nop + scored, where raw =
-- blue-flag messages; unm = unmatched (no clock offset, or no driver lap at
-- the corrected time); dup = further messages for an own lap already
-- flagged; laps = distinct blue own-laps; neu = blue laps on SC/VSC/red laps
-- (excluded by design, below); nop = blue laps with no proximity bins
-- (2018: all 28 are 2018_1 and 2018_2, which have no position telemetry at
-- all); scored = what the rates use.
--
-- For the record, the old statistic on the old join, same date and copy:
-- blue/other median closest car 0.300/0.899 (2018), 0.300/0.899, 0.659/0.861
-- (2020, ratio 0.77, the old worst), 0.421/0.879, 0.320/0.580, 0.220/0.580,
-- 0.220/0.619, 0.000/0.540 (2025: 59% of blue laps read exactly 0.0), over
-- 257-859 matched blue laps per season.
--
-- The 0.85 factor is unchanged and is slack, not a target: the worst season
-- is 2020 at 0.152. The failure guarded against is the measure decoupling
-- from physical reality altogether (a binning bug, a self-match leaking in,
-- the crossing clock losing its common origin), which sends the ratio to
-- ~1.0, not a seasonal wobble around 0.1.
--
-- FAILS LOUDLY ON LOST FLAGS. A flag that cannot be matched is reported, not
-- dropped in silence: a season fails if more than 5% of its blue-flag
-- messages are unmatched or land on a lap with no proximity bins (worst on
-- dev: 2018, 35/862 = 4.1%, of which 28 are the two telemetry-less races;
-- next is 2022, 14/525 = 2.7%). The unmatched messages and no-proximity
-- laps are summed against raw messages, a slight overcount by design. Every
-- count column is in the output, so a failing row shows raw, duplicates,
-- matches and the statistic together.
--
-- Neutralised laps are excluded on the same reasoning int_lap_proximity zeroes
-- them: under a safety car the whole field is within a second of itself and
-- both arms of the comparison collapse.
--
-- THIS TEST IS VACUOUS ON THE CI FIXTURE, DELIBERATELY, AND THAT IS RECORDED
-- HERE SO A GREEN CI RUN IS NOT MISREAD AS EVIDENCE. The `n_raw >= 100` guard
-- (both the ratio and the 5% unmatched check) is what makes a rate a rate
-- rather than a coin flip, and the three-race fixture carries 12 / 1 blue-flag
-- messages in its two seasons that have any (verified 2026-10-22 against a
-- copy of data/ci.duckdb; 10 scored blue laps in 2023, 0 in 2024). No
-- season clears the guard, so on `--target ci` this test asserts over an
-- empty set -- the "gate asserting over nothing" shape. It is a dev/prod
-- gate: on data/dev.duckdb it exercises 8 seasons
-- carrying 271-878 scored blue laps each. Enlarging the fixture until a
-- season clears 100 would mean carrying several more races of telemetry in
-- git; lowering the guard would make the test flaky rather than make it work.
WITH blue_msgs AS (
    SELECT
        race_year,
        race_id,
        message_index,
        driver_id,
        message_time_s
    FROM {{ ref('stg_race_control') }}
    WHERE is_blue_flag_event
),

driver_laps AS (
    SELECT
        race_id,
        driver_id,
        lap_number,
        lap_start_time_s AS lap_start_s,
        COALESCE(
            LEAD(lap_start_time_s) OVER (
                PARTITION BY race_id, driver_id ORDER BY lap_number
            ),
            lap_start_time_s + lap_time_s
        ) AS lap_end_s
    FROM {{ ref('stg_laps') }}
    WHERE lap_start_time_s IS NOT NULL
),

-- The leader's lap L window: race control's lap counter.
leader_laps AS (
    SELECT
        race_id,
        lap_number,
        MIN(lap_start_time_s) AS leader_start_s
    FROM {{ ref('stg_laps') }}
    GROUP BY 1, 2
),

-- Each message admits a band of clock offsets: those that put it inside the
-- leader's window for its lap.
offset_bands AS (
    SELECT
        rc.race_id,
        rc.message_time_s - nxt.leader_start_s - 1.0 AS offset_lo,
        rc.message_time_s - cur.leader_start_s + 1.0 AS offset_hi
    FROM {{ ref('stg_race_control') }} AS rc
    INNER JOIN leader_laps AS cur
        ON rc.race_id = cur.race_id AND rc.lap_number = cur.lap_number
    INNER JOIN leader_laps AS nxt
        ON rc.race_id = nxt.race_id AND rc.lap_number + 1 = nxt.lap_number
    WHERE rc.message_time_s IS NOT NULL
),

offset_candidates AS (
    SELECT
        c.race_id,
        c.candidate_s,
        COUNT(*) FILTER (
            WHERE c.candidate_s BETWEEN b.offset_lo AND b.offset_hi
        ) AS n_consistent
    FROM (
        SELECT race_id, offset_lo AS candidate_s FROM offset_bands
        UNION
        SELECT race_id, offset_hi AS candidate_s FROM offset_bands
    ) AS c
    INNER JOIN offset_bands AS b ON c.race_id = b.race_id
    GROUP BY 1, 2
),

-- Midpoint of the best-supported offsets: deterministic, no tie-break needed.
best_support AS (
    SELECT
        race_id,
        MAX(n_consistent) AS max_consistent
    FROM offset_candidates
    GROUP BY 1
),

race_offset AS (
    SELECT
        c.race_id,
        (MIN(c.candidate_s) + MAX(c.candidate_s)) / 2.0 AS offset_s
    FROM offset_candidates AS c
    INNER JOIN best_support AS b
        ON
            c.race_id = b.race_id
            AND c.n_consistent = b.max_consistent
    GROUP BY 1
),

-- One row per message, with the driver's own lap (NULL = unmatched).
msg_matched AS (
    SELECT
        m.race_year,
        m.race_id,
        m.message_index,
        m.driver_id,
        MAX(dl.lap_number) AS own_lap
    FROM blue_msgs AS m
    LEFT JOIN race_offset AS o ON m.race_id = o.race_id
    LEFT JOIN driver_laps AS dl
        ON
            m.race_id = dl.race_id
            AND m.driver_id = dl.driver_id
            AND m.message_time_s - o.offset_s >= dl.lap_start_s
            AND m.message_time_s - o.offset_s < dl.lap_end_s
    GROUP BY 1, 2, 3, 4
),

blue_laps AS (
    SELECT DISTINCT
        race_year,
        race_id,
        driver_id,
        own_lap AS lap_number
    FROM msg_matched
    WHERE own_lap IS NOT NULL
),

blue_lap_status AS (
    SELECT
        b.race_year,
        COUNT(*) AS n_blue_laps,
        COUNT(*) FILTER (WHERE p.is_neutralised_lap) AS n_neutralised,
        COUNT(*) FILTER (
            WHERE p.lap_id IS NULL OR p.proximity_bin_count IS NULL
        ) AS n_no_proximity
    FROM blue_laps AS b
    LEFT JOIN {{ ref('int_lap_proximity') }} AS p
        ON
            b.race_id = p.race_id
            AND b.driver_id = p.driver_id
            AND b.lap_number = p.lap_number
    GROUP BY 1
),

msg_counts AS (
    SELECT
        m.race_year,
        COUNT(*) AS n_raw,
        COUNT(*) FILTER (WHERE m.own_lap IS NULL) AS n_unmatched,
        COUNT(m.own_lap) - ANY_VALUE(bl.n_blue_laps) AS n_duplicate
    FROM msg_matched AS m
    LEFT JOIN blue_lap_status AS bl ON m.race_year = bl.race_year
    GROUP BY 1
),

labelled AS (
    SELECT
        p.race_year,
        COALESCE(p.gap_behind_min_s >= 1.0, TRUE) AS no_car_within_1s_behind,
        b.race_id IS NOT NULL AS is_blue_lap
    FROM {{ ref('int_lap_proximity') }} AS p
    LEFT JOIN blue_laps AS b
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
        COUNT(*) FILTER (WHERE is_blue_lap) AS n_scored,
        AVG(CAST(no_car_within_1s_behind AS DOUBLE)) FILTER (
            WHERE is_blue_lap
        ) AS blue_clear_behind_share,
        AVG(CAST(no_car_within_1s_behind AS DOUBLE)) FILTER (
            WHERE NOT is_blue_lap
        ) AS other_clear_behind_share
    FROM labelled
    GROUP BY 1
),

report AS (
    SELECT
        mc.race_year,
        mc.n_raw,
        mc.n_unmatched,
        mc.n_duplicate,
        bl.n_blue_laps,
        bl.n_neutralised,
        bl.n_no_proximity,
        ps.n_scored,
        ps.blue_clear_behind_share,
        ps.other_clear_behind_share,
        ps.blue_clear_behind_share
        / NULLIF(ps.other_clear_behind_share, 0) AS clear_behind_ratio,
        (mc.n_unmatched + COALESCE(bl.n_no_proximity, 0))
        / CAST(mc.n_raw AS DOUBLE) AS lost_share
    FROM msg_counts AS mc
    LEFT JOIN blue_lap_status AS bl ON mc.race_year = bl.race_year
    LEFT JOIN per_season AS ps ON mc.race_year = ps.race_year
)

SELECT *
FROM report
WHERE
    n_raw >= 100
    AND (
        lost_share > 0.05
        OR n_scored IS NULL
        OR blue_clear_behind_share > 0.85 * other_clear_behind_share
    )
