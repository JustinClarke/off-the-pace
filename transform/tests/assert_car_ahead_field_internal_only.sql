-- AX-24 / D2: no published number may read FastF1's DriverAhead or
-- DistanceToDriverAhead. Returns one row per model that reads the field and is
-- not on the internal list. Zero rows passes.
--
-- What this checks: the SQL text of every dbt model (comments stripped) for the
-- raw field and for the staging aliases that carry it (driverahead,
-- distancetodriverahead, driver_ahead_number, distance_to_ahead_m,
-- ff_driver_ahead, ff_ahead_identity_agreement). Only the three internal
-- readers may match. Any mart, or any other model, that starts reading the
-- field fails here.
--   stg_telemetry_position  carries the field as a staging column, unpublished
--   int_lap_air_state       held reader (D2): filter for held outputs until it
--                           is rebuilt on int_lap_proximity crossings
--   int_lap_proximity       reads only the diagnostic agreement score
-- What it does NOT check: transitive dependence. Marts that read
-- int_lap_air_state (fct_cliff_prediction_features, mart_race_coverage and the
-- dirty-air chain) still inherit the held reader until the rebuild (AX-24
-- open part). Python models are not scanned.
{% set tokens = [
    'driverahead', 'distancetodriverahead', 'driver_ahead_number',
    'distance_to_ahead_m', 'ff_driver_ahead', 'ff_ahead_identity_agreement'
] %}
{% set internal = [
    'stg_telemetry_position', 'int_lap_air_state', 'int_lap_proximity'
] %}
{% set hits = [] %}
{% if execute %}
  {% for node in graph.nodes.values() %}
    {% if node.resource_type == 'model' and node.language == 'sql' and node.name not in internal %}
      {% set code = modules.re.sub('--[^\n]*', '', node.raw_code | lower) %}
      {% for t in tokens %}
        {% if t in code and [node.name, t] not in hits %}
          {% do hits.append([node.name, t]) %}
        {% endif %}
      {% endfor %}
    {% endif %}
  {% endfor %}
{% endif %}

SELECT
    CAST(model_name AS VARCHAR) AS model_name,
    CAST(token AS VARCHAR) AS token
FROM (
    SELECT NULL AS model_name, NULL AS token WHERE FALSE
    {% for h in hits %}
    UNION ALL SELECT '{{ h[0] }}', '{{ h[1] }}'
    {% endfor %}
) AS offenders
