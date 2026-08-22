-- Every official qualifying segment time must have been set inside the segment
-- we assigned it to.
--
-- int_qualifying_segments recovers the Q1/Q2/Q3 windows from the session-status
-- timeline; stg_results_qualifying is the official record of what each driver's
-- best lap in each segment actually was. Matching an official time back to the
-- lap that set it and checking which segment that lap landed in is the direct
-- test of the recovery: if a boundary is off, laps cross it and this fails.
--
-- Official times with no matching lap are skipped rather than failed. Those are
-- source artefacts, not assignment errors: a handful of the staged results are
-- exactly 1.000s off the lap that set them, and a few laps deleted for track
-- limits are not flagged Deleted in bronze, so the driver's fastest lap in the
-- segment is quicker than their official time.
--
-- A time identical to the next segment's is skipped for the same reason: FastF1
-- copies a driver's later time back into the earlier column when they set
-- nothing in the earlier segment (three drivers in 2024 Interlagos), so the
-- earlier column points at a lap that genuinely belongs to the later segment.

WITH official AS (
    SELECT
        race_year, race_id, driver_id, 'Q1' AS quali_segment,
        q1_time_s AS official_best_s
    FROM {{ ref('stg_results_qualifying') }}
    WHERE
        q1_time_s IS NOT NULL
        AND (q2_time_s IS NULL OR ABS(q1_time_s - q2_time_s) >= 0.0005)
    UNION ALL
    SELECT
        race_year, race_id, driver_id, 'Q2' AS quali_segment,
        q2_time_s AS official_best_s
    FROM {{ ref('stg_results_qualifying') }}
    WHERE
        q2_time_s IS NOT NULL
        AND (q3_time_s IS NULL OR ABS(q2_time_s - q3_time_s) >= 0.0005)
    UNION ALL
    SELECT
        race_year, race_id, driver_id, 'Q3' AS quali_segment,
        q3_time_s AS official_best_s
    FROM {{ ref('stg_results_qualifying') }}
    WHERE q3_time_s IS NOT NULL
),

matched AS (
    SELECT
        o.race_year,
        o.race_id,
        o.driver_id,
        o.quali_segment,
        o.official_best_s,
        COUNT(*) AS matching_lap_n,
        COUNT(*) FILTER (
            WHERE p.quali_segment = o.quali_segment
        ) AS in_expected_segment_n
    FROM official AS o
    INNER JOIN {{ ref('int_qualifying_push_laps') }} AS p
        ON
            o.race_year = p.race_year
            AND o.race_id = p.race_id
            AND o.driver_id = p.driver_id
            AND ABS(p.lap_time_s - o.official_best_s) < 0.0005
    GROUP BY o.race_year, o.race_id, o.driver_id, o.quali_segment,
        o.official_best_s
)

SELECT
    race_year,
    race_id,
    driver_id,
    quali_segment,
    official_best_s,
    matching_lap_n,
    in_expected_segment_n
FROM matched
WHERE in_expected_segment_n = 0
