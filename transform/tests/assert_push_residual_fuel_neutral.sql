-- T37 (F47, WI-15b). push_residual is measured on fuel-corrected lap time, and
-- the EW window still runs over every lap of the stint.
--
-- Before F47, int_lap_thermal_proxy took its baseline and residual from raw
-- stg_laps.lap_time_s. Fuel burn-off alone makes each lap faster than the
-- stint's earlier ones, so burn-off read as pushing: 67.6% of training-eligible
-- laps past lap_in_stint 20 were coded "pushing" on raw time, 32.5%
-- fuel-corrected. push_residual and the two loads built on it are contract
-- features in all five model families.
--
-- assert_no_future_leakage re-derives the baseline from the model's OWN
-- weight_corrected_lap_time column, so on its own it would follow a revert to
-- raw time without noticing. This test pins that column to its source.
--   1. corrected_time: on every lap int_lap_fuel_state covers (the valid laps),
--      the model's weight_corrected_lap_time equals int_lap_fuel_state's.
--      Fails on every lap if raw time is put back under the corrected name.
--   2. missing_lap: every int_stint_geometry lap has a thermal row. The first
--      F47 build used int_lap_fuel_state (valid laps only) as the lap SOURCE,
--      which dropped the 28,378 invalid laps and closed the gaps the LAG window
--      keeps open across SC periods and stops (it moved the bulk load on 7,890
--      of 137,759 training-eligible rows). That build fails this check on all
--      28,378.
--   3. uncorrected_valid_lap: no valid lap is left without a corrected time.
--      The fuel join is a LEFT join, so a race missing from int_lap_fuel_state
--      (a seed gap) would otherwise NULL its thermal features silently.
{{ config(severity='error') }}

SELECT
    t.lap_id,
    'corrected_time' AS check_name,
    f.weight_corrected_lap_time AS expected,
    t.weight_corrected_lap_time AS actual
FROM {{ ref('int_lap_thermal_proxy') }} AS t
INNER JOIN {{ ref('int_lap_fuel_state') }} AS f ON t.lap_id = f.lap_id
WHERE
    t.weight_corrected_lap_time IS NULL
    OR ABS(t.weight_corrected_lap_time - f.weight_corrected_lap_time) > 1e-9

UNION ALL

SELECT
    g.lap_id,
    'missing_lap' AS check_name,
    NULL AS expected,
    NULL AS actual
FROM {{ ref('int_stint_geometry') }} AS g
LEFT JOIN {{ ref('int_lap_thermal_proxy') }} AS t ON g.lap_id = t.lap_id
WHERE t.lap_id IS NULL

UNION ALL

SELECT
    t.lap_id,
    'uncorrected_valid_lap' AS check_name,
    NULL AS expected,
    NULL AS actual
FROM {{ ref('int_lap_thermal_proxy') }} AS t
INNER JOIN {{ ref('int_stint_geometry') }} AS g ON t.lap_id = g.lap_id
WHERE
    g.is_valid_lap
    AND t.weight_corrected_lap_time IS NULL
