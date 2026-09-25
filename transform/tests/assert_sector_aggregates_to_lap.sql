-- T26 (F34). Real implementation, replacing a vacuous (unconditionally empty-result)
-- placeholder body whose own header derived this exact math and then never ran it.
--
-- The header's worked example distinguishes two identities, and only one of them holds:
--   * SUMing the sector RESIDUALS does NOT equal the lap residual. sector_pace_delta_s
--     (sector-median baseline) and the lap's pace_delta_s (trimmed-mean baseline) are
--     built from different smoothing, so the median-of-a-sum vs. sum-of-medians gap
--     leaks into the residual. Confirmed empirically: on the 2026-09-25 dev build the
--     residual sum is off by up to 64.7s -- this is real and expected, not a bug.
--   * SUMing the sector-grain EXPLAINED PHYSICS COMPONENTS (fuel, compound, rubber,
--     ambient, constructor, dirty-air) DOES equal the lap-grain component, because
--     int_sector_residual_decomposed.sql's `allocated` CTE builds each one as
--     lap_component * (sector_time_s / lap_time_s), and the three shares sum to 1.
--     This is the identity actually tested here.
--
-- One term does NOT close as cleanly as the other five, and it is a real finding, not
-- this test's own slack: sector_dirty_air_tax_s is gated on `dirty_air_share_lap > 0`
-- (the CURRENT lap's share), but the lap-grain dirty_air_tax_s it is meant to
-- re-distribute is priced from `dirty_air_share_lag1` (the PREVIOUS lap's share --
-- int_dirty_air_tax_component.sql's whole causal-identification argument). On a lap
-- where those two differ (this lap clean, last lap dirty, or vice versa), the sector
-- allocation and the lap total disagree. Measured on the 2026-09-25 dev build: 11,892
-- of 161,040 three-sector laps (7.4%), max discrepancy 0.161s -- isolated by checking
-- each of the six terms independently; the other five close to float precision
-- (< 2e-15) on every one of the same laps. This is a latent int_sector_residual_
-- decomposed.sql defect (new finding, not yet numbered/triaged), out of scope for a
-- guard-repair item to fix -- hence WARN, not error, so this test can be wired in
-- truthfully today without a build-breaking side effect that WI-07 did not set out
-- to cause. Fixing it means re-deriving dirty_air_share_lag1 (or an equivalent lag)
-- at the sector grain rather than reusing the lap's own current-lap air state.
--
-- Tolerance: 0.001s (3-sector float accumulation), matching assert_sector_residual_identity.sql.
{{ config(severity='warn', tags=['sector_grain']) }}

WITH sector_totals AS (
    SELECT
        lap_id,
        COUNT(*) AS n_sectors,
        SUM(
            sector_fuel_component_s + sector_compound_component_s + sector_rubber_component_s
            + sector_ambient_component_s + sector_constructor_component_s + sector_dirty_air_tax_s
        ) AS sector_explained_sum_s
    FROM {{ ref('int_sector_residual_decomposed') }}
    GROUP BY lap_id
),

lap_totals AS (
    SELECT
        lap_id,
        fuel_component_s + COALESCE(compound_component_s, 0.0) + rubber_component_s
        + ambient_component_s + constructor_component_s + dirty_air_tax_s AS lap_explained_s
    FROM {{ ref('int_lap_residual_decomposed') }}
)

SELECT
    s.lap_id,
    s.n_sectors,
    s.sector_explained_sum_s,
    l.lap_explained_s,
    ABS(s.sector_explained_sum_s - l.lap_explained_s) AS discrepancy
FROM sector_totals AS s
INNER JOIN lap_totals AS l ON s.lap_id = l.lap_id
-- Only laps with all 3 sectors present can be expected to reach the lap total; a lap
-- missing a sector (no field baseline for it) is a partial sum by construction, not
-- a broken identity.
WHERE
    s.n_sectors = 3
    AND ABS(s.sector_explained_sum_s - l.lap_explained_s) > 0.001
