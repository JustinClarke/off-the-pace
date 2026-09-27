{% macro driver_isolation_identity_terms() %}
  {#-
  The cumulative-identity split of tier 3, aggregated over any group of
  fct_driver_isolation_pair_lap rows (WI-16a). Use inside a GROUP BY over that model.

  Per pair row, relative = pace_gap + car_advantage + traffic_advantage, and
  pace_gap = pure_gap + tactical_gap where both drivers' tactical values exist (a "split"
  row). The aggregate keeps that identity exact by expressing every term as a
  CONTRIBUTION: its sum over the group's closed rows (both cars have a car term, so
  pace_gap is non-NULL) divided by identity_n_pair_laps. Then

    identity_relative_pace_gain_s = identity_pure_gap_gain_s
                                  + identity_tactical_gap_gain_s
                                  + identity_pace_gap_unsplit_gain_s
                                  + identity_car_advantage_gain_s
                                  + identity_traffic_advantage_gain_s

  holds to float precision (T42 checks it). A contribution over zero rows is 0, not a
  measurement: read identity_n_split_pair_laps before quoting the pure/tactical split. All
  columns are NULL when the group has no closed row. Seconds per lap, positive = in the
  focal driver's favour.

  Emits: n_pair_laps, identity_n_pair_laps, identity_n_split_pair_laps,
  identity_relative_pace_gain_s, identity_pure_gap_gain_s, identity_tactical_gap_gain_s,
  identity_pace_gap_unsplit_gain_s, identity_car_advantage_gain_s,
  identity_traffic_advantage_gain_s.

  Usage:
    SELECT stint_id, {{ driver_isolation_identity_terms() }}
    FROM {{ ref('fct_driver_isolation_pair_lap') }}
    GROUP BY stint_id
  -#}
  {%- set n = 'COUNT(pace_gap_gain_s)' %}
    COUNT(*) AS n_pair_laps,
    {{ n }} AS identity_n_pair_laps,
    COUNT(tactical_gap_gain_s) AS identity_n_split_pair_laps,
    CASE WHEN {{ n }} > 0 THEN
        SUM(CASE WHEN pace_gap_gain_s IS NOT NULL THEN relative_pace_gain_s END) / {{ n }}
    END AS identity_relative_pace_gain_s,
    CASE WHEN {{ n }} > 0 THEN
        COALESCE(SUM(CASE WHEN tactical_gap_gain_s IS NOT NULL THEN pure_gap_gain_s END), 0.0)
        / {{ n }}
    END AS identity_pure_gap_gain_s,
    CASE WHEN {{ n }} > 0 THEN
        COALESCE(SUM(tactical_gap_gain_s), 0.0) / {{ n }}
    END AS identity_tactical_gap_gain_s,
    CASE WHEN {{ n }} > 0 THEN
        COALESCE(SUM(CASE WHEN tactical_gap_gain_s IS NULL THEN pace_gap_gain_s END), 0.0)
        / {{ n }}
    END AS identity_pace_gap_unsplit_gain_s,
    CASE WHEN {{ n }} > 0 THEN
        SUM(CASE WHEN pace_gap_gain_s IS NOT NULL THEN car_advantage_gain_s END) / {{ n }}
    END AS identity_car_advantage_gain_s,
    CASE WHEN {{ n }} > 0 THEN
        SUM(CASE WHEN pace_gap_gain_s IS NOT NULL THEN traffic_advantage_gain_s END) / {{ n }}
    END AS identity_traffic_advantage_gain_s
{%- endmacro %}
