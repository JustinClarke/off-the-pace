{% macro power_law_beta_grid() %}
  {#-
  WI-17: the beta grid both power-law fits profile over, 0.20 to 3.00 in steps of 0.05.

  Built from integers (beta_k = 4..60, beta = beta_k / 20) so every value is exact and
  identical to ml/src/powerlaw_fit.py's BETA_GRID. beta_k = 20 is beta = 1, the straight line,
  which is why a profiled fit can never do worse than a line (T50). beta_k 4 and 60 are the
  grid edges.

  Used as: `grid AS ({{ power_law_beta_grid() }})` inside a WITH clause.
  -#}
  SELECT
      CAST(beta_k AS INTEGER) AS beta_k,
      CAST(beta_k AS DOUBLE) / 20.0 AS beta
  FROM generate_series(4, 60) AS t (beta_k)
{% endmacro %}
