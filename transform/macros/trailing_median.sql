{% macro trailing_window_frame(partition_by, order_by, lookback=none, frame='rows') %}
  {#-
  Builds the OVER(...) frame shared by trailing_median and trailing_observation_count.

  The frame ALWAYS ends at `1 PRECEDING`. That is the whole point: it is what makes the
  window backward-only, so a row is never scored against a value it could not have seen.
  Do not add a variant that ends at CURRENT ROW -- a baseline that includes the lap it
  scores is a different statistic, and the two must not share a name.

  Args:
    partition_by:  list of column names, or a raw string, or none for an UNPARTITIONED
                   window (one global series -- e.g. the pooled shrinkage prior in
                   int_sc_hazard_history, which is a rate across all circuits and so has
                   no entity to partition by). `none` is not the same as omitting the
                   argument: it is a deliberate "the whole table is one series".
    order_by:      list of column names, or a raw string (the time axis)
    lookback:      integer N for `N PRECEDING`, or none for `UNBOUNDED PRECEDING`
    frame:         'rows' or 'range'. ROWS counts rows; RANGE counts values of the
                   ORDER BY column, which is what a FIELD statistic across several
                   entities at the same time index needs (see 02g), and what a
                   SEASON-lagged statistic needs when a season may hold many rows (02d).
  -#}
  {%- set ord = order_by | join(', ') if order_by is not string else order_by -%}
  {%- set frame_kw = frame | upper -%}
  {%- if frame_kw not in ('ROWS', 'RANGE') -%}
    {{ exceptions.raise_compiler_error("trailing_window_frame: frame must be 'rows' or 'range', got " ~ frame) }}
  {%- endif -%}
  {%- set start = 'UNBOUNDED PRECEDING' if lookback is none else (lookback | string) ~ ' PRECEDING' -%}
  {%- if partition_by is not none -%}
    {%- set part = partition_by | join(', ') if partition_by is not string else partition_by -%}
    PARTITION BY {{ part }}
  {%- endif %} ORDER BY {{ ord }} {{ frame_kw }} BETWEEN {{ start }} AND 1 PRECEDING
{% endmacro %}


{% macro trailing_value_expr(value_col, valid_condition=none) %}
  {#-
  The value a trailing window aggregates: `value_col`, masked to NULL where the row is not
  a valid observation. CASE, not FILTER -- DuckDB does not support FILTER in ordered-set
  aggregates inside window functions, which is why int_lap_thermal_proxy used to
  pre-aggregate with a GROUP BY and reach forward as a result.
  -#}
  {%- if valid_condition is none -%}
    {{ value_col }}
  {%- else -%}
    CASE WHEN {{ valid_condition }} THEN {{ value_col }} END
  {%- endif -%}
{% endmacro %}


{% macro trailing_median(value_col, partition_by, order_by, lookback=none, frame='rows', min_observations=1, valid_condition=none) %}
  {#-
  Median of `value_col` over observations STRICTLY BEFORE the current row.

  The canonical point-in-time baseline. Two models compute one (int_lap_thermal_proxy's
  stint baseline, 08e; int_corner_skill_residuals' corner field median, 02g). A third
  point-in-time rebuild, int_sc_hazard_history (02d), needs a trailing RATE rather than a
  median and so calls trailing_sum() below over the same frame. Both leaks that opened 08
  were a baseline
  built with a GROUP BY over a block that included the row it scored -- write the window
  once, here, so the next one is a call rather than a rediscovery.

  Returns NULL where fewer than `min_observations` valid observations precede the row,
  rather than a median over one or two laps that is mostly noise. Those NULLs are NOT
  declarable from the feature contract: they are deterministic on the count of valid
  prior observations, which is not a contract axis. Emit trailing_observation_count()
  alongside as a companion column so a consumer can condition on it.

  Args:
    value_col:        column or expression to take the median of
    partition_by:     list of columns, or a raw string -- the entity the baseline is for
    order_by:         list of columns, or a raw string -- the time axis
    lookback:         integer N for a trailing-N window, or none for expanding.
                      Expanding pools the whole history; trailing-N keeps the window
                      local to current conditions. The choice belongs to the caller and
                      is a decision its leaf doc must record.
    frame:            'rows' (default) or 'range' -- see trailing_window_frame
    min_observations: floor below which the result is NULL (default 1)
    valid_condition:  boolean expression; rows failing it contribute no observation

  Returns: scalar expression composable in a SELECT list.

  Usage:
    SELECT
      {{ trailing_median('lap_time_s', ['stint_id'], ['lap_in_stint'],
                         valid_condition='is_valid_lap') }} AS stint_baseline_pace,
      {{ trailing_observation_count('lap_time_s', ['stint_id'], ['lap_in_stint'],
                         valid_condition='is_valid_lap') }} AS baseline_observations_n
    FROM combined
  -#}
  {%- set vexpr = trailing_value_expr(value_col, valid_condition) -%}
  {%- set win = trailing_window_frame(partition_by, order_by, lookback, frame) -%}
  (CASE
      WHEN COUNT({{ vexpr }}) OVER ({{ win }}) >= {{ min_observations }}
      THEN MEDIAN({{ vexpr }}) OVER ({{ win }})
   END)
{% endmacro %}


{% macro trailing_sum(value_col, partition_by, order_by, lookback=none, frame='rows', min_observations=1, valid_condition=none) %}
  {#-
  Sum of `value_col` over observations STRICTLY BEFORE the current row. Same frame as
  trailing_median -- deliberately so: 08b's forward-window auditor has ONE shape to
  whitelist, not one per aggregate.

  This is the aggregate a point-in-time RATE needs. A rate is not a median of per-period
  rates: it is sum(numerator) / sum(denominator) over the window, so that a 78-lap race
  carries more weight than a 44-lap one. Build it from two trailing_sum calls sharing a
  frame, never from a trailing_median of a ratio column.

  Returns NULL where fewer than `min_observations` valid observations precede the row --
  which is what distinguishes "no prior history" (NULL, unknowable) from "prior history
  with no events" (0.0, a real measurement). Ship trailing_observation_count() alongside
  so the NULLs are explainable from the data rather than silent.

  Args: as trailing_median.

  Returns: scalar expression composable in a SELECT list.

  Usage (int_sc_hazard_history, 02d -- hazard as of the START of season S):
    SELECT
      {{ trailing_sum('n_any_onsets', ['circuit_slug'], ['season'], frame='range') }}
        / NULLIF({{ trailing_sum('racing_laps', ['circuit_slug'], ['season'], frame='range') }}, 0)
        AS any_hazard_per_lap
    FROM per_circuit_season
  -#}
  {%- set vexpr = trailing_value_expr(value_col, valid_condition) -%}
  {%- set win = trailing_window_frame(partition_by, order_by, lookback, frame) -%}
  (CASE
      WHEN COUNT({{ vexpr }}) OVER ({{ win }}) >= {{ min_observations }}
      THEN COALESCE(SUM({{ vexpr }}) OVER ({{ win }}), 0)
   END)
{% endmacro %}


{% macro trailing_observation_count(value_col, partition_by, order_by, lookback=none, frame='rows', valid_condition=none) %}
  {#-
  How many valid observations the matching trailing_median() actually saw. Ship it beside
  every trailing_median in a model that feeds the ML contract: it is what makes that
  median's NULLs and its early-window instability visible to a consumer instead of silent.

  Args: as trailing_median, minus min_observations (the count is what the floor is applied
  to, so it is reported unfloored).

  Returns: scalar expression composable in a SELECT list.
  -#}
  {%- set vexpr = trailing_value_expr(value_col, valid_condition) -%}
  {%- set win = trailing_window_frame(partition_by, order_by, lookback, frame) -%}
  COUNT({{ vexpr }}) OVER ({{ win }})
{% endmacro %}
