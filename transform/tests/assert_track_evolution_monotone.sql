-- Track evolution's rubber-in slope must stay physically plausible, not merely pass a
-- test purchased by clamping the sign away.
--
-- F34: the old body checked lap-over-lap monotonicity of `rubber_component_s`, the
-- PUBLISHED column -- built in int_track_evolution.sql's `race_slope` CTE as
-- `LEAST(raw_ols_slope, 0.0)`, i.e. floored at zero by construction. A column built
-- from a slope that can never be positive is trivially non-increasing in lap_number;
-- the old test could not fail no matter what the underlying OLS fit produced.
--
-- This re-derives the PRE-CLAMP raw_slope independently -- the same OLS formula the
-- model uses (COV(lap_number, field_pace_smoothed_s) / VAR(lap_number), grouped by
-- race, on the model's own eligible panel: WHERE NOT low_sample_flag) -- and bounds it
-- on both sides rather than asserting a strict sign.
--
-- A strict "raw_slope <= 0" cannot be the enforced condition: measured on the
-- 2026-09-25 dev build, 106 of 171 races (62%) have a POSITIVE raw slope. This in-SQL
-- linear approximation is documented, in int_track_evolution.sql's own header, to
-- capture "~80% of the rubber effect" -- a whole-race straight-line trend is not
-- guaranteed monotone once tyre degradation, fuel-burn timing and neutralised-lap
-- noise are all folded into one slope. Failing on noise this common would make the
-- gate meaningless, not stricter.
--
-- What IS a real, checkable invariant: the trend must stay within a physically
-- plausible range. Measured range today: -0.337 to +0.142 s/lap. 0.5 s/lap is well
-- outside that range in both directions, but tight enough to catch a genuine blowup
-- (a broken join, a unit error, a sign flip upstream) rather than routine per-race
-- regression noise.
{{ config(tags=['track_evolution']) }}

WITH pace AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        field_pace_smoothed_s
    FROM {{ ref('int_field_pace_curve') }}
    WHERE NOT low_sample_flag
),

race_means AS (
    SELECT
        race_year,
        race_id,
        AVG(lap_number) AS mean_lap,
        AVG(field_pace_smoothed_s) AS mean_pace
    FROM pace
    GROUP BY race_year, race_id
),

race_slope AS (
    SELECT
        p.race_year,
        p.race_id,
        SUM(
            (p.lap_number - rm.mean_lap) * (p.field_pace_smoothed_s - rm.mean_pace)
        ) / NULLIF(SUM(POWER(p.lap_number - rm.mean_lap, 2)), 0) AS raw_slope_s_per_lap
    FROM pace AS p
    INNER JOIN race_means AS rm
        ON p.race_year = rm.race_year AND p.race_id = rm.race_id
    GROUP BY p.race_year, p.race_id
)

SELECT
    race_year,
    race_id,
    raw_slope_s_per_lap
FROM race_slope
WHERE ABS(raw_slope_s_per_lap) > 0.5
