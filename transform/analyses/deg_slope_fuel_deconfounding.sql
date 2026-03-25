-- Transform v0.2 Fix 1.4: fuel deconfounding check for constructor deg slopes.
--
-- Question: is the within-stint age slope in int_constructor_deg_sensitivity a
-- tyre-degradation signal, or a residual fuel-burn artifact that survived
-- int_lap_fuel_state's weight correction?
--
-- Identification: within a stint, tyre age and fuel load are collinear (both move
-- one step per lap), so the check demeans within (race, driver) instead across
-- stints the collinearity breaks because the same tyre age recurs at different
-- fuel loads (stint 1 age 5 = heavy fuel, stint 3 age 5 = light fuel). On that
-- variation we fit the bivariate OLS  resid ~ age + fuel_mass_kg  and compare the
-- age coefficient with and without the fuel control.
--
-- VERDICT (2026-06-11, 2024 season, clean dry pre-cliff laps):
-- The slope is NOT a fuel artifact. Pooled age slope moves from -0.0845 to
-- -0.0749 s/lap on HARD (-11%), -0.0842 to -0.0706 on MEDIUM (-16%), -0.0681 to
-- -0.0614 on SOFT (-10%) when fuel is controlled it attenuates slightly, it
-- does not collapse. The residual fuel coefficient is small and positive
-- (~+0.005 s/kg), confirming a modest common under-correction in the fuel
-- component; because it is common across constructors it is cancelled by the
-- field-centring in int_constructor_deg_sensitivity. Per-constructor HARD slopes
-- keep their ordering and ~0.05 s/lap spread under fuel control (Ferrari/McLaren
-- remain the most tyre-gentle, Red Bull/Aston Martin the harshest); mid-field
-- deviations of ±0.01 s/lap scale are sensitive to the conditioning and should
-- not be over-read. Fix 1.3 may proceed.

WITH clean AS (
    SELECT
        race_id,
        driver_id,
        constructor_id,
        compound,
        CAST(age_in_stint AS DOUBLE)    AS age,
        driver_skill_residual_s         AS resid,
        fuel_mass_kg
    FROM {{ ref('int_lap_residual_decomposed') }}
    WHERE correction_weight = 1.0
      AND COALESCE(rainfall_flag, FALSE) = FALSE
      AND compound IN ('SOFT', 'MEDIUM', 'HARD')
      AND lap_in_stint > 1
      AND COALESCE(cliff_onset_passed, FALSE) = FALSE
      AND driver_skill_residual_s IS NOT NULL
      AND age_in_stint IS NOT NULL
      AND fuel_mass_kg IS NOT NULL
),

demeaned AS (
    SELECT
        constructor_id,
        compound,
        age          - AVG(age)          OVER (PARTITION BY race_id, driver_id) AS dx,
        resid        - AVG(resid)        OVER (PARTITION BY race_id, driver_id) AS dy,
        fuel_mass_kg - AVG(fuel_mass_kg) OVER (PARTITION BY race_id, driver_id) AS df
    FROM clean
),

sums AS (
    SELECT
        compound,
        COUNT(*)        AS n,
        SUM(dx * dx)    AS sxx,
        SUM(df * df)    AS sff,
        SUM(dx * df)    AS sxf,
        SUM(dx * dy)    AS sxy,
        SUM(df * dy)    AS sfy
    FROM demeaned
    GROUP BY compound
)

SELECT
    compound,
    n,
    sxy / sxx                                               AS b_age_univariate,
    (sxy * sff - sfy * sxf) / (sxx * sff - sxf * sxf)       AS b_age_fuel_controlled,
    (sfy * sxx - sxy * sxf) / (sxx * sff - sxf * sxf)       AS b_fuel_s_per_kg,
    sxf / SQRT(sxx * sff)                                   AS corr_age_fuel,
    1.0 - (sxy * sff - sfy * sxf) / (sxx * sff - sxf * sxf) / (sxy / sxx)
                                                            AS age_slope_attenuation
FROM sums
ORDER BY compound
