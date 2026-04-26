{# Standard normal CDF Phi(x).

   DuckDB has no erf/normal CDF builtin, so we use the Zelen & Severo rational
   approximation (Abramowitz & Stegun 26.2.17): max absolute error ~7.5e-8 over
   the whole real line far below any calibration tolerance we care about.

   Phi(x) = 1 - phi(x) * t * (b1 + t(b2 + t(b3 + t(b4 + t b5)))),  t = 1/(1+p|x|)
   with phi(x) = exp(-x^2/2)/sqrt(2*pi); reflected for x < 0 via Phi(x)=1-Phi(-x).

   Pass a simple column / scalar expression (it is inlined several times).
#}
{% macro normal_cdf(x) %}
(
    0.5 * (1.0 + SIGN({{ x }}))
    - SIGN({{ x }})
      * (EXP(-0.5 * ({{ x }}) * ({{ x }})) / 2.5066282746310002)
      * (1.0 / (1.0 + 0.2316419 * ABS({{ x }})))
      * ( 0.319381530
        + (1.0 / (1.0 + 0.2316419 * ABS({{ x }}))) * (-0.356563782
        + (1.0 / (1.0 + 0.2316419 * ABS({{ x }}))) * ( 1.781477937
        + (1.0 / (1.0 + 0.2316419 * ABS({{ x }}))) * (-1.821255978
        + (1.0 / (1.0 + 0.2316419 * ABS({{ x }}))) *   1.330274429))))
)
{% endmacro %}
