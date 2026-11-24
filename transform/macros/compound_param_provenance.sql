{#
  compound_param_provenance: one definition of how the three per-parameter source tags
  (onset / gradient / severity, vocabulary in fit_compound_cliff.py PARAM_SOURCES) collapse
  into the cell-level is_measured flag and provenance_class label. Used by
  dim_compounds_season and by tests/assert_compound_provenance_semantics.sql.

  is_measured is TRUE only when all three are 'fitted' (own-history fit). A NULL tag
  yields FALSE, never TRUE.
#}
{% macro compound_is_measured(onset_source, gradient_source, severity_source) -%}
COALESCE(
    {{ onset_source }} = 'fitted' AND {{ gradient_source }} = 'fitted' AND {{ severity_source }} = 'fitted',
    FALSE
)
{%- endmacro %}

{% macro compound_provenance_class(onset_source, gradient_source, severity_source) -%}
CASE
    WHEN {{ onset_source }} = 'fitted' AND {{ gradient_source }} = 'fitted' AND {{ severity_source }} = 'fitted'
        THEN 'own_history_fitted'
    WHEN {{ onset_source }} = {{ gradient_source }} AND {{ gradient_source }} = {{ severity_source }}
        THEN CAST({{ onset_source }} AS VARCHAR)
    ELSE 'mixed'
END
{%- endmacro %}
