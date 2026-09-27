-- T16 (F22, WI-01). For laps with an evolution row: if
-- base_track_pace_s = race_mean + rubber_component_s + ambient_component_s
-- + unexplained_residual_s within 1e-6 (i.e. rubber/ambient are already
-- inside the base, which is true by construction -- int_track_evolution is
-- an OLS decomposition of int_field_pace_curve's own base), then
-- driver_skill_residual_s must NOT be reachable by additionally subtracting
-- rubber_component_s or ambient_component_s from pace_delta_s: it must equal
-- pace_delta_s minus fuel/compound/constructor/dirty-air only.
--
-- race_mean is AVG(track_state_index_s) from int_track_evolution itself, the
-- mean its rubber/ambient fit is centred on (it drops low-sample laps). An
-- earlier version averaged int_field_pace_curve over every lap, low-sample
-- ones included, so the premise held on only 22.8% of rows and the test
-- silently skipped the rest. With the right mean it holds on 100% (max gap
-- 2.8e-14, 149,375 laps on the 2026-09-27 build), and a row where it stops
-- holding now FAILS ('premise broken') instead of being skipped, so the test
-- cannot go vacuous again without saying so.
--
-- Mirrors verify_findings.py's F22 check as a build-time gate.
{{ config(severity='error') }}

WITH race_mean AS (
    SELECT
        race_year,
        race_id,
        AVG(track_state_index_s) AS mean_base_s
    FROM {{ ref('int_track_evolution') }}
    GROUP BY race_year, race_id
),

checked AS (
    SELECT
        r.lap_id,
        r.base_track_pace_s,
        rm.mean_base_s,
        e.rubber_component_s,
        e.ambient_component_s,
        e.unexplained_residual_s,
        r.pace_delta_s,
        r.driver_skill_residual_s,
        r.fuel_component_s,
        r.compound_component_s,
        r.constructor_component_s,
        r.dirty_air_tax_s,
        ABS(
            r.base_track_pace_s
            - (rm.mean_base_s + e.rubber_component_s + e.ambient_component_s + e.unexplained_residual_s)
        ) AS base_identity_gap
    FROM {{ ref('int_lap_residual_decomposed') }} AS r
    INNER JOIN {{ ref('int_track_evolution') }} AS e
        ON
            r.race_year = e.race_year
            AND r.race_id = e.race_id
            AND r.lap_number = e.lap_number
    INNER JOIN race_mean AS rm
        ON r.race_year = rm.race_year AND r.race_id = rm.race_id
    WHERE r.pace_delta_s IS NOT NULL
)

SELECT
    *,
    'rubber/ambient subtracted again on top of a base that contains them' AS failure
FROM checked
WHERE base_identity_gap < 1e-6
  AND ABS(
      driver_skill_residual_s
      - (pace_delta_s - fuel_component_s - compound_component_s - constructor_component_s - dirty_air_tax_s)
  ) > 1e-6

UNION ALL

SELECT
    *,
    'premise broken: base no longer = race mean + rubber + ambient + unexplained; re-derive this test' AS failure
FROM checked
WHERE base_identity_gap >= 1e-6
