-- Results-anchored guard: the best (lowest) era_adjusted_rating
-- driver-season must rest on a full season of racing, not a small-sample
-- artifact. The old asymmetric P20-minus-teammate-median signal put weak-car,
-- weak-teammate driver-seasons (e.g. Mick Schumacher 2021) at the all-time #1
-- spot; the symmetric field signal must not. Fails if the all-time #1 rated
-- season has fewer than 10 races — a cheap tripwire against any regression back
-- to a small-sample-favouring statistic.
--
-- Inert on the CI fixture warehouse (3 races spread one-per-season, so every
-- driver-season caps at n_races = 1): the gate only fires once the dataset
-- contains at least one driver-season that could plausibly clear the 10-race
-- bar in the first place, same "can't fail on data too thin to test"
-- principle as the baseline-snapshot regression gates above.
WITH ranked AS (
    SELECT
        driver_id,
        season,
        n_races,
        era_adjusted_rating,
        ROW_NUMBER() OVER (ORDER BY era_adjusted_rating ASC) AS rn
    FROM {{ ref('int_era_normalized_driver_rating') }}
    WHERE era_adjusted_rating IS NOT NULL
),

max_coverage AS (
    SELECT MAX(n_races) AS max_n_races FROM ranked
)

SELECT
    r.driver_id,
    r.season,
    r.n_races,
    r.era_adjusted_rating
FROM ranked AS r
CROSS JOIN max_coverage AS mc
WHERE r.rn = 1
  AND r.n_races < 10
  AND mc.max_n_races >= 10
