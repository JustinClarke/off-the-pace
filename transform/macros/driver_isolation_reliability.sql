{% macro driver_isolation_reliability(prefix, raw, se, tau2, method_score, method_grade) %}
  {#-
  The confidence columns every driver-isolation rating carries (WI-16a), at any grain.

  Given a raw rating, its standard error, the signal variance tau^2 of that rating at
  that grain and season, and the rating's method score and grade (from the
  driver_isolation_method_scores seed), emits four columns:

    <prefix>_lambda          reliability tau^2 / (tau^2 + SE^2), in [0, 1]
    <prefix>_shrunk_gain_s   lambda * raw: the normal-normal posterior mean with prior
                             mean 0 (every rating is field- or peer-centred). Equivalent to
                             bayesian_shrinkage() with prior_weight = sigma_w^2 / tau^2 in
                             effective laps when SE^2 = sigma_w^2 / n_eff.
    <prefix>_confidence_pct  ROUND(100 * lambda * method_score); NULL without a lambda or
                             before the method is validated. A declared policy, not an
                             estimated quantity.
    <prefix>_trust_label     'unvalidated' (method score NULL), 'suppress' (grade F, no
                             lambda, or confidence < 25), 'thin' (25-50), 'indicative'
                             (50-75), 'solid' (>= 75); NULL when there is no raw value.

  Floors come before this: a raw value is already NULL below its sample floor, so the
  shrinkage only handles the range between "just enough" and "plenty".

  Args:
    prefix:        column-name prefix, e.g. 'pure_skill_5lap'
    raw:           expression for the raw rating (s/lap, positive = faster)
    se:            expression for its standard error (s/lap)
    tau2:          expression for the signal variance (s^2)
    method_score:  expression for the rating's method score in [0, 1], or NULL
    method_grade:  expression for the rating's grade (A/B/C/F, or 'unvalidated')

  Usage:
    SELECT {{ driver_isolation_reliability('pure_skill', 'pure_raw', 'pure_se',
                                           'tau.pure_tau2', 'ms.method_score',
                                           'ms.grade') }}
  -#}
  {#- SE = 0 means the raw value is known exactly: lambda is 1, the SE -> 0 limit,
      rather than 0/0 when tau^2 is also 0. -#}
  {%- set lam -%}
    (CASE
        WHEN {{ raw }} IS NULL OR {{ se }} IS NULL OR {{ tau2 }} IS NULL THEN NULL
        WHEN {{ se }} = 0 THEN 1.0
        ELSE {{ tau2 }} / ({{ tau2 }} + ({{ se }}) * ({{ se }}))
    END)
  {%- endset %}
    {{ lam }} AS {{ prefix }}_lambda,
    {{ lam }} * ({{ raw }}) AS {{ prefix }}_shrunk_gain_s,
    ROUND(100.0 * {{ lam }} * ({{ method_score }})) AS {{ prefix }}_confidence_pct,
    CASE
        WHEN {{ raw }} IS NULL THEN NULL
        WHEN {{ method_score }} IS NULL THEN 'unvalidated'
        WHEN {{ method_grade }} = 'F' OR {{ lam }} IS NULL THEN 'suppress'
        -- On the rounded value, so a published "75%" is never labelled 'indicative'.
        WHEN ROUND(100.0 * {{ lam }} * ({{ method_score }})) >= 75 THEN 'solid'
        WHEN ROUND(100.0 * {{ lam }} * ({{ method_score }})) >= 50 THEN 'indicative'
        WHEN ROUND(100.0 * {{ lam }} * ({{ method_score }})) >= 25 THEN 'thin'
        ELSE 'suppress'
    END AS {{ prefix }}_trust_label
{%- endmacro %}
