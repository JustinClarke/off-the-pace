{% macro median_ci_order_rank(n_relation, n_col='n', alpha_half=0.025) %}
  {#-
  TX-01. Order-statistic rank j for a distribution-free CI of a median.

  For n values sorted x_1 <= ... <= x_n, [x_j, x_{n-j+1}] covers the
  population median with probability >= 1 - 2 * alpha_half, where j is the
  largest k with P(Bin(n, 1/2) <= k - 1) <= alpha_half. No such k exists for
  small n (n < 6 at alpha_half = 0.025): j is NULL there and so is the CI.
  Known values at 0.025: n = 6 -> 1, n = 10 -> 2, n = 20 -> 6.

  Deterministic (no bootstrap). Binomial pmf from lgamma; the running CDF is
  compared with a 1e-12 tolerance (a Bin(n, 1/2) CDF is a dyadic rational, so
  it never equals 0.025 exactly and the tolerance only absorbs float error).

  Returns a SELECT with columns (n, ci_rank_j), one row per distinct n >= 1 in
  n_relation.n_col. Use it as a CTE body.
  -#}
    SELECT
        n,
        MAX(i + 1) FILTER (
            WHERE cdf <= {{ alpha_half }} + 1e-12
        ) AS ci_rank_j
    FROM (
        SELECT
            n,
            i,
            SUM(
                EXP(
                    LGAMMA(n + 1) - LGAMMA(i + 1) - LGAMMA(n - i + 1)
                    - n * LN(2)
                )
            ) OVER (PARTITION BY n ORDER BY i) AS cdf
        FROM (
            SELECT
                n,
                UNNEST(RANGE(0, n)) AS i
            FROM (
                SELECT DISTINCT CAST({{ n_col }} AS BIGINT) AS n
                FROM {{ n_relation }}
                WHERE {{ n_col }} >= 1
            )
        )
    )
    GROUP BY n
{% endmacro %}
