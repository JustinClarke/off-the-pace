-- WI-13 (T29's data half for survival_weight). A lap with no prior-season survival
-- cell carries survival_weight = 1.0 (unweighted), as fct_cliff_prediction_features
-- documents: the first ingested season (no earlier season to lag from), a lap with
-- no compound (nothing to join on), and a (compound, lap_in_stint) no earlier
-- season reached (a compound new to the data, or a stint longer than any before it).
--
-- The weight is 1 / survival_prob clipped to [0.25, 4], COALESCEd to 1.0. The clip
-- used to be GREATEST(0.25, LEAST(4.0, ...)), and DuckDB's LEAST skips a NULL
-- argument, so every one of these rows came out at 4.0 -- the MAXIMUM weight --
-- and the COALESCE never fired: 24,800 rows on the 2026-09-24 dev build (all
-- 17,367 known-compound 2018 rows, the 4,088 unknown-compound rows, and 3,345
-- later-season rows with no prior cell), 18,878 of them training-eligible.
-- Every value is inside [0.25, 4], so no range test could see it.
--
-- The "no prior cell" population is re-derived here from int_lap_residual_decomposed
-- (the model's own source) rather than read off the model's CTEs: a cell exists for
-- a row when some EARLIER season has a lap of the same compound at the same
-- lap_in_stint.

WITH first_season_reached AS (
    SELECT
        compound,
        lap_in_stint,
        MIN(race_year) AS first_race_year
    FROM {{ ref('int_lap_residual_decomposed') }}
    WHERE compound IS NOT NULL
    GROUP BY compound, lap_in_stint
)

SELECT
    f.lap_id,
    f.race_year,
    f.compound,
    f.lap_in_stint,
    f.is_training_eligible,
    f.survival_weight
FROM {{ ref('fct_cliff_prediction_features') }} AS f
LEFT JOIN first_season_reached AS fs
    ON
        f.compound = fs.compound
        AND f.lap_in_stint = fs.lap_in_stint
WHERE
    (
        f.compound IS NULL
        OR fs.first_race_year IS NULL
        OR fs.first_race_year >= f.race_year
    )
    AND (f.survival_weight IS NULL OR f.survival_weight <> 1.0)
