{% macro posterior_variance(n_col, observation_variance_expr, prior_variance_expr) %}
  {#-
  Computes posterior variance from normal-normal conjugate model.

  Given:
    observation variance: σ² (e.g., from a fitted model's residual variance)
    prior variance: σ₀²
    sample size: n

  The posterior variance (precision-weighted average) is:
    posterior_var = 1 / (n / σ² + 1 / σ₀²)

  This is the inverse of the sum of precisions. Returns NULL if either variance is NULL or ≤0.

  Args:
    n_col:                    column name or expression for sample size (e.g., 'panel_observations_n')
    observation_variance_expr: expression for observation variance σ² (e.g., '0.0001' for small noise)
    prior_variance_expr:      expression for prior variance σ₀² (e.g., a column or constant)

  Returns: scalar expression composable in SELECT lists (posterior variance, ≥0).

  Usage:
    SELECT
      driver_id,
      shrunken_estimate,
      SQRT({{ posterior_variance('sample_count', '0.0001', 'prior_var') }}) as posterior_se
    FROM panel_data
  -#}

  CASE
    WHEN ({{ n_col }} IS NULL OR {{ n_col }} <= 0)
      OR ({{ observation_variance_expr }} IS NULL OR {{ observation_variance_expr }} <= 0)
      OR ({{ prior_variance_expr }} IS NULL OR {{ prior_variance_expr }} <= 0)
    THEN NULL
    ELSE 1 / ({{ n_col }} / {{ observation_variance_expr }} + 1 / {{ prior_variance_expr }})
  END
{% endmacro %}
