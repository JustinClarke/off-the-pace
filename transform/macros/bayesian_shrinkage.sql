{% macro bayesian_shrinkage(n_col, observed_col, prior_mean_expr, prior_weight) %}
  {#-
  Computes Bayesian shrinkage estimate from observed data and prior.

  Normal-normal conjugate model:
    posterior_mean = (n × observed + prior_weight × prior_mean) / (n + prior_weight)

  Args:
    n_col:            column name or expression for sample size (e.g., 'panel_observations_n')
    observed_col:     column name or expression for observed mean (e.g., 'observed_coefficient')
    prior_mean_expr:  expression for prior mean (e.g., '0' for a zero-centered prior, or a column ref)
    prior_weight:     numeric or expression for prior strength (e.g., '10' means 10 equivalent samples)

  Returns: scalar expression composable in SELECT lists.

  Tolerates n=0 by returning NULL (via NULLIF), which is the correct behaviour for unobserved cells.

  Usage:
    SELECT
      driver_id,
      {{ bayesian_shrinkage('sample_count', 'observed_skill', '0', '5') }} as shrunken_skill
    FROM panel_data
  -#}

  (
    ({{ n_col }} * {{ observed_col }} + {{ prior_weight }} * {{ prior_mean_expr }})
    / NULLIF({{ n_col }} + {{ prior_weight }}, 0)
  )
{% endmacro %}
