{#
  driver_isolation_pure_season_offset(year_col)

  The declared season-level offset added to pure skill (W33, 2026-09-30), as a SQL
  expression in seconds per lap, positive = the season's pure is raised. It reads the
  map var('isolation_pure_season_offset_gain_s') {season: offset}; a season not in the
  map gets 0.0. See that var in dbt_project.yml for why the offset exists and how the
  value was measured.

  It is a per-season constant, so it cancels in every within-season difference: pair
  gaps (pure_gap_gain_s), the tier-3 identity, and any ranking inside one season are
  unchanged. It moves only a season's level against the other seasons.

  Used by int_driver_isolation_lap_values (where pure_skill_gain_s is derived) and
  fct_driver_isolation_race (which exposes it), so the two cannot drift apart.
#}
{% macro driver_isolation_pure_season_offset(year_col) -%}
    {%- set offsets = var('isolation_pure_season_offset_gain_s', {}) -%}
    {%- if offsets | length == 0 -%}
        CAST(0.0 AS DOUBLE)
    {%- else -%}
        CAST(CASE {{ year_col }}
            {%- for season, offset in offsets.items() %}
            WHEN {{ season | int }} THEN {{ offset | float }}
            {%- endfor %}
            ELSE 0.0
        END AS DOUBLE)
    {%- endif -%}
{%- endmacro %}
