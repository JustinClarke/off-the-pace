{#
  clamp_or_null -- bound an expression to [lo, hi], and keep a NULL a NULL.

  GREATEST(LEAST(x, hi), lo) is the obvious clamp and it is wrong on a NULL x in
  DuckDB: both functions SKIP NULL arguments, so LEAST(NULL, hi) is hi and the
  clamp turns "unknown" into the upper bound (F39's defect class). The CASE form
  propagates NULL by construction -- every comparison with NULL is unknown, so
  the ELSE branch returns x itself -- and equals the GREATEST/LEAST clamp on
  every non-NULL x (lo < hi).

  The lint in transform/tasks/coefficients/tests/test_sql_least_greatest_nullable.py
  flags a bare LEAST/GREATEST over a nullable expression; this macro is the fix
  it points to for a two-sided bound.
#}
{% macro clamp_or_null(expr, lo, hi) -%}
CASE
    WHEN ({{ expr }}) > {{ hi }} THEN {{ hi }}
    WHEN ({{ expr }}) < {{ lo }} THEN {{ lo }}
    ELSE ({{ expr }})
END
{%- endmacro %}
