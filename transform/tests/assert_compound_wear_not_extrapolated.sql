{{ config(tags=['intermediate'], severity='error') }}
-- CO-15 (ruling CD9). The linear wear term must not grow past
-- onset + compound_wear_hold_after_onset_laps (macros/compound_cliff_wear.sql,
-- NO AGE EXTRAPOLATION). Fails on any valid lap whose wear exceeds the held
-- value of its cell, i.e. on any return of the unbounded-in-age curve that put
-- 2024_8's field base at 0.905 x the race's fastest lap.
--
-- held_wear_s is the curve's maximum over its held range: the linear term at
-- age onset + hold (floored at 0, so the bound stays an upper bound if a cell
-- ever fits a negative gradient; every seed gradient is positive today) plus
-- the full plateau, under the shared cap. int_compound_cliff_predicted holds
-- valid laps only. A lap with no cell (NULL onset) has no held value and is
-- not judged here.
WITH held AS (
    SELECT
        lap_id,
        race_id,
        age_in_stint,
        compound_cliff_onset_laps,
        compound_wear_s,
        LEAST(
            GREATEST(
                COALESCE(compound_wear_gradient, 0.0)
                * (compound_cliff_onset_laps
                   + {{ var('compound_wear_hold_after_onset_laps') }}),
                0.0)
            + GREATEST(COALESCE(compound_cliff_severity, 0.0), 0.0),
            {{ var('compound_wear_max_s_per_lap', 10.0) }}
        ) AS held_wear_s
    FROM {{ ref('int_compound_cliff_predicted') }}
    WHERE compound_wear_s IS NOT NULL
      AND compound_cliff_onset_laps IS NOT NULL
)

SELECT *
FROM held
WHERE compound_wear_s > held_wear_s + 1e-9
