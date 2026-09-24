{#
  fuel_regulatory_max_kg -- the FIA race-fuel limit (kg) in force for a season.
  WI-05 (F32, F52).

  Reads var('fuel_regulatory_max_kg_by_season'), a map {first_season: kg}. Each
  limit applies from its key until the next key, so the macro emits the keys
  newest-first:

      CASE WHEN season >= 2019 THEN 110.0 WHEN season >= 2018 THEN 105.0 END

  A season older than every key gets NULL, deliberately: a fuel load with no
  regulation behind it is unknown, and the fuel test fails on it rather than the
  model inventing one.
#}
{% macro fuel_regulatory_max_kg(season_column) -%}
{%- set limits = var('fuel_regulatory_max_kg_by_season') -%}
CASE
{%- for first_season in limits | list | sort | reverse %}
    WHEN {{ season_column }} >= {{ first_season }} THEN CAST({{ limits[first_season] }} AS DOUBLE)
{%- endfor %}
END
{%- endmacro %}
