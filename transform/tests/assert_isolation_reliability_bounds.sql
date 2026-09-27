-- T47 (WI-16a): shrinkage only ever shrinks.
--
-- For every rating at every grain (5-lap window, stint phase, driver-race):
--   0 <= lambda <= 1
--   |shrunk| <= |raw|
--   sign(shrunk) = sign(raw), or shrunk = 0 (lambda = 0 when tau^2 = 0)
-- and lambda exists wherever raw and its SE do. lambda = tau^2 / (tau^2 + SE^2) with tau^2
-- floored at 0, so a failure means a negative tau^2 or SE^2 got through, or the shrunk
-- column was computed from a different raw value than the one stored beside it.
-- (The column is aliased `reliability`, not `lambda`: LAMBDA is a DuckDB keyword.)

WITH ratings AS (
    {%- for grain, model, key, ratings in [
        ('window', 'fct_driver_isolation_lap', 'lap_id',
            [('pure_skill_5lap', 'pure_skill_5lap_gain_s', 'pure_skill_5lap_se_s'),
             ('tactical_5lap', 'tactical_5lap_gain_s', 'tactical_5lap_se_s'),
             ('relative_pace_5lap', 'relative_pace_5lap_gain_s', 'relative_pace_5lap_se_s')]),
        ('stint', 'fct_driver_isolation_stint', 'stint_phase_id',
            [('pure_skill', 'pure_skill_gain_s', 'pure_skill_se_s'),
             ('tactical', 'tactical_gain_s', 'tactical_se_s'),
             ('relative_pace', 'relative_pace_gain_s', 'relative_pace_se_s')]),
        ('race', 'fct_driver_isolation_race', 'driver_race_id',
            [('pure_skill', 'pure_skill_gain_s', 'pure_skill_se_s'),
             ('tactical', 'tactical_gain_s', 'tactical_se_s'),
             ('relative_pace', 'relative_pace_gain_s', 'relative_pace_se_s')]),
    ] %}
    {%- set outer = loop %}
    {%- for prefix, raw, se in ratings %}
    SELECT
        '{{ grain }}' AS grain,
        '{{ prefix }}' AS rating,
        {{ key }} AS row_id,
        {{ raw }} AS raw_gain_s,
        {{ se }} AS se_s,
        {{ prefix }}_lambda AS reliability,
        {{ prefix }}_shrunk_gain_s AS shrunk_gain_s
    FROM {{ ref(model) }}
    {%- if not (outer.last and loop.last) %}
    UNION ALL
    {%- endif %}
    {%- endfor %}
    {%- endfor %}
)

SELECT
    grain,
    rating,
    row_id,
    raw_gain_s,
    se_s,
    reliability,
    shrunk_gain_s
FROM ratings
WHERE
    reliability < 0
    OR reliability > 1
    OR ABS(shrunk_gain_s) > ABS(raw_gain_s) + 1e-12
    OR (shrunk_gain_s != 0 AND SIGN(shrunk_gain_s) != SIGN(raw_gain_s))
    OR (reliability IS NULL AND raw_gain_s IS NOT NULL AND se_s IS NOT NULL)
    OR (reliability IS NOT NULL AND shrunk_gain_s IS NULL)
