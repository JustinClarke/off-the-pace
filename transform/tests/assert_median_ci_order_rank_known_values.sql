-- TX-01. median_ci_order_rank (the order-statistic rank j behind the race
-- rating's distribution-free CI) on a literal CTE, against hand-checked
-- values of the largest k with P(Bin(n, 1/2) <= k - 1) <= 0.025:
--   n = 5 -> NULL (P(X <= 0) = 1/32 = 0.03125 > 0.025), n = 6 -> 1
--   (1/64 = 0.0156; P(X <= 1) = 7/64 = 0.109), n = 10 -> 2, n = 20 -> 6.
-- Fails per wrong or missing n.
WITH ns AS (
    SELECT t.n FROM (VALUES (1), (5), (6), (10), (20)) AS t (n)
),

expected AS (
    SELECT
        t.n,
        t.ci_rank_j
    FROM (
        VALUES (1, NULL), (5, NULL), (6, 1), (10, 2), (20, 6)
    ) AS t (n, ci_rank_j)
),

got AS (
    {{ median_ci_order_rank('ns', 'n') }}
)

SELECT e.n, e.ci_rank_j AS expected_j, g.ci_rank_j AS got_j
FROM expected AS e
LEFT JOIN got AS g ON e.n = g.n
WHERE g.n IS NULL OR g.ci_rank_j IS DISTINCT FROM e.ci_rank_j
