-- The two window orderings int_lap_proximity depends on must be TOTAL orders.
--
-- This is a reproducibility gate, and it exists because the model shipped
-- without it and was wrong. `LAG`/`LEAD` over a non-total order pick an
-- arbitrary row inside a tied block, and the choice moves with DuckDB's scan
-- parallelism -- so two builds of byte-identical SQL produce different gaps.
-- It is invisible to every other test in the suite: row counts, null rates,
-- ranges and the blue-flag agreement all survive it, because the values stay
-- individually plausible and only the ASSIGNMENT of neighbours moves.
--
-- How it was actually found: this phase's p50 ablation arm scored 1.017496
-- against one build of the mart and 1.021648 against the next, with no code
-- change in between -- a 0.28x-of-noise-floor swing from a rebuild. The
-- baseline arm was bit-identical across the same pair, which localised it to
-- the nine proximity columns. 223,602 of 15,821,726 crossings (1.39%) tie on
-- (race_id, track_bin, crossing_time_s).
--
-- stg_telemetry carries the same lesson one layer down (982,303 car-channel
-- samples tied on distance_m, "two builds of this identical SQL disagreed on
-- ~500 laps"). That note was in the repo the whole time; the fix here is the
-- same shape, and this test is what stg_telemetry never got.
--
-- There were TWO of them, and the second only surfaced after the first was
-- fixed: `wd`, which measures how long a driver spent in a bin, ties AT THE
-- LAP ROLLOVER, because FastF1 gives the lap-transition sample to both laps
-- and so bin 99 of lap N and bin 0 of lap N+1 carry the same crossing time
-- (76 pairs across 149 races). Unordered, LEAD could hand a bin a whole lap
-- of duration. That one moved `time_within_1s` by up to 2.841 s -- 5.06%
-- relative -- while `share_lap_within_1s`, computed over the same bin SET,
-- did not move at all: the set was stable and only the weights were not,
-- which is why a row-count or share-based check could never have caught it.
--
-- Two orderings, both asserted with the tie-breaks the model actually uses:
--   w  = (race_id, track_bin) ORDER BY crossing_time_s, driver_id
--   wd = (race_id, driver_id) ORDER BY crossing_time_s, lap_number, track_bin
WITH crossings AS (
    SELECT
        race_id,
        driver_id,
        lap_number,
        CAST(FLOOR(relative_distance * 100) AS INTEGER) AS track_bin,
        MIN(session_time_s) AS crossing_time_s
    FROM {{ ref('stg_telemetry_position') }}
    GROUP BY 1, 2, 3, 4
),

-- w: adding driver_id must make the key unique. A duplicate here would mean a
-- driver crossing one bin twice at the same instant.
neighbour_order AS (
    SELECT
        'neighbour_window' AS which,
        race_id,
        CAST(track_bin AS VARCHAR) AS part,
        crossing_time_s,
        COUNT(*) AS n
    FROM crossings
    GROUP BY 1, 2, 3, 4, driver_id
    HAVING COUNT(*) > 1
),

-- wd: crossing_time_s alone is NOT unique per driver per race (the lap
-- rollover, above), so the ordering must carry lap_number and track_bin. With
-- them the key contains the full crossings grain and is total by construction
-- -- which is the point: this arm fails the moment someone shortens that
-- ORDER BY back to what it obviously "should" be.
duration_order AS (
    SELECT
        'duration_window' AS which,
        race_id,
        driver_id AS part,
        crossing_time_s,
        COUNT(*) AS n
    FROM crossings
    GROUP BY 1, 2, 3, 4, lap_number, track_bin
    HAVING COUNT(*) > 1
)

SELECT * FROM neighbour_order
UNION ALL
SELECT * FROM duration_order
