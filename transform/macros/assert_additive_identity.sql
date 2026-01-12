{% macro assert_additive_identity(model_ref, total_col, component_cols, residual_col, tolerance=0.0001) %}
  {#-
  Validates that an additive identity holds: total = sum(components) + residual ± tolerance

  Args:
    model_ref:       ref() to the model to validate
    total_col:       name of the total column (e.g., 'pace_delta_s')
    component_cols:  list of component column names (e.g., ['fuel_component_s', 'compound_component_s', ...])
    residual_col:    name of the residual closure column (e.g., 'driver_skill_residual_s')
    tolerance:       allowable deviation in the same units as total_col (default 0.0001 s)

  Returns: rows where the identity does NOT hold (i.e., failing rows).

  Usage in a singular test file:
    {{ assert_additive_identity(
         ref('int_lap_residual_decomposed'),
         'pace_delta_s',
         ['fuel_component_s', 'compound_component_s', 'rubber_component_s',
          'ambient_component_s', 'constructor_component_s', 'dirty_air_tax_s'],
         'driver_skill_residual_s'
    ) }}

  The test fails (returns rows) if the identity does not hold to within tolerance.
  -#}

  SELECT *
  FROM {{ model_ref }}
  WHERE {{ total_col }} IS NOT NULL
    AND ABS(
        {{ total_col }}
       -({{ component_cols | join(' + ') }})
       -{{ residual_col }}
    ) > {{ tolerance }}
{% endmacro %}
