-- Safety-car hazard history: the estimate for season S must not see season S
-- or any season after it.
--
-- int_sc_hazard_history is an expanding, SEASON-LAGGED rate (02d): the row for
-- (circuit_slug, season) is estimated from races at that circuit in seasons
-- strictly before it. This test re-derives that window from the sources with an
-- INEQUALITY JOIN rather than a window frame, so a frame that silently ends at
-- CURRENT ROW instead of 1 PRECEDING -- the exact defect that opened work item
-- 08 twice -- shows up as a count mismatch rather than as a plausible number.
--
-- Three failure modes, each with its own reason string:
--   window_mismatch   the trailing totals differ from a < season recomputation,
--                     i.e. the frame admits or drops races
--   rate_mismatch     a published rate is not its own numerator/denominator
--   not_monotone      prior_racing_laps falls as season rises, which an
--                     expanding backward window cannot do
-- Gate: YES bug if any rows returned.

WITH races_in_scope AS (
    SELECT DISTINCT
        race_year,
        race_id,
        race_slug AS circuit_slug
    FROM {{ ref('stg_track_status') }}
),

onsets AS (
    SELECT
        ts.race_year,
        ts.race_id,
        COUNT(*) FILTER (WHERE ts.status_code = '4') AS n_sc_onsets,
        COUNT(*) FILTER (WHERE ts.status_code = '6') AS n_vsc_onsets
    FROM {{ ref('stg_track_status') }} AS ts
    GROUP BY ts.race_year, ts.race_id
),

exposure AS (
    SELECT
        race_year,
        race_id,
        MAX(lap_number) AS racing_laps
    FROM {{ ref('stg_laps') }}
    GROUP BY race_year, race_id
),

per_race AS (
    SELECT
        s.circuit_slug,
        s.race_year,
        s.race_id,
        COALESCE(o.n_sc_onsets, 0) AS n_sc_onsets,
        COALESCE(o.n_vsc_onsets, 0) AS n_vsc_onsets,
        e.racing_laps
    FROM races_in_scope AS s
    LEFT JOIN onsets AS o ON s.race_year = o.race_year AND s.race_id = o.race_id
    INNER JOIN exposure AS e
        ON s.race_year = e.race_year AND s.race_id = e.race_id
    WHERE e.racing_laps > 0
),

-- The window, rebuilt the slow honest way: for each published row, every race
-- at that circuit in a STRICTLY EARLIER season.
expected AS (
    SELECT
        h.circuit_slug,
        h.season,
        COUNT(p.race_id) AS prior_races_n,
        COUNT(DISTINCT p.race_year) AS prior_seasons_n,
        SUM(p.n_sc_onsets) AS prior_sc_onsets,
        SUM(p.n_vsc_onsets) AS prior_vsc_onsets,
        SUM(p.n_sc_onsets + p.n_vsc_onsets) AS prior_any_onsets,
        SUM(p.racing_laps) AS prior_racing_laps
    FROM {{ ref('int_sc_hazard_history') }} AS h
    LEFT JOIN per_race AS p
        -- `h.season > p.race_year` is the whole assertion: admit a race only if
        -- the published row's season comes strictly after it.
        ON h.circuit_slug = p.circuit_slug AND h.season > p.race_year
    GROUP BY h.circuit_slug, h.season
),

published AS (
    SELECT
        circuit_slug,
        season,
        prior_seasons_n,
        prior_races_n,
        prior_sc_onsets,
        prior_vsc_onsets,
        prior_any_onsets,
        prior_racing_laps,
        sc_hazard_per_lap,
        vsc_hazard_per_lap,
        any_hazard_per_lap,
        LAG(prior_racing_laps) OVER (
            PARTITION BY circuit_slug ORDER BY season
        ) AS prev_prior_racing_laps
    FROM {{ ref('int_sc_hazard_history') }}
),

checks AS (
    SELECT
        h.circuit_slug,
        h.season,
        h.prior_races_n,
        h.prior_racing_laps,
        e.prior_races_n AS expected_prior_races_n,
        e.prior_racing_laps AS expected_prior_racing_laps,
        CASE
            -- A row with no prior season publishes NULL; the recomputation
            -- reports 0 races / NULL sums for the same rows. Both encode "no
            -- prior exposure", so compare on COALESCE-to-zero throughout.
            WHEN
                COALESCE(h.prior_races_n, 0) != COALESCE(e.prior_races_n, 0)
                OR COALESCE(h.prior_seasons_n, 0)
                != COALESCE(e.prior_seasons_n, 0)
                OR COALESCE(h.prior_sc_onsets, 0)
                != COALESCE(e.prior_sc_onsets, 0)
                OR COALESCE(h.prior_vsc_onsets, 0)
                != COALESCE(e.prior_vsc_onsets, 0)
                OR COALESCE(h.prior_any_onsets, 0)
                != COALESCE(e.prior_any_onsets, 0)
                OR COALESCE(h.prior_racing_laps, 0)
                != COALESCE(e.prior_racing_laps, 0)
                THEN 'window_mismatch'
            WHEN
                ABS(
                    COALESCE(h.sc_hazard_per_lap, 0)
                    - COALESCE(
                        CAST(h.prior_sc_onsets AS DOUBLE)
                        / NULLIF(h.prior_racing_laps, 0), 0
                    )
                ) > 1e-12
                OR ABS(
                    COALESCE(h.vsc_hazard_per_lap, 0)
                    - COALESCE(
                        CAST(h.prior_vsc_onsets AS DOUBLE)
                        / NULLIF(h.prior_racing_laps, 0), 0
                    )
                ) > 1e-12
                OR ABS(
                    COALESCE(h.any_hazard_per_lap, 0)
                    - COALESCE(
                        CAST(h.prior_any_onsets AS DOUBLE)
                        / NULLIF(h.prior_racing_laps, 0), 0
                    )
                ) > 1e-12
                THEN 'rate_mismatch'
            WHEN
                h.prev_prior_racing_laps IS NOT NULL
                AND COALESCE(h.prior_racing_laps, 0) < h.prev_prior_racing_laps
                THEN 'not_monotone'
        END AS failure_reason
    FROM published AS h
    INNER JOIN expected AS e
        ON h.circuit_slug = e.circuit_slug AND h.season = e.season
)

SELECT *
FROM checks
WHERE failure_reason IS NOT NULL
