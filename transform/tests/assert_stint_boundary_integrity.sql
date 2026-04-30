-- Stint boundary integrity test.
-- At lap_in_stint = 1 the EW windows partition by stint_id, so no prior-stint data bleeds in.
-- Three checks across three models:

-- 1. Thermal proxy: cumulative_push_load_surface = GREATEST(push_residual,0) exactly at lap 1.
SELECT
    'thermal_surface' AS check_name,
    lap_id,
    lap_in_stint,
    cumulative_push_load_surface AS actual,
    GREATEST(push_residual, 0)    AS expected
FROM {{ ref('int_lap_thermal_proxy') }}
WHERE lap_in_stint = 1
  AND ABS(cumulative_push_load_surface-GREATEST(push_residual, 0)) > 0.0001

UNION ALL

-- 2. Thermal proxy: cumulative_push_load_bulk = GREATEST(push_residual,0) exactly at lap 1.
SELECT
    'thermal_bulk' AS check_name,
    lap_id,
    lap_in_stint,
    cumulative_push_load_bulk     AS actual,
    GREATEST(push_residual, 0)    AS expected
FROM {{ ref('int_lap_thermal_proxy') }}
WHERE lap_in_stint = 1
  AND ABS(cumulative_push_load_bulk-GREATEST(push_residual, 0)) > 0.0001

UNION ALL

-- 3 & 4. Air state: at lap_in_stint=1 there must be no prior-stint LAG contributions.
-- When clean (no bleed), surface_load = 0.600 * intensity and bulk_load = 0.250 * intensity,
-- so surface/0.600 == bulk/0.250 == intensity. Any bleed-in breaks this identity.
-- dirty_air_intensity = 1.0/GREATEST(gap_s, 0.3) so max is ~3.33; bounds 0.6 & 0.25 were
-- wrong assumptions. Instead we verify the two-load ratio is consistent (same intensity).
SELECT
    'air_lap1_load_ratio_mismatch' AS check_name,
    lap_id,
    lap_in_stint,
    dirty_air_thermal_load_surface AS actual,
    ROUND(dirty_air_thermal_load_bulk * (0.600 / 0.2500), 4) AS expected
FROM {{ ref('int_lap_air_state') }}
WHERE lap_in_stint = 1
  AND (dirty_air_thermal_load_surface > 0.0001 OR dirty_air_thermal_load_bulk > 0.0001)
  AND ABS(dirty_air_thermal_load_surface-ROUND(dirty_air_thermal_load_bulk * (0.600 / 0.2500), 4)) > 0.001

UNION ALL

-- 5. Fuel state: fuel_mass_kg must be monotonically non-increasing over lap_number
--    within each (race_year, race_id, driver_id). A jump upward indicates a lap-
--    numbering bug where laps were re-ordered or assigned to the wrong stint.
SELECT
    'fuel_monotone' AS check_name,
    lap_id,
    lap_number      AS lap_in_stint,
    fuel_mass_kg    AS actual,
    LAG(fuel_mass_kg) OVER (
        PARTITION BY race_year, race_id, driver_id
        ORDER BY lap_number
    )               AS expected_max
FROM {{ ref('int_lap_fuel_state') }}
QUALIFY fuel_mass_kg > LAG(fuel_mass_kg) OVER (
    PARTITION BY race_year, race_id, driver_id
    ORDER BY lap_number
) + 0.0001
