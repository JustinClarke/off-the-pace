-- No-future-leakage test for EW cumulative loads.
-- Re-derives the expected value at each lap using only backward-looking LAGs
-- (same formula as int_lap_thermal_proxy). If the model ever used a FOLLOWING
-- window or forward-looking data, actual != expected and rows appear here.
--
-- Note: int_lap_air_state leakage is validated by assert_stint_boundary_integrity
-- (ratio identity at lap_in_stint=1). The lap-2 max-bound check was removed because
-- dirty_air_intensity = 1/GREATEST(gap_s, 0.3) can reach 3.33, making the 0.840 bound
-- incorrect. Thermal proxy checks above are the definitive future-leakage guard.

-- surface check: re-derive using 4-lap lookback (α=0.6 → weights 0.717, 0.514, 0.369, 0.264)
SELECT
    lap_id,
    'push_surface' AS check_name,
    ROUND(
        GREATEST(push_residual, 0)
        + 0.717 * GREATEST(COALESCE(LAG(push_residual, 1) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.514 * GREATEST(COALESCE(LAG(push_residual, 2) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.369 * GREATEST(COALESCE(LAG(push_residual, 3) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.264 * GREATEST(COALESCE(LAG(push_residual, 4) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0),
    4) AS expected,
    cumulative_push_load_surface AS actual
FROM {{ ref('int_lap_thermal_proxy') }}
QUALIFY ABS(cumulative_push_load_surface-expected) > 0.0001

UNION ALL

-- bulk check: re-derive using 7-lap lookback (α=0.25 → weights decay as 0.25^k)
SELECT
    lap_id,
    'push_bulk' AS check_name,
    ROUND(
        GREATEST(push_residual, 0)
        + 0.819 * GREATEST(COALESCE(LAG(push_residual, 1) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.670 * GREATEST(COALESCE(LAG(push_residual, 2) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.549 * GREATEST(COALESCE(LAG(push_residual, 3) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.449 * GREATEST(COALESCE(LAG(push_residual, 4) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.368 * GREATEST(COALESCE(LAG(push_residual, 5) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.301 * GREATEST(COALESCE(LAG(push_residual, 6) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.247 * GREATEST(COALESCE(LAG(push_residual, 7) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0),
    4) AS expected,
    cumulative_push_load_bulk AS actual
FROM {{ ref('int_lap_thermal_proxy') }}
QUALIFY ABS(cumulative_push_load_bulk-expected) > 0.0001
